"""Windows helpers for the split-screen presenter layout."""

from __future__ import annotations

import ctypes
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class WindowBounds:
    left: int
    top: int
    width: int
    height: int

    def to_dict(self) -> dict[str, int]:
        return {
            "left": self.left,
            "top": self.top,
            "width": self.width,
            "height": self.height,
        }


@dataclass(frozen=True)
class PresenterLayout:
    powerpoint: WindowBounds
    app: WindowBounds

    def to_dict(self) -> dict[str, dict[str, int]]:
        return {
            "powerpoint": self.powerpoint.to_dict(),
            "app": self.app.to_dict(),
        }


def calculate_split(
    work_area: WindowBounds,
    slide_ratio: float = 0.67,
) -> PresenterLayout:
    """Split a monitor work area without gaps or taskbar overlap."""
    ratio = max(0.5, min(0.8, float(slide_ratio)))
    slide_width = max(1, round(work_area.width * ratio))
    app_width = max(1, work_area.width - slide_width)
    return PresenterLayout(
        powerpoint=WindowBounds(
            left=work_area.left,
            top=work_area.top,
            width=slide_width,
            height=work_area.height,
        ),
        app=WindowBounds(
            left=work_area.left + slide_width,
            top=work_area.top,
            width=app_width,
            height=work_area.height,
        ),
    )


def primary_work_area() -> WindowBounds:
    if os.name != "nt":
        raise RuntimeError("Automatic presenter layout is available only on Windows.")

    class Rect(ctypes.Structure):
        _fields_ = [
            ("left", ctypes.c_long),
            ("top", ctypes.c_long),
            ("right", ctypes.c_long),
            ("bottom", ctypes.c_long),
        ]

    rect = Rect()
    spi_get_work_area = 0x0030
    if not ctypes.windll.user32.SystemParametersInfoW(
        spi_get_work_area,
        0,
        ctypes.byref(rect),
        0,
    ):
        raise ctypes.WinError()
    return WindowBounds(
        left=int(rect.left),
        top=int(rect.top),
        width=int(rect.right - rect.left),
        height=int(rect.bottom - rect.top),
    )


def presenter_layout(slide_ratio: float = 0.67) -> PresenterLayout:
    return calculate_split(primary_work_area(), slide_ratio)


def system_dpi() -> int:
    if os.name != "nt":
        return 96
    try:
        dpi = int(ctypes.windll.user32.GetDpiForSystem())
        return dpi if dpi > 0 else 96
    except Exception:
        return 96


def powerpoint_points(
    bounds: WindowBounds,
    dpi: int | None = None,
) -> tuple[float, float, float, float]:
    """Convert Win32 pixels to the points expected by PowerPoint COM."""
    scale = 72.0 / float(dpi or system_dpi())
    return tuple(
        round(value * scale, 2)
        for value in (bounds.left, bounds.top, bounds.width, bounds.height)
    )


def _edge_path() -> str | None:
    if found := shutil.which("msedge"):
        return found
    candidates = [
        Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Microsoft/Edge/Application/msedge.exe",
        Path(os.environ.get("PROGRAMFILES", "")) / "Microsoft/Edge/Application/msedge.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft/Edge/Application/msedge.exe",
    ]
    return str(next((path for path in candidates if path.is_file()), "")) or None


def launch_presenter_app(url: str, bounds: WindowBounds) -> dict[str, Any]:
    edge = _edge_path()
    if not edge:
        return {"ok": False, "error": "Microsoft Edge was not found."}
    args = [
        edge,
        f"--app={url}",
        "--new-window",
        f"--window-position={bounds.left},{bounds.top}",
        f"--window-size={bounds.width},{bounds.height}",
    ]
    subprocess.Popen(args, close_fds=True)
    return {"ok": True, "browser": edge, "bounds": bounds.to_dict()}


def _find_app_window(title_fragment: str = "AIRA Presenter") -> int | None:
    try:
        import win32gui
    except ImportError:
        return None

    matches: list[int] = []

    def collect(hwnd: int, _: object) -> None:
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = win32gui.GetWindowText(hwnd)
        if title_fragment.casefold() in title.casefold():
            matches.append(hwnd)

    win32gui.EnumWindows(collect, None)
    return matches[0] if matches else None


def arrange_app_window(bounds: WindowBounds) -> dict[str, Any]:
    try:
        import win32con
        import win32gui
    except ImportError:
        return {"ok": False, "error": "pywin32 window helpers are unavailable."}

    hwnd = _find_app_window()
    if not hwnd:
        return {"ok": False, "error": "The AIRA Presenter window was not found."}
    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    win32gui.SetWindowPos(
        hwnd,
        win32con.HWND_TOP,
        bounds.left,
        bounds.top,
        bounds.width,
        bounds.height,
        win32con.SWP_SHOWWINDOW,
    )
    return {"ok": True, "hwnd": hwnd, "bounds": bounds.to_dict()}
