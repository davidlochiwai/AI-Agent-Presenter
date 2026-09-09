from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class ShowStatus:
    """Point-in-time snapshot of the live slide show.

    This is the read model the future presenter agent should use before
    deciding which action to take.
    """

    running: bool
    slide_index: int | None
    slide_count: int
    title: str
    notes: str
    body: str = ""
    state: int | None = None
    state_name: str = "unknown"
    pointer_type: int | None = None
    pointer_name: str = "unknown"
    laser: bool | None = None
    click_index: int | None = None
    click_count: int | None = None
    elapsed_seconds: float | None = None
    presenter_view: bool | None = None
    window_count: int = 0
    show_type: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ActionResult:
    name: str
    status: str  # pass | fail | skip
    detail: str = ""
    elapsed_ms: int = 0
    before: dict[str, Any] = field(default_factory=dict)
    after: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
