from __future__ import annotations

import time
import unittest

from voice_app.events import EventBus
from voice_app.runtime import PresenterRuntime


def _wait_until(predicate, timeout_s: float = 2.0) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


class FakeNavRuntime(PresenterRuntime):
    def __init__(self) -> None:
        super().__init__(EventBus(), enable_com=False)
        self.applied: list[int] = []
        self._tts_start_wait_s = 0.35

    def perform(self, name: str, args: dict | None = None) -> dict[str, object]:
        args = args or {}
        self.applied.append(int(args.get("slide_number") or 0))
        return {"ok": True}


class RuntimeNavSynchronizationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime = FakeNavRuntime()

    def tearDown(self) -> None:
        self.runtime.reset_talk_state()

    def _enqueue(self, slide: int) -> None:
        self.runtime.enqueue_nav(
            [("goto_slide", {"slide_number": slide})],
            spoken_text=f"slide {slide}",
        )

    def test_does_not_flip_while_current_line_is_still_being_spoken(self) -> None:
        self._enqueue(9)
        self.assertTrue(_wait_until(lambda: self.runtime.applied == [9]))
        self.runtime.set_agent_speaking(True)

        self._enqueue(10)
        time.sleep(0.2)
        self.assertEqual(self.runtime.applied, [9])

        self.runtime.set_agent_speaking(False)
        self.assertTrue(_wait_until(lambda: self.runtime.applied == [9, 10]))

    def test_leftover_speech_is_not_treated_as_the_next_slide(self) -> None:
        self._enqueue(9)
        self.assertTrue(_wait_until(lambda: self.runtime.applied == [9]))
        self.runtime.set_agent_speaking(True)
        self._enqueue(10)
        self._enqueue(11)
        self._enqueue(12)

        time.sleep(0.15)
        self.assertEqual(self.runtime.applied, [9])

        self.runtime.set_agent_speaking(False)
        self.assertTrue(_wait_until(lambda: self.runtime.applied == [9, 10]))
        time.sleep(self.runtime._tts_start_wait_s + 0.2)
        self.assertEqual(self.runtime.applied, [9, 10])

    def test_next_slide_waits_for_a_new_speech_cycle(self) -> None:
        self._enqueue(10)
        self.assertTrue(_wait_until(lambda: self.runtime.applied == [10]))
        self.assertTrue(_wait_until(lambda: self.runtime.speech_ready()["pending_speech"]))
        self.runtime.set_agent_speaking(True)
        self.assertTrue(_wait_until(lambda: self.runtime.speech_ready()["speaking"]))
        self.runtime.set_agent_speaking(False)
        self.assertTrue(
            _wait_until(lambda: self.runtime.speech_ready()["completed_speech_cycle"] >= 1)
        )

        self._enqueue(11)
        self.assertTrue(_wait_until(lambda: self.runtime.applied == [10, 11]))
        self._enqueue(12)
        time.sleep(self.runtime._tts_start_wait_s + 0.2)
        self.assertEqual(self.runtime.applied, [10, 11])

    def test_speech_already_in_progress_counts_for_the_slide_just_shown(self) -> None:
        self._enqueue(4)
        self.assertTrue(_wait_until(lambda: self.runtime.applied == [4]))
        self.runtime.set_agent_speaking(True)
        self.assertTrue(_wait_until(lambda: self.runtime.speech_ready()["speaking"]))
        self._enqueue(5)
        time.sleep(0.15)
        self.assertEqual(self.runtime.applied, [4])
        self.runtime.set_agent_speaking(False)
        self.assertTrue(_wait_until(lambda: self.runtime.applied == [4, 5]))


if __name__ == "__main__":
    unittest.main()
