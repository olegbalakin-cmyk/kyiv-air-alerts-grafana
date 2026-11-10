"""New source-routing checks on retained inputs; no generation, SQL or source HTTP."""
from contextlib import ExitStack
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import socket
import tempfile
import unittest
from unittest.mock import patch

from scripts import c6_json_source_preview as preview


class SourcePreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.site = Path(os.environ["C6_TEST_SITE"])
        cls.proof = Path(os.environ["C6_TEST_PROOF"])
        cls.bundle = Path(os.environ["C6_TEST_BUNDLE"])

    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.temp = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        # Any accidental network/DB socket fails the new checks immediately.
        self.stack.enter_context(patch.object(socket.socket, "connect", side_effect=AssertionError("NO_NETWORK")))
        self.stack.enter_context(patch.object(socket, "create_connection", side_effect=AssertionError("NO_NETWORK")))

    def stage(self, source="git", output=None, proof=None, site=None):
        return preview.stage(site or self.site, output or self.temp / "preview",
                             bundle=self.bundle, source=source,
                             proof=proof if proof is not None else self.proof)

    def test_default_off_uses_git_without_neon(self):
        result = preview.stage(self.site, self.temp / "preview", bundle=self.bundle)
        self.assertEqual(result["source"], "git")
        self.assertIsNone(result["proof_artifact"])
        self.assertFalse(result["publication_allowed"])

    def test_neon_routes_six_exact_files_and_preserves_assets(self):
        result = self.stage("neon")
        out = self.temp / "preview"
        for name in preview.FILES:
            self.assertEqual((out / "data" / name).read_bytes(),
                             (self.proof / "candidate" / name).read_bytes())
        for name in ("styles.css", "chart-share.js", "kpi-range.js", "features.json"):
            self.assertEqual((out / name).read_bytes(), (self.site / "pages-preview" / name).read_bytes())
        app = (out / "app.js").read_text()
        original = (self.site / "pages-preview/app.js").read_text()
        self.assertEqual(app, original.replace(preview.RAW_BASE, 'const RAW_DATA_BASE = "data/";'))
        self.assertIn("Data is frozen", (out / "index.html").read_text())
        self.assertFalse(result["publication_allowed"])

    def test_new_switch_rollback_restores_all_git_bytes(self):
        out = self.temp / "preview"
        git = self.stage()
        frontend_before = {p.name: preview.digest(p) for p in (self.site / "pages-preview").iterdir() if p.is_file()}
        self.stage("neon")
        rollback = self.stage()
        self.assertEqual(git, rollback)
        self.assertEqual(git["input_files_sha256"], {n: preview.digest(out / "data" / n) for n in preview.FILES})
        self.assertEqual(frontend_before, {p.name: preview.digest(p) for p in (self.site / "pages-preview").iterdir() if p.is_file()})

    def test_missing_proof_does_not_fall_back(self):
        with self.assertRaisesRegex(preview.Blocked, "MISSING_NEON_PROOF"):
            preview.stage(self.site, self.temp / "preview", bundle=self.bundle, source="neon")
        self.assertFalse((self.temp / "preview").exists())

    def test_changed_or_missing_proof_blocks_without_mutating_old_preview(self):
        self.stage()
        before = (self.temp / "preview" / preview.MARKER).read_bytes()
        bad = self.temp / "bad-proof"
        shutil.copytree(self.proof, bad)
        (bad / "candidate/dashboard_data.json").unlink()
        with self.assertRaisesRegex(preview.Blocked, "PROOF_FILE_MISSING_OR_CHANGED"):
            self.stage("neon", proof=bad)
        self.assertEqual(before, (self.temp / "preview" / preview.MARKER).read_bytes())
        (bad / "sha256_manifest.json").write_text("{}")
        with self.assertRaisesRegex(preview.Blocked, "UNACCEPTED_PROOF_MANIFEST"):
            self.stage("neon", proof=bad)

    def test_missing_git_bundle_blocks(self):
        with self.assertRaises(FileNotFoundError):
            preview.stage(self.site, self.temp / "preview", bundle=self.temp / "missing.zip")

    def test_incompatible_json_rejected(self):
        data = {n: preview.read(self.proof / "candidate" / n) for n in preview.FILES}
        baseline = json.loads(json.dumps(data["dashboard_data.json"]))
        data["dashboard_data.json"]["multicity_meta"]["production_city_keys"].pop()
        with self.assertRaisesRegex(preview.Blocked, "CITY_BOUNDARY_CHANGED"):
            preview.compatible(data, baseline)

    def test_unowned_and_input_outputs_rejected(self):
        out = self.temp / "unowned"
        out.mkdir()
        with self.assertRaisesRegex(preview.Blocked, "REFUSE_UNOWNED_OUTPUT"):
            self.stage(output=out)
        with self.assertRaisesRegex(preview.Blocked, "OUTPUT_OVERLAPS_INPUT"):
            self.stage(output=self.site / "data")

    def test_existing_proof_is_only_a_frozen_preview(self):
        blockers = preview.history_release_blockers(self.proof)
        self.assertEqual(sum(b.startswith("HISTORY_CAPTURE_OR_CONTINUITY:") for b in blockers), 23)
        self.assertIn("FOUR_DST_CASES_UNRESOLVED", blockers)
        self.assertFalse(any("ACTIVE_STATUS" in b for b in blockers))

    def test_kyiv_membership_change_blocks_without_rebinding(self):
        rows = preview.read(self.proof / "candidate/alerts_combined.json")
        with self.assertRaisesRegex(preview.Blocked, "KYIV_DISPLAY_MEMBERSHIP_CHANGED"):
            preview.verify_kyiv_membership(rows, rows[:-1])

    def test_age_recomputed_and_live_status_is_not_a_history_gate(self):
        proof = self.temp / "gates"
        proof.mkdir()
        preview.write(proof / "verdict.json", {"dst_repair_certified": True,
                      "kyiv_current_provenance_certified": True})
        gate = {"source_captured_at_utc": "2026-11-07T12:00:00Z",
                "source_capture_verified": True, "continuity_verified": True,
                "source_age_seconds": 0, "active_status_certified": False}
        preview.write(proof / "source_gates.json", {"kyiv": gate})
        within = datetime(2026, 11, 8, 12, tzinfo=timezone.utc)
        stale = datetime(2026, 11, 9, 12, tzinfo=timezone.utc)
        self.assertEqual(preview.history_release_blockers(proof, within), ["OWNER_CUTOVER_NOT_AUTHORIZED"])
        self.assertIn("HISTORY_CAPTURE_OR_CONTINUITY:kyiv", preview.history_release_blockers(proof, stale))


if __name__ == "__main__":
    unittest.main()
