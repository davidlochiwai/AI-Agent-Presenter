from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "voice_app" / "static"


class PresenterUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.html = (STATIC / "index.html").read_text(encoding="utf-8")
        cls.javascript = (STATIC / "app.js").read_text(encoding="utf-8")
        cls.css = (STATIC / "styles.css").read_text(encoding="utf-8")

    def test_presenter_view_is_the_default(self) -> None:
        self.assertIn('<body data-view="presenter">', self.html)
        self.assertIn('id="presenterSurface"', self.html)
        self.assertIn('id="maintenanceShell"', self.html)
        self.assertIn('id="viewToggle"', self.html)

    def test_dialogue_and_avatar_assets_are_present(self) -> None:
        self.assertIn('id="agentDialogue"', self.html)
        self.assertIn('id="userDialogue"', self.html)
        self.assertIn("<video", self.html)
        self.assertIn("/static/aira-avatar.mp4", self.html)
        self.assertIn("/static/aira-avatar-first-frame.png", self.html)
        self.assertIn("muted", self.html)
        self.assertIn("playsinline", self.html)
        self.assertIn("loop", self.html)
        self.assertTrue((STATIC / "aira-avatar-first-frame.png").is_file())
        self.assertTrue((STATIC / "aira-avatar.mp4").is_file())

    def test_avatar_video_plays_and_rewinds_with_speech(self) -> None:
        self.assertIn("els.agentAvatar.play()", self.javascript)
        self.assertIn("els.agentAvatar.pause()", self.javascript)
        self.assertIn("els.agentAvatar.currentTime = 0", self.javascript)

    def test_mode_switch_does_not_reload_the_page(self) -> None:
        self.assertIn("window.history.replaceState", self.javascript)
        self.assertIn('event.key.toLowerCase() === "m"', self.javascript)
        self.assertNotIn("window.location.reload", self.javascript)

    def test_transcript_updates_presenter_dialogue(self) -> None:
        self.assertIn("function renderDialogue(turns)", self.javascript)
        self.assertIn("renderDialogue(parts);", self.javascript)
        self.assertIn('turn.role === "agent"', self.javascript)
        self.assertIn('turn.role === "user"', self.javascript)

    def test_maintenance_hint_points_at_script_and_knowledge_files(self) -> None:
        self.assertIn("data/script.xlsx", self.html)
        self.assertIn("data/knowledge_sources", self.html)
        self.assertNotIn("data/knowledge.xlsx", self.html)
        self.assertIn("Talk script", self.javascript)

    def test_between_slide_processing_indicator_is_visible_and_animated(self) -> None:
        self.assertIn('data-processing="false"', self.html)
        self.assertIn("function setAvatarProcessing()", self.javascript)
        self.assertIn("Preparing next slide…", self.javascript)
        self.assertIn("}, slidePauseMs);", self.javascript)
        self.assertIn('.avatar-stage[data-processing="true"]', self.css)
        self.assertIn("@keyframes processing-spin", self.css)

    def test_maintenance_does_not_mention_n8n(self) -> None:
        self.assertNotIn("n8n", self.html.lower())
        self.assertNotIn("n8n", self.javascript.lower())
        self.assertIn('id="directorNextBtn"', self.html)

    def test_presenter_and_maintenance_surfaces_are_mutually_exclusive(self) -> None:
        self.assertIn(
            'body[data-view="presenter"] .maintenance-shell',
            self.css,
        )
        self.assertIn(
            'body[data-view="maintenance"] .presenter-shell',
            self.css,
        )


if __name__ == "__main__":
    unittest.main()
