#!/usr/bin/env python3
"""Offline fail-closed contract tests. No Neon, upstream HTTP or Actions."""
from __future__ import annotations
import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from scripts import neon_json_shadow as shadow
from scripts import neon_json_shadow_generator as generator


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

    def native_readback(self, *, meta=None, **overrides):
        """Exercise execute's live-driver boundary, without a DB or full projection."""
        read_at = datetime(2026, 11, 7, 21, 34, 9, 123456, tzinfo=timezone.utc)
        rows = [{**row, "uid": "00000000-0000-0000-0000-%012d" % i,
                 "start_at": datetime.fromisoformat(row["start_at"].replace("Z", "+00:00")),
                 "end_at": datetime.fromisoformat(row["end_at"].replace("Z", "+00:00"))}
                for i, row in enumerate(self.episodes)]
        snap = {"meta": {"read_only": "on", "isolation": "repeatable read",
                         "snapshot": "1:2:", "read_at": read_at, **(meta or {})},
                "episodes": rows, "observations": [], "checkpoints": [],
                "runs": [{"run_id": "run-1", "db_branch": "br-c2", "status": "succeeded",
                          "parameters": {"corpus_sha256": self.receipt["corpus_sha256"]}}],
                "classifications": [], "source_links": [], "events": []}
        names = {"dashboard_data.json", "site_derived.json", "alerts_combined.json",
                 "historical-daily-kpi.json", *shadow.AUXILIARIES}

        def generate(args, work, *unused):
            # A live datetime must cross the real evidence writer before generation.
            evidence = shadow.load(work / "readback_proof.json")
            self.assertEqual(evidence["meta"]["read_at"], shadow.utc(read_at))
            self.assertIs(snap["meta"]["read_at"], read_at)
            candidate = work / "candidate"
            candidate.mkdir()
            for name in names:
                shadow.write(candidate / name, {})
            for name in ("kyiv_selection.json", "projection_lineage.json", "git_dependencies.json",
                         "utc_union_diagnostics.json", "active_rows_unmodified.json"):
                shadow.write(work / name, {})
            return {"candidate_sha256": {name: shadow.digest(candidate / name) for name in names}}

        fake = SimpleNamespace(Closed=generator.Closed, fingerprint=generator.fingerprint,
                               prepare=Mock(return_value=(None, None, {})),
                               snapshot=Mock(return_value=snap),
                               verify_snapshot=Mock(return_value=(rows, [])),
                               source_report=Mock(return_value={key: {"source_capture_verified": False}
                                                               for key in self.keys}),
                               generate=Mock(side_effect=generate))
        for key, value in overrides.items():
            setattr(fake, key, value)
        # reader=None deliberately exercises the same physical branch as Actions;
        # only the transport and expensive accepted projection are replaced.
        with patch("socket.socket.connect", side_effect=AssertionError("NO_NETWORK")), \
                patch.object(shadow, "load_generator", return_value=fake):
            return self.execute(writer_database_url="postgresql://ep-a.neon.tech/neondb")

    def test_native_datetime_readback_evidence(self):
        verdict = self.native_readback()
        self.assertEqual(verdict["status"], "PASS")
        self.assertEqual(len(verdict["candidate_files"]), 6)
        self.assertFalse(verdict["publication_allowed"])
        evidence = shadow.load(self.root / "shadow/readback_proof.json")
        self.assertEqual(evidence["meta"]["read_at"], "2026-11-07T21:34:09.123456Z")

    def assert_safe_stage(self, stage):
        output = self.root / "shadow"
        verdict = shadow.load(output / "verdict.json")
        self.assertEqual(verdict["status"], "BLOCKED")
        self.assertEqual(verdict["error_stage"], stage)
        self.assertFalse(verdict["publication_allowed"])
        self.assertEqual(verdict["candidate_files"], {})
        self.assertFalse((output / "candidate").exists())
        self.assertEqual({p.name for p in output.iterdir()}, {"verdict.json"})
        self.assertNotIn("SENSITIVE_EXCEPTION_TEXT", (output / "verdict.json").read_text())

    def test_snapshot_typeerror_stage_without_exception_text(self):
        with self.assertRaises(TypeError):
            self.native_readback(snapshot=Mock(side_effect=TypeError("SENSITIVE_EXCEPTION_TEXT")))
        self.assert_safe_stage("READ_NEON_SNAPSHOT")

    def test_readback_writer_typeerror_stage_without_exception_text(self):
        original = shadow.write

        def fail_evidence(path, value):
            if path.name == "readback_proof.json":
                raise TypeError("SENSITIVE_EXCEPTION_TEXT")
            return original(path, value)

        with patch.object(shadow, "write", side_effect=fail_evidence), self.assertRaises(TypeError):
            self.native_readback()
        self.assert_safe_stage("WRITE_READBACK_PROOF")

    def test_source_report_typeerror_stage_without_exception_text(self):
        with self.assertRaises(TypeError):
            self.native_readback(source_report=Mock(side_effect=TypeError("SENSITIVE_EXCEPTION_TEXT")))
        self.assert_safe_stage("BUILD_SOURCE_REPORT")

    def test_generator_typeerror_stage_without_exception_text(self):
        with self.assertRaises(shadow.ShadowBlocked):
            self.native_readback(generate=Mock(side_effect=TypeError("SENSITIVE_EXCEPTION_TEXT")))
        self.assert_safe_stage("GENERATE_FRONTEND")

    def test_evidence_writer_still_rejects_unknown_types(self):
        with self.assertRaises(TypeError):
            shadow.write(self.root / "unknown.json", {"unexpected": object()})

    def test_native_naive_timestamp_blocks_without_candidate(self):
        with self.assertRaisesRegex(shadow.ShadowBlocked, "NAIVE_TIMESTAMP"):
            self.native_readback(meta={"read_at": datetime(2026, 11, 7, 21, 34)})
        self.assert_safe_stage("WRITE_READBACK_PROOF")

    def test_unknown_metadata_type_blocks_without_string_fallback(self):
        with self.assertRaises(TypeError):
            self.native_readback(meta={"unexpected": object()})
        self.assert_safe_stage("WRITE_READBACK_PROOF")


if __name__ == "__main__":
    unittest.main()
