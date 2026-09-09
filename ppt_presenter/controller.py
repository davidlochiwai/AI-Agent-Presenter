"""Live PowerPoint presenter controller (Windows COM).

This is the API the future presenter agent should call. The tester drives
the same methods and then reads ``status()`` to verify each action.
"""

from __future__ import annotations

import shutil
import sys
import time
from pathlib import Path
from typing import Any

from ppt_presenter.constants import (
    MSO_FALSE,
    MSO_TRUE,
    PP_ALERTS_NONE,
    PP_WINDOW_NORMAL,
    AdvanceMode,
    PointerType,
    ShowRangeType,
    ShowState,
    ShowType,
    pointer_type_name,
    rgb,
    show_state_name,
)
from ppt_presenter.errors import PowerPointNotFoundError, PresenterError, SlideshowNotRunningError
from ppt_presenter.models import ShowStatus
from ppt_presenter.slide_text import read_body, read_notes, read_title

try:
    import pythoncom
    import win32com.client
except ImportError as exc:  # pragma: no cover - environment specific
    pythoncom = None  # type: ignore[assignment]
    win32com = None  # type: ignore[assignment]
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None

_GEN_PY_CLEARED = False


def _clear_win32com_gen_py() -> None:
    """Drop a corrupt pywin32 gen_py cache (missing CLSIDToClassMap)."""
    global _GEN_PY_CLEARED
    for name in list(sys.modules):
        if "win32com.gen_py" in name:
            sys.modules.pop(name, None)
    try:
        import win32com.client.gencache as gencache

        shutil.rmtree(gencache.GetGeneratePath(), ignore_errors=True)
    except Exception:
        pass
    _GEN_PY_CLEARED = True


def _ppt_dispatch(source: Any) -> Any:
    # GetActiveObject returns IUnknown. DumbDispatch needs IDispatch, and
    # early-bound win32com.client.Dispatch hits a corrupt gen_py cache.
    if not isinstance(source, str):
        source = source.QueryInterface(pythoncom.IID_IDispatch)
    return win32com.client.dynamic.DumbDispatch(source)


def _com_error_message(exc: BaseException) -> str:
    args = getattr(exc, "args", ())
    if len(args) >= 3 and isinstance(args[2], tuple) and len(args[2]) >= 3:
        return str(args[2][2] or exc)
    return str(exc)


class PresenterController:
    def __init__(self, settle_s: float = 0.35) -> None:
        if _IMPORT_ERROR is not None:
            raise PowerPointNotFoundError(
                "pywin32 is required. Install it with: pip install pywin32"
            ) from _IMPORT_ERROR
        self.settle_s = settle_s
        self.app: Any = None
        self.pres: Any = None
        self.window: Any = None
        self.started_app = False
        self.created_pres = False
        self._com_ready = False

    def _ensure_com(self) -> None:
        if self._com_ready:
            return
        pythoncom.CoInitialize()
        self._com_ready = True

    def _settle(self, extra: float = 0.0) -> None:
        time.sleep(max(0.0, self.settle_s + extra))

    def connect(self, start_if_needed: bool = True) -> None:
        """Attach to a running PowerPoint, or launch one."""
        self._ensure_com()
        if not _GEN_PY_CLEARED:
            _clear_win32com_gen_py()
        try:
            self.app = _ppt_dispatch(pythoncom.GetActiveObject("PowerPoint.Application"))
            str(self.app.Version)
            self.started_app = False
        except Exception:
            if not start_if_needed:
                raise PowerPointNotFoundError("PowerPoint is installed but not running.") from None
            try:
                self.app = _ppt_dispatch("PowerPoint.Application")
            except AttributeError as exc:
                if "CLSIDToClassMap" not in str(exc):
                    raise PowerPointNotFoundError(
                        "Could not start PowerPoint. "
                        f"{_com_error_message(exc)} "
                        "Confirm desktop Microsoft PowerPoint is installed and licensed."
                    ) from exc
                _clear_win32com_gen_py()
                try:
                    self.app = _ppt_dispatch("PowerPoint.Application")
                except Exception as retry_exc:
                    raise PowerPointNotFoundError(
                        "Could not start PowerPoint. "
                        f"{_com_error_message(retry_exc)} "
                        "Confirm desktop Microsoft PowerPoint is installed and licensed."
                    ) from retry_exc
            except Exception as exc:
                raise PowerPointNotFoundError(
                    "Could not start PowerPoint. "
                    f"{_com_error_message(exc)} "
                    "Confirm desktop Microsoft PowerPoint is installed and licensed."
                ) from exc
            self.started_app = True
        try:
            self.app.Visible = True
            self.app.DisplayAlerts = PP_ALERTS_NONE
            self.app.WindowState = PP_WINDOW_NORMAL
        except Exception:
            pass

    def probe(self) -> dict[str, Any]:
        self.connect()
        version = str(self.app.Version)
        count = int(self.app.Presentations.Count)
        shows = int(self.app.SlideShowWindows.Count)
        return {
            "powerpoint_version": version,
            "presentations_open": count,
            "slideshow_windows": shows,
            "started_app": self.started_app,
        }

    def open(self, path: str | Path) -> None:
        self.connect()
        path = Path(path).resolve()
        if not path.exists():
            raise PresenterError(f"presentation not found: {path}")
        try:
            for index in range(1, int(self.app.Presentations.Count) + 1):
                existing = self.app.Presentations(index)
                try:
                    if Path(str(existing.FullName)).resolve() == path:
                        self.pres = existing
                        self.created_pres = False
                        return
                except Exception:
                    continue
        except Exception:
            pass
        # Open(FileName, ReadOnly, Untitled, WithWindow) — late-bound COM
        # does not accept keyword arguments reliably.
        try:
            self.pres = self.app.Presentations.Open(str(path), MSO_FALSE, MSO_FALSE, MSO_TRUE)
        except AttributeError as exc:
            if "CLSIDToClassMap" not in str(exc):
                raise
            _clear_win32com_gen_py()
            self.app = None
            self.connect()
            self.pres = self.app.Presentations.Open(str(path), MSO_FALSE, MSO_FALSE, MSO_TRUE)
        self.created_pres = False

    def list_slides(self) -> list[dict[str, Any]]:
        if self.pres is None:
            raise PresenterError("No presentation is loaded.")
        slides: list[dict[str, Any]] = []
        for index in range(1, int(self.pres.Slides.Count) + 1):
            slide = self.pres.Slides(index)
            notes = read_notes(slide)
            slides.append(
                {
                    "index": index,
                    "title": read_title(slide),
                    "notes_preview": notes[:240],
                }
            )
        return slides

    def use_presentation(self, pres: Any, created: bool = True) -> None:
        self.connect()
        self.pres = pres
        self.created_pres = created

    def _settings(self) -> Any:
        if self.pres is None:
            raise PresenterError("No presentation is loaded.")
        return self.pres.SlideShowSettings

    def start(
        self,
        *,
        from_slide: int = 1,
        presenter_view: bool = False,
        windowed: bool | None = None,
        window_bounds: tuple[float, float, float, float] | None = None,
    ) -> None:
        """Start a live slide show.

        Windowed mode is the default because it is safer for automated tests.
        Presenter View requires speaker (fullscreen) mode.
        """
        if self.pres is None:
            raise PresenterError("No presentation is loaded.")
        if self.is_running():
            self.end()
        if windowed is None:
            windowed = not presenter_view
        if presenter_view and windowed:
            raise PresenterError("Presenter View cannot run in windowed mode.")
        if window_bounds is not None and not windowed:
            raise PresenterError("Window bounds require windowed slide show mode.")

        settings = self._settings()
        settings.ShowType = int(ShowType.WINDOW if windowed else ShowType.SPEAKER)
        settings.ShowPresenterView = MSO_TRUE if presenter_view else MSO_FALSE
        settings.ShowWithAnimation = MSO_TRUE
        settings.AdvanceMode = int(AdvanceMode.MANUAL)
        settings.LoopUntilStopped = MSO_FALSE
        settings.RangeType = int(ShowRangeType.ALL)

        self.window = settings.Run()
        deadline = time.time() + 8.0
        while time.time() < deadline:
            if self.is_running():
                break
            time.sleep(0.1)
        else:
            raise PresenterError("Slide show did not start.")
        if window_bounds is not None:
            self.set_window_bounds(window_bounds)
        self._settle(0.25)
        if from_slide > 1:
            self.goto(from_slide)

    def set_window_bounds(
        self,
        bounds: tuple[float, float, float, float],
    ) -> None:
        """Apply left, top, width, and height in PowerPoint points."""
        if self.window is None or not self.is_running():
            raise SlideshowNotRunningError("No slide show window is available.")
        left, top, width, height = (float(value) for value in bounds)
        if width <= 0 or height <= 0:
            raise PresenterError("Slide show width and height must be positive.")
        self.window.Left = left
        self.window.Top = top
        self.window.Width = width
        self.window.Height = height

    def is_running(self) -> bool:
        if self.app is None:
            return False
        try:
            return int(self.app.SlideShowWindows.Count) > 0
        except Exception:
            return False

    def _view(self) -> Any:
        if not self.is_running():
            raise SlideshowNotRunningError("No slide show is running.")
        try:
            if self.pres is not None:
                return self.pres.SlideShowWindow.View
        except Exception:
            pass
        try:
            return self.app.SlideShowWindows(1).View
        except Exception as exc:
            raise SlideshowNotRunningError(_com_error_message(exc)) from exc

    def end(self) -> None:
        if not self.is_running():
            self.window = None
            return
        try:
            self._view().Exit()
        except Exception:
            try:
                self.app.SlideShowWindows(1).View.Exit()
            except Exception as exc:
                raise PresenterError(f"could not end slide show: {_com_error_message(exc)}") from exc
        deadline = time.time() + 5.0
        while time.time() < deadline and self.is_running():
            time.sleep(0.1)
        self.window = None
        self._settle()

    def next(self) -> None:
        self._view().Next()
        self._settle()

    def previous(self) -> None:
        self._view().Previous()
        self._settle()

    def goto(self, slide: int, reset: bool = True) -> None:
        self._view().GotoSlide(int(slide), MSO_TRUE if reset else MSO_FALSE)
        self._settle()

    def first(self) -> None:
        self._view().First()
        self._settle()

    def last(self) -> None:
        self._view().Last()
        self._settle()

    def next_slide(self) -> None:
        status = self.status()
        if status.slide_index is None:
            raise PresenterError("Cannot read the current slide index.")
        if status.slide_index >= status.slide_count:
            raise PresenterError("Already on the last slide.")
        self.goto(status.slide_index + 1)

    def previous_slide(self) -> None:
        status = self.status()
        if status.slide_index is None:
            raise PresenterError("Cannot read the current slide index.")
        if status.slide_index <= 1:
            raise PresenterError("Already on the first slide.")
        self.goto(status.slide_index - 1)

    def black(self) -> None:
        self._view().State = int(ShowState.BLACK_SCREEN)
        self._settle()

    def white(self) -> None:
        self._view().State = int(ShowState.WHITE_SCREEN)
        self._settle()

    def pause(self) -> None:
        self._view().State = int(ShowState.PAUSED)
        self._settle()

    def resume(self) -> None:
        self._view().State = int(ShowState.RUNNING)
        self._settle()

    def set_pointer(self, kind: PointerType) -> None:
        view = self._view()
        try:
            if bool(view.LaserPointerEnabled):
                view.LaserPointerEnabled = False
        except Exception:
            pass
        view.PointerType = int(kind)
        self._settle()

    def set_laser(self, enabled: bool) -> None:
        view = self._view()
        try:
            view.LaserPointerEnabled = bool(enabled)
        except Exception as exc:
            raise PresenterError(
                f"laser pointer is not available: {_com_error_message(exc)}"
            ) from exc
        self._settle()

    def set_pen_color(self, red: int, green: int, blue: int) -> None:
        self._view().PointerColor.RGB = rgb(red, green, blue)
        self._settle()

    def draw_line(self, x1: float, y1: float, x2: float, y2: float) -> None:
        self._view().DrawLine(float(x1), float(y1), float(x2), float(y2))
        self._settle()

    def erase_ink(self) -> None:
        self._view().EraseDrawing()
        self._settle()

    def goto_click(self, index: int) -> None:
        self._view().GotoClick(int(index))
        self._settle(0.15)

    def reset_timer(self) -> None:
        self._view().ResetSlideTime()
        self._settle()

    def close_deck(self, *, quit_app: bool | None = None) -> None:
        if self.is_running():
            self.end()
        if self.pres is not None:
            try:
                self.pres.Saved = True
                self.pres.Close()
            except Exception:
                pass
            self.pres = None
        should_quit = self.started_app if quit_app is None else quit_app
        if should_quit and self.app is not None:
            try:
                if int(self.app.Presentations.Count) == 0:
                    self.app.Quit()
            except Exception:
                pass
            self.app = None
        self.window = None

    def status(self) -> ShowStatus:
        if self.pres is None and self.app is not None:
            try:
                if int(self.app.Presentations.Count) > 0:
                    self.pres = self.app.ActivePresentation
            except Exception:
                pass
        slide_count = int(self.pres.Slides.Count) if self.pres is not None else 0
        presenter_view = None
        show_type = None
        if self.pres is not None:
            try:
                presenter_view = bool(self.pres.SlideShowSettings.ShowPresenterView)
                show_type = int(self.pres.SlideShowSettings.ShowType)
            except Exception:
                pass
        window_count = 0
        if self.app is not None:
            try:
                window_count = int(self.app.SlideShowWindows.Count)
            except Exception:
                pass
        if not self.is_running():
            return ShowStatus(
                running=False,
                slide_index=None,
                slide_count=slide_count,
                title="",
                notes="",
                presenter_view=presenter_view,
                window_count=window_count,
                show_type=show_type,
            )
        view = self._view()
        slide_index = None
        title = ""
        notes = ""
        body = ""
        state = None
        pointer = None
        laser = None
        click_index = None
        click_count = None
        elapsed = None
        try:
            state = int(view.State)
        except Exception:
            pass
        try:
            slide_index = int(view.CurrentShowPosition)
        except Exception:
            pass
        try:
            slide = view.Slide
            slide_index = int(slide.SlideIndex)
            title = read_title(slide)
            body = read_body(slide)
            notes = read_notes(slide)
        except Exception:
            pass
        try:
            pointer = int(view.PointerType)
        except Exception:
            pass
        try:
            laser = bool(view.LaserPointerEnabled)
        except Exception:
            pass
        try:
            click_index = int(view.GetClickIndex())
        except Exception:
            pass
        try:
            click_count = int(view.GetClickCount())
        except Exception:
            pass
        try:
            elapsed = float(view.SlideElapsedTime)
        except Exception:
            pass
        return ShowStatus(
            running=True,
            slide_index=slide_index,
            slide_count=slide_count,
            title=title,
            notes=notes,
            body=body,
            state=state,
            state_name=show_state_name(state),
            pointer_type=pointer,
            pointer_name=pointer_type_name(pointer),
            laser=laser,
            click_index=click_index,
            click_count=click_count,
            elapsed_seconds=elapsed,
            presenter_view=presenter_view,
            window_count=window_count,
            show_type=show_type,
        )

    def __enter__(self) -> PresenterController:
        return self

    def __exit__(self, *exc: object) -> None:
        try:
            self.close_deck()
        except Exception:
            pass
