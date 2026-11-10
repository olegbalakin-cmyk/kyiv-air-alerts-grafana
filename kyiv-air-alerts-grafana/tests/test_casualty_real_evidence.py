"""Real retained news excerpts; facts must be inferred, not injected."""
import csv
import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kyiv-air-alerts-grafana/scripts"))
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
        cls.reports = extract_cached_reports(cls.queue, cls.articles)
        cls.baseline = json.loads((SCRIPT.parent.parent /
            "casualty_automated_review_2026_11_10/baseline_coverage.json").read_text())
        with (SCRIPT.parent/"pinned_revisions.csv").open(encoding="utf-8", newline="") as fh:
            cls.ledger = list(csv.DictReader(fh))

    def test_all_four_excerpts_hashed(self):
        self.assertEqual(len(self.articles), 4)
        for article in self.data["articles"]:
            self.assertTrue(proof.retained_text(article))

    def test_genuine_counts_extracted_without_prelabelled_facts(self):
        counts = {x["source_id"]: x["lexical_signals_only"]["death_total_mentions"]
                  for x in self.signals}
        self.assertEqual(counts, {"DN-SUSPILNE": [2], "DN-ARMYINFORM": [2],
                                  "OD-SUSPILNE": [3], "OD-LB": [3]})
        self.assertTrue(all(x["lexical_signals_only"]["civilian_status_explicit"] is None
                            for x in self.signals))

    def test_real_dated_casualties_presumed_and_supported(self):
        result = prepare(self.queue, self.ledger, self.reports, self.baseline)
        proposed = {row["city_key"]: int(row["deaths_delta"]) for row in result["proposals"]}
        self.assertEqual(proposed, {"dnipro": 2, "odesa": 3})
        ready = {e["incident"]["city_key"]: e for e in result["events"]
                 if e["category"] == "AUTO_READY"}
        self.assertEqual(set(ready), {"dnipro", "odesa"})
        for city, event in ready.items():
            self.assertEqual(event["civilian_status"], "civilian_presumed")
            self.assertGreaterEqual(len(event["reports"]), 1)
            self.assertEqual(event["already_accounted"], 0)
            self.assertTrue(any(s.get("contract") == "attributed-competent-official-v1"
                                for report in event["reports"] for s in report["sources"]))
        self.assertFalse(result["summary"]["publication_allowed"])

    def test_odesa_later_repeat_not_counted_twice(self):
        lb = next(x for x in self.signals if x["source_id"] == "OD-LB")
        self.assertTrue(lb["lexical_signals_only"]["separate_later_attack_mentioned"])
        out = prepare(self.queue, self.ledger, self.reports, self.baseline)
        self.assertEqual(sum(int(p["deaths_delta"]) for p in out["proposals"]), 5)
        odesa = [e for e in out["events"] if e["incident"].get("city_key") == "odesa"]
        self.assertEqual(sum(e["category"] == "AUTO_READY" for e in odesa), 1)

    def test_pending_replay_adds_no_deaths(self):
        first = prepare(self.queue, self.ledger, self.reports, self.baseline)
        replay = prepare(self.queue, self.ledger, self.reports, self.baseline,
                         previous_proposals=first["proposals"])
        self.assertEqual(replay["proposals"], [])
        self.assertEqual(replay["summary"]["prior_proposals_suppressed"], 2)

    def test_absent_primary_attribution_not_auto_ready(self):
        queue = [c for c in self.queue if "DN-SUSPILNE" in [
            s["source_id"] for s in self.data["articles"] if s["url"] == c["url"]]]
        articles = [a for a in self.articles if a["candidate_id"] == queue[0]["candidate_id"]]
        result = prepare(queue, self.ledger, extract_cached_reports(queue, articles), self.baseline)
        self.assertFalse(result["proposals"])


if __name__ == "__main__":
    unittest.main()
