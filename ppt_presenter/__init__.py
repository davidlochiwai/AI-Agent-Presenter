"""PowerPoint presenter-action controller and live tester."""

from ppt_presenter.catalog import ACTIONS, PresenterAction
from ppt_presenter.controller import PresenterController
from ppt_presenter.errors import PowerPointNotFoundError, PresenterError, SlideshowNotRunningError
from ppt_presenter.models import ShowStatus

__all__ = [
    "ACTIONS",
    "PresenterAction",
    "PresenterController",
    "PresenterError",
    "PowerPointNotFoundError",
    "ShowStatus",
    "SlideshowNotRunningError",
]

__version__ = "0.1.0"
