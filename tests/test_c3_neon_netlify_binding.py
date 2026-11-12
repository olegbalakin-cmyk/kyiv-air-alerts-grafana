"""Exercise the REAL inline production artifact validator in isolated offline fixtures."""
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
WORKFLOW = REPO / ".github/workflows/netlify-production.yml"
NAMES = ("dashboard_data.json", "site_derived.json", "alerts_combined.json",
         "kyiv_threat_mix.json", "sevastopol_events.json", "historical-daily-kpi.json")
GEN = "2026-11-12T12:00:00+00:00"
BRANCH = "br-bold-mode-b5rub8pq"
C2_SHA = "a" * 40
CORPUS = "b" * 64
CITY = ["kyiv", "sevastopol"] + ["city" + str(i) for i in range(21)]


def sha(payload):
    return hashlib.sha256(payload).hexdigest()


def dump(payload):
    return json.dumps(payload, sort_keys=True).encode()


def build_zip(file, files):
    with zipfile.ZipFile(file, "w") as bundle:
        for name, payload in files.items():
            bundle.writestr(name, payload)


def production_validator():
    wf = yaml.safe_load(WORKFLOW.read_text())
    job = wf["jobs"]["deploy-production"]
    steps = [s for s in job["steps"] if s.get("name", "").startswith("Select approved exact Neon KPI")]
    assert len(steps) == 1
    run = steps[0]["run"]
    snippets = re.findall(r"python - <<'PY'\n(.*?)\nPY", run, flags=re.S)
    assert len(snippets) == 2
    return snippets[-1]


class NetlifyNeonBindingOffline(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.root = Path(self.t.name)
        (self.root / "_approved_c6").mkdir()
        index = {"meta": {"source_ref": "neon:" + BRANCH,
                          "source_dashboard_generated_at": GEN,
                          "expected_cities": 23, "verified_count": 23},
                 "cities": {c: {"status": "verified"} for c in CITY}}
        dash = {"meta": {"generated_at": GEN}, "historical_daily_kpi": index}
        values = {name: (index if name == "historical-daily-kpi.json" else
                         dash if name == "dashboard_data.json" else
                         [] if name == "alerts_combined.json" else {"aux": name})
                  for name in NAMES}
        self.files = {
            (name if name == "historical-daily-kpi.json" else
             "kyiv-air-alerts-grafana/data/" + name): sha(dump(values[name]))
            for name in NAMES}
        report = {"state": "INTEGRATION_PREPARED_PUBLICATION_OFF",
                  "publication_allowed": False,
                  "production_git_push_executed": False, "prepared_files": 6,
                  "neon_branch": BRANCH, "c2_corpus_sha256": CORPUS,
                  "files": self.files}
        six = {"candidate/" + dest: dump(values[name]) for name, dest in (
            (n, n if n == "historical-daily-kpi.json" else
             "kyiv-air-alerts-grafana/data/" + n) for n in NAMES)}
        six["REPORT.json"] = dump(report)
        self.candidate = six
        last = datetime.now(timezone.utc).isoformat()
        self.proof = {
            "verdict.json": dump({
                "status": "PASS", "physical_neon_readback_run": True,
                "city_count": 23, "neon_branch": BRANCH,
                "c2_corpus_sha256": CORPUS,
                "candidate_files": {n: sha(dump(values[n])) for n in NAMES}}),
            "readback_proof.json": dump({
                "capture_run_identity": {"github_run_id": 123,
                                         "github_run_attempt": 1,
                                         "workflow_sha": C2_SHA},
                "c2_corpus_sha256": CORPUS}),
            "sha256_manifest.json": dump({
                "schema": "isolated-neon-shadow-proof-v1",
                "files": {"candidate/" + n: sha(dump(values[n])) for n in NAMES}
                | {"other/" + str(i): "d"*64 for i in range(12)}}),
            "historical_freshness_gate.json": dump({
                "status": "FRESHNESS_READY_FOR_INTEGRATION",
                "publication_allowed": False, "fresh_cities": 23,
                "full_receipt_cities": 23, "historically_bound_cities": 23}),
            "historical_freshness_binding.json": dump({
                "sources": {city: {"continuity_verified": True,
                                   "last_checked_at": last} for city in CITY}})}
        (self.root/"_approved_c6/run.json").write_bytes(dump({"head_sha": C2_SHA}))

    def execute(self):
        build_zip(self.root/"_approved_c6/artifact.zip", self.candidate)
        build_zip(self.root/"_approved_c6/work-a-artifact.zip", self.proof)
        env=os.environ.copy()
        env.update({"APPROVED_KPI_SHA": self.files["historical-daily-kpi.json"],
                    "APPROVED_GENERATION": GEN, "C6_RUN_ID": "123",
                    "C6_ATTEMPT": "1"})
        return subprocess.run([sys.executable, "-c", production_validator()],
                              cwd=self.root, env=env, capture_output=True,
                              text=True)

    def test_positive_exact_six_and_physical_proof(self):
        result=self.execute()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(sha((self.root/"historical-daily-kpi.json").read_bytes()),
                         self.files["historical-daily-kpi.json"])

    def test_wrong_work_a_source_blocks(self):
        payload=json.loads(self.proof["verdict.json"])
        payload["neon_branch"]="wrong"
        self.proof["verdict.json"]=dump(payload)
        self.assertNotEqual(self.execute().returncode, 0)

    def test_wrong_c2_attempt_blocks(self):
        payload=json.loads(self.proof["readback_proof.json"])
        payload["capture_run_identity"]["github_run_attempt"]=2
        self.proof["readback_proof.json"]=dump(payload)
        self.assertNotEqual(self.execute().returncode, 0)

    def test_stale_city_blocks(self):
        payload=json.loads(self.proof["historical_freshness_binding.json"])
        payload["sources"]["kyiv"]["last_checked_at"]="2026-01-01T00:00:00+00:00"
        self.proof["historical_freshness_binding.json"]=dump(payload)
        self.assertNotEqual(self.execute().returncode, 0)

    def test_missing_kpi_blocks(self):
        self.candidate.pop("candidate/historical-daily-kpi.json")
        self.assertNotEqual(self.execute().returncode, 0)

    def test_git_only_branch_unchanged(self):
        wf=yaml.safe_load(WORKFLOW.read_text())
        steps=wf["jobs"]["deploy-production"]["steps"]
        legacy=next(s for s in steps if "Git-only default" in s.get("name", ""))
        self.assertIn("!inputs.neon_release_mode", legacy["if"])
        self.assertIn("build_preview_historical_daily.py", legacy["run"])
        neon=next(s for s in steps if "Select approved exact Neon KPI" in s.get("name", ""))
        self.assertIn("inputs.neon_release_mode", neon["if"])
        self.assertIn("C6_NEON_RELEASE_OWNER_APPROVED", str(neon))
        self.assertIn("C6_NEON_WORK_A_APPROVED_RUN_ID", str(neon))


if __name__ == "__main__":
    unittest.main()
