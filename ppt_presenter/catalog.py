"""Catalog of PowerPoint presenter actions.

The live tester covers every action marked ``com_testable``. Actions that
only exist in Presenter View chrome (thumbnails, on-screen timer gadgets)
are listed so the future agent knows they are not COM-controllable.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PresenterAction:
    name: str
    description: str
    shortcut: str
    com: str
    com_testable: bool
    notes: str = ""


ACTIONS: tuple[PresenterAction, ...] = (
    PresenterAction(
        "start",
        "Start the slide show from the beginning (F5) or a given slide (Shift+F5).",
        "F5 / Shift+F5 / Alt+F5 (Presenter View)",
        "SlideShowSettings.Run()",
        True,
    ),
    PresenterAction(
        "end",
        "End the slide show and return to the editor.",
        "Esc / - / Ctrl+Break",
        "SlideShowView.Exit()",
        True,
    ),
    PresenterAction(
        "next",
        "Advance to the next animation, or the next slide when none remain.",
        "N / Space / Enter / PageDown / Right",
        "SlideShowView.Next()",
        True,
    ),
    PresenterAction(
        "previous",
        "Go back one animation or slide.",
        "P / Backspace / PageUp / Left",
        "SlideShowView.Previous()",
        True,
    ),
    PresenterAction(
        "next_slide",
        "Jump to the next slide, skipping leftover animations on the current slide.",
        "No single default key; Presenter View 'Next slide'",
        "SlideShowView.GotoSlide(index + 1)",
        True,
    ),
    PresenterAction(
        "previous_slide",
        "Jump to the previous slide.",
        "Presenter View 'Previous slide'",
        "SlideShowView.GotoSlide(index - 1)",
        True,
    ),
    PresenterAction(
        "goto",
        "Jump to a specific slide number.",
        "<n> then Enter",
        "SlideShowView.GotoSlide(n)",
        True,
    ),
    PresenterAction(
        "first",
        "Jump to the first slide in the show.",
        "Home (in some modes)",
        "SlideShowView.First()",
        True,
    ),
    PresenterAction(
        "last",
        "Jump to the last slide in the show.",
        "End (in some modes)",
        "SlideShowView.Last()",
        True,
    ),
    PresenterAction(
        "black",
        "Blank the audience screen to black.",
        "B / .",
        "SlideShowView.State = ppSlideShowBlackScreen",
        True,
    ),
    PresenterAction(
        "white",
        "Blank the audience screen to white.",
        "W / ,",
        "SlideShowView.State = ppSlideShowWhiteScreen",
        True,
    ),
    PresenterAction(
        "pause",
        "Pause an automatic/timed show. Manual shows may ignore this.",
        "S (timed shows)",
        "SlideShowView.State = ppSlideShowPaused",
        True,
        "Often a no-op when the show is already on manual advance.",
    ),
    PresenterAction(
        "resume",
        "Return from black, white, or paused state to a running show.",
        "B / W / S again, or any advance key",
        "SlideShowView.State = ppSlideShowRunning",
        True,
    ),
    PresenterAction(
        "pointer_arrow",
        "Use the default arrow pointer.",
        "Ctrl+A / A",
        "SlideShowView.PointerType = ppSlideShowPointerArrow",
        True,
    ),
    PresenterAction(
        "pointer_pen",
        "Switch to the pen so the presenter can ink on the slide.",
        "Ctrl+P",
        "SlideShowView.PointerType = ppSlideShowPointerPen",
        True,
    ),
    PresenterAction(
        "pointer_eraser",
        "Switch to the ink eraser.",
        "Ctrl+E / E (erase all ink)",
        "SlideShowView.PointerType = ppSlideShowPointerEraser",
        True,
        "Microsoft 365 16.0 coerces COM value 5 to auto-arrow; use EraseDrawing() to clear ink.",
    ),
    PresenterAction(
        "pointer_hidden",
        "Hide the pointer.",
        "Ctrl+H",
        "SlideShowView.PointerType = ppSlideShowPointerAlwaysHidden",
        True,
    ),
    PresenterAction(
        "laser",
        "Toggle the laser pointer.",
        "Ctrl+L",
        "SlideShowView.LaserPointerEnabled",
        True,
        "May be unavailable in a windowed (non-speaker) slide show.",
    ),
    PresenterAction(
        "pen_color",
        "Set the ink/pen color.",
        "Presenter View pen color picker",
        "SlideShowView.PointerColor.RGB",
        True,
    ),
    PresenterAction(
        "draw_line",
        "Draw an ink stroke on the current slide.",
        "Click-drag with pen",
        "SlideShowView.DrawLine(x1, y1, x2, y2)",
        True,
        "Verified by COM success, not by pixel capture.",
    ),
    PresenterAction(
        "erase_ink",
        "Clear on-slide ink.",
        "E / Ctrl+M (hide ink)",
        "SlideShowView.EraseDrawing()",
        True,
    ),
    PresenterAction(
        "goto_click",
        "Jump to a specific animation click on the current slide.",
        "No default key",
        "SlideShowView.GotoClick(index)",
        True,
    ),
    PresenterAction(
        "reset_timer",
        "Reset the elapsed time for the current slide.",
        "Presenter View timer reset",
        "SlideShowView.ResetSlideTime()",
        True,
    ),
    PresenterAction(
        "read_notes",
        "Read speaker notes for the current slide.",
        "Presenter View notes pane (read-only via COM)",
        "Slide.NotesPage.Shapes.Placeholders(2)",
        True,
    ),
    PresenterAction(
        "status",
        "Snapshot of current slide, notes, pointer, and show state.",
        "n/a (agent observation)",
        "SlideShowView + Presentation",
        True,
    ),
    PresenterAction(
        "presenter_view",
        "Open the show in Presenter View (notes, next-slide preview, timer).",
        "Alt+F5",
        "SlideShowSettings.ShowPresenterView + ShowType=Speaker",
        True,
        "Needs a real desktop session. Dual monitors help; UI chrome is not scriptable.",
    ),
    PresenterAction(
        "see_all_slides",
        "Show the slide grid in Presenter View.",
        "Ctrl+S",
        "",
        False,
        "Presenter View UI only; no COM method.",
    ),
    PresenterAction(
        "zoom",
        "Magnify a region of the current slide.",
        "+ / =",
        "",
        False,
        "Presenter View / slide show UI only.",
    ),
    PresenterAction(
        "hide_slide",
        "Skip a hidden slide while presenting.",
        "H (next hidden slide)",
        "Slide.SlideShowTransition.Hidden (setup, not a live toggle)",
        False,
        "Hidden flag is a deck property, not a live presenter click.",
    ),
)


def testable_actions() -> tuple[PresenterAction, ...]:
    return tuple(action for action in ACTIONS if action.com_testable)


def format_catalog() -> str:
    lines = [
        f"{'action':<18} {'testable':<9} {'shortcut':<42} COM / notes",
        "-" * 110,
    ]
    for action in ACTIONS:
        flag = "yes" if action.com_testable else "no"
        extra = action.com or action.notes
        lines.append(f"{action.name:<18} {flag:<9} {action.shortcut:<42} {extra}")
    return "\n".join(lines)
