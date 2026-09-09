from __future__ import annotations

from typing import Any

from voice_app.runtime import PresenterRuntime

TOOL_SPECS: tuple[dict[str, Any], ...] = (
    {
        "name": "get_status",
        "description": (
            "Read the live slideshow: current slide number, title, speaker notes, "
            "and whether the show is running. Call this before answering questions "
            "about where you are in the deck."
        ),
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "list_slides",
        "description": (
            "List every slide number and title (plus a short notes preview). "
            "Use this when the presenter asks for a topic or section by name "
            "instead of a number."
        ),
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_notes",
        "description": "Read speaker notes for the current slide so you can help the presenter.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "goto_slide",
        "description": (
            "Jump the live slideshow to a specific 1-based slide number. "
            "Use when the presenter says go to slide N, page N, or a named slide. "
            "If they named a topic, call list_slides first to find the number."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "slide_number": {
                    "type": "integer",
                    "description": "1-based slide number to show",
                }
            },
            "required": ["slide_number"],
        },
    },
    {
        "name": "next",
        "description": "Advance one click: the next animation, or the next slide if none remain.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "previous",
        "description": "Go back one click or slide.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "next_slide",
        "description": "Skip leftover animations and jump to the next slide.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "previous_slide",
        "description": "Jump to the previous slide.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "first",
        "description": "Jump to the first slide.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "last",
        "description": "Jump to the last slide.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "black_screen",
        "description": "Blank the audience screen to black.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "white_screen",
        "description": "Blank the audience screen to white.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "resume_screen",
        "description": "Return from a black or white blank to the current slide.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
)


def dispatch_tool(runtime: PresenterRuntime, name: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
    return runtime.perform(name, args or {})
