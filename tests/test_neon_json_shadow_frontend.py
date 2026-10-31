#!/usr/bin/env python3
"""Offline fail-closed contract tests. No Neon, upstream HTTP or Actions."""
from __future__ import annotations
import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from scripts import neon_json_shadow as shadow


class ShadowOfflineContracts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.site = self.root / "site"
        (self.site / "data").mkdir(parents=True)
        self.keys = ["city%02d" % i for i in range(23)]
        self.episodes = [
            {"city_key": city, "legacy_episode_id": "legacy_" + city,
             "alert_type": "AIR", "episode_state": "closed",
             "canonicalization_version": shadow.VERSION,
             "start_at": "2026-10-01T01:00:00Z",
             "end_at": "2026-10-01T02:00:00Z"}
            for city in self.keys
        ]
        self.receipt = {
            "status": "succeeded", "workflow_sha": "a"*40, "input_sha": "b"*40,
            "corpus_sha256": "", "canonical_episode_count": 23,
            "db_branch": "br-c2", "city_count": 23, "run_id": "run-1"
        }
        self.status = {
            "canonical_persistence_status": "NEON_SUCCEEDED",
            "canonical_receipt_validated": True, "canonical_db_commit": "CONFIRMED",
            "workflow_sha": self.receipt["workflow_sha"],
            "input_sha": self.receipt["input_sha"]
        }
        payload = {
            "format": "multicity-canonical-same-run-v1",
            "canonicalization_version": shadow.VERSION,
            "cities": {city: {"episode_count": 1, "episodes": [self.episodes[i]]}
                       for i,city in enumerate(self.keys)}
        }
        dashboard = {"multicity_meta": {"production_city_keys": self.keys}}
        serial = {"canonicalization_version": shadow.VERSION,
                  "production_city_keys": self.keys, "episodes": self.episodes}
        self.receipt["corpus_sha256"] = hashlib.sha256(json.dumps(
            serial, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False).encode()).hexdigest()
        self.paths = {}
        for name, value in (("status", self.status), ("payload", payload),
                            ("dashboard", dashboard), ("receipt", self.receipt)):
            self.paths[name] = self.root / (name + ".json")
            self.paths[name].write_text(json.dumps(value), encoding="utf-8")

    def verify(self, **override):
        args = dict(site=self.site, receipt_path=self.paths["receipt"],
                    status_path=self.paths["status"], payload_path=self.paths["payload"],
                    dashboard_path=self.paths["dashboard"], verifier=lambda p: self.receipt)
        args.update(override)
        return shadow.verified_inputs(**args)

    def execute(self, **override):
        args = dict(site=self.site, receipt_path=self.paths["receipt"],
                    status_path=self.paths["status"], payload_path=self.paths["payload"],
                    dashboard_path=self.paths["dashboard"], verifier=lambda p: self.receipt,
                    output=self.root / "shadow", database_url="postgresql://ro:secret@ep-a.neon.tech/neondb",
                    writer_database_url="postgresql://writer:secret@ep-b.neon.tech/neondb",
                    expected_branch="br-c2", workflow_sha="a"*40, input_sha="b"*40)
        args.update(override)
        return shadow.execute(**args)

    def test_23city_corpus_checksum_pass(self):
        receipt, keys, rows = self.verify()
        self.assertEqual(len(keys), 23)
        self.assertEqual(len(rows), 23)
        self.assertEqual(receipt["corpus_sha256"], self.receipt["corpus_sha256"])

    def test_c2_gate_failed_blocks(self):
        self.status["canonical_persistence_status"] = "NEON_FAILED"
        self.paths["status"].write_text(json.dumps(self.status), encoding="utf-8")
        with self.assertRaisesRegex(shadow.ShadowBlocked, "C2_GATE_NOT_CONFIRMED"):
            self.verify()

    def test_c2_corpus_mismatch_blocks(self):
        self.receipt["corpus_sha256"] = "0"*64
        with self.assertRaisesRegex(shadow.ShadowBlocked, "C2_CORPUS_BINDING_MISMATCH"):
            self.verify()

    def test_wrong_city_count_blocks(self):
        obj = json.loads(self.paths["dashboard"].read_text())
        obj["multicity_meta"]["production_city_keys"].pop()
        self.paths["dashboard"].write_text(json.dumps(obj), encoding="utf-8")
        with self.assertRaisesRegex(shadow.ShadowBlocked, "CITY_BOUNDARY_NOT_23"):
            self.verify()

    def test_wrong_workflow_sha_blocks_before_neon(self):
        with self.assertRaisesRegex(shadow.ShadowBlocked, "WORKFLOW_SHA_MISMATCH"):
            self.execute(workflow_sha="c"*40)
        self.assertFalse((self.site / "data" / "new.json").exists())
        self.assertFalse((self.root / "shadow" / "candidate").exists())
        self.assertFalse(json.loads((self.root/"shadow"/"verdict.json").read_text())
                         ["publication_allowed"])

    def test_wrong_branch_blocks_before_neon(self):
        with self.assertRaisesRegex(shadow.ShadowBlocked, "NEON_BRANCH_RECEIPT_MISMATCH"):
            self.execute(expected_branch="br-other")

    def test_wrong_endpoint_blocks_before_neon(self):
        with self.assertRaisesRegex(shadow.ShadowBlocked, "NEON_ENDPOINT_BRANCH_MISMATCH"):
            self.execute()

    def test_readback_uuid_and_interval_match(self):
        from uuid import uuid4
        rows = [{**r, "episode_uid": str(uuid4())} for r in self.episodes]
        by_city = shadow.validated_neon_rows(self.episodes, self.keys, rows)
        self.assertEqual(len(by_city), 23)
        rows[0]["end_at"] = "2026-10-02T02:00:00Z"
        with self.assertRaisesRegex(shadow.ShadowBlocked, "READBACK_SEMANTIC_MISMATCH"):
            shadow.validated_neon_rows(self.episodes, self.keys, rows)

    def test_flag_and_builders_position_static(self):
        workflow = (Path(__file__).resolve().parents[1] /
                    ".github/workflows/update-netlify-site.yml").read_text()
        self.assertEqual(workflow.count("vars.NEON_JSON_SHADOW_ENABLED == 'true'"), 3)
        self.assertNotIn("vars.NEON_JSON_SHADOW_ENABLED == '1'", workflow)
        self.assertLess(workflow.index("Build Kyiv alert-cause"),
                        workflow.index("Generate non-publishing six-file"))
        self.assertLess(workflow.index("Generate non-publishing six-file"),
                        workflow.index("Commit updated production data"))

    def test_original_six_file_contract_in_generator(self):
        text = (Path(__file__).resolve().parents[1] /
                "scripts/neon_json_shadow_generator.py").read_text()
        for name in ("dashboard_data.json", "site_derived.json", "alerts_combined.json",
                     "historical-daily-kpi.json", "kyiv_threat_mix.json",
                     "sevastopol_events.json"):
            self.assertIn(name, text)
        self.assertNotIn("br-crimson-star-b59u7ge3", text)
        self.assertNotIn("FRESH_ROOT", text)
        self.assertIn("UNAUTHORIZED_CLASSIFICATION_REBIND", text)


if __name__ == "__main__":
    unittest.main()
