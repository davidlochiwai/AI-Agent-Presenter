"""Thin PowerPoint adapter for the local director. No script cursor, no LLM."""

from __future__ import annotations

import re
from typing import Any

from ppt_presenter.errors import PresenterError

from voice_app.runtime import PresenterRuntime, status_payload

ACTIONS: tuple[str, ...] = (
    "status",
    "slides",
    "start",
    "end",
    "goto_slide",
    "next",
    "previous",
    "next_slide",
    "previous_slide",
    "first",
    "last",
    "black_screen",
    "white_screen",
    "resume_screen",
)

_GOTO = re.compile(r"^(goto_slide|goto|go_to_slide)\s*[:=]?\s*(\d+)$", re.I)
_NAV = {
    "goto_slide",
    "next",
    "previous",
    "next_slide",
    "previous_slide",
    "first",
    "last",
}


def parse_action_list(raw: str | list[Any] | None) -> list[tuple[str, dict[str, Any]]]:
    if raw is None:
        return []
    if isinstance(raw, list):
        parts = [str(item).strip() for item in raw if str(item).strip()]
    else:
        parts = [part.strip() for part in re.split(r"[;,\n]+", str(raw)) if part.strip()]
    parsed: list[tuple[str, dict[str, Any]]] = []
    for part in parts:
        match = _GOTO.match(part.replace(" ", ""))
        if match:
            parsed.append(("goto_slide", {"slide_number": int(match.group(2))}))
            continue
        name = part.strip().lower().replace(" ", "_")
        parsed.append((name, {}))
    return parsed


def catalog() -> dict[str, Any]:
    return {
        "ok": True,
        "service": "slide-bridge",
        "actions": list(ACTIONS),
        "run": 'POST {"actions": "goto_slide:3; next"}',
    }


def run_actions(
    runtime: PresenterRuntime,
    actions: str | list[Any] | None,
    interrupt: bool = False,
    spoken_text: str = "",
) -> dict[str, Any]:
    steps = parse_action_list(actions)
    if not steps:
        raise PresenterError("Provide actions, for example goto_slide:3 or next.")
    nav = any(name in _NAV for name, _ in steps)
    if interrupt and nav:
        runtime.drop_queued_nav()
        last: dict[str, Any] = {"ok": True}
        applied: list[str] = []
        for name, args in steps:
            last = dispatch(runtime, name, args)
            if not last.get("ok"):
                return {**last, "applied": applied}
            applied.append(name)
        runtime.note_slide_advance()
        last["applied"] = applied
        return last
    if nav:
        runtime.enqueue_nav(steps, spoken_text=spoken_text)
        snap = runtime.snapshot()
        return {
            "ok": True,
            "queued": True,
            "applied": [name for name, _ in steps],
            "status": snap.get("status"),
        }
    last = {"ok": True}
    applied = []
    for name, args in steps:
        last = dispatch(runtime, name, args)
        if not last.get("ok"):
            return {**last, "applied": applied}
        applied.append(name)
    last["applied"] = applied
    return last


def dispatch(runtime: PresenterRuntime, name: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
    args = args or {}
    action = name.strip().lower().replace("-", "_")
    if action in {"status", "get_status"}:
        snap = runtime.snapshot()
        return {"ok": True, "status": snap.get("status"), "loaded": snap.get("loaded"), "name": snap.get("name")}
    if action in {"slides", "list_slides"}:
        snap = runtime.snapshot()
        return {"ok": True, "slides": snap.get("slides") or []}
    if action in {"start", "start_show"}:
        presenter_view = bool(args.get("presenter_view") or False)
        return {"ok": True, **runtime.start_show(presenter_view=presenter_view)}
    if action in {"end", "end_show", "end_slideshow"}:
        return {"ok": True, **runtime.end_show()}
    result = runtime.perform(action, args)
    return result


def snapshot_for_bridge(runtime: PresenterRuntime) -> dict[str, Any]:
    snap = runtime.snapshot()
    status = snap.get("status") or {}
    ready = runtime.speech_ready()
    return {
        "loaded": bool(snap.get("loaded")),
        "deck_name": snap.get("name") or "",
        "deck_path": snap.get("path") or "",
        "slides": snap.get("slides") or [],
        "status": status if isinstance(status, dict) else status_payload(status),
        "idle": ready["idle"],
        "speaking": ready["speaking"],
        "pending_speech": ready["pending_speech"],
        "idle_ms": ready["idle_ms"],
    }
