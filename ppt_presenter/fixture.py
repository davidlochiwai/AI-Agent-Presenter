"""Build an in-memory PowerPoint deck that exercises presenter actions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ppt_presenter.constants import (
    MSO_ANIM_EFFECT_APPEAR,
    MSO_ANIM_TRIGGER_ON_PAGE_CLICK,
    MSO_ANIMATE_LEVEL_NONE,
    MSO_SHAPE_RECTANGLE,
    PP_SAVE_AS_OPEN_XML_PRESENTATION,
    SlideLayout,
    rgb,
)
from ppt_presenter.slide_text import set_body, set_notes, set_title

FIXTURE_SLIDE_COUNT = 5
SECRET_NOTE_TOKEN = "SECRET_NOTE_TOKEN: alpha-42"
ANIMATION_SLIDE_INDEX = 2
ANIMATION_CLICK_COUNT = 3


def _add_slide(pres: Any, layout: SlideLayout) -> Any:
    try:
        return pres.Slides.Add(pres.Slides.Count + 1, int(layout))
    except Exception:
        layouts = pres.SlideMaster.CustomLayouts
        index = 1 if layout == SlideLayout.TITLE else min(2, int(layouts.Count))
        return pres.Slides.AddSlide(pres.Slides.Count + 1, layouts(index))


def create_fixture_presentation(app: Any, save_path: Path | None = None) -> Any:
    """Create a 5-slide deck with notes and on-click animations."""
    pres = app.Presentations.Add()
    try:
        pres.PageSetup.SlideWidth = 960
        pres.PageSetup.SlideHeight = 540
    except Exception:
        pass

    title = _add_slide(pres, SlideLayout.TITLE)
    set_title(title, "Presenter Action Tester")
    set_body(title, "COM fixture for AI Agent Presenter")
    set_notes(title, "Welcome notes for slide 1. Start here.")

    animation = _add_slide(pres, SlideLayout.TITLE_ONLY)
    set_title(animation, "Animation Clicks")
    labels = ("One", "Two", "Three")
    colors = ((220, 70, 70), (70, 170, 80), (70, 110, 210))
    for index, (label, color) in enumerate(zip(labels, colors, strict=True)):
        shape = animation.Shapes.AddShape(
            MSO_SHAPE_RECTANGLE,
            80 + index * 220,
            200,
            180,
            100,
        )
        shape.Fill.ForeColor.RGB = rgb(*color)
        shape.Line.Visible = 0
        shape.TextFrame.TextRange.Text = label
        animation.TimeLine.MainSequence.AddEffect(
            shape,
            MSO_ANIM_EFFECT_APPEAR,
            MSO_ANIMATE_LEVEL_NONE,
            MSO_ANIM_TRIGGER_ON_PAGE_CLICK,
        )
    set_notes(animation, "Advance three times to reveal the colored boxes.")

    notes_slide = _add_slide(pres, SlideLayout.TEXT)
    set_title(notes_slide, "Speaker Notes")
    set_body(
        notes_slide,
        "This slide exists so the tester can read presenter notes over COM.",
    )
    set_notes(notes_slide, f"{SECRET_NOTE_TOKEN}. Mention the roadmap.")

    jump = _add_slide(pres, SlideLayout.TEXT)
    set_title(jump, "Jump Target")
    set_body(jump, "Goto-slide landing pad.")
    set_notes(jump, "You jumped here.")

    last = _add_slide(pres, SlideLayout.TEXT)
    set_title(last, "Last Slide")
    set_body(last, "End of the fixture deck.")
    set_notes(last, "Ready to close the show.")

    if save_path is not None:
        save_path = Path(save_path).expanduser().resolve()
        save_path.parent.mkdir(parents=True, exist_ok=True)
        pres.SaveAs(str(save_path), PP_SAVE_AS_OPEN_XML_PRESENTATION)

    return pres
