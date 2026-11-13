"""Work J: mock-only extraction, rejection and audit cards. No source network."""
from __future__ import annotations

import hashlib
import unittest
from datetime import datetime, timezone

from research.casualty_evidence_ingestion_2026_11_13 import ingest as e
from casualty_auto_review import _fatal_total, _incident_scopes, extract_cached_reports


def candidate(cid="mock"):
    return {"candidate_id": cid, "city_key": "zaporizhzhia", "city": "Запоріжжя",
            "title": "synthetic offline test", "snippet": "",
            "url": "https://news.google.com/rss/articles/synthetic",
            "published_at": "2026-10-22T12:00:00Z", "status": "needs_review"}


def article(text, cid="mock"):
    return {"candidate_id": cid, "url": "https://mig.com.ua/synthetic-offline",
            "text": text, "observed_at": "2026-10-22T14:00:00Z"}


class ParserDiagnostics(unittest.TestCase):
    def test_ukrainian_count_forms(self):
        self.assertEqual(_fatal_total("загинули двоє людей"), 2)
        self.assertEqual(_fatal_total("загинули троє людей"), 3)
        self.assertEqual(_fatal_total("кількість загиблих зросла до трьох"), 3)
        self.assertIsNone(_fatal_total("постраждали двоє людей"))
        self.assertIsNone(_fatal_total("ймовірно загинули двоє людей"))
        self.assertIsNone(_fatal_total("помер у лікарні після поранення"))

    def test_missing_text_reason(self):
        d = {}
        self.assertEqual(extract_cached_reports([candidate()], [article("")], diagnostics=d), [])
        self.assertEqual(d["source_decisions"][0]["reason"], "SOURCE_TEXT_NOT_RETAINED")

    def test_no_death_reason(self):
        d = {}
        self.assertEqual(extract_cached_reports([candidate()], [article(
            "Ворог атакував Запоріжжя ракетою 22 жовтня вранці. Постраждали двоє людей."
        )], diagnostics=d), [])
        self.assertIn("NO_FATAL_CLAIM", d["reason_counts"])

    def test_no_attack_date_not_auto_ready(self):
        d = {}
        self.assertEqual(extract_cached_reports([candidate()], [article(
            "Російська ракета атакувала Запоріжжя вранці. Загинули двоє людей."
        )], diagnostics=d), [])
        self.assertTrue(any(x["reason"] in {"ATTACK_DATE_MISSING", "ATTACK_IDENTITY_AMBIGUOUS"}
                            for x in d["source_decisions"]))

    def test_multiple_attacks_never_merged(self):
        text = ("Російська ракета атакувала Запоріжжя вранці 22 жовтня. "
                "Загинули двоє людей. Також окремо атакували Запоріжжя увечері. "
                "Загинули троє людей.")
        d = {}
        reports = extract_cached_reports([candidate()], [article(text)], diagnostics=d)
        self.assertEqual(reports, [])
        self.assertGreaterEqual(len(_incident_scopes(text.casefold())), 2)
        self.assertIn("MULTIPLE_POSSIBLE_INCIDENTS", d["reason_counts"])

    def test_no_automatic_credit_of_source_cards(self):
        text = ("22 жовтня російська ракета атакувала Запоріжжя вранці. "
                "Загинули двоє людей.")
        d = {}
        extract_cached_reports([candidate()], [article(text)], diagnostics=d)
        self.assertEqual(d["stage_counts"]["articles_seen"], 1)
        self.assertIn("structured_reports", d["stage_counts"])


class Retention(unittest.TestCase):
    def test_different_sources_not_stitched(self):
        q = [candidate()]
        text = "22 жовтня російська ракета атакувала Запоріжжя. Загинули двоє людей."
        original = {"articles": [article(text)],
                    "official_articles": [{"url": "https://zp.npu.gov.ua/synthetic",
                                           "text": "Поліція повідомила про одну поранену людину.",
                                           "observed_at": "2026-10-22T15:00:00Z",
                                           "response_sha256": "1" * 64}],
                    "receipts": [{"candidate_id": "mock",
                                  "resolved_url": "https://mig.com.ua/synthetic-offline",
                                  "response_sha256": "2" * 64}]}
        cards = e.minimal_capture_facts(original, q)
        self.assertEqual(len(cards["facts"]), 2)
        pub, police = cards["facts"]
        self.assertEqual(pub["candidate_id"], "mock")
        self.assertIsNone(police["candidate_id"])
        self.assertIsNone(police["claim_deaths"])
        self.assertEqual(pub["document_sha256"], "2" * 64)
        self.assertEqual(police["document_sha256"], "1" * 64)
        self.assertEqual(pub["decision"], "NEEDS_REVIEW")
        self.assertEqual(cards["automatic_credits"], 0)
        self.assertEqual(cards["official_incidents_automatically_matched"], 0)
        self.assertNotIn("text", pub)
        self.assertTrue(all(len(x["text"]) <= 170 for x in pub["excerpts"]))

    def test_missing_text_never_inferred_from_url(self):
        result = e.minimal_capture_facts(
            {"articles": [article("")], "official_articles": []}, [candidate()])
        self.assertEqual(result["facts"], [])
        self.assertEqual(result["decisions"][0]["reason"], "SOURCE_TEXT_NOT_RETAINED")

    def test_controlled_capture_still_default_off(self):
        with self.assertRaisesRegex(RuntimeError, "DEFAULT_OFF"):
            e.validate_capture_approval({}, False, [candidate()])
        self.assertEqual(e.MODE_DEFAULT, "OFFLINE_REPLAY")
        self.assertNotIn("raw_articles.json", e.ALLOWED_OUTPUTS)


if __name__ == "__main__":
    unittest.main()
