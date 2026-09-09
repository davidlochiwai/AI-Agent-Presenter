"""Serialize all PowerPoint COM work onto one STA thread."""

from __future__ import annotations

import concurrent.futures
import queue
import threading
import time
from pathlib import Path
from typing import Any

from ppt_presenter.controller import PresenterController
from ppt_presenter.errors import PresenterError
from ppt_presenter.models import ShowStatus

from voice_app import config
from voice_app.events import EventBus
from voice_app.window_layout import powerpoint_points, presenter_layout


def estimate_hold_s(text: str) -> float:
    """Approximate Cantonese TTS duration from script length."""
    n = len((text or "").strip())
    if n <= 0:
        return 8.0
    return min(40.0, max(3.0, n / 3.8 + 0.8))


def hold_s_for_slide(slide: int | None, spoken_text: str = "") -> float:
    if (spoken_text or "").strip():
        return estimate_hold_s(spoken_text)
    if slide:
        try:
            from voice_app.talk_content import SCRIPT

            for beat in SCRIPT:
                if int(beat.get("slide") or 0) == int(slide):
                    return estimate_hold_s(str(beat.get("script_yue") or ""))
        except Exception:
            pass
    return 8.0


def status_payload(status: ShowStatus) -> dict[str, Any]:
    return {
        "running": status.running,
        "slide": status.slide_index,
        "slide_count": status.slide_count,
        "title": status.title,
        "body": status.body,
        "notes": status.notes,
        "state": status.state_name,
        "presenter_view": status.presenter_view,
    }


class PresenterRuntime:
    def __init__(self, events: EventBus, *, enable_com: bool = True) -> None:
        self.events = events
        self.deck_path: str | None = None
        self.presenter_view = False
        self._show_bounds: tuple[float, float, float, float] | None = None
        self._ctrl: PresenterController | None = None
        self._jobs: queue.Queue[tuple[concurrent.futures.Future[Any], Any, tuple, dict]] = queue.Queue()
        self._tts_start_wait_s = 12.0
        self._pending_speech_timeout_s = 40.0
        self._agent_speaking = False
        self._speech_cycle = 0
        self._completed_speech_cycle = 0
        self._agent_idle = threading.Event()
        self._agent_idle.set()
        self._speech_change = threading.Event()
        self._pending_speech = False
        self._pending_since = 0.0
        self._last_stop_at = 0.0
        self._speak_started = 0.0
        self._nav_queue: queue.Queue[dict[str, Any]] = queue.Queue()
        self._nav_cancel = threading.Event()
        self._nav_epoch = 0
        if enable_com:
            self._thread = threading.Thread(target=self._loop, name="ppt-com", daemon=True)
            self._thread.start()
        else:
            self._thread = None
        self._nav_thread = threading.Thread(target=self._nav_loop, name="slide-nav", daemon=True)
        self._nav_thread.start()

    def _loop(self) -> None:
        self._ctrl = PresenterController(settle_s=0.2)
        while True:
            future, method, args, kwargs = self._jobs.get()
            try:
                future.set_result(method(*args, **kwargs))
            except Exception as exc:
                future.set_exception(exc)

    def _run(self, method: Any, *args: Any, **kwargs: Any) -> Any:
        future: concurrent.futures.Future[Any] = concurrent.futures.Future()
        self._jobs.put((future, method, args, kwargs))
        return future.result(timeout=60)

    def _ctrl_or_raise(self) -> PresenterController:
        if self._ctrl is None:
            raise PresenterError("PowerPoint worker is not ready.")
        return self._ctrl

    def load(self, path: str) -> dict[str, Any]:
        self.reset_talk_state()
        return self._run(self._load, path)

    def _load(self, path: str) -> dict[str, Any]:
        resolved = Path(path).expanduser().resolve()
        if not resolved.exists():
            raise PresenterError(f"File not found: {resolved}")
        if resolved.suffix.lower() not in {".ppt", ".pptx", ".ppsx", ".pptm"}:
            raise PresenterError("Choose a PowerPoint file (.pptx, .ppt, .ppsx, .pptm).")
        ctrl = self._ctrl_or_raise()
        ctrl.open(resolved)
        self.deck_path = str(resolved)
        slides = ctrl.list_slides()
        status = ctrl.status()
        payload = {
            "path": self.deck_path,
            "name": resolved.name,
            "slides": slides,
            "status": status_payload(status),
        }
        self.events.publish({"type": "deck_loaded", **payload})
        return payload

    def _notify_speech(self) -> None:
        self._speech_change.set()

    def set_agent_speaking(self, speaking: bool) -> None:
        speaking = bool(speaking)
        was_speaking = self._agent_speaking
        self._agent_speaking = speaking
        if speaking:
            if not was_speaking:
                self._speech_cycle += 1
            self._pending_speech = False
            if not was_speaking:
                self._speak_started = time.time()
            self._agent_idle.clear()
        else:
            if was_speaking:
                self._completed_speech_cycle = self._speech_cycle
                self._last_stop_at = time.time()
            self._agent_idle.set()
        self._notify_speech()

    def note_slide_advance(self) -> None:
        """A new beat was shown; wait until the agent actually starts then stops talking."""
        self._pending_speech = True
        self._pending_since = time.time()
        self._notify_speech()

    def clear_pending_speech(self) -> None:
        self._pending_speech = False
        self._pending_since = 0.0
        self._notify_speech()

    def reset_talk_state(self) -> None:
        """Drop queued flips and speech flags. Call when a new session starts."""
        self._nav_epoch += 1
        self._nav_cancel.set()
        self._notify_speech()
        self._agent_idle.set()
        self._drain_nav_queue()
        self._agent_speaking = False
        self._speech_cycle = 0
        self._completed_speech_cycle = 0
        self._pending_speech = False
        self._pending_since = 0.0
        self._speak_started = 0.0
        self._last_stop_at = 0.0
        self._nav_cancel.clear()
        self._notify_speech()

    def speech_ready(self) -> dict[str, Any]:
        now = time.time()
        speaking = self._agent_speaking
        pending = self._pending_speech
        if pending and self._pending_since and now - self._pending_since > self._pending_speech_timeout_s:
            self._pending_speech = False
            pending = False
            self._notify_speech()
        if speaking and self._speak_started and now - self._speak_started > 90:
            self._agent_speaking = False
            speaking = False
            self._completed_speech_cycle = self._speech_cycle
            self._last_stop_at = now
            self._agent_idle.set()
            self._notify_speech()
        idle = not speaking and not pending
        idle_ms = 0
        if idle and self._last_stop_at:
            idle_ms = int((now - self._last_stop_at) * 1000)
        return {
            "ok": True,
            "idle": idle,
            "speaking": speaking,
            "pending_speech": pending,
            "idle_ms": idle_ms,
            "speech_cycle": self._speech_cycle,
            "completed_speech_cycle": self._completed_speech_cycle,
        }

    def _wait_speech_loop(self, timeout_s: float, predicate) -> dict[str, Any]:
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            if self._nav_cancel.is_set():
                ready = self.speech_ready()
                ready["cancelled"] = True
                return ready
            ready = self.speech_ready()
            if predicate(ready):
                return ready
            remaining = deadline - time.time()
            if remaining <= 0:
                break
            self._speech_change.wait(timeout=min(0.25, remaining))
            self._speech_change.clear()
        ready = self.speech_ready()
        ready["timed_out"] = True
        return ready

    def wait_until_not_speaking(self, timeout_s: float = 90.0) -> dict[str, Any]:
        return self._wait_speech_loop(timeout_s, lambda ready: not ready["speaking"])

    def wait_until_line_finished(self, timeout_s: float = 90.0) -> dict[str, Any]:
        """Previous beat is done: not talking, and not waiting for TTS to start."""
        return self._wait_speech_loop(
            timeout_s,
            lambda ready: (not ready["speaking"] and not ready["pending_speech"]),
        )

    def wait_until_speaking(self, timeout_s: float = 8.0) -> dict[str, Any]:
        return self._wait_speech_loop(timeout_s, lambda ready: ready["speaking"])

    def wait_until_new_speech(self, previous_cycle: int, timeout_s: float = 12.0) -> dict[str, Any]:
        """Wait until a newer speech cycle has started, or already finished."""
        return self._wait_speech_loop(
            timeout_s,
            lambda ready: int(ready.get("speech_cycle") or 0) > int(previous_cycle)
            and (
                int(ready.get("completed_speech_cycle") or 0) > int(previous_cycle)
                or bool(ready["speaking"])
            ),
        )

    def wait_until_agent_idle(self, timeout_s: float = 20.0) -> bool:
        ready = self.wait_until_line_finished(timeout_s)
        return (not ready.get("speaking")) and (not ready.get("pending_speech"))

    def _drain_nav_queue(self) -> int:
        dropped = 0
        while True:
            try:
                self._nav_queue.get_nowait()
                dropped += 1
            except queue.Empty:
                break
        return dropped

    def drop_queued_nav(self) -> None:
        """Abort waiting flips (used for Q&A jump)."""
        self._nav_epoch += 1
        self._nav_cancel.set()
        self._notify_speech()
        self._drain_nav_queue()
        self._nav_cancel.clear()
        self._notify_speech()

    def enqueue_nav(
        self,
        steps: list[tuple[str, dict[str, Any]]],
        spoken_text: str = "",
    ) -> None:
        slide = None
        for _name, args in steps:
            if args.get("slide_number"):
                slide = int(args["slide_number"])
                break
        hold_s = hold_s_for_slide(slide, spoken_text)
        labels = ", ".join(
            f"{name}{':' + str(args.get('slide_number')) if args.get('slide_number') else ''}"
            for name, args in steps
        )
        print(
            f"Slide queue: queued {labels} hold={hold_s:.1f}s (depth {self._nav_queue.qsize() + 1})",
            flush=True,
        )
        self._nav_queue.put(
            {
                "steps": steps,
                "epoch": self._nav_epoch,
                "hold_s": hold_s,
                "slide": slide,
            }
        )

    def _apply_nav_item(self, item: dict[str, Any]) -> None:
        steps = item.get("steps") or []
        labels = ", ".join(
            f"{name}{':' + str(args.get('slide_number')) if args.get('slide_number') else ''}"
            for name, args in steps
        )
        print(f"Slide queue: applying {labels}", flush=True)
        for name, args in steps:
            self.perform(name, args)

    def _hold_through_speech(self, epoch: int, slide: int | None = None) -> None:
        """Keep this slide visible until its speech starts and finishes.

        If Retell starts TTS before this hold begins, the in-progress cycle
        belongs to this slide. Waiting for a later cycle would stall the talk.
        """
        already = self._agent_speaking
        cycle_before = self._speech_cycle - 1 if already else self._speech_cycle
        if already:
            self.clear_pending_speech()
        else:
            self.note_slide_advance()
        observed = self.wait_until_new_speech(cycle_before, self._tts_start_wait_s)
        if self._nav_epoch != epoch or observed.get("cancelled"):
            return
        cycle_seen = int(observed.get("speech_cycle") or 0)
        completed = int(observed.get("completed_speech_cycle") or 0)
        if cycle_seen <= cycle_before:
            dropped = self._drain_nav_queue()
            label = f"slide {slide}" if slide else "current slide"
            print(
                f"Slide queue: TTS did not start for {label}; "
                f"dropped {dropped} queued advance(s)",
                flush=True,
            )
            self.clear_pending_speech()
            return
        if completed > cycle_before:
            self.clear_pending_speech()
            return
        while True:
            if self._nav_epoch != epoch or self._nav_cancel.is_set():
                return
            ready = self.speech_ready()
            if not ready["speaking"]:
                return
            self._speech_change.wait(timeout=0.25)
            self._speech_change.clear()

    def _nav_loop(self) -> None:
        while True:
            item = self._nav_queue.get()
            steps = item.get("steps") or []
            epoch = item.get("epoch", self._nav_epoch)
            if not steps or epoch != self._nav_epoch or self._nav_cancel.is_set():
                continue
            waited = self.wait_until_line_finished(90.0)
            if self._nav_epoch != epoch or waited.get("cancelled"):
                print("Slide queue: cancelled before apply", flush=True)
                continue
            if waited.get("timed_out"):
                print(
                    "Slide queue: previous line wait timed out; flipping anyway",
                    flush=True,
                )
            try:
                self._apply_nav_item(item)
            except Exception as exc:
                print(f"Slide queue: apply failed: {exc}", flush=True)
                continue
            if self._nav_epoch != epoch:
                continue
            self._hold_through_speech(epoch, item.get("slide"))

    def _configured_show_bounds(self) -> tuple[float, float, float, float] | None:
        if self.presenter_view or not config.PRESENTER_SPLIT_LAYOUT:
            return None
        try:
            return powerpoint_points(
                presenter_layout(config.PRESENTER_SLIDE_RATIO).powerpoint,
            )
        except Exception as exc:
            print(f"Presenter layout unavailable: {exc}", flush=True)
            return None

    def start_show(self, presenter_view: bool = False) -> dict[str, Any]:
        return self._run(self._start_show, presenter_view)

    def _start_show(self, presenter_view: bool) -> dict[str, Any]:
        ctrl = self._ctrl_or_raise()
        if ctrl.pres is None:
            raise PresenterError("Load a presentation first.")
        self.presenter_view = presenter_view
        self._show_bounds = self._configured_show_bounds()
        if not ctrl.is_running():
            ctrl.start(
                presenter_view=presenter_view,
                windowed=not presenter_view,
                window_bounds=self._show_bounds,
            )
        elif self._show_bounds is not None:
            ctrl.set_window_bounds(self._show_bounds)
        return {"status": status_payload(ctrl.status())}

    def arrange_show(self) -> dict[str, Any]:
        return self._run(self._arrange_show)

    def _arrange_show(self) -> dict[str, Any]:
        ctrl = self._ctrl_or_raise()
        self._show_bounds = self._configured_show_bounds()
        if self._show_bounds is None:
            return {"ok": False, "error": "Split layout is disabled or Presenter View is active."}
        if not ctrl.is_running():
            return {"ok": False, "error": "The PowerPoint slide show is not running."}
        ctrl.set_window_bounds(self._show_bounds)
        return {"ok": True, "bounds": self._show_bounds}

    def end_show(self) -> dict[str, Any]:
        self.reset_talk_state()
        return self._run(self._end_show)

    def _end_show(self) -> dict[str, Any]:
        ctrl = self._ctrl_or_raise()
        if ctrl.is_running():
            ctrl.end()
        return {"status": status_payload(ctrl.status())}

    def snapshot(self) -> dict[str, Any]:
        return self._run(self._snapshot)

    def _snapshot(self) -> dict[str, Any]:
        ctrl = self._ctrl_or_raise()
        status = ctrl.status()
        slides = ctrl.list_slides() if ctrl.pres is not None else []
        return {
            "path": self.deck_path,
            "name": Path(self.deck_path).name if self.deck_path else "",
            "loaded": ctrl.pres is not None,
            "slides": slides,
            "status": status_payload(status),
        }

    def perform(self, name: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
        args = args or {}
        result = self._run(self._perform, name, args)
        self.events.publish({"type": "tool", "name": name, "args": args, "result": result})
        return result

    def _ensure_show(self) -> None:
        ctrl = self._ctrl_or_raise()
        if ctrl.pres is None:
            raise PresenterError("Load a presentation before using presenter tools.")
        if not ctrl.is_running():
            self._show_bounds = self._configured_show_bounds()
            ctrl.start(
                presenter_view=self.presenter_view,
                windowed=not self.presenter_view,
                window_bounds=self._show_bounds,
            )

    def _perform(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        ctrl = self._ctrl_or_raise()
        action = name.strip().lower()
        if action in {"get_status", "status"}:
            if ctrl.pres is None:
                raise PresenterError("No presentation is loaded.")
            return {"ok": True, "status": status_payload(ctrl.status())}
        if action == "list_slides":
            if ctrl.pres is None:
                raise PresenterError("No presentation is loaded.")
            return {"ok": True, "slides": ctrl.list_slides()}
        self._ensure_show()
        if action in {"goto_slide", "goto", "go_to_slide"}:
            slide = int(args.get("slide_number") or args.get("slide") or args.get("page") or 0)
            if slide < 1:
                raise PresenterError("slide_number must be a 1-based slide number.")
            count = int(ctrl.pres.Slides.Count)
            if slide > count:
                raise PresenterError(f"Slide {slide} is out of range (1-{count}).")
            ctrl.goto(slide)
        elif action in {"next", "next_click"}:
            ctrl.next()
        elif action in {"previous", "prev", "back"}:
            ctrl.previous()
        elif action == "next_slide":
            ctrl.next_slide()
        elif action in {"previous_slide", "prev_slide"}:
            ctrl.previous_slide()
        elif action == "first":
            ctrl.first()
        elif action == "last":
            ctrl.last()
        elif action in {"black", "black_screen"}:
            ctrl.black()
        elif action in {"white", "white_screen"}:
            ctrl.white()
        elif action in {"resume", "resume_screen"}:
            ctrl.resume()
        elif action == "get_notes":
            pass
        elif action == "end_slideshow":
            ctrl.end()
        else:
            raise PresenterError(f"Unknown presenter tool: {name}")
        status = status_payload(ctrl.status())
        message = (
            f"On slide {status['slide']} of {status['slide_count']}: {status['title'] or '(untitled)'}"
        )
        return {"ok": True, "message": message, "status": status}
