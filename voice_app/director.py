"""In-process presentation director used by Retell custom functions."""

from __future__ import annotations

import threading
import time
from dataclasses import asdict, dataclass
from typing import Any

from voice_app import config
from voice_app.bridge import run_actions
from voice_app.qa_rag import QARagService
from voice_app.runtime import PresenterRuntime
from voice_app.script_loader import load_script_beats

_SPEAK_ONE = (
    "Speak spoken_text verbatim in Cantonese. Stop at the last character. "
    "Do not continue into the next slide. After that one line, call deliver_next "
    "once. Never call it again in this turn."
)
_LAST_LINE = (
    "Speak spoken_text verbatim once. The prepared talk is then complete. "
    "Do not repeat it and do not call deliver_next on silence. Remain listening. "
    "If the audience asks a real question, call handle_audience_question."
)
_QA_INSTRUCTION = (
    "Speak spoken_text verbatim. Stop. Then call deliver_next. "
    "Do not recap or invite questions."
)


@dataclass
class DirectorState:
    call_id: str = ""
    beat_index: int = 0
    bookmark: int | None = None
    mode: str = "presenting"
    last_slide: int = 1
    last_seq: int | None = None
    slide_count: int = 0
    last_advance_at: float = 0.0
    line_lock_until: float = 0.0
    slide_pause_ms: int = 800
    talk_done: bool = False
    required_speech_cycle: int = 0
    speech_wait_started_at: float = 0.0


def _payload(raw: dict[str, Any]) -> dict[str, Any]:
    body = raw.get("body")
    return body if isinstance(body, dict) else raw


def _request_call_id(raw: dict[str, Any], payload: dict[str, Any]) -> str:
    args = payload.get("args") if isinstance(payload.get("args"), dict) else {}
    call = payload.get("call") if isinstance(payload.get("call"), dict) else {}
    return str(
        payload.get("call_id")
        or raw.get("call_id")
        or args.get("call_id")
        or call.get("call_id")
        or ""
    )


def _question(raw: dict[str, Any], payload: dict[str, Any]) -> str:
    args = payload.get("args") if isinstance(payload.get("args"), dict) else {}
    query = raw.get("query") if isinstance(raw.get("query"), dict) else {}
    value = (
        payload.get("question")
        or args.get("question")
        or query.get("question")
        or payload.get("text")
        or ""
    )
    if not value:
        call = payload.get("call") if isinstance(payload.get("call"), dict) else {}
        transcript = str(call.get("transcript") or "")
        for line in reversed(transcript.splitlines()):
            if line.lower().startswith(("user:", "caller:")):
                value = line.split(":", 1)[1].strip()
                break
    return str(value).strip()


def _int_or_none(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _nonnegative_int_or_none(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


class PresentationDirector:
    """Own the script cursor and Q&A bookmark for the active presentation."""

    def __init__(
        self,
        runtime: PresenterRuntime,
        qa_service: QARagService,
        beats: list[dict[str, Any]] | None = None,
    ) -> None:
        self.runtime = runtime
        self.qa_service = qa_service
        self.script_source = "provided beats"
        if beats is None:
            loaded, source = load_script_beats()
            self.beats = loaded
            self.script_source = source
        else:
            self.beats = [dict(beat) for beat in beats]
        self._lock = threading.RLock()
        self._state = DirectorState(slide_pause_ms=config.SLIDE_PAUSE_MS)

    def reload_beats(self) -> dict[str, Any]:
        """Re-read data/script.xlsx so Excel edits apply on the next Start."""
        loaded, source = load_script_beats()
        with self._lock:
            self.beats = loaded
            self.script_source = source
        return {"ok": True, "beats_total": len(loaded), "script_source": source}

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            state = asdict(self._state)
        state["beats_total"] = len(self.beats)
        state["script_source"] = self.script_source
        return state

    def reset(self, payload: dict[str, Any]) -> dict[str, Any]:
        status = payload.get("status") if isinstance(payload.get("status"), dict) else {}
        pause = _nonnegative_int_or_none(payload.get("slide_pause_ms"))
        with self._lock:
            self._state = DirectorState(
                call_id=str(payload.get("call_id") or ""),
                last_slide=_int_or_none(status.get("slide") or payload.get("current_slide")) or 1,
                slide_count=_int_or_none(
                    status.get("slide_count") or payload.get("slide_count")
                )
                or len(self.beats),
                slide_pause_ms=(
                    max(0, pause) if pause is not None else config.SLIDE_PAUSE_MS
                ),
            )
            state = asdict(self._state)
        return {
            "ok": True,
            "event": "session_reset",
            "call_id": state["call_id"],
            "beat_index": 0,
            "hint": "Python director reset. The presentation is ready.",
        }

    def _stale(self, request_call_id: str) -> bool:
        return bool(
            self._state.call_id
            and request_call_id
            and request_call_id != self._state.call_id
        )

    def _silent_done(self) -> dict[str, Any]:
        self._state.talk_done = True
        return {
            "ok": True,
            "done": True,
            "auto_continue": False,
            "repeat": False,
            "next_action": "listen_for_questions",
            "instruction": (
                "The prepared talk is finished. Do not repeat the last line and do "
                "not call deliver_next. Remain listening. If the audience asks a "
                "real question, call handle_audience_question."
            ),
            "spoken_text": "",
            "spoken_text_en": "",
            "slide": self._state.last_slide,
            "seq": self._state.last_seq,
            "beat_index": self._state.beat_index,
            "beats_total": len(self.beats),
            "error": "",
        }

    def _hold_ms(self, text: str) -> int:
        speech_ms = round((len(text) / 3.8) * 1000 + 400)
        return min(40000, max(2500, speech_ms)) + self._state.slide_pause_ms

    def _speech_wait_response(self) -> dict[str, Any]:
        return {
            "ok": True,
            "done": False,
            "auto_continue": False,
            "repeat": True,
            "next_action": "stay_silent",
            "instruction": (
                "Stay silent. Do not speak or repeat the previous line. "
                "Wait for that line to finish before calling deliver_next again."
            ),
            "spoken_text": "",
            "spoken_text_en": "",
            "slide": self._state.last_slide,
            "seq": self._state.last_seq,
            "beat_index": self._state.beat_index,
            "beats_total": len(self.beats),
            "error": "",
        }

    def _speech_cycle_pending(self, now: float, ready: dict[str, Any]) -> bool:
        required = self._state.required_speech_cycle
        completed = int(ready.get("completed_speech_cycle") or 0)
        if required > 0 and completed >= required:
            self._state.required_speech_cycle = 0
            self._state.speech_wait_started_at = 0.0
            self._state.line_lock_until = 0.0
            required = 0
        if ready.get("speaking"):
            return True
        if required <= 0:
            return False
        if ready.get("pending_speech"):
            return True
        if (
            self._state.speech_wait_started_at
            and now - self._state.speech_wait_started_at >= 90.0
        ):
            print(
                f"Director: speech cycle {required} was not observed; releasing stale lock.",
                flush=True,
            )
            self._state.required_speech_cycle = 0
            self._state.speech_wait_started_at = 0.0
            self._state.line_lock_until = 0.0
            return False
        return True

    def deliver_next(self, raw: dict[str, Any] | None = None) -> dict[str, Any]:
        raw = raw or {}
        payload = _payload(raw)
        args = payload.get("args") if isinstance(payload.get("args"), dict) else {}
        from_console = payload.get("source") == "console" or raw.get("source") == "console"
        dry = payload.get("dry") in {True, "true", "1"} or raw.get("dry") is True
        request_call_id = _request_call_id(raw, payload)

        with self._lock:
            if self._stale(request_call_id) and not from_console:
                return {
                    "ok": False,
                    "done": False,
                    "repeat": False,
                    "next_action": "stay_silent",
                    "instruction": (
                        "This request belongs to an inactive presentation. Stay silent."
                    ),
                    "spoken_text": "",
                    "spoken_text_en": "",
                    "error": "Stale call_id; the presentation cursor was not changed.",
                }

            incoming_pause_raw = payload.get("slide_pause_ms")
            if incoming_pause_raw is None:
                incoming_pause_raw = args.get("slide_pause_ms")
            incoming_pause = _nonnegative_int_or_none(incoming_pause_raw)
            if from_console and incoming_pause is not None:
                self._state.slide_pause_ms = max(0, incoming_pause)

            if self._state.mode == "qa" and self._state.bookmark is not None:
                self._state.beat_index = self._state.bookmark
                self._state.bookmark = None
                self._state.mode = "presenting"
                self._state.last_advance_at = 0.0
                self._state.line_lock_until = 0.0
                self._state.talk_done = False

            now = time.time()
            if self._state.talk_done:
                return self._silent_done()
            ready = self.runtime.speech_ready()
            if (
                not from_console
                and not dry
                and self._speech_cycle_pending(now, ready)
            ):
                return self._speech_wait_response()
            if (
                not from_console
                and not dry
                and self._state.line_lock_until
                and now < self._state.line_lock_until
            ):
                return {
                    "ok": True,
                    "done": False,
                    "auto_continue": False,
                    "repeat": True,
                    "next_action": "stay_silent",
                    "instruction": (
                        "Stay silent. Do not speak. Do not repeat the previous line. "
                        "After the room is quiet, call deliver_next once."
                    ),
                    "spoken_text": "",
                    "spoken_text_en": "",
                    "slide": self._state.last_slide,
                    "seq": self._state.last_seq,
                    "beat_index": self._state.beat_index,
                    "beats_total": len(self.beats),
                    "error": "",
                }
            if self._state.beat_index >= len(self.beats):
                return self._silent_done()

            beat = dict(self.beats[self._state.beat_index])
            self._state.beat_index += 1
            is_last = self._state.beat_index >= len(self.beats)
            spoken_text = str(beat.get("script_yue") or "")
            self._state.mode = "presenting"
            self._state.last_advance_at = now
            self._state.last_slide = int(beat.get("slide") or self._state.last_slide)
            self._state.last_seq = int(beat.get("seq") or self._state.beat_index)
            self._state.line_lock_until = now + self._hold_ms(spoken_text) / 1000
            if not from_console and not dry:
                self._state.required_speech_cycle = (
                    int(ready.get("speech_cycle") or 0) + 1
                )
                self._state.speech_wait_started_at = now
            if is_last:
                self._state.talk_done = True
            state = asdict(self._state)

        bridge: dict[str, Any] = {}
        error = ""
        actions = beat.get("actions")
        if actions and not dry:
            try:
                bridge = run_actions(
                    self.runtime,
                    actions,
                    spoken_text=spoken_text,
                )
                error = str(bridge.get("error") or bridge.get("message") or "")
            except Exception as exc:
                error = str(exc)

        bridge_status = bridge.get("status") if isinstance(bridge.get("status"), dict) else {}
        return {
            "ok": not error,
            "done": is_last,
            "auto_continue": False,
            "repeat": False,
            "next_action": (
                "listen_for_questions" if is_last else "speak_then_wait_for_silence"
            ),
            "instruction": _LAST_LINE if is_last else _SPEAK_ONE,
            "spoken_text": spoken_text,
            "spoken_text_en": str(beat.get("script_en") or ""),
            "slide": bridge_status.get("slide") or beat.get("slide"),
            "seq": beat.get("seq"),
            "beat_index": state["beat_index"],
            "beats_total": len(self.beats),
            "applied": bridge.get("applied") or [],
            "error": error,
            "bridge": bridge,
        }

    def handle_question(self, raw: dict[str, Any] | None = None) -> dict[str, Any]:
        raw = raw or {}
        payload = _payload(raw)
        request_call_id = _request_call_id(raw, payload)

        with self._lock:
            if self._stale(request_call_id):
                return {
                    "ok": False,
                    "mode": "qa",
                    "done": False,
                    "auto_continue": False,
                    "answerable": False,
                    "decline": True,
                    "spoken_text": "",
                    "spoken_text_en": "",
                    "next_action": "stay_silent",
                    "instruction": (
                        "This request belongs to an inactive presentation. Stay silent."
                    ),
                    "presentation_done": self._state.talk_done,
                    "error": "Stale call_id; the presentation cursor was not changed.",
                }
            if self._state.bookmark is None:
                self._state.bookmark = self._state.beat_index
            self._state.mode = "qa"
            self._state.last_advance_at = 0.0
            self._state.line_lock_until = 0.0
            bookmark = self._state.bookmark
            presentation_done = self._state.talk_done

        question = _question(raw, payload)
        snapshot = self.runtime.snapshot()
        status = snapshot.get("status") if isinstance(snapshot.get("status"), dict) else {}
        current_slide = _int_or_none(status.get("slide"))
        slide_count = _int_or_none(status.get("slide_count")) or len(self.beats)
        agent = self.qa_service.answer(question, current_slide=current_slide)

        default_text = (
            "呢條問題我喺現有資料搵唔到可靠答案。我而家接返簡報。"
            if question
            else "我未聽清楚問題。可以再問一次，或者我接返簡報。"
        )
        spoken = str(agent.get("spoken_text") or "").strip()
        usable = agent.get("ok") is True and bool(spoken)
        if not usable:
            spoken = default_text

        slide = _int_or_none(agent.get("slide"))
        recommended_slide = _int_or_none(
            agent.get("recommended_slide") or agent.get("slide")
        )
        if slide is not None and slide > slide_count:
            slide = None
        if recommended_slide is not None and recommended_slide > slide_count:
            recommended_slide = None
        should_flip = bool(
            usable
            and agent.get("should_change_slide") is True
            and slide
            and slide != current_slide
        )

        bridge: dict[str, Any] = {}
        bridge_error = ""
        if should_flip and slide is not None:
            try:
                bridge = run_actions(
                    self.runtime,
                    f"goto_slide:{slide}",
                    interrupt=True,
                )
                bridge_error = str(bridge.get("error") or bridge.get("message") or "")
            except Exception as exc:
                bridge_error = str(exc)
        bridge_status = bridge.get("status") if isinstance(bridge.get("status"), dict) else {}
        error = str(agent.get("error") or agent.get("message") or "") if not usable else ""
        with self._lock:
            ready = self.runtime.speech_ready()
            self._state.required_speech_cycle = int(ready.get("speech_cycle") or 0) + 1
            self._state.speech_wait_started_at = time.time()
        return {
            "ok": usable and not bridge_error,
            "mode": "qa",
            "done": False,
            "auto_continue": True,
            "answerable": usable and agent.get("answerable") is not False,
            "decline": not usable or agent.get("answerable") is False,
            "slide_changed": should_flip,
            "spoken_text": spoken,
            "spoken_grounding": spoken,
            "spoken_text_en": str(agent.get("spoken_text_en") or "") if usable else "",
            "next_action": "speak_then_call_deliver_next",
            "instruction": str(agent.get("instruction") or _QA_INSTRUCTION),
            "slide": bridge_status.get("slide") or (slide if should_flip else None),
            "recommended_slide": recommended_slide,
            "bookmark": bookmark,
            "presentation_done": presentation_done,
            "qa_mode": str(agent.get("mode") or "safe_abstention"),
            "answer_confidence": float(agent.get("answer_confidence") or 0),
            "slide_confidence": float(agent.get("slide_confidence") or 0),
            "source_ids": agent.get("source_ids") if isinstance(agent.get("source_ids"), list) else [],
            "sources": agent.get("sources") if isinstance(agent.get("sources"), list) else [],
            "applied": bridge.get("applied") or [],
            "error": error or bridge_error,
        }
