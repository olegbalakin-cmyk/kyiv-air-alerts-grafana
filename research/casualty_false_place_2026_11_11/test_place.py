#!/usr/bin/env python3
"""Offline location-only regression over immutable publisher evidence."""
import csv
import hashlib
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kyiv-air-alerts-grafana/scripts"))
from casualty_auto_review import (
    _attack_place, _fatal_total, _incident_scopes,
    extract_cached_reports, prepare, run_offline,
)

THREE = ROOT / "research/casualty_false_place_2026_11_11/input/evidence.json"
SELECTED = ROOT / "research/casualty_three_new_http_2026_11_11/selected_queue.json"
LEDGER = ROOT / "research/casualty_real_evidence_2026_11_10/pinned_revisions.csv"
BASELINE = ROOT / "research/casualty_automated_review_2026_11_10/baseline_coverage.json"
OUT = ROOT / "research/casualty_false_place_2026_11_11/results"
EVIDENCE_SHA = "84ffea1315d41b8ec67b55a07273d6bbd7d6e8e14191801402168f7fddf4e5df"
IVANO_SHA = "ce5dde16ff43e43f03a53ae0b39e637f068daa0bef31bb924a2f3f43a60d646d"
IVANO = "42f2a273f56c87e0bcd22af8"
ZAP = "e0fba98b19473874e9a1d8f1"
KHARKIV = "5e46ae290e43745fc4b827fa"
BASE = {"dnipro": {"through": "2026-09-18"}}
PREFIX = "Вранці 3 листопада РФ атакувала Дніпро ракетами. "
DEATHS = "У Дніпрі загинули двоє людей. "
OFFICIAL = "Про це повідомили в ДСНС."


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def real():
    assert sha(THREE) == EVIDENCE_SHA
    manifest = json.loads((THREE.parent / "manifest.json").read_text(encoding="utf-8"))
    for name, expected in manifest["sha256"].items():
        assert sha(THREE.parent / name) == expected
    evidence = json.loads(THREE.read_text(encoding="utf-8"))
    queue = json.loads(SELECTED.read_text(encoding="utf-8"))
    return queue, evidence


def replay(text, *, candidate=None):
    c = candidate or {
        "candidate_id": "SYNTHETIC-place", "city_key": "dnipro",
        "city": "Дніпро", "title": "Удар у Дніпрі", "snippet": "",
        "status": "needs_review", "url": "https://suspilne.media/dnipro/test",
        "publisher_url": "https://suspilne.media",
        "published_at": "2026-11-03T10:00:00Z",
    }
    article = {
        "candidate_id": c["candidate_id"], "url": c["url"],
        "text": text, "observed_at": "2026-11-03",
    }
    reports = extract_cached_reports([c], [article])
    return reports, prepare([c], [], reports, BASE)


class FalsePlaceTests(unittest.TestCase):
    def test_real_ivano_retained_warning_not_attack_location(self):
        queue, evidence = real()
        c = next(c for c in queue if c["candidate_id"] == IVANO)
        a = next(a for a in evidence["articles"] if a["candidate_id"] == IVANO)
        self.assertEqual(hashlib.sha256(a["text"].encode()).hexdigest(), IVANO_SHA)
        scope = next(s for s in _incident_scopes(a["text"].casefold())
                     if _fatal_total(s) is not None)
        old_match = re.search(r"(?:за адресою|на вулиці)\s+([^.;\n]{3,65})", scope)
        self.assertIsNotNone(old_match, "Original defect must reproduce from original article")
        old_place = " ".join(old_match[1].split())
        self.assertIn("під час", old_place)
        reports = extract_cached_reports([c], [a])
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0]["incident"]["place"], "unlocated")
        self.assertEqual(reports[0]["count"]["value"], 3)
        self.assertEqual(reports[0]["civilian_status"], "civilian_ambiguous")
        self.assertIsNot(reports[0]["facts"]["civilian"], True)
        self.assertEqual(reports[0]["sources"][0]["origin_id"], "unattributed")
        result = prepare([c], [], reports, json.loads(BASELINE.read_text()))
        self.assertEqual(result["events"][0]["category"], "NEEDS_REVIEW")
        self.assertIn("CIVILIAN_AMBIGUOUS", result["events"][0]["reasons"])
        self.assertEqual(result["proposals"], [])
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "ivano_before_after.json").write_text(json.dumps({
            "candidate_id": IVANO, "article_sha256": IVANO_SHA,
            "old_place": old_place, "new_place": reports[0]["incident"]["place"],
            "civilian_status": reports[0]["civilian_status"],
            "review_status": result["events"][0]["category"],
            "reasons": result["events"][0]["reasons"],
            "civilian_proposals": len(result["proposals"]),
            "publication_allowed": False,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def test_real_three_source_replay_and_dedup(self):
        real()
        before = {str(p): sha(p) for p in (THREE, SELECTED, LEDGER, BASELINE)}
        with tempfile.TemporaryDirectory() as folder:
            first, repeat = Path(folder) / "first", Path(folder) / "repeat"
            a = run_offline(SELECTED, LEDGER, THREE, BASELINE, first)
            b = run_offline(SELECTED, LEDGER, THREE, BASELINE, repeat,
                            first / "proposals.csv")
            events = json.loads((first / "events.json").read_text())
            lookup = {m["candidate_id"]: e for e in events for m in e["messages"]}
            self.assertEqual(lookup[IVANO]["incident"]["place"], "unlocated")
            self.assertEqual(lookup[IVANO]["category"], "NEEDS_REVIEW")
            self.assertEqual(lookup[KHARKIV]["category"], "NEEDS_REVIEW")
            self.assertEqual(lookup[ZAP]["category"], "AUTO_READY")
            self.assertEqual(lookup[ZAP]["confirmed_total_claim"], 23)
            with (first / "proposals.csv").open(newline="") as stream:
                proposals = list(csv.DictReader(stream))
            with (repeat / "proposals.csv").open(newline="") as stream:
                duplicates = list(csv.DictReader(stream))
            self.assertEqual(len(proposals), 1)
            self.assertEqual(proposals[0]["candidate_ids"], ZAP)
            self.assertEqual(proposals[0]["deaths_delta"], "23")
            self.assertEqual(duplicates, [])
            self.assertEqual(a["unique_proposals"], 1)
            self.assertEqual(b["unique_proposals"], 0)
            self.assertEqual(before, {str(p): sha(p) for p in (THREE, SELECTED, LEDGER, BASELINE)})
            OUT.mkdir(parents=True, exist_ok=True)
            (OUT / "three_source_replay.json").write_text(json.dumps({
                "statuses": {k: lookup[k]["category"] for k in (IVANO, KHARKIV, ZAP)},
                "places": {k: lookup[k]["incident"].get("place") for k in (IVANO, KHARKIV, ZAP)},
                "zaporizhzhia_total": lookup[ZAP]["confirmed_total_claim"],
                "first_proposals": proposals, "repeat_proposals": duplicates,
                "protected_input_sha256_unchanged": True,
                "publication_allowed": False,
            }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def test_safety_warnings_alone_never_create_a_place(self):
        examples = (
            "Не перебувайте на вулиці під час тривоги.",
            'Не залишайтесь на вулиці під час сигналу "повітряна тривога".',
            "Перейдіть в укриття.",
            "Не підходьте до вікон.",
            "Мешканців Дніпра попередили про загальну небезпеку під час тривоги.",
            "Після удару мешканців закликають не перебувати на вулиці.",
            "Через небезпеку ударів радять не виходити на вулицю.",
            "На вулиці перебувати небезпечно через можливість обстрілів.",
        )
        for text in examples:
            with self.subTest(text=text):
                self.assertIsNone(_attack_place(text.casefold()))
                reports, out = replay(PREFIX + DEATHS + OFFICIAL + " " + text)
                self.assertEqual(len(reports), 1)
                self.assertEqual(reports[0]["incident"]["place"], "unlocated")
                self.assertEqual(out["events"][0]["category"], "AUTO_READY")
    
    def test_real_attack_street_address_building_and_object_still_recognized(self):
        cases = (
            ("Ракета влучила у будинок на вулиці Шевченка.", "шевченка"),
            ("На вулиці Незалежності пошкоджено будинок після удару.", "незалежності"),
            ("БпЛА завдав удару по вулиці Героїв УПА.", "героїв упа"),
            ("Ракета влучила у будівлю за адресою Галицька 15.", "галицька 15"),
            ("Ракета влучила у житловий будинок.", "residential-buildings"),
            ("Під час удару пошкоджений склад харчових продуктів.", "food-warehouse"),
            ("Унаслідок удару пошкоджено інфраструктурний об'єкт.", "infrastructure-object"),
        )
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(_attack_place(text.casefold()), expected)
                reports, result = replay(PREFIX + text + " " + DEATHS + OFFICIAL)
                self.assertEqual(len(reports), 1)
                self.assertEqual(reports[0]["incident"]["place"], expected)
                self.assertEqual(result["events"][0]["category"], "AUTO_READY")

    def test_location_of_second_nonfatal_attack_not_donated(self):
        text = (PREFIX + DEATHS + OFFICIAL + " "
                "Також російські війська атакували іншу громаду. "
                "Безпілотник влучив у будинок на вулиці Шевченка, загиблих немає.")
        reports, out = replay(text)
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0]["incident"]["place"], "unlocated")
        self.assertEqual(reports[0]["incident"]["attack_type"], "missile")
        self.assertEqual(out["events"][0]["category"], "AUTO_READY")

    def test_place_of_first_nonfatal_attack_not_donated_to_second(self):
        text = ("Вранці 3 листопада РФ атакувала Дніпро ракетами. "
                "Ракета влучила у будинок на вулиці Шевченка, загиблих немає. "
                "Також увечері 3 листопада РФ атакувала Дніпро дронами. "
                "У Дніпрі загинули троє людей. Про це повідомили в ДСНС.")
        reports, result = replay(text)
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0]["incident"]["place"], "unlocated")
        self.assertEqual(reports[0]["incident"]["attack_type"], "drone")
        self.assertEqual(reports[0]["count"]["value"], 3)
        self.assertEqual(result["events"][0]["category"], "AUTO_READY")

    def test_explicit_other_strike_without_narrative_delimiter_not_borrowed(self):
        text = (PREFIX + DEATHS + OFFICIAL +
                " Другий удар припав на вулицю Шевченка, але минув без жертв.")
        reports, _ = replay(text)
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0]["incident"]["place"], "unlocated")

    def test_place_does_not_override_missing_attack_date(self):
        text = ("РФ атакувала Дніпро ракетами. "
                "Ракета влучила у будинок на вулиці Шевченка. " + DEATHS + OFFICIAL)
        reports, out = replay(text)
        self.assertEqual(reports, [])
        self.assertEqual(out["events"][0]["category"], "NEEDS_REVIEW")
        self.assertEqual(out["proposals"], [])

    def test_place_does_not_override_city_boundary(self):
        text = ("Вранці 3 листопада РФ атакувала передмістя Дніпра ракетами. "
                "Ракета влучила у будинок на вулиці Шевченка. " + DEATHS + OFFICIAL)
        reports, out = replay(text)
        self.assertEqual(reports, [])
        self.assertEqual(out["events"][0]["category"], "NEEDS_REVIEW")
        self.assertEqual(out["proposals"], [])

    def test_place_does_not_override_missing_air_weapon(self):
        text = ("Вранці 3 листопада РФ атакувала Дніпро. "
                "Удар припав на вулицю Шевченка. " + DEATHS + OFFICIAL)
        reports, out = replay(text)
        self.assertEqual(reports, [])
        self.assertEqual(out["events"][0]["category"], "NEEDS_REVIEW")
        self.assertEqual(out["proposals"], [])

    def test_place_does_not_override_military_civilian_guard(self):
        text = (PREFIX + "Ракета влучила у будинок на вулиці Шевченка. " +
                DEATHS + "Загиблі — військовослужбовці. " + OFFICIAL)
        reports, out = replay(text)
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0]["incident"]["place"], "шевченка")
        self.assertEqual(reports[0]["civilian_status"], "civilian_ambiguous")
        self.assertEqual(out["events"][0]["category"], "NEEDS_REVIEW")
        self.assertIn("CIVILIAN_AMBIGUOUS", out["events"][0]["reasons"])
        self.assertEqual(out["proposals"], [])

    def test_place_does_not_override_official_attribution(self):
        text = PREFIX + "Ракета влучила у будинок на вулиці Шевченка. " + DEATHS
        reports, out = replay(text)
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0]["incident"]["place"], "шевченка")
        self.assertEqual(reports[0]["sources"][0]["origin_id"], "unattributed")
        self.assertEqual(out["events"][0]["category"], "NEEDS_REVIEW")
        self.assertEqual(out["proposals"], [])

    def test_place_does_not_override_missing_fatal_total(self):
        text = PREFIX + "Ракета влучила у будинок на вулиці Шевченка. Постраждала одна людина. " + OFFICIAL
        reports, out = replay(text)
        self.assertEqual(reports, [])
        self.assertEqual(out["events"][0]["category"], "NEEDS_REVIEW")
        self.assertEqual(out["proposals"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
