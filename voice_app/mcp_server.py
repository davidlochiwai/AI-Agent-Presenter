from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from voice_app.runtime import PresenterRuntime
from voice_app.tools import dispatch_tool

mcp = FastMCP(
    "PowerPoint Presenter",
    instructions=(
        "Tools that drive a live Microsoft PowerPoint slideshow on the presenter's Windows PC. "
        "Prefer goto_slide when they ask for a page number. Use list_slides to resolve a topic name."
    ),
)

_runtime: PresenterRuntime | None = None


def bind_runtime(runtime: PresenterRuntime) -> None:
    global _runtime
    _runtime = runtime


def _rt() -> PresenterRuntime:
    if _runtime is None:
        raise RuntimeError("Presenter runtime is not ready.")
    return _runtime


def _call(name: str, **args: Any) -> dict[str, Any]:
    return dispatch_tool(_rt(), name, args)


@mcp.tool
def get_status() -> dict[str, Any]:
    """Read the live slideshow: current slide number, title, speaker notes, and running state."""
    return _call("get_status")


@mcp.tool
def list_slides() -> dict[str, Any]:
    """List every slide number and title. Use this when the presenter names a topic instead of a number."""
    return _call("list_slides")


@mcp.tool
def get_notes() -> dict[str, Any]:
    """Read speaker notes for the current slide."""
    return _call("get_notes")


@mcp.tool
def goto_slide(slide_number: int) -> dict[str, Any]:
    """Jump to a 1-based slide number. Use when they say go to slide/page N."""
    return _call("goto_slide", slide_number=slide_number)


@mcp.tool(name="next")
def advance_next() -> dict[str, Any]:
    """Advance one click (next animation, or next slide if none remain)."""
    return _call("next")


@mcp.tool
def previous() -> dict[str, Any]:
    """Go back one click or slide."""
    return _call("previous")


@mcp.tool
def next_slide() -> dict[str, Any]:
    """Skip leftover animations and jump to the next slide."""
    return _call("next_slide")


@mcp.tool
def previous_slide() -> dict[str, Any]:
    """Jump to the previous slide."""
    return _call("previous_slide")


@mcp.tool
def first() -> dict[str, Any]:
    """Jump to the first slide."""
    return _call("first")


@mcp.tool
def last() -> dict[str, Any]:
    """Jump to the last slide."""
    return _call("last")


@mcp.tool
def black_screen() -> dict[str, Any]:
    """Blank the audience screen to black."""
    return _call("black_screen")


@mcp.tool
def white_screen() -> dict[str, Any]:
    """Blank the audience screen to white."""
    return _call("white_screen")


@mcp.tool
def resume_screen() -> dict[str, Any]:
    """Return from a black or white blank to the current slide."""
    return _call("resume_screen")
