"""Work Q: saved-excerpt regressions and CI path-scope simulation. Offline only."""
import json
import re
import unittest
from pathlib import Path

from casualty_auto_review import _fatal_total, _fatal_issue, extract_cached_reports
from research.casualty_evidence_ingestion_2026_11_13 import ingest as e
from research.casualty_fact_retention_workj_2026_11_13.test_workj import candidate, article
from research.casualty_one_time_capture_2026_11_13 import run_capture as runner


def card(text):
    original = {"articles": [article(text)], "official_articles": [],
                "receipts": [{"candidate_id": "mock",
                              "resolved_url": "https://mig.com.ua/synthetic-offline",
                              "response_sha256": "f" * 64}]}
    return e.minimal_capture_facts(original, [candidate()])["facts"][0]


class RealExcerptRegressions(unittest.TestCase):
    def test_t03_local_number_is_two_but_full_article_still_unknown(self):
        sentence = "Загинули двоє людей», - написав очільник ОВА."
        self.assertEqual(_fatal_total(sentence.casefold()), 2)
        local = card(sentence)
        self.assertEqual(local["claim_deaths"], 2)
        self.assertEqual(local["decision"], "NEEDS_REVIEW")
        # This is not a reconstruction of the real article; ambiguity blocks
        # extrapolation from the single saved excerpt.
        mixed = "Загинули двоє людей. Загинули троє людей."
        self.assertIsNone(_fatal_total(mixed.casefold()))
        self.assertEqual(_fatal_issue(mixed.casefold()), "CONFLICTING_FATAL_TOTALS")
        self.assertIsNone(card(mixed)["claim_deaths"])

    def test_t04_additional_not_total_or_69(self):
        sentence = "Пізніше стало відомо, що загинула також 69-річна жінка."
        self.assertIsNone(_fatal_total(sentence.casefold()))
        self.assertEqual(_fatal_issue(sentence.casefold()), "ADDITIONAL_DEATH_REPORTED")
        result = card(sentence)
        self.assertIsNone(result["claim_deaths"])
        self.assertEqual(result["claim_type"], "ADDITIONAL_DEATH_REPORTED")
        self.assertEqual(result["fatal_total_diagnostic"], "ADDITIONAL_DEATH_REPORTED")
        self.assertEqual(result["decision"], "NEEDS_REVIEW")
        self.assertNotIn(69, [x["claim_number"] for x in result["excerpts"]])
        self.assertFalse(result["publication_allowed"])
        self.assertIn("NO_AUTOMATIC_CREDIT", result["reasons"])

    def test_additional_after_prior_two_does_not_infer_three(self):
        text = ("Загинули двоє людей. "
                "Пізніше стало відомо, що загинула також 69-річна жінка.")
        self.assertIsNone(_fatal_total(text.casefold()))
        self.assertIsNone(card(text)["claim_deaths"])
        self.assertNotIn(3, [card(text)["claim_deaths"]])

    def test_regular_numerals_and_cumulative_never_add(self):
        for wording, total in (("Загинули двоє людей.", 2),
                               ("Загинули троє людей.", 3),
                               ("Кількість загиблих зросла до трьох.", 3)):
            self.assertEqual(_fatal_total(wording.casefold()), total)
        self.assertIsNone(_fatal_total("Загинули двоє людей. Загинули троє людей."))
        self.assertEqual(card("Кількість загиблих зросла до трьох.")["claim_deaths"], 3)

    def test_uncertainty_and_separate_attacks_stay_blocked(self):
        for text in ("Ймовірно загинули двоє людей.",
                     "Загинули двоє людей, але це не підтверджено.",
                     "Ніхто не загинув."):
            self.assertIsNone(_fatal_total(text.casefold()))
        separate = ("Російська ракета атакувала Запоріжжя вранці 22 жовтня. "
                    "Загинули двоє людей. Також окремо атакували Запоріжжя увечері. "
                    "Загинули троє людей.")
        self.assertEqual(_fatal_issue(separate.casefold()), "MULTIPLE_POSSIBLE_INCIDENTS")
        self.assertEqual(extract_cached_reports([candidate()], [article(separate)]), [])

    def test_t05_unlinked_and_zero_auto_credits(self):
        official = {"articles": [], "receipts": [], "official_articles": [{
            "url": "https://zp.npu.gov.ua/synthetic",
            "text": "Унаслідок влучання загинули троє людей.",
            "response_sha256": "a" * 64}]}
        result = e.minimal_capture_facts(official, [candidate()])
        c = result["facts"][0]
        self.assertEqual(c["claim_deaths"], 3)
        self.assertIsNone(c["attack_date_explicit"])
        self.assertIsNone(c["candidate_id"])
        self.assertEqual(c["decision"], "NEEDS_REVIEW")
        self.assertEqual(result["official_incidents_automatically_matched"], 0)
        self.assertEqual(result["automatic_credits"], 0)

    def test_short_excerpts_privacy_and_no_html(self):
        c = card("Пізніше стало відомо, що загинула також 69-річна жінка.")
        runner.withhold_unsafe_excerpts(c)
        self.assertTrue(all(len(x["text"]) <= 170 for x in c["excerpts"]))
        self.assertFalse(any(k in c for k in ("body", "html", "text")))
        unsafe = card("Загинули двоє людей, повідомив свідок Петро Іваненко.")
        runner.withhold_unsafe_excerpts(unsafe)
        self.assertEqual(unsafe["excerpts"], [])

    def test_ci_launch_only_is_ignored_mixed_push_not_ignored(self):
        root = Path(__file__).resolve().parents[2]
        worko = (root / ".github/workflows/research-casualty-worko-offline.yml").read_text()
        workl = (root / ".github/workflows/research-casualty-workl-offline.yml").read_text()
        live = (root / ".github/workflows/research-casualty-workl-three-live-once.yml").read_text()
        launch = "research/casualty_one_time_capture_2026_11_13/launch.json"
        self.assertIn("paths-ignore:\n      - " + launch, worko)
        self.assertIn("paths-ignore:\n      - " + launch, workl)
        # For GitHub's push paths-ignore: skip iff every changed path is ignored.
        ignored = lambda changed: all(x == launch for x in changed)
        self.assertTrue(ignored([launch]))
        self.assertFalse(ignored([launch, "kyiv-air-alerts-grafana/scripts/casualty_auto_review.py"]))
        self.assertFalse(ignored(["research/casualty_parser_evidence_worko_2026_11_13/test_worko.py"]))
        self.assertIn("github.run_attempt == 1", live)
        self.assertIn("GITHUB_RUN_ATTEMPT", live)
        self.assertIn("validate_launch(launch,template,q)", live)
        self.assertIn("validate_one_launch_commit(launch,plan)", live)
        self.assertFalse((runner.HERE / "launch.json").exists())
        self.assertEqual(e.MODE_DEFAULT, "OFFLINE_REPLAY")


if __name__ == "__main__":
    unittest.main()
