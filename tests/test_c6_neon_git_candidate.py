"""Fail-closed offline staging contract; no database, source HTTP or Git push."""
import json
import shutil
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from scripts import c6_neon_git_candidate as stage

BRANCH = "br-bold-mode-b5rub8pq"
SHA40 = "a" * 40
CORPUS = "c" * 64
BUNDLE = "d" * 64
FILES = stage.FILES


class CandidateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.site = root / "site"
        self.proof = root / "proof"
        self.output = root / "prepared"
        (self.site / "data").mkdir(parents=True)
        (self.proof / "candidate").mkdir(parents=True)
        self.old = [(f"2026-01-{day:02}T12:00:00+02:00",
                     f"2026-01-{day:02}T13:00:00+02:00") for day in (1, 2)]
        alerts = [{"start": a, "end": b, "source": "verified"} for a, b in self.old]
        self.dashboard = {
            "meta": {"generated_at": "2026-11-12T10:00:00+00:00",
                     "publication_authority": {"publication_allowed": False}},
            "casualties": {"kyiv": 5}, "casualties_by_city": {"kyiv": 5}
        }
        self.index = {"meta": {"source_ref": "neon:" + BRANCH,
                              "source_dashboard_generated_at":
                                  self.dashboard["meta"]["generated_at"]}}
        self.dashboard["historical_daily_kpi"] = self.index
        for name, value in {
            "dashboard_data.json": self.dashboard,
            "site_derived.json": {"source": "previous"},
            "alerts_combined.json": alerts,
            "kyiv_threat_mix.json": {"aux": 1},
            "sevastopol_events.json": {"aux": 2},
        }.items():
            self.write(self.site / "data" / name, value)
            if name == "site_derived.json":
                value = {"source": "candidate"}
            self.write(self.proof / "candidate" / name, value)
        self.write(self.proof / "candidate/historical-daily-kpi.json", self.index)
        self.write(self.proof / "verdict.json", {
            "publication_allowed": False, "c2_corpus_sha256": CORPUS,
            "neon_branch": BRANCH})
        self.write(self.proof / "historical_freshness_binding.json", {
            "corpus_sha256": CORPUS, "db_branch": BRANCH, "input_sha": SHA40})
        self.write(self.proof / "readback_proof.json", {
            "c2_corpus_sha256": CORPUS,
            "capture_run_identity": {
                "github_run_id": 123, "github_run_attempt": 1,
                "workflow_sha": SHA40, "input_sha": SHA40}})
        self.rehash()
        self.bindings = {
            "as_of": datetime.now(timezone.utc),
            "expected_c2_corpus": CORPUS, "expected_branch": BRANCH,
            "expected_input_sha": SHA40, "expected_workflow_sha": SHA40,
            "expected_run_id": 123, "expected_run_attempt": 1,
            "expected_bundle_sha256": BUNDLE,
        }

    @staticmethod
    def write(path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")

    def alter(self, path, fn):
        data = json.loads(path.read_text())
        fn(data)
        self.write(path, data)
        self.rehash()

    def rehash(self):
        hashes = {n: stage.sha((self.proof / "candidate" / n).read_bytes())
                  for n in FILES}
        self.write(self.proof / "sha256_manifest.json", {
            "files": {"candidate/" + n: digest for n, digest in hashes.items()}})
        self.result = {
            "status": "PASS_SCOPED_PROOF_NO_PUBLICATION",
            "production_publication_allowed": False,
            "candidate_files": hashes,
        }

    def prepare(self):
        with patch.object(stage.gate, "inspect", return_value=self.result):
            return stage.prepare(proof=self.proof, site=self.site,
                                 output=self.output, **self.bindings)

    def blocked(self):
        baseline = {p.name: p.read_bytes() for p in (self.site / "data").iterdir()}
        with self.assertRaises(stage.Blocked):
            self.prepare()
        self.assertFalse(self.output.exists())
        self.assertEqual(baseline, {
            p.name: p.read_bytes() for p in (self.site / "data").iterdir()})

    def test_six_files_prepared_without_publication(self):
        report = self.prepare()
        self.assertEqual(report["prepared_files"], 6)
        self.assertIs(report["publication_allowed"], False)
        self.assertFalse(report["production_git_push_executed"])
        self.assertEqual(len(report["files"]), 6)
        for _, path in FILES.items():
            self.assertEqual(stage.sha((self.output / "candidate" / path).read_bytes()),
                             report["files"][path])

    def test_missing_receipt_identity(self):
        self.alter(self.proof / "readback_proof.json",
                   lambda d: d.pop("capture_run_identity"))
        self.blocked()

    def test_wrong_run_id(self):
        self.bindings["expected_run_id"] = 124
        self.blocked()

    def test_corpus_mismatch(self):
        self.bindings["expected_c2_corpus"] = "0" * 64
        self.blocked()

    def test_stale_source_gate(self):
        with patch.object(stage.gate, "inspect", side_effect=stage.gate.Blocked("STALE")):
            with self.assertRaises(stage.gate.Blocked):
                stage.prepare(proof=self.proof, site=self.site,
                              output=self.output, **self.bindings)
        self.assertFalse(self.output.exists())

    def test_generator_missing_candidate(self):
        (self.proof / "candidate/dashboard_data.json").unlink()
        with self.assertRaises(OSError):
            self.prepare()
        self.assertFalse(self.output.exists())

    def test_wrong_historical_index(self):
        self.alter(self.proof / "candidate/historical-daily-kpi.json",
                   lambda d: d["meta"].update(source_dashboard_generated_at="wrong"))
        self.blocked()

    def test_casualty_preserved(self):
        self.alter(self.proof / "candidate/dashboard_data.json",
                   lambda d: d["casualties"].update(kyiv=123))
        self.blocked()

    def test_auxiliary_bytes_preserved(self):
        self.alter(self.proof / "candidate/sevastopol_events.json",
                   lambda d: d.update(aux=3))
        self.blocked()

    def test_kyiv_intervals_preserved(self):
        self.alter(self.proof / "candidate/alerts_combined.json", lambda d: d.pop())
        self.blocked()

    def test_forged_release_permission(self):
        self.alter(self.proof / "verdict.json",
                   lambda d: d.update(publication_allowed=True))
        self.blocked()

    def test_output_cannot_be_inside_live_site(self):
        self.output = self.site / "data" / "candidate"
        self.blocked()

    def test_duplicate_output_never_overwritten(self):
        self.output.mkdir()
        with self.assertRaises(stage.Blocked):
            self.prepare()

    def test_exact_parser_pin_rejects_drift(self):
        from scripts import c6_pr93_generator_compat as compat
        with self.assertRaises(compat.PinBlocked):
            compat.patched_bytes(b"unverified generator",
                                 b"unverified parser")


if __name__ == "__main__":
    unittest.main()
