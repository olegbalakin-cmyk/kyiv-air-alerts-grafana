"""Kyiv September–October benchmark is RESEARCH ONLY, no network or writes."""
import csv
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).parent


def rows(filename):
    with (ROOT / filename).open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


class MonthReconciliation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = json.loads((ROOT / "monthly_benchmarks.json").read_text(encoding="utf-8"))
        cls.days = rows("daily_coverage_spine.csv")
        cls.sources = rows("indexed_source_leads.csv")

    def test_all_days_present_not_zeroed(self):
        self.assertEqual(len(self.days), 61)
        self.assertEqual(len({x["date"] for x in self.days}), 61)
        self.assertEqual(sum(d["month"] == "2026-09" for d in self.days), 30)
        self.assertEqual(sum(d["month"] == "2026-10" for d in self.days), 31)
        self.assertTrue(all(d["day_closed"] == "NO" and
                            d["exact_air_attack_daily_deaths"] == "" and
                            d["safe_new_credit"] == "0" for d in self.days))

    def test_monthly_un_metrics_not_promoted(self):
        self.assertEqual([m["verified_minimum_killed"] for m in
                          self.doc["ohchr_benchmarks"]], [32, 25])
        self.assertFalse(self.doc["publication_allowed"])
        self.assertEqual(self.doc["PROMOTE"], "OFF")
        self.assertFalse(self.doc["month_complete_verified"])
        self.assertEqual(self.doc["newly_authorized_credits"], 0)
        self.assertTrue(all(not m["verified_month_complete_for_our_site"] and
                            m["direct_site_scope_parity"] == "UNVERIFIED"
                            for m in self.doc["ohchr_benchmarks"]))

    def test_prior_and_new_candidate_counts_remain_uncredited(self):
        by_day = {d["date"]: d for d in self.days}
        self.assertEqual(sum(int(d["research_held_proposed_delta"] or 0)
                             for d in self.days if d["month"] == "2026-09"), 15)
        self.assertEqual(sum(int(d["research_held_proposed_delta"] or 0)
                             for d in self.days if d["month"] == "2026-10"), 11)
        self.assertEqual([int(by_day[x]["additional_indexed_official_event_minimum"])
                          for x in ("2026-10-13", "2026-10-21", "2026-10-19", "2026-10-26")], [5, 2, 1, 1])
        self.assertEqual(self.doc["research_proposals"]["september"]["published_partial_baseline"], 18)
        self.assertEqual(self.doc["research_proposals"]["october"]["arithmetic_research_only_11_plus_5_plus_2_plus_1_plus_1"], 20)

    def test_leads_are_indexed_not_archived(self):
        self.assertEqual(len(self.sources), 9)
        self.assertTrue(all(s["url"].startswith("https://") for s in self.sources))
        self.assertEqual(self.doc["body_captures_performed"], 0)
        self.assertEqual(self.doc["netlify_deploys"], 0)
        self.assertTrue(any(s["id"] == "OCT13-POLICE-FINAL" and
                            s["reported_deaths"] == "5" for s in self.sources))
        self.assertTrue(any(s["id"] == "OCT21-CITY" and
                            s["reported_deaths"] == "2" for s in self.sources))

    def test_prior_month_window_is_not_daily_proof(self):
        baseline = [d for d in self.days if "PARTIAL_BASELINE_THROUGH" in d["baseline_window"]]
        self.assertEqual(len(baseline), 15)
        self.assertEqual(baseline[0]["date"], "2026-09-01")
        self.assertEqual(baseline[-1]["date"], "2026-09-15")


if __name__ == "__main__":
    unittest.main()
