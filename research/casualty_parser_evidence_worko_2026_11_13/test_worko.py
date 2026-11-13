"""Work O: synthetic offline parser/excerpt/privacy controls only, never source HTTP."""
import io
import json
import tempfile
import unittest
from html import escape
from pathlib import Path

from research.casualty_evidence_ingestion_2026_11_13 import ingest as e
from research.casualty_one_time_capture_2026_11_13 import run_capture as r
from research.casualty_fact_retention_workj_2026_11_13.test_workj import candidate, article
from casualty_auto_review import _fatal_total, _incident_scopes, extract_cached_reports


def original(text):
    return {"articles": [article(text)],
            "receipts": [{"candidate_id": "mock",
                          "resolved_url": "https://mig.com.ua/synthetic-offline",
                          "response_sha256": "a" * 64}],
            "official_articles": []}


def card(text):
    return e.minimal_capture_facts(original(text), [candidate()])["facts"][0]


class WorkO(unittest.TestCase):
    def test_01_ukrainian_count_forms_in_both_paths(self):
        for wording, expected in [
            ("Загинули двоє людей.", 2), ("Загинули троє людей.", 3),
            ("Кількість загиблих зросла до трьох.", 3),
        ]:
            with self.subTest(wording=wording):
                self.assertEqual(_fatal_total(wording.casefold()), expected)
                c = card("Російська ракета атакувала Запоріжжя. " + wording)
                self.assertEqual(c["claim_deaths"], expected)
                self.assertEqual(len(c["excerpts"]), 1)
                self.assertLessEqual(len(c["excerpts"][0]["text"]), 170)
                self.assertEqual(c["excerpts"][0]["claim_number"], expected)

    def test_02_uncertain_count_stays_unverified_but_excerpt_retained(self):
        wording = "Після удару повідомляють про можливу загибель людей."
        self.assertIsNone(_fatal_total(wording.casefold()))
        c = card("Російська ракета атакувала Запоріжжя. " + wording)
        self.assertIsNone(c["claim_deaths"])
        self.assertIsNone(c["excerpts"][0]["claim_number"])
        self.assertIn("SHORT_EVIDENCE_RETAINED_COUNT_UNCONFIRMED", c["reasons"])
        self.assertEqual(extract_cached_reports([candidate()], [article(wording)]), [])

    def test_03_unknown_and_missing_text_never_produce_a_fact(self):
        for text in ("", "Пошкоджено будинок, кількість постраждалих уточнюється."):
            with self.subTest(text=text):
                result = e.minimal_capture_facts(original(text), [candidate()])
                if text:
                    self.assertIsNone(result["facts"][0]["claim_deaths"])
                    self.assertEqual(result["facts"][0]["excerpts"], [])
                else:
                    self.assertEqual(result["facts"], [])
                self.assertEqual(extract_cached_reports([candidate()], [article(text)]), [])

    def test_04_html_main_survives_short_teaser_and_skips_menu(self):
        html = """<html><head><title>Новини</title><script>bad()</script></head>
        <body><nav>Навігація загинули 99 людей</nav>
        <article>Рекламний анонс</article><main><div>""" + (
            "Ситуація у місті залишається складною. " * 6) + (
            "Російська ракета атакувала Запоріжжя 22 жовтня вранці. "
            "Загинули двоє людей.") + """</div></main>
        <aside>Інше повідомлення: загинули 8 людей</aside></body></html>"""
        parser = e._TextExtractor()
        parser.feed(html)
        text = parser.body()
        self.assertEqual(parser.content_scope, "main")
        self.assertIn("Загинули двоє людей", text)
        self.assertNotIn("99 людей", text)
        self.assertNotIn("8 людей", text)
        self.assertEqual(card(text)["claim_deaths"], 2)
        d = {}
        self.assertEqual(len(extract_cached_reports(
            [candidate()], [article(text)], diagnostics=d)), 1)
        self.assertEqual(d["stage_counts"]["unique_fatal_scope"], 1)

    def test_05_cumulative_two_then_three_never_five(self):
        for wording in ["Загинули двоє людей.", "Кількість загиблих зросла до трьох."]:
            self.assertNotEqual(_fatal_total(wording.casefold()), 5)
        facts = [card("Російська ракета атакувала Запоріжжя. " + x)
                 for x in ["Загинули двоє людей.", "Кількість загиблих зросла до трьох."]]
        self.assertEqual([x["claim_deaths"] for x in facts], [2, 3])
        self.assertTrue(all(x["decision"] == "NEEDS_REVIEW" for x in facts))
        self.assertEqual(e.minimal_capture_facts(original("Загинули двоє людей."),
                                                  [candidate()])["automatic_credits"], 0)

    def test_06_separate_attacks_are_not_merged(self):
        text = ("Російська ракета атакувала Запоріжжя вранці 22 жовтня. "
                "Загинули двоє людей. Також окремо атакували Запоріжжя увечері. "
                "Загинули троє людей.")
        d = {}
        self.assertGreaterEqual(len(_incident_scopes(text.casefold())), 2)
        self.assertEqual(extract_cached_reports([candidate()], [article(text)],
                                                diagnostics=d), [])
        self.assertIn("MULTIPLE_POSSIBLE_INCIDENTS", d["reason_counts"])

    def test_07_no_attack_date_or_official_match(self):
        text = "Російська ракета атакувала Запоріжжя. Загинули троє людей."
        c = card(text)
        self.assertEqual(c["claim_deaths"], 3)
        self.assertIsNone(c["attack_date_explicit"])
        self.assertEqual(c["decision"], "NEEDS_REVIEW")
        self.assertEqual(extract_cached_reports([candidate()], [article(text)]), [])
        police = {"articles": [], "receipts": [], "official_articles": [{
            "url": "https://zp.npu.gov.ua/synthetic",
            "text": "Поліція повідомила: загинули троє людей.",
            "response_sha256": "b" * 64}]}
        result = e.minimal_capture_facts(police, [candidate()])
        self.assertIsNone(result["facts"][0]["candidate_id"])
        self.assertIn("OFFICIAL_INCIDENT_MATCH_NOT_VERIFIED", result["facts"][0]["reasons"])
        self.assertEqual(result["official_incidents_automatically_matched"], 0)

    def test_08_safe_excerpt_and_privacy_withholding(self):
        safe = card("Загинули двоє людей.")
        r.withhold_unsafe_excerpts(safe)
        self.assertEqual(len(safe["excerpts"]), 1)
        private = card("Загинули двоє людей, повідомив свідок Петро Іваненко.")
        r.withhold_unsafe_excerpts(private)
        self.assertEqual(private["excerpts"], [])
        self.assertIn("PRIVACY_REVIEW_EXCERPT_WITHHELD", private["reasons"])

    def test_09_no_truncation_of_context_or_untrusted_quote(self):
        text = "Загинули двоє людей, " + "продовження відомостей " * 15 + "не підтверджено."
        self.assertEqual(e._short_excerpts(text, [2]), [])
        self.assertIsNone(_fatal_total(text.casefold()))
        self.assertEqual(e._short_excerpts("Загинули двоє людей, інформацію не підтверджено.", [2]), [])
        self.assertEqual(len(e._short_excerpts(
            "Ймовірно загинули двоє людей.", [])), 1)

    def test_10_stage_diagnostics_no_source_text(self):
        d = {}
        text = "Ймовірно загинули двоє людей."
        self.assertEqual(extract_cached_reports([candidate()], [article(text)],
                                                diagnostics=d), [])
        self.assertEqual(d["stage_counts"]["fatal_mention_articles"], 1)
        self.assertEqual(d["stage_counts"]["unparseable_fatal_mention_articles"], 1)
        self.assertEqual(d["stage_counts"]["structured_reports"], 0)
        self.assertNotIn(text, json.dumps(d, ensure_ascii=False))

    def test_11_minimal_card_publication_guards(self):
        c = card("Загинули двоє людей.")
        self.assertFalse(c["publication_allowed"])
        self.assertEqual(c["decision"], "NEEDS_REVIEW")
        self.assertNotIn("text", c)
        self.assertNotIn("body", c)
        self.assertEqual(len(c["excerpts"][0]["text"]), len("Загинули двоє людей."))
        self.assertFalse(r.LIMITS["retries"])
        self.assertEqual(e.MODE_DEFAULT, "OFFLINE_REPLAY")

    def test_12_no_unapproved_source_requests(self):
        # Tests run on synthetic strings only; no source capture entrypoint.
        self.assertFalse((r.HERE / "launch.json").exists())
        self.assertEqual(r.LIMITS["max_initial_urls"], 3)
        self.assertEqual(r.LIMITS["max_requests_total"], 6)


if __name__ == "__main__":
    unittest.main()
