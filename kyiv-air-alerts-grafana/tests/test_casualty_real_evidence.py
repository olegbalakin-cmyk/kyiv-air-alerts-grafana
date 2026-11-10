"""Targeted regression on four real, hashed article excerpts; no live reads/writes."""
import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "research/casualty_real_evidence_2026_11_10/reproduce.py"
spec = importlib.util.spec_from_file_location("casualty_real_excerpt_proof", SCRIPT)
proof = importlib.util.module_from_spec(spec)
spec.loader.exec_module(proof)
from casualty_auto_review import extract_cached_reports, prepare


class RealExcerptSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((SCRIPT.parent / "sources.json").read_text(encoding="utf-8"))
        cls.queue, cls.articles, cls.signals = proof.shadow_inputs(cls.data)

    def test_all_four_excerpts_hashed(self):
        self.assertEqual(len(self.articles), 4)
        for article in self.data["articles"]:
            self.assertEqual(len(article["excerpt_sha256"]), 64)
            self.assertTrue(proof.retained_text(article))

    def test_genuine_count_mentions_extracted_without_prelabelled_facts(self):
        counts = {x["source_id"]: x["lexical_signals_only"]["death_total_mentions"]
                  for x in self.signals}
        self.assertEqual(counts, {"DN-SUSPILNE": [2], "DN-ARMYINFORM": [2],
                                  "OD-SUSPILNE": [3], "OD-LB": [3]})
        self.assertTrue(all(x["lexical_signals_only"]["civilian_status_explicit"] is None
                            for x in self.signals))

    def test_later_odesa_attack_is_detected_not_added_as_deaths(self):
        lb = next(x for x in self.signals if x["source_id"] == "OD-LB")
        self.assertTrue(lb["lexical_signals_only"]["separate_later_attack_mentioned"])
        self.assertEqual(lb["lexical_signals_only"]["death_total_mentions"], [3])

    def test_current_reviewer_fail_closed_on_real_excerpts(self):
        reports = extract_cached_reports(self.queue, self.articles)
        self.assertEqual(reports, [])
        baseline = json.loads((SCRIPT.parent.parent /
                               "casualty_automated_review_2026_11_10/baseline_coverage.json").read_text())
        result = prepare(self.queue, [], reports, baseline)
        self.assertEqual(result["summary"]["needs_review"], 4)
        self.assertEqual(result["summary"]["unique_proposals"], 0)
        self.assertTrue(all(e["category"] == "NEEDS_REVIEW" for e in result["events"]))


if __name__ == "__main__":
    unittest.main()
