#!/usr/bin/env python3
"""Issue 247 read-only October evidence guard. No network or production writes."""
import csv
import hashlib
import json
import re
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LEDGER = ROOT / "october_next_incident_ledger.json"
DECISIONS = ROOT / "october_next_credit_decisions.csv"
PR236 = ROOT / "october_2026_verified_event_candidates.json"
PR235 = ROOT / "incident_reconciliation_2026_10.csv"

class OctoberNextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
        with DECISIONS.open(encoding="utf-8", newline="") as f:
            cls.csv = list(csv.DictReader(f))
        with PR235.open(encoding="utf-8", newline="") as f:
            cls.pr235 = list(csv.DictReader(f))
        cls.pr236 = json.loads(PR236.read_text(encoding="utf-8"))

    def test_offline_fail_closed(self):
        d = self.ledger
        self.assertEqual(d["promotion"], "OFF")
        self.assertIs(d["publication_allowed"], False)
        self.assertIs(d["read_only"], True)
        self.assertIs(d["no_publisher_get"], True)
        self.assertFalse(d["totals"]["is_monthly_total"])
        self.assertTrue(d["totals"]["unknown_not_zero"])

    def test_immutable_receipts(self):
        p = self.ledger["pins"]
        self.assertEqual(p["pr235_head"], "17291da5ab7a682eabc1b9458685b2a2724b3d71")
        self.assertEqual(p["pr236_head"], "270702ccc4a76d81ee8cc5b9cf73059fd19df025")
        self.assertEqual(p["capture_zip_sha256"], "f2a95945e98dc92cdc49529be2bb127a5d4c3fe8a9e71ad82ebf2437b7c2eb9f")
        self.assertEqual(p["capture_report_sha256"], "be053f77ade09db833eb976a67a6bcb036fb42cff1c98f81bfd90dde1fbe7ed8")
        self.assertEqual(p["site_prod_revisions_blob_sha"], "8d7a2e2540bf4bf0f8c6227023821390bf82ce13")
        self.assertEqual(p["site_prod_review_queue_blob_sha"], "8ae078bc60f2c27838b61e9aebf90b7286e0dd55")

    def test_source_hashes_and_references(self):
        sources = self.ledger["sources"]
        for identifier, src in sources.items():
            self.assertRegex(identifier, r"^(q[0-9]+|s[0-9]+)$")
            self.assertRegex(src["sha256"], r"^[0-9a-f]{64}$")
            self.assertTrue(src["url"].startswith("https://"))
            self.assertFalse(src["full_html_archived"])
        for event in self.ledger["subincidents"]:
            self.assertGreaterEqual(len(set(event["source_ids"])), 2)
            self.assertTrue(set(event["source_ids"]) <= set(sources))
        self.assertEqual({s for s in sources if s.startswith("s")}, {"s10", "s11"})

    def test_13_groups_exact_consistency(self):
        d = self.ledger
        self.assertEqual(len(d["decisions"]), 13)
        self.assertEqual({x["candidate_group_id"] for x in d["decisions"]},
                         {x["incident_key"] for x in self.pr235})
        self.assertEqual(len(self.csv), 13)
        for row in self.csv:
            x = next(x for x in d["decisions"] if x["candidate_group_id"] == row["candidate_group_id"])
            for k, v in row.items():
                self.assertEqual(v, "" if x[k] is None else str(x[k]))

    def test_prior_four_exact_not_recredited(self):
        d = self.ledger
        expected = {"lutsk": 6, "poltava": 1, "ivano-frankivsk": 1, "khmelnytskyi": 3}
        self.assertEqual(d["already_verified_by_pr236"], expected)
        self.assertEqual({x["city_slug"]: x["civilian_deaths_cumulative"] for x in self.pr236["events"]}, expected)
        old = [x for x in d["decisions"] if x["decision"] == "ALREADY_APPROVED_DO_NOT_RECOUNT"]
        self.assertEqual(len(old), 4)
        self.assertEqual(sum(x["preapproved_minimum"] for x in old), 11)
        self.assertTrue(all(x["new_verified_minimum"] == 0 for x in old))

    def test_six_distinct_subincidents_without_duplicates(self):
        events = self.ledger["subincidents"]
        self.assertEqual(len(events), 6)
        self.assertEqual(len({x["incident_id"] for x in events}), 6)
        self.assertTrue(all(x["city_slug"] == "kyiv" and x["victim_identity_and_dedup"] for x in events))
        self.assertTrue(all(x["baseline_credited"] == 0 for x in events))
        groups = Counter()
        for x in events:
            groups[x["candidate_group_id"]] += x["civilian_fatality_minimum"]
        self.assertEqual(dict(groups), {
            "KYIV-2026-10-07-BALLISTIC": 2,
            "KYIV-2026-10-07-EVENING-UAV": 4,
            "KYIV-2026-10-08-MORNING-UAV": 4,
            "KYIV-2026-10-20-UAV": 1,
        })
        self.assertEqual(sum(groups.values()), 11)
        self.assertEqual(len([x for x in events if x["attack_date"] == "2026-10-07"]), 3)
        self.assertEqual(len([x for x in events if x["attack_date"] == "2026-10-08"]), 2)
        self.assertEqual(len([x for x in events if x["attack_date"] == "2026-10-20"]), 1)

    def test_kyiv_day_chronology_and_attribution(self):
        d = self.ledger
        ev = d["subincidents"]
        by_day = Counter()
        for x in ev:
            by_day[x["attack_date"]] += x["civilian_fatality_minimum"]
        self.assertEqual(dict(by_day), {
            "2026-10-07": 6, "2026-10-08": 4, "2026-10-20": 1
        })
        self.assertEqual(d["sources"]["q69"]["sha256"], "32367854f1ecffa318fab0a5b64195f94daec65d26017dd3bcb59ef960068812")
        self.assertEqual(d["sources"]["q65"]["sha256"], "40fbcdd4bf77f19648804352e5dfee3582283ea3ea9ea4f35317ccd6a14cb679")
        self.assertTrue(any("Chabany" in x["evidence_summary"] for x in d["sources"].values()))
        self.assertNotIn("chabany", [x["district"] for x in ev])

    def test_unresolved_cases_not_credited(self):
        held = [x for x in self.ledger["decisions"] if x["decision"] == "HELD_NEEDS_SOURCE"]
        self.assertEqual(len(held), 5)
        self.assertEqual({x["city_slug"] for x in held},
                         {"dnipro", "zaporizhzhia", "kropyvnytskyi", "chernihiv", "kherson"})
        self.assertTrue(all(x["new_verified_minimum"] is None and x["missing_source"] for x in held))
        self.assertTrue(all(x["baseline_credited"] == 0 for x in held))

    def test_september_baseline_not_overwritten(self):
        self.assertEqual(self.ledger["baseline"]["october_city_rows_in_site_prod"], 0)
        self.assertEqual(self.ledger["baseline"]["october_confirmed_revisions_in_site_prod"], 0)
        self.assertEqual(self.ledger["baseline"]["new_events_baseline_credited"], 0)
        self.assertEqual(self.ledger["baseline"]["october_for_other_cities"], "UNKNOWN_NOT_ZERO")
        self.assertEqual(self.ledger["totals"]["combined_distinct_event_minimum"], 22)

    def test_twelve_source_hashes_not_content_proof(self):
        self.assertEqual(len(self.ledger["sources"]), 12)
        self.assertIn("not full archived publisher HTML", self.ledger["source_limitation"])
        self.assertFalse(self.ledger["publication_allowed"])

if __name__ == "__main__":
    unittest.main(verbosity=2)
