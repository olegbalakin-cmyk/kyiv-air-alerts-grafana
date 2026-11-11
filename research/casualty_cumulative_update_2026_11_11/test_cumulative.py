#!/usr/bin/env python3
"""Immutable publisher-evidence and fail-closed cumulative-death-count regression."""
import csv
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kyiv-air-alerts-grafana/scripts"))
from casualty_auto_review import _fatal_total, _cumulative_total_update, extract_cached_reports, prepare, run_offline

CAPTURE = ROOT / "research/casualty_cumulative_update_2026_11_11/input/evidence.json"
SELECTED = ROOT / "research/casualty_three_new_http_2026_11_11/selected_queue.json"
LEDGER = ROOT / "research/casualty_real_evidence_2026_11_10/pinned_revisions.csv"
BASELINE = ROOT / "research/casualty_automated_review_2026_11_10/baseline_coverage.json"
EVIDENCE_SHA = "84ffea1315d41b8ec67b55a07273d6bbd7d6e8e14191801402168f7fddf4e5df"
ZAP_SHA = "011894b7c4bd906dcfd0c5d2f7cef07a932976ca313220fa9089999264feb259"
ZAP_ID = "e0fba98b19473874e9a1d8f1"
MILITARY_ID = "42f2a273f56c87e0bcd22af8"
KHARKIV_ID = "5e46ae290e43745fc4b827fa"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source():
    assert sha(CAPTURE) == EVIDENCE_SHA
    return json.loads(CAPTURE.read_text()), json.loads(SELECTED.read_text())


class CumulativeTests(unittest.TestCase):
    def test_real_zaporizhzhia_official_23_end_to_end(self):
        evidence, queue = source()
        a = next(x for x in evidence["articles"] if x["candidate_id"] == ZAP_ID)
        c = next(x for x in queue if x["candidate_id"] == ZAP_ID)
        self.assertEqual(hashlib.sha256(a["text"].encode()).hexdigest(), ZAP_SHA)
        self.assertEqual(c["city_key"], "zaporizhzhia")
        self.assertIn("За уточненими даними, 23 людини", a["text"])
        self.assertIn("До 20 людей зросла", a["text"])
        self.assertIn("18 загиблих", a["text"])
        reports = extract_cached_reports([c], [a])
        self.assertEqual(len(reports), 1)
        r = reports[0]
        self.assertEqual(r["count"], {"kind": "total", "value": 23})
        self.assertEqual(r["incident"]["city_key"], "zaporizhzhia")
        self.assertEqual(r["incident"]["attack_date"], "2026-10-10")
        self.assertEqual(r["incident"]["attack_slot"], "morning")
        self.assertEqual(r["incident"]["attack_type"], "guided-bomb")
        self.assertEqual(r["sources"][0]["origin_id"], "dsns")
        self.assertEqual(r["provenance"]["article_sha256"], ZAP_SHA)
        update = r["provenance"]["cumulative_update"]
        self.assertEqual(update["value"], 23)
        self.assertEqual(update["reported_totals"], [18, 20, 23])
        self.assertEqual(update["origin_id"], "dsns")
        out = prepare([c], [], reports, json.loads(BASELINE.read_text()))
        ev = out["events"][0]
        self.assertEqual(ev["confirmed_total_claim"], 23)
        self.assertEqual(ev["category"], "AUTO_READY", ev["reasons"])
        self.assertEqual(len(out["proposals"]), 1)
        self.assertEqual(out["proposals"][0]["deaths_delta"], "23")
        self.assertFalse(out["summary"]["publication_allowed"])

    def test_real_three_article_offline_replay_dedup_and_immutable(self):
        source()
        protected = [CAPTURE, SELECTED, LEDGER, BASELINE]
        before = {str(p): sha(p) for p in protected}
        with tempfile.TemporaryDirectory() as d:
            one, two = Path(d)/"first", Path(d)/"repeat"
            first = run_offline(SELECTED, LEDGER, CAPTURE, BASELINE, one)
            second = run_offline(SELECTED, LEDGER, CAPTURE, BASELINE, two, one/"proposals.csv")
            events = json.loads((one/"events.json").read_text())
            by_id = {m["candidate_id"]: e for e in events for m in e["messages"]}
            self.assertEqual(by_id[ZAP_ID]["category"], "AUTO_READY", by_id[ZAP_ID]["reasons"])
            self.assertEqual(by_id[MILITARY_ID]["category"], "NEEDS_REVIEW")
            self.assertIn("CIVILIAN_AMBIGUOUS", by_id[MILITARY_ID]["reasons"])
            self.assertEqual(by_id[KHARKIV_ID]["category"], "NEEDS_REVIEW")
            self.assertEqual(first["unique_proposals"], 1)
            self.assertEqual(second["unique_proposals"], 0)
            with (one/"proposals.csv").open() as f:
                proposals = list(csv.DictReader(f))
            with (two/"proposals.csv").open() as f:
                repeated = list(csv.DictReader(f))
            self.assertEqual(len(proposals), 1)
            self.assertEqual(proposals[0]["deaths_delta"], "23")
            self.assertEqual(proposals[0]["candidate_ids"], ZAP_ID)
            self.assertEqual(repeated, [])
            self.assertEqual(before, {str(p): sha(p) for p in protected})
            OUT = ROOT / "research/casualty_cumulative_update_2026_11_11/results"
            OUT.mkdir(parents=True, exist_ok=True)
            for name, value in [("first_events.json", events), ("first_summary.json", first),
                                ("repeat_summary.json", second), ("shadow_proposals.json", proposals)]:
                (OUT/name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+"\n")

    def test_same_event_does_not_add_all_again_if_already_counted(self):
        evidence, queue = source()
        c = next(x for x in queue if x["candidate_id"] == ZAP_ID)
        a = next(x for x in evidence["articles"] if x["candidate_id"] == ZAP_ID)
        r = extract_cached_reports([c], [a])
        base = json.loads(BASELINE.read_text())
        first = prepare([c], [], r, base)["proposals"][0]
        previous = {**first, "record_id": "already-counted-18", "deaths_delta": "18"}
        out = prepare([c], [previous], r, base)
        self.assertEqual(len(out["proposals"]), 1)
        self.assertEqual(out["proposals"][0]["deaths_delta"], "5")
        again = prepare([c], [previous, *out["proposals"]], r, base)
        self.assertEqual(again["proposals"], [])
        self.assertEqual(again["events"][0]["action"], "ALREADY_ACCOUNTED")

    def test_no_cross_attack_borrowing_even_same_city(self):
        text = ("Вранці 10 жовтня РФ атакувала Запоріжжя КАБами. "
                "У Запоріжжі загинули 18 людей. "
                "Також 11 жовтня російські війська атакували Запоріжжя КАБами. "
                "За уточненими даними, 23 людини загинули внаслідок другої атаки, повідомили в ДСНС.")
        self.assertIsNone(_fatal_total(text.casefold()))
        self.assertIsNone(_cumulative_total_update(text.casefold()))

    def test_explicit_later_official_downward_correction_not_max(self):
        text = ("Вранці 10 жовтня РФ атакувала Запоріжжя КАБами. "
                "Спочатку повідомляли, що загинули 23 людини. "
                "Пізніше ДСНС уточнили, що загинули 20 людей.")
        selection = _cumulative_total_update(text.casefold())
        self.assertIsNotNone(selection)
        self.assertEqual(selection["value"], 20)
        self.assertEqual(_fatal_total(text.casefold()), 20)

    def test_ambiguous_two_official_updates_held(self):
        text = ("Вранці 10 жовтня РФ атакувала Запоріжжя КАБами. "
                "За уточненими даними, 23 людини загинули, повідомили в ДСНС. "
                "За уточненими даними, 20 людей загинули, повідомили в ДСНС.")
        self.assertIsNone(_fatal_total(text.casefold()))

    def test_unexplained_count_not_assumed_earlier(self):
        text = ("Вранці 10 жовтня РФ атакувала Запоріжжя КАБами. "
                "Загинули 18 людей. За уточненими даними, загинули 23 людини, повідомили в ДСНС.")
        self.assertIsNone(_fatal_total(text.casefold()))

    def test_additional_deaths_not_cumulative_total(self):
        text = ("Вранці 10 жовтня РФ атакувала Запоріжжя КАБами. "
                "Спочатку загинули 18 людей. Згодом ще 5 людей загинули, повідомили в ДСНС.")
        self.assertIsNone(_fatal_total(text.casefold()))

    def test_prior_military_protection_still_applies(self):
        evidence, queue = source()
        c = next(x for x in queue if x["candidate_id"] == MILITARY_ID)
        a = next(x for x in evidence["articles"] if x["candidate_id"] == MILITARY_ID)
        out = prepare([c], [], extract_cached_reports([c], [a]), json.loads(BASELINE.read_text()))
        self.assertEqual(out["events"][0]["category"], "NEEDS_REVIEW")
        self.assertIn("CIVILIAN_AMBIGUOUS", out["events"][0]["reasons"])
        self.assertFalse(out["proposals"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
