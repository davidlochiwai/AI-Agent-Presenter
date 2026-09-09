"""Read and write slide title/body/notes without depending on one placeholder type."""

from __future__ import annotations

from typing import Any

TITLE_PLACEHOLDER_TYPES = {1, 3, 6}  # title, center title, vertical title
BODY_PLACEHOLDER_TYPES = {2, 4, 7}  # body, subtitle, vertical body
PP_PLACEHOLDER_BODY = 2
MSO_TEXT_ORIENTATION_HORIZONTAL = 1


def _placeholder_type(shape: Any) -> int | None:
    try:
        return int(shape.PlaceholderFormat.Type)
    except Exception:
        return None


def _has_text(shape: Any) -> bool:
    try:
        return bool(shape.HasTextFrame)
    except Exception:
        return False


def _get_text(shape: Any) -> str:
    try:
        return str(shape.TextFrame.TextRange.Text).replace("\r", "\n").strip()
    except Exception:
        return ""


def _set_text(shape: Any, text: str) -> None:
    shape.TextFrame.TextRange.Text = text


def _iter_text_shapes(container: Any) -> list[Any]:
    found: list[Any] = []
    try:
        for shape in container.Shapes:
            if _has_text(shape):
                found.append(shape)
    except Exception:
        return found
    return found


def _shape_with_type(container: Any, types: set[int]) -> Any | None:
    for shape in _iter_text_shapes(container):
        if _placeholder_type(shape) in types:
            return shape
    return None


def set_title(slide: Any, text: str) -> None:
    shape = _shape_with_type(slide, TITLE_PLACEHOLDER_TYPES)
    if shape is None:
        shapes = _iter_text_shapes(slide)
        shape = shapes[0] if shapes else None
    if shape is None:
        shape = slide.Shapes.AddTextbox(MSO_TEXT_ORIENTATION_HORIZONTAL, 40, 20, 880, 80)
    _set_text(shape, text)


def set_body(slide: Any, text: str) -> None:
    shape = _shape_with_type(slide, BODY_PLACEHOLDER_TYPES)
    if shape is not None:
        _set_text(shape, text)
        return
    shape = slide.Shapes.AddTextbox(MSO_TEXT_ORIENTATION_HORIZONTAL, 40, 120, 880, 200)
    _set_text(shape, text)


def read_title(slide: Any) -> str:
    shape = _shape_with_type(slide, TITLE_PLACEHOLDER_TYPES)
    if shape is not None:
        return _get_text(shape)
    shapes = _iter_text_shapes(slide)
    return _get_text(shapes[0]) if shapes else ""


def read_body(slide: Any) -> str:
    shape = _shape_with_type(slide, BODY_PLACEHOLDER_TYPES)
    if shape is not None:
        return _get_text(shape)
    return ""


def set_notes(slide: Any, text: str) -> None:
    try:
        slide.NotesPage.Shapes.Placeholders(PP_PLACEHOLDER_BODY).TextFrame.TextRange.Text = text
        return
    except Exception:
        pass
    for shape in _iter_text_shapes(slide.NotesPage):
        ptype = _placeholder_type(shape)
        if ptype in BODY_PLACEHOLDER_TYPES or ptype is None:
            _set_text(shape, text)
            return
    raise RuntimeError("could not write speaker notes")


def read_notes(slide: Any) -> str:
    try:
        text = slide.NotesPage.Shapes.Placeholders(PP_PLACEHOLDER_BODY).TextFrame.TextRange.Text
        return str(text).replace("\r", "\n").strip()
    except Exception:
        pass
    chunks: list[str] = []
    for shape in _iter_text_shapes(slide.NotesPage):
        chunk = _get_text(shape)
        if chunk:
            chunks.append(chunk)
    return "\n".join(chunks)
