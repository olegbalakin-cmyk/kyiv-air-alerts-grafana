#!/usr/bin/env python3
"""Offline only. The sole article input is the immutable prior HTTP artifact."""
import csv
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kyiv-air-alerts-grafana/scripts"))
from casualty_auto_review import (_attack_slot, _fatal_total, _incident_scopes,
                                  _origin_attribution, extract_cached_reports, prepare,
                                  run_offline)

EVIDENCE = ROOT / "research/casualty_attribution_2026_11_11/input/evidence.json"
ORIGINAL_SHA = "68ceccdcca68a0c93d42a0c0173c32c9ab47b659415e9bd2b274df8d9cf0fdf9"
SELECTED = ROOT / "research/casualty_five_candidate_selection_2026_11_11/selected_queue.json"
LEDGER = ROOT / "research/casualty_real_evidence_2026_11_10/pinned_revisions.csv"
BASELINE = ROOT / "research/casualty_automated_review_2026_11_10/baseline_coverage.json"
OUT = ROOT / "research/casualty_attribution_2026_11_11/results"

def source_data():
    assert hashlib.sha256(EVIDENCE.read_bytes()).hexdigest() == ORIGINAL_SHA
    return json.loads(EVIDENCE.read_text(encoding="utf-8"))

def synthetic_replay(text):
    queue = json.loads(SELECTED.read_text(encoding="utf-8"))
    c = next(c for c in queue if c["city_key"] == "dnipro")
    a = {"candidate_id": c["candidate_id"], "url": "https://suspilne.media/dnipro/test",
         "text": text, "observed_at": "2026-11-03"}
    reports = extract_cached_reports([c], [a])
    result = prepare([c], [], reports, {"dnipro": {"through": "2026-09-18"}})
    return reports, result


class AttributionTests(unittest.TestCase):
    def test_real_odesa_direct_city_mva(self):
        article = next(a for a in source_data()["articles"]
                       if a["candidate_id"] == "f4719e871b92e7563c7150da")
        self.assertIn("повідомив очільник Одеської міської військової адміністрації", article["text"])
        self.assertEqual(_origin_attribution(article["text"].casefold()),
                         ("city-mva", "Міська військова адміністрація"))

    def test_real_dnipro_is_still_unattributed(self):
        article = next(a for a in source_data()["articles"]
                       if a["candidate_id"] == "5d60e1c78026fdc494ea3c84")
        self.assertEqual(_origin_attribution(article["text"].casefold()), ("unattributed", None))

    def test_unrelated_police_or_prosecutor_mention_is_not_attribution(self):
        for line in (
            "У зведенні згадана поліція. Загинули двоє людей.",
            "Прокуратура також розташована у цьому районі. Загинули двоє людей.",
            "Міська військова адміністрація працює в будівлі. Загинули двоє людей.",
            "Повідомив журналіст. Поліція перебувала на місці.",
            "Очільник міської військової адміністрації прибув на місце події.",
        ):
            with self.subTest(line=line):
                self.assertEqual(_origin_attribution(line.casefold()), ("unattributed", None))

    def test_real_odesa_separates_three_attacks(self):
        article = next(a for a in source_data()["articles"]
                       if a["candidate_id"] == "f4719e871b92e7563c7150da")
        scopes = _incident_scopes(article["text"].casefold())
        self.assertEqual(len(scopes), 3)
        self.assertEqual(_fatal_total(scopes[0]), 1)
        self.assertIsNone(_fatal_total(scopes[1]))
        self.assertIsNone(_fatal_total(scopes[2]))
        self.assertEqual(_attack_slot(scopes[0]), "evening")
        self.assertNotRegex(scopes[0], r"житлов\w* будин|безпілотник|дрон|бпла")
        self.assertIn("північ одеської області", scopes[2])
        selected = json.loads(SELECTED.read_text(encoding="utf-8"))
        c = next(c for c in selected if c["candidate_id"] == article["candidate_id"])
        self.assertEqual(extract_cached_reports([c], [article]), [])

    def test_north_is_not_a_night_time_signal(self):
        self.assertIsNone(_attack_slot("атакували північ області"))
        self.assertIsNone(_attack_slot("на півночі одеської області"))
        self.assertIsNone(_attack_slot("у північній частині міста"))
        self.assertEqual(_attack_slot("вночі атакували місто"), "night")
        self.assertEqual(_attack_slot("нічний удар по місту"), "night")

    def test_single_unambiguous_attack_still_auto_ready_and_idempotent(self):
        text = ("Вранці 3 листопада РФ атакувала Дніпро ракетами. "
                "У Дніпрі загинули двоє людей. Про це повідомили в ДСНС.")
        reports, result = synthetic_replay(text)
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0]["incident"]["attack_type"], "missile")
        self.assertEqual(reports[0]["incident"]["attack_slot"], "morning")
        self.assertEqual(result["summary"]["auto_ready"], 1)
        self.assertEqual([p["deaths_delta"] for p in result["proposals"]], ["2"])
        queue = json.loads(SELECTED.read_text(encoding="utf-8"))
        c = next(c for c in queue if c["city_key"] == "dnipro")
        replay = prepare([c], [], reports, {"dnipro": {"through": "2026-09-18"}},
                         result["proposals"])
        self.assertEqual(replay["proposals"], [])
        self.assertEqual(replay["summary"]["prior_proposals_suppressed"], 1)

    def test_separate_nonfatal_attack_cannot_supply_weapon_or_place(self):
        text = ("Увечері 3 листопада РФ атакувала Дніпро. "
                "У Дніпрі загинули двоє людей. Про це повідомили в ДСНС. "
                "Також російські війська атакували північ області ударним дроном. "
                "Там пошкоджений житловий будинок, загиблих немає.")
        reports, result = synthetic_replay(text)
        self.assertEqual(reports, [])
        self.assertEqual(result["events"][0]["category"], "NEEDS_REVIEW")
        self.assertEqual(result["proposals"], [])

    def test_second_official_statement_not_borrowed(self):
        text = ("Вранці 3 листопада РФ атакувала Дніпро ракетами. "
                "У Дніпрі загинули двоє людей. "
                "Також російські війська атакували іншу громаду. "
                "Про це повідомили в ДСНС.")
        reports, result = synthetic_replay(text)
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0]["sources"][0]["origin_id"], "unattributed")
        self.assertEqual(result["events"][0]["category"], "NEEDS_REVIEW")
        self.assertEqual(result["proposals"], [])

    def test_multiple_fatal_attack_sections_are_held(self):
        text = ("Вранці 3 листопада РФ атакувала Дніпро ракетами. "
                "У Дніпрі загинули двоє людей. Повідомили в ДСНС. "
                "Також російські війська атакували Дніпро дронами. "
                "Унаслідок іншого удару загинули троє людей.")
        reports, result = synthetic_replay(text)
        self.assertEqual(reports, [])
        self.assertEqual(result["events"][0]["category"], "NEEDS_REVIEW")
        self.assertFalse(result["proposals"])

    def test_replay_preserves_input_and_records_outcome(self):
        evidence=source_data()
        before={str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in (EVIDENCE, SELECTED, LEDGER, BASELINE)}
        OUT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory() as tmp:
            first=Path(tmp)/"first"
            second=Path(tmp)/"second"
            summary=run_offline(SELECTED, LEDGER, EVIDENCE, BASELINE, first)
            replay=run_offline(SELECTED, LEDGER, EVIDENCE, BASELINE, second, first/"proposals.csv")
            with (first/"proposals.csv").open(newline="") as fp:
                proposals=list(csv.DictReader(fp))
            with (second/"proposals.csv").open(newline="") as fp:
                duplicates=list(csv.DictReader(fp))
            events=json.loads((first/"events.json").read_text())
            odesa=next(e for e in events if e["incident"]["city_key"]=="odesa")
            dnipro=next(e for e in events if e["incident"]["city_key"]=="dnipro")
            self.assertEqual(dnipro["reports"][0]["sources"][0]["origin_id"], "unattributed")
            self.assertEqual(odesa["category"], "NEEDS_REVIEW")
            self.assertFalse(odesa["reports"])
            self.assertIn("NO_CACHED_FACT_EVIDENCE_TITLE_IS_NOT_PROOF", odesa["reasons"])
            self.assertEqual(summary["auto_ready"], 0)
            self.assertEqual(len(proposals), 0)
            self.assertEqual(odesa["incident"], {"city_key": "odesa"})
            self.assertEqual(duplicates, [])
            self.assertEqual({str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                             for p in (EVIDENCE, SELECTED, LEDGER, BASELINE)},before)
            result={
                "before_auto_ready": 0,
                "after_auto_ready": summary["auto_ready"],
                "after_new_proposals": len(proposals),
                "replay_new_proposals": len(duplicates),
                "after_event_status": {e["incident"]["city_key"]: e["category"] for e in events
                                      if e["incident"]["city_key"] in ("dnipro","odesa")},
                "odesa_incident": odesa["incident"],
                "odesa_attribution": _origin_attribution(next(a["text"] for a in evidence["articles"]
                    if a["candidate_id"] == "f4719e871b92e7563c7150da").casefold())[0],
                "protected_inputs_unchanged": True,
                "publication_allowed": False,
                "proposals_for_offline_analysis_only": proposals,
            }
            (OUT/"verdict.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
            print("OFFLINE VERDICT",json.dumps(result,ensure_ascii=False))

if __name__=="__main__":
    unittest.main(verbosity=2)
