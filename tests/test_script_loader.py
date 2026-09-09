from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

from voice_app.script_loader import load_script_beats


class ScriptLoaderTests(unittest.TestCase):
    def test_loads_sample_script_xlsx(self) -> None:
        beats, source = load_script_beats()
        self.assertGreaterEqual(len(beats), 12)
        self.assertIn("script.xlsx", source)
        self.assertEqual(beats[0]["seq"], 1)
        self.assertTrue(beats[0]["script_yue"])
        self.assertTrue(str(beats[0]["actions"]).startswith("goto_slide:"))

    def test_reads_custom_workbook(self) -> None:
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "script"
        sheet.append(["seq", "slide", "actions", "script_yue", "script_en", "notes"])
        sheet.append([1, 1, "", "第一頁講呢句。", "First slide.", ""])
        sheet.append([2, 3, "goto_slide:3", "跳去第三頁。", "Jump to slide 3.", ""])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "script.xlsx"
            workbook.save(path)
            beats, source = load_script_beats(path)
        self.assertEqual(source, str(path))
        self.assertEqual(len(beats), 2)
        self.assertEqual(beats[0]["actions"], "goto_slide:1")
        self.assertEqual(beats[1]["slide"], 3)
        self.assertEqual(beats[1]["script_yue"], "跳去第三頁。")

    def test_falls_back_when_workbook_has_no_spoken_rows(self) -> None:
        workbook = Workbook()
        workbook.active.append(["seq", "slide", "script_yue"])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "empty.xlsx"
            workbook.save(path)
            beats, source = load_script_beats(path)
        self.assertIn("empty", source)
        self.assertEqual(len(beats), 12)
        self.assertEqual(beats[0]["slide"], 1)


if __name__ == "__main__":
    unittest.main()
