from __future__ import annotations


class PresenterError(RuntimeError):
    """Raised when a presenter action cannot be carried out."""


class PowerPointNotFoundError(PresenterError):
    """PowerPoint is not installed or the COM server cannot be created."""


class SlideshowNotRunningError(PresenterError):
    """An action was requested while no slide show is running."""


class SkipTest(Exception):
    """A live test cannot run in this environment; not a product failure."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason
