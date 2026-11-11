#!/usr/bin/env python3
"""Offline-only military victim safety regression. Real article comes from pinned Actions artifact."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kyiv-air-alerts-grafana/scripts"))
from casualty_auto_review import _civilian_status, extract_cached_reports, prepare, run_offline

SOURCE = ROOT / "research/casualty_military_status_fix_2026_11_11/input"
CAPTURE = SOURCE / "evidence.json"
ZIP_SHA = "f7255cba58faea1ecb7defbe2cdbed40db2ddf05a5b92f5fe3530cead32f2148"
EVIDENCE_SHA = "84ffea1315d41b8ec67b55a07273d6bbd7d6e8e14191801402168f7fddf4e5df"
SELECTED = ROOT / "research/casualty_three_new_http_2026_11_11/selected_queue.json"
LEDGER = ROOT / "research/casualty_real_evidence_2026_11_10/pinned_revisions.csv"
BASELINE = ROOT / "research/casualty_automated_review_2026_11_10/baseline_coverage.json"
CID = "42f2a273f56c87e0bcd22af8"
BASE = {"dnipro": {"through": "2026-09-18"}}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def synthetic(text, suffix="only"):
    # An explicitly synthetic input with otherwise sufficient, dated, attributed proof.
    candidate = {
        "candidate_id": "SYNTHETIC-military-"+suffix, "city_key": "dnipro",
        "city": "Дніпро", "title": "Удар у Дніпрі", "snippet": "",
        "status": "needs_review", "url": "https://suspilne.media/dnipro/test",
        "publisher_url": "https://suspilne.media",
        "published_at": "2026-11-03T10:00:00Z"}
    article = {"candidate_id": candidate["candidate_id"],
               "url": "https://suspilne.media/dnipro/test", "text": text,
               "observed_at": "2026-11-03"}
    reports = extract_cached_reports([candidate], [article])
    return reports, prepare([candidate], [], reports, BASE)


PREFIX = "Вранці 3 листопада РФ атакувала Дніпро ракетами. У Дніпрі загинули двоє людей. "
OFFICIAL = "Про це повідомили в ДСНС."


class MilitaryStatusTests(unittest.TestCase):
    def test_real_retained_ivano_frankivsk_end_to_end(self):
        self.assertEqual(sha(CAPTURE), EVIDENCE_SHA)
        manifest = json.loads((SOURCE / "manifest.json").read_text())
        for filename, digest in manifest["sha256"].items():
            self.assertEqual(sha(SOURCE / filename), digest)
        original = json.loads(CAPTURE.read_text())
        row = next(x for x in json.loads(SELECTED.read_text()) if x["candidate_id"] == CID)
        article = next(x for x in original["articles"] if x["candidate_id"] == CID)
        self.assertEqual(row["city_key"], "ivano-frankivsk")
        self.assertIn("Загиблі - військовослужбовці", article["text"])
        self.assertEqual(hashlib.sha256(article["text"].encode()).hexdigest(),
                         "ce5dde16ff43e43f03a53ae0b39e637f068daa0bef31bb924a2f3f43a60d646d")
        reports = extract_cached_reports([row], [article])
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0]["count"]["value"], 3)
        self.assertEqual(reports[0]["civilian_status"], "civilian_ambiguous")
        self.assertIsNot(reports[0]["facts"]["civilian"], True)
        self.assertEqual(reports[0]["sources"][0]["origin_id"], "unattributed")
        with tempfile.TemporaryDirectory() as folder:
            # Full frozen three-article replay, but do NOT assert the known
            # unrelated Zaporizhzhia cumulative-update defect is repaired.
            out = Path(folder) / "first"
            again = Path(folder) / "repeat"
            before = {str(p): sha(p) for p in (CAPTURE, SELECTED, LEDGER, BASELINE)}
            run_offline(SELECTED, LEDGER, CAPTURE, BASELINE, out)
            run_offline(SELECTED, LEDGER, CAPTURE, BASELINE, again,
                        out / "proposals.csv")
            events = json.loads((out / "events.json").read_text())
            event = next(e for e in events if any(m.get("candidate_id") == CID
                         for m in e["messages"]))
            self.assertEqual(event["category"], "NEEDS_REVIEW")
            self.assertIn("CIVILIAN_AMBIGUOUS", event["reasons"])
            self.assertEqual(event["reports"][0]["civilian_status"], "civilian_ambiguous")
            self.assertIsNot(event["reports"][0]["facts"]["civilian"], True)
            self.assertFalse((out / "proposals.csv").read_text().strip().splitlines()[1:])
            self.assertFalse((again / "proposals.csv").read_text().strip().splitlines()[1:])
            self.assertEqual(before, {str(p): sha(p)
                                     for p in (CAPTURE, SELECTED, LEDGER, BASELINE)})

    def test_synthetic_official_military_only_blocks_independently(self):
        reports, result = synthetic(PREFIX + "Загиблі — військовослужбовці. " + OFFICIAL)
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0]["sources"][0]["origin_id"], "dsns")
        self.assertEqual(reports[0]["facts"]["city_boundary"], True)
        self.assertEqual(reports[0]["facts"]["russian_air_attack"], True)
        self.assertEqual(reports[0]["facts"]["death_count"], True)
        self.assertEqual(reports[0]["civilian_status"], "civilian_ambiguous")
        self.assertIsNone(reports[0]["facts"]["civilian"])
        self.assertEqual(result["events"][0]["category"], "NEEDS_REVIEW")
        self.assertIn("CIVILIAN_AMBIGUOUS", result["events"][0]["reasons"])
        self.assertNotIn("CIVILIAN_INSUFFICIENT_EVIDENCE", result["events"][0]["reasons"])
        self.assertFalse(result["proposals"])

    def test_positive_presumption_unchanged(self):
        reports, result = synthetic(PREFIX + OFFICIAL, "civilian")
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0]["civilian_status"], "civilian_presumed")
        self.assertIs(reports[0]["facts"]["civilian"], True)
        self.assertEqual(result["events"][0]["category"], "AUTO_READY")
        self.assertEqual(len(result["proposals"]), 1)
        self.assertEqual(result["proposals"][0]["deaths_delta"], "2")

    def test_wounded_military_does_not_override_deceased(self):
        reports, result = synthetic(PREFIX + "Поранені троє військовослужбовців. " + OFFICIAL)
        self.assertEqual(reports[0]["civilian_status"], "civilian_presumed")
        self.assertEqual(result["events"][0]["category"], "AUTO_READY")

    def test_military_status_denied(self):
        for wording in ("Загиблі — не військовослужбовці.",
                        "Військовослужбовці не загинули.",
                        "Серед загиблих немає військовослужбовців."):
            with self.subTest(wording=wording):
                reports, result = synthetic(PREFIX + wording + " " + OFFICIAL, "negation")
                self.assertEqual(reports[0]["civilian_status"], "civilian_presumed")
                self.assertEqual(result["events"][0]["category"], "AUTO_READY")

    def test_other_incident_military_injured_not_imported(self):
        text = (PREFIX + OFFICIAL + " Також російські військові атакували іншу громаду. "
                "Під час іншої атаки поранені військовослужбовці.")
        reports, result = synthetic(text, "other")
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0]["civilian_status"], "civilian_presumed")
        self.assertEqual(result["events"][0]["category"], "AUTO_READY")

    def test_mixed_victims_held(self):
        reports, result = synthetic(PREFIX + "Серед загиблих військовослужбовці. " + OFFICIAL,
                                    "mixed")
        self.assertEqual(reports[0]["civilian_status"], "civilian_ambiguous")
        self.assertEqual(result["events"][0]["category"], "NEEDS_REVIEW")
        self.assertFalse(result["proposals"])

    def test_explicit_variants_and_objects(self):
        for phrase in ("Загиблі - військовослужбовці.",
                       "Загиблі: військовослужбовці.",
                       "Серед загиблих військовослужбовці.",
                       "Загинули троє військовослужбовців.",
                       "Троє військовослужбовців загинули.",
                       "На військовий об’єкт припав удар."):
            with self.subTest(phrase=phrase):
                self.assertEqual(_civilian_status((PREFIX + phrase).casefold(), 2),
                                 "civilian_ambiguous")


if __name__ == "__main__":
    unittest.main(verbosity=2)
