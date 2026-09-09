"""PowerPoint COM constants used by presenter automation.

Values match the official Office VBA enumerations so we do not depend on
pywin32 generated wrappers (which go stale across Office updates).
"""

from __future__ import annotations

from enum import IntEnum


MSO_TRUE = -1
MSO_FALSE = 0

PP_ALERTS_NONE = 2
PP_SAVE_AS_OPEN_XML_PRESENTATION = 24  # .pptx
PP_WINDOW_NORMAL = 1

PP_PLACEHOLDER_TITLE = 1
PP_PLACEHOLDER_BODY = 2

MSO_SHAPE_RECTANGLE = 1
MSO_ANIM_EFFECT_APPEAR = 1
MSO_ANIMATE_LEVEL_NONE = 0
MSO_ANIM_TRIGGER_ON_PAGE_CLICK = 1

MSO_CLICK_STATE_BEFORE_AUTOMATIC_ANIMATIONS = -1
MSO_CLICK_STATE_AFTER_ALL_ANIMATIONS = -2


class SlideLayout(IntEnum):
    TITLE = 1
    TEXT = 2
    TITLE_ONLY = 11
    BLANK = 12


class ShowType(IntEnum):
    SPEAKER = 1
    WINDOW = 2
    KIOSK = 3


class ShowRangeType(IntEnum):
    ALL = 1
    SLIDE_RANGE = 2
    NAMED_SHOW = 3


class AdvanceMode(IntEnum):
    MANUAL = 1
    USE_TIMINGS = 2
    REHEARSE = 3


class ShowState(IntEnum):
    RUNNING = 1
    PAUSED = 2
    BLACK_SCREEN = 3
    WHITE_SCREEN = 4
    DONE = 5


class PointerType(IntEnum):
    NONE = 0
    ARROW = 1
    PEN = 2
    ALWAYS_HIDDEN = 3
    AUTO_ARROW = 4
    # Documented as eraser in current VBA docs, but Microsoft 365 16.0
    # coerces 5 to AUTO_ARROW.
    ERASER = 5


def rgb(red: int, green: int, blue: int) -> int:
    """Pack an RGB triple into the integer format COM ColorFormat expects."""
    return int(red) + (int(green) << 8) + (int(blue) << 16)


def show_state_name(value: int | None) -> str:
    if value is None:
        return "unknown"
    try:
        return ShowState(value).name.lower()
    except ValueError:
        return f"state_{value}"


def pointer_type_name(value: int | None) -> str:
    if value is None:
        return "unknown"
    try:
        return PointerType(value).name.lower()
    except ValueError:
        return f"pointer_{value}"
