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
from casualty_auto_review import _origin_attribution, extract_cached_reports, run_offline

EVIDENCE = ROOT / "research/casualty_attribution_2026_11_11/input/evidence.json"
ORIGINAL_SHA = "68ceccdcca68a0c93d42a0c0173c32c9ab47b659415e9bd2b274df8d9cf0fdf9"
SELECTED = ROOT / "research/casualty_five_candidate_selection_2026_11_11/selected_queue.json"
LEDGER = ROOT / "research/casualty_real_evidence_2026_11_10/pinned_revisions.csv"
BASELINE = ROOT / "research/casualty_automated_review_2026_11_10/baseline_coverage.json"
OUT = ROOT / "research/casualty_attribution_2026_11_11/results"

def source_data():
    assert hashlib.sha256(EVIDENCE.read_bytes()).hexdigest() == ORIGINAL_SHA
    return json.loads(EVIDENCE.read_text(encoding="utf-8"))

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
            self.assertEqual(odesa["reports"][0]["sources"][0]["origin_id"], "city-mva")
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
                "odesa_attribution": odesa["reports"][0]["sources"][0]["origin_id"],
                "protected_inputs_unchanged": True,
                "publication_allowed": False,
                "proposals_for_offline_analysis_only": proposals,
            }
            (OUT/"verdict.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
            print("OFFLINE VERDICT",json.dumps(result,ensure_ascii=False))

if __name__=="__main__":
    unittest.main(verbosity=2)
