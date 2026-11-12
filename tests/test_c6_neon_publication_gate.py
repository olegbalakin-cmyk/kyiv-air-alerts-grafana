"""Real pinned physical-proof regression. No network, Git push or production writes."""
import importlib.util
import json
import os
import shutil
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("c6_neon_publication_gate",
                                             ROOT / "scripts/c6_neon_publication_gate.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class GateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = Path(os.environ["C6_PINNED_PHYSICAL_PROOF"])
        if not cls.original.is_dir():
            raise RuntimeError("Real physical proof artifact missing; fail closed")
        data = json.loads((cls.original / "historical_freshness_gate.json").read_text())
        cls.as_of = gate.utc(data["evaluated_at_utc"])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "proof"
        shutil.copytree(self.original, self.root)

    def accept(self):
        return gate.inspect(self.root, as_of=self.as_of)

    def reject(self):
        with self.assertRaises(gate.Blocked):
            self.accept()

    def alter(self, name, change):
        path = self.root / name
        data = json.loads(path.read_text(encoding="utf-8"))
        change(data)
        path.write_text(json.dumps(data, sort_keys=True), encoding="utf-8")
        m = self.root / "sha256_manifest.json"
        manifests = json.loads(m.read_text())
        manifests["files"][name] = gate.digest(path.read_bytes())
        m.write_text(json.dumps(manifests))

    def test_physical_proof_is_structurally_valid_but_not_publishable(self):
        result = self.accept()
        self.assertEqual(result["status"], "PASS_SCOPED_PROOF_NO_PUBLICATION")
        self.assertIs(result["production_publication_allowed"], False)
        self.assertFalse(result["compatible_runtime_git_baseline_proven"])
        self.assertEqual(result["city_count"], 23)
        self.assertEqual(len(result["candidate_files"]), 6)

    def test_tampered_bytes_fail(self):
        with (self.root / "candidate/dashboard_data.json").open("ab") as f:
            f.write(b"attack")
        self.reject()

    def test_missing_candidate_fails(self):
        (self.root / "candidate/sevastopol_events.json").unlink()
        self.reject()

    def test_extra_current_alerts_file_fails(self):
        (self.root / "candidate/current_alerts.json").write_text("{}")
        self.reject()

    def test_wrong_neon_verdict_fails(self):
        self.alter("verdict.json", lambda r: r.update(neon_readback_verified=False))
        self.reject()

    def test_forged_publication_permission_fails(self):
        self.alter("verdict.json", lambda r: r.update(publication_allowed=True))
        self.reject()

    def test_one_unverified_receipt_fails(self):
        self.alter("historical_freshness_gate.json",
                   lambda r: r["cities"]["sevastopol"].update(continuity_verified=False))
        self.reject()

    def test_missing_receipt_fails(self):
        self.alter("historical_freshness_gate.json",
                   lambda r: r["cities"].pop("sevastopol"))
        self.reject()

    def test_source_recheck_future_stale_fails(self):
        with self.assertRaises(gate.Blocked):
            gate.inspect(self.root, as_of=self.as_of + timedelta(hours=70))

    def test_future_readback_timestamp_fails(self):
        with self.assertRaises(gate.Blocked):
            gate.inspect(self.root, as_of=self.as_of - timedelta(days=4))

    def test_wrong_dashboard_index_generation_fails(self):
        self.alter("candidate/historical-daily-kpi.json",
                   lambda r: r["meta"].update(source_dashboard_generated_at="2020-01-01T00:00:00Z"))
        self.reject()

    def test_wrong_candidate_hash_manifest_fails(self):
        self.alter("verdict.json",
                   lambda r: r["candidate_files"].update({"dashboard_data.json": "0" * 64}))
        self.reject()

    def test_missing_auxiliary_provenance_fails(self):
        self.alter("git_dependencies.json", lambda r: r[0].update(site_input_sha="0" * 40))
        self.reject()

    def test_forged_historical_freshness_publish_permission_fails(self):
        self.alter("historical_freshness_gate.json",
                   lambda r: r.update(publication_allowed=True))
        self.reject()

    def test_unproven_current_alert_status_fails(self):
        self.alter("candidate/dashboard_data.json",
                   lambda r: r["cities"]["kyiv"]["meta"].update(current_source_verified=True))
        self.reject()

    def test_malformed_extra_file_fails(self):
        (self.root / "casualty_override.json").write_text("{}")
        self.reject()

    def test_symlink_not_allowed(self):
        (self.root / "accidental-link").symlink_to(self.root / "verdict.json")
        self.reject()


if __name__ == "__main__":
    unittest.main()
