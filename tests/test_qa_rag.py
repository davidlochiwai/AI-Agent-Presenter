from __future__ import annotations

import json
import unittest
from pathlib import Path

from voice_app import config
from voice_app.presenter_prompt import GENERAL_PROMPT, PROMPT_MARKER
from voice_app.qa_rag import (
    QARagService,
    QdrantStore,
    _document_records,
    _excel_records,
    _knowledge_source_files,
    _normalized,
    _slide_records,
)


class QARagTests(unittest.TestCase):
    def test_normalizes_full_width_numbers_and_punctuation(self) -> None:
        self.assertEqual(_normalized(" １２８０％， ARR "), "1280%, arr")

    def test_extracts_sample_slides_and_knowledge(self) -> None:
        slides = _slide_records(config.SAMPLE_DECK_PATH, "sample")
        knowledge = _excel_records(config.SAMPLE_KNOWLEDGE_PATH, "sample")
        self.assertEqual(len(slides), 12)
        self.assertGreaterEqual(len(knowledge), 15)
        finance = next(item for item in slides if item["slide_number"] == 7)
        self.assertIn("1,860", finance["text"])
        self.assertIn("18", finance["text"])
        self.assertIn("Prepared script:", finance["text"])

    def test_knowledge_files_live_only_under_knowledge_sources(self) -> None:
        self.assertEqual(config.SAMPLE_KNOWLEDGE_PATH.parent, config.QA_KNOWLEDGE_DIR)
        self.assertTrue(config.SAMPLE_KNOWLEDGE_PATH.exists())
        self.assertFalse((config.ROOT / "data" / "knowledge.xlsx").exists())
        names = {path.name for path in _knowledge_source_files()}
        self.assertIn("knowledge.xlsx", names)
        records = _document_records(config.QA_KNOWLEDGE_DIR, "sample")
        excel = [item for item in records if item["source_label"].startswith("knowledge.xlsx,")]
        self.assertGreaterEqual(len(excel), 15)
        service = QARagService()
        combined = service._records_for(config.SAMPLE_DECK_PATH, "sample")
        knowledge = [item for item in combined if item["kind"] == "knowledge"]
        self.assertGreaterEqual(len(knowledge), len(excel))

    def test_qdrant_delete_except_skips_current_index(self) -> None:
        from unittest.mock import patch

        store = QdrantStore("http://127.0.0.1:6333", "presenter_knowledge")

        class FakeResponse:
            status_code = 200

            def raise_for_status(self) -> None:
                return None

        with patch("voice_app.qa_rag.httpx.post", return_value=FakeResponse()) as posted:
            store.delete_except("current-hash")
        args, kwargs = posted.call_args
        self.assertTrue(str(args[0]).endswith("/points/delete"))
        self.assertEqual(
            kwargs["json"]["filter"]["must_not"][0]["key"],
            "index_id",
        )
        self.assertEqual(
            kwargs["json"]["filter"]["must_not"][0]["match"]["value"],
            "current-hash",
        )

    def test_index_prunes_qdrant_after_sync(self) -> None:
        class FakeQdrant:
            configured = True

            def __init__(self) -> None:
                self.deleted_except = ""
                self.upserts = 0

            def count(self, index_id: str) -> int:
                return 10_000

            def ensure(self, dimensions: int) -> None:
                return None

            def upsert(self, index_id: str, records: list, vectors: list) -> None:
                self.upserts += 1

            def delete_except(self, index_id: str) -> None:
                self.deleted_except = index_id

        service = QARagService()
        service.azure.api_key = "test"
        service.azure.endpoint = "https://example.invalid"
        service.azure.api_version = "test"
        service.azure.chat_deployment = "chat"
        service.azure.embedding_deployment = "embedding"
        service.qdrant = FakeQdrant()  # type: ignore[assignment]
        service._index(config.SAMPLE_DECK_PATH, force=False)
        self.assertEqual(service.qdrant.upserts, 0)
        self.assertEqual(service._status["backend"], "qdrant")
        self.assertEqual(service.qdrant.deleted_except, service._status["index_id"])
        self.assertTrue(service.qdrant.deleted_except)

    def test_attaches_script_xlsx_to_a_custom_deck_path(self) -> None:
        import shutil
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "custom.pptx"
            shutil.copy(config.SAMPLE_DECK_PATH, dest)
            slides = _slide_records(dest, "custom")
        finance = next(item for item in slides if item["slide_number"] == 7)
        self.assertIn("Prepared script:", finance["text"])

    def test_extracts_evaluation_reference_documents(self) -> None:
        records = _document_records(config.QA_KNOWLEDGE_DIR, "sample")
        labels = {item["source_label"].split(",", 1)[0] for item in records}
        self.assertTrue(
            {
                "customer-pilot-retrospective.md",
                "security-and-data-handling.md",
                "deployment-readiness-guide.md",
                "support-and-escalation-policy.md",
            }.issubset(labels)
        )
        support = next(
            item
            for item in records
            if item["source_label"] == "support-and-escalation-policy.md, chunk 1"
        )
        self.assertEqual(support["slide_number"], 10)

    def test_without_azure_uses_safe_abstention_only(self) -> None:
        service = QARagService()
        service.azure.api_key = ""
        service._records = _slide_records(config.SAMPLE_DECK_PATH, "sample")
        service._records.extend(_excel_records(config.SAMPLE_KNOWLEDGE_PATH, "sample"))
        result = service.answer("公司現金跑道仲有幾耐？", current_slide=4)
        self.assertFalse(result["answerable"])
        self.assertEqual(result["mode"], "safe_abstention")
        self.assertIsNone(result["slide"])
        self.assertEqual(result["source_ids"], [])

    def test_workflow_contains_validated_rag_branch(self) -> None:
        root = Path(__file__).resolve().parents[1]
        workflow = json.loads((root / "n8n" / "powerpoint-director.json").read_text(encoding="utf-8"))
        names = {node["name"] for node in workflow["nodes"]}
        self.assertTrue(
            {
                "Prepare question",
                "Call Q&A agent",
                "Validate Q&A",
                "Flip for question?",
                "POST question slide",
                "Merge question",
            }.issubset(names)
        )
        self.assertEqual(
            workflow["connections"]["Webhook handle-question"]["main"][0][0]["node"],
            "Prepare question",
        )
        self.assertEqual(
            workflow["connections"]["Validate Q&A"]["main"][0][0]["node"],
            "Flip for question?",
        )
        next_beat = next(node for node in workflow["nodes"] if node["name"] == "Next beat")
        prepare = next(node for node in workflow["nodes"] if node["name"] == "Prepare question")
        self.assertIn("Stale call_id", next_beat["parameters"]["jsCode"])
        self.assertIn("listen_for_questions", next_beat["parameters"]["jsCode"])
        self.assertIn("staleSession", prepare["parameters"]["jsCode"])
        merge = next(node for node in workflow["nodes"] if node["name"] == "Merge question")
        self.assertIn("presentation_done", merge["parameters"]["jsCode"])

    def test_retell_prompt_keeps_listening_after_last_slide(self) -> None:
        self.assertEqual(PROMPT_MARKER, "harbour-presenter-prompt v12")
        self.assertNotIn("stay silent forever", GENERAL_PROMPT)
        self.assertIn("including after the prepared talk is finished", GENERAL_PROMPT)
        self.assertIn("presentation_done is true", GENERAL_PROMPT)

    def test_model_cannot_select_a_slide_outside_retrieved_candidates(self) -> None:
        service = QARagService()
        records = _slide_records(config.SAMPLE_DECK_PATH, "sample")
        records.extend(_excel_records(config.SAMPLE_KNOWLEDGE_PATH, "sample"))
        service._records = records
        service._vectors = {item["record_id"]: [1.0, 0.0] for item in records}
        service._status.update(
            {"state": "ready", "backend": "memory_vectors", "index_id": "test"}
        )
        service.azure.api_key = "test"
        service.azure.endpoint = "https://example.invalid"
        service.azure.api_version = "test"
        service.azure.chat_deployment = "chat"
        service.azure.embedding_deployment = "embedding"
        service.azure.embed = lambda _texts: [[1.0, 0.0]]  # type: ignore[method-assign]
        service.azure.answer = lambda *_args: {  # type: ignore[method-assign]
            "answerable": True,
            "answer_yue": "根據資料，現金跑道約十八個月。",
            "answer_en": "Cash runway is about 18 months.",
            "answer_confidence": 0.9,
            "source_ids": ["knowledge:k_founded"],
            "recommended_slide": 99,
            "slide_confidence": 0.99,
            "should_change_slide": True,
        }
        result = service.answer("現金跑道幾耐？", current_slide=4)
        self.assertTrue(result["answerable"])
        self.assertNotEqual(result["recommended_slide"], 99)
        self.assertIn(result["recommended_slide"], range(1, 13))


if __name__ == "__main__":
    unittest.main()
