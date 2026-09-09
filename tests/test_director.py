from __future__ import annotations

import unittest
from unittest.mock import patch

from voice_app.director import PresentationDirector


class FakeRuntime:
    def __init__(self) -> None:
        self.speaking = False
        self.pending_speech = False
        self.speech_cycle = 0
        self.completed_speech_cycle = 0

    def speech_ready(self) -> dict[str, object]:
        return {
            "speaking": self.speaking,
            "pending_speech": self.pending_speech,
            "speech_cycle": self.speech_cycle,
            "completed_speech_cycle": self.completed_speech_cycle,
        }

    def snapshot(self) -> dict[str, object]:
        return {"status": {"slide": 1, "slide_count": 2}}


class FakeQaService:
    def answer(self, question: str, current_slide: int | None = None) -> dict[str, object]:
        return {
            "ok": True,
            "answerable": True,
            "spoken_text": "答案",
            "should_change_slide": False,
        }


class DirectorSpeechSynchronizationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime = FakeRuntime()
        self.director = PresentationDirector(
            self.runtime,  # type: ignore[arg-type]
            FakeQaService(),  # type: ignore[arg-type]
            beats=[
                {
                    "seq": 1,
                    "slide": 1,
                    "actions": "goto_slide:1",
                    "script_yue": "第一頁",
                },
                {
                    "seq": 2,
                    "slide": 2,
                    "actions": "goto_slide:2",
                    "script_yue": "第二頁",
                },
            ],
        )
        self.director.reset(
            {"call_id": "call-1", "status": {"slide": 1, "slide_count": 2}}
        )

    @patch("voice_app.director.run_actions", return_value={"ok": True, "queued": True})
    def test_duplicate_delivery_waits_for_a_complete_speech_cycle(self, run_actions) -> None:
        first = self.director.deliver_next({"call_id": "call-1"})
        self.assertEqual(first["spoken_text"], "第一頁")
        self.assertEqual(run_actions.call_count, 1)

        immediate = self.director.deliver_next({"call_id": "call-1"})
        self.assertTrue(immediate["repeat"])
        self.assertEqual(immediate["spoken_text"], "")
        self.assertEqual(run_actions.call_count, 1)

        self.runtime.speaking = True
        self.runtime.speech_cycle = 1
        while_speaking = self.director.deliver_next({"call_id": "call-1"})
        self.assertTrue(while_speaking["repeat"])
        self.assertEqual(run_actions.call_count, 1)

        self.runtime.speaking = False
        self.runtime.completed_speech_cycle = 1
        second = self.director.deliver_next({"call_id": "call-1"})
        self.assertEqual(second["spoken_text"], "第二頁")
        self.assertEqual(run_actions.call_count, 2)

    @patch("voice_app.director.run_actions", return_value={"ok": True, "queued": True})
    def test_does_not_advance_while_avatar_is_still_talking(self, run_actions) -> None:
        first = self.director.deliver_next({"call_id": "call-1"})
        self.assertEqual(first["spoken_text"], "第一頁")

        self.runtime.speech_cycle = 1
        self.runtime.completed_speech_cycle = 1
        self.runtime.speaking = True
        blocked = self.director.deliver_next({"call_id": "call-1"})
        self.assertTrue(blocked["repeat"])
        self.assertEqual(blocked["spoken_text"], "")
        self.assertEqual(run_actions.call_count, 1)

        self.runtime.speaking = False
        second = self.director.deliver_next({"call_id": "call-1"})
        self.assertEqual(second["spoken_text"], "第二頁")
        self.assertEqual(run_actions.call_count, 2)

    @patch("voice_app.director.run_actions", return_value={"ok": True, "queued": True})
    def test_stale_pending_flag_does_not_block_after_speech_completes(self, run_actions) -> None:
        first = self.director.deliver_next({"call_id": "call-1"})
        self.assertEqual(first["spoken_text"], "第一頁")

        self.runtime.speech_cycle = 1
        self.runtime.completed_speech_cycle = 1
        self.runtime.speaking = False
        self.runtime.pending_speech = True
        second = self.director.deliver_next({"call_id": "call-1"})
        self.assertEqual(second["spoken_text"], "第二頁")
        self.assertEqual(run_actions.call_count, 2)

    @patch("voice_app.director.run_actions", return_value={"ok": True, "queued": True})
    def test_initial_delivery_waits_if_agent_is_already_talking(self, run_actions) -> None:
        self.runtime.speaking = True
        self.runtime.speech_cycle = 1

        result = self.director.deliver_next({"call_id": "call-1"})

        self.assertTrue(result["repeat"])
        self.assertEqual(result["spoken_text"], "")
        run_actions.assert_not_called()


if __name__ == "__main__":
    unittest.main()
