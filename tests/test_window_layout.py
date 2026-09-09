from __future__ import annotations

import unittest
from unittest.mock import patch

from ppt_presenter.controller import PresenterController
from ppt_presenter.errors import PresenterError
from voice_app.window_layout import (
    WindowBounds,
    calculate_split,
    launch_presenter_app,
    powerpoint_points,
)


class WindowLayoutTests(unittest.TestCase):
    def test_split_fills_work_area_without_overlap(self) -> None:
        layout = calculate_split(WindowBounds(0, 0, 1920, 1040), 0.67)

        self.assertEqual(layout.powerpoint, WindowBounds(0, 0, 1286, 1040))
        self.assertEqual(layout.app, WindowBounds(1286, 0, 634, 1040))
        self.assertEqual(
            layout.powerpoint.width + layout.app.width,
            1920,
        )

    def test_split_ratio_is_kept_in_safe_range(self) -> None:
        low = calculate_split(WindowBounds(10, 20, 1000, 700), 0.1)
        high = calculate_split(WindowBounds(10, 20, 1000, 700), 0.95)

        self.assertEqual(low.powerpoint.width, 500)
        self.assertEqual(high.powerpoint.width, 800)
        self.assertEqual(high.app.left, 810)

    def test_pixel_bounds_convert_to_powerpoint_points(self) -> None:
        points = powerpoint_points(WindowBounds(0, 0, 1280, 960), dpi=96)
        self.assertEqual(points, (0.0, 0.0, 960.0, 720.0))

    def test_controller_applies_window_bounds(self) -> None:
        class FakeWindow:
            Left = 0.0
            Top = 0.0
            Width = 0.0
            Height = 0.0

        ctrl = object.__new__(PresenterController)
        ctrl.window = FakeWindow()
        ctrl.is_running = lambda: True

        ctrl.set_window_bounds((12.5, 8.0, 960.0, 720.0))

        self.assertEqual(
            (ctrl.window.Left, ctrl.window.Top, ctrl.window.Width, ctrl.window.Height),
            (12.5, 8.0, 960.0, 720.0),
        )

    def test_controller_rejects_invalid_window_size(self) -> None:
        ctrl = object.__new__(PresenterController)
        ctrl.window = object()
        ctrl.is_running = lambda: True

        with self.assertRaises(PresenterError):
            ctrl.set_window_bounds((0, 0, 0, 720))

    @patch("voice_app.window_layout.subprocess.Popen")
    @patch("voice_app.window_layout._edge_path", return_value=r"C:\Edge\msedge.exe")
    def test_edge_app_launch_uses_requested_bounds(self, _edge, popen) -> None:
        result = launch_presenter_app(
            "http://127.0.0.1:8787/",
            WindowBounds(1280, 0, 640, 1040),
        )

        self.assertTrue(result["ok"])
        args = popen.call_args.args[0]
        self.assertIn("--app=http://127.0.0.1:8787/", args)
        self.assertIn("--window-position=1280,0", args)
        self.assertIn("--window-size=640,1040", args)


if __name__ == "__main__":
    unittest.main()
