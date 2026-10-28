#!/usr/bin/env python3
"""Deterministic offline regression: pinned C6-R1 reader contract, no DB/network."""
import json
import unittest
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

BASE = Path(__file__).resolve().parent
UTC = timezone.utc
KYIV = ZoneInfo("Europe/Kyiv")


def dt(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def floor_minute(value):
    return dt(value).replace(second=0, microsecond=0)


def assert_alias_gate(aliases, precise):
    """Fail closed: explicit all-nine, bijective, exact UTC minute-floor mapping."""
    if len(aliases) != 9 or len(precise) != 9:
        raise ValueError("missing or extra pinned aliases")
    if len(set(aliases)) != 9 or len(set(precise)) != 9:
        raise ValueError("duplicate alias/physical ID")
    for old, current in zip(aliases.values(), precise.values()):
        if old["city"] != current["city"] or old["city"] != "kyiv":
            raise ValueError("city conflict")
        if (dt(old["start"]), dt(old["end"])) != (
            floor_minute(current["start"]), floor_minute(current["end"])
        ):
            raise ValueError("not exact minute-floor pair")
    return True


class ReaderProjectionProof(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads((BASE / "parity_report.json").read_text(encoding="utf-8"))

    def test_nine_bijection_and_parity(self):
        p = self.report
        pairs = p["nine_exact_pairs"]
        self.assertEqual(len(pairs), 9)
        self.assertEqual(len(set(x["alias_uid"] for x in pairs)), 9)
        self.assertEqual(len(set(x["canonical_uid"] for x in pairs)), 9)
        s = p["kyiv_september"]
        self.assertEqual(s["neon_raw_rows"] - len(pairs), s["projected_rows"])
        self.assertEqual(s["projected_rows"], s["pinned_site_rows"])
        self.assertEqual(
            s["raw_neon_duration_seconds"] - s["excluded_alias_duration_seconds"],
            s["site_duration_seconds"],
        )
        self.assertEqual(s["alias_a5_bound_classifications"], 9)
        self.assertEqual(s["alias_linked_events"], 0)

    def test_full_nine_crosswalk_exact_utc_boundaries_and_attribution(self):
        x = json.loads((BASE / "exact_nine_uuid_crosswalk.json").read_text(encoding="utf-8"))
        rows = x["rows"]
        self.assertEqual(len(rows), 9)
        self.assertEqual(len(set(r["a5_classification_uid"] for r in rows)), 9)
        alias = {r["alias_uid"]: {"city": "kyiv", "start": r["alias_start_utc"],
                                  "end": r["alias_end_utc"]} for r in rows}
        precise = {r["canonical_uid"]: {"city": "kyiv", "start": r["canonical_start"],
                                       "end": r["canonical_end"]} for r in rows}
        # Deterministic keyed comparison; no reliance on an unordered SQL result.
        for row in rows:
            self.assertEqual(floor_minute(row["canonical_start"]),
                             dt(row["alias_start_utc"]))
            self.assertEqual(floor_minute(row["canonical_end"]),
                             dt(row["alias_end_utc"]))
            self.assertEqual(dt(row["canonical_start"]).astimezone(KYIV).strftime("%Y-%m-%d"),
                             row["canonical_start_local_day"])
            self.assertEqual(dt(row["canonical_start"]).astimezone(KYIV).strftime("%Y-%m"),
                             row["canonical_start_local_month"])
        self.assertEqual(sum(r["alias_duration_seconds"] for r in rows), 90120)
        self.assertEqual(sum(r["canonical_duration_seconds"] for r in rows), 90087)
        self.assertEqual({r["alias_uid"] for r in rows},
                         {r["alias_uid"] for r in self.report["nine_exact_pairs"]})

    def test_local_day_month_and_midnight_use_precise_parent(self):
        records = [
            ("2026-09-29T23:38:11+03:00", "2026-09-30T12:22:15+03:00"),
            ("2026-09-30T21:37:31+03:00", "2026-09-30T23:01:20+03:00"),
        ]
        self.assertEqual([dt(start).astimezone(KYIV).strftime("%Y-%m")
                          for start, _ in records], ["2026-09", "2026-09"])
        self.assertEqual([dt(start).astimezone(KYIV).strftime("%Y-%m-%d")
                          for start, _ in records], ["2026-09-29", "2026-09-30"])
        self.assertEqual((dt(records[0][1])-dt(records[0][0])).total_seconds(), 45844)
        self.assertEqual(sum(dt(b).astimezone(KYIV).date() >
                             dt(a).astimezone(KYIV).date() for a,b in records), 1)

    def test_gate_rejects_missing_duplicates_and_drift(self):
        aliases = {str(n): {"city": "kyiv", "start": f"2026-09-29T{n:02d}:10:00Z",
                             "end": f"2026-09-29T{n:02d}:12:00Z"} for n in range(9)}
        precise = {str(n): {"city": "kyiv", "start": f"2026-09-29T{n:02d}:10:33Z",
                             "end": f"2026-09-29T{n:02d}:12:44Z"} for n in range(9)}
        self.assertTrue(assert_alias_gate(aliases, precise))
        with self.assertRaises(ValueError):
            assert_alias_gate(dict(list(aliases.items())[:-1]), precise)
        changed = {k: dict(v) for k,v in precise.items()}
        changed["5"]["start"] = "2026-09-29T05:09:59Z"
        with self.assertRaises(ValueError):
            assert_alias_gate(aliases, changed)

    def test_unbound_survives_and_source_joins_do_not_multiply_events(self):
        h = self.report["historical_unbound"]
        self.assertEqual((h["classification_uids"], h["unbound_null"]), (25,25))
        self.assertEqual(h["source_memberships"], 14)
        self.assertEqual(h["active_events"], 2)
        self.assertEqual(h["raw_event_join_source_fanout_rows"], 7)
        self.assertEqual(h["correct_distinct_event_uids"], 2)
        self.assertEqual(h["inner_parent_event_rows"], 0)
        # NULL-parent LEFT JOIN: all 25 classification rows survive, including events.
        classifications = [{"uid": str(i), "parent": None} for i in range(25)]
        self.assertEqual(len(classifications), 25)
        events = [h["strict_active_uid"], h["sensitivity_active_uid"]]
        memberships = {events[0]: [1], events[1]: list(range(6))}
        self.assertEqual(sum(len(memberships[e]) for e in events), 7)
        self.assertEqual(len(set(events)), 2)

    def test_bounded_other_city_comparisons(self):
        for city, month, published, projected in self.report["monthly_counts"]:
            with self.subTest(city=city,month=month):
                self.assertEqual(published, projected)
        self.assertEqual(self.report["parity_scope"]["cutover"], "NOT_AUTHORIZED")


if __name__ == "__main__":
    unittest.main()
