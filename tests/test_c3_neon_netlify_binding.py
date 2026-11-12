"""One isolated end-to-end PR95 -> Netlify PR104 -> PR100 consumer proof.

Uses the actual PR95 release binding when its immutable checkout is supplied.
All inputs are synthetic fixtures. A PASS never grants production permission.
"""
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
WORKFLOW = REPO / ".github/workflows/netlify-production.yml"
PR95 = Path(os.environ.get("WORK_H_PINNED_PR95_ROOT", REPO / "approved-pr95"))
PR100 = Path(os.environ.get("WORK_H_PINNED_PR100_ROOT", REPO / "approved-pr100"))
NAMES = ("dashboard_data.json", "site_derived.json", "alerts_combined.json",
         "kyiv_threat_mix.json", "sevastopol_events.json", "historical-daily-kpi.json")
ROOT = "historical-daily-kpi.json"
DATA = "kyiv-air-alerts-grafana/data/"
PATHS = {n: (ROOT if n == ROOT else DATA + n) for n in NAMES}
BRANCH = "br-bold-mode-b5rub8pq"
RUN_SHA = "a" * 40
INPUT_SHA = "c" * 40
CORPUS = "b" * 64
CITIES = ["kyiv", "sevastopol"] + ["city" + str(i) for i in range(21)]


def digest(b):
    return hashlib.sha256(b).hexdigest()


def encode(obj):
    return (json.dumps(obj, sort_keys=True, ensure_ascii=False) + "\n").encode()


def zip_bytes(items, target):
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for name, contents in sorted(items.items()):
            z.writestr(name, contents)


def read_zip(target):
    with zipfile.ZipFile(target) as z:
        return {name: z.read(name) for name in z.namelist()}


def production_contract():
    path = REPO / "scripts/c3_final_neon_kpi_contract.py"
    spec = importlib.util.spec_from_file_location("work_h_contract", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def pinned_pr95_release():
    path = PR95 / "scripts/c6_neon_release_binding.py"
    if not path.is_file():
        raise AssertionError("Exact PR95 checkout required for end-to-end test")
    assert subprocess.check_output(["git", "hash-object", str(path)], text=True).strip() == (
        "f2aefc7280611e456dede640b641534662cbb5d0"), "PR95 binding code drift"
    # The production release generator imports from its own frozen checkout.
    sys.path.insert(0, str(PR95))
    try:
        for n in list(sys.modules):
            if n == "scripts" or n.startswith("scripts.c6_neon_"):
                del sys.modules[n]
        from scripts import c6_neon_release_binding as release
        return release
    finally:
        sys.path.pop(0)


class FinalContract(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = self.base / "work"
        self.root.mkdir()
        self.art = self.root / "_approved_c6"
        self.art.mkdir()
        self.now = datetime.now(timezone.utc)
        self.gen = (self.now - timedelta(minutes=10)).isoformat()
        receipts_at = (self.now - timedelta(minutes=20)).isoformat()
        read_at = (self.now - timedelta(minutes=30)).isoformat()
        authority = {
            "publication_allowed": False,
            "scope": "RESEARCH_CANDIDATE_NOT_CURRENT_DATA_CERTIFICATION",
            "branch_id": BRANCH,
            "historical_freshness": {"binding_sha256": "9" * 64},
            "dst_simulation": False, "source_fallback": False,
            "active_status": "UNKNOWN_UNCERTIFIED",
        }
        idx = {"schema": "verified-historical-daily-start-counts-v1",
               "meta": {"source_ref": "neon:" + BRANCH,
                        "source_dashboard_generated_at": self.gen,
                        "expected_cities": 23, "verified_count": 23},
               "cities": {city: {"status": "verified"} for city in CITIES}}
        dash = {
            "meta": {"generated_at": self.gen, "publication_authority": authority},
            "multicity_meta": {"production_city_keys": CITIES},
            "cities": {city: {"meta": {"current_source_verified": False}} for city in CITIES},
            "historical_daily_kpi": idx,
            "casualties": {}, "casualties_by_city": {},
        }
        values = {
            "dashboard_data.json": dash,
            "site_derived.json": {"meta": {"publication_authority": authority}},
            "alerts_combined.json": [{"start": "2026-01-01", "end": "2026-01-02"}],
            "kyiv_threat_mix.json": {"aux": "kyiv"},
            "sevastopol_events.json": {"aux": "sev"},
            ROOT: idx,
        }
        self.prepared = self.base / "prepared"
        self.research = self.prepared / "candidate"
        self.research.mkdir(parents=True)
        for n, p in PATHS.items():
            dest = self.research / p
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(encode(values[n]))
        self.source_files = {p: digest((self.research / p).read_bytes()) for p in PATHS.values()}
        self.report = {
            "state": "INTEGRATION_PREPARED_PUBLICATION_OFF",
            "publication_allowed": False, "production_git_push_executed": False,
            "prepared_files": 6, "neon_branch": BRANCH,
            "c2_run_id": 123, "c2_run_attempt": 1,
            "c2_workflow_sha": RUN_SHA, "c2_input_sha": INPUT_SHA,
            "c2_bundle_sha256": "d" * 64,
            "c2_corpus_sha256": CORPUS, "files": self.source_files,
        }
        self.candidate = {"REPORT.json": encode(self.report)}
        self.candidate.update({"candidate/" + p: (self.research/p).read_bytes()
                               for p in self.source_files})
        self.release = pinned_pr95_release()
        self.final_root = self.base / "final-release"
        self.result = self.release.release_candidate(
            self.prepared, self.report,
            repository="olegbalakin-cmyk/kyiv-air-alerts-grafana",
            release_id="release-work-h-test-01", output=self.final_root)
        self.final_zip = {"candidate/" + p: (self.final_root/"candidate"/p).read_bytes()
                          for p in self.source_files}
        for n in ("RELEASE_BINDING.json", "RELEASE_MANIFEST.json"):
            self.final_zip[n] = (self.final_root/n).read_bytes()

        binding = {
            "schema": "c6-historical-freshness-v1", "publication_allowed": False,
            "corpus_sha256": CORPUS, "db_branch": BRANCH, "input_sha": INPUT_SHA,
            "binding_sha256": "9"*64,
            "city_keys": CITIES,
            "sources": {city: {"continuity_verified": True,
                               "last_checked_at": receipts_at} for city in CITIES},
        }
        readback = {
            "physical_neon_readback_run": True,
            "meta": {"read_only": "on", "isolation": "repeatable read",
                     "read_at": read_at},
            "capture_run_identity": {"github_run_id": 123, "github_run_attempt": 1,
                                     "workflow_sha": RUN_SHA, "input_sha": INPUT_SHA},
            "c2_corpus_sha256": CORPUS,
        }
        binding["readback"] = readback
        freshness = {
            "status": "FRESHNESS_READY_FOR_INTEGRATION",
            "publication_allowed": False, "fresh_cities": 23,
            "full_receipt_cities": 23, "historically_bound_cities": 23,
            "freshness_ceiling_hours": 36.0,
            "cities": {city: {"reasons": [], "continuity_verified": True,
                              "full_receipt_verified": True,
                              "historical_binding_verified": True} for city in CITIES},
        }
        verdict = {
            "status": "PASS", "frontend_compatible": True,
            "neon_readback_verified": True, "physical_neon_readback_run": True,
            "physical_readback_verdict": "PHYSICAL_NEON_READBACK_RUN",
            "generation_verdict": "PHYSICAL_GENERATION_PASS",
            "readback_mode": "physical", "publication_allowed": False,
            "production_publication": "PRODUCTION_PUBLICATION_NOT_AUTHORIZED",
            "neon_writes": 0, "upstream_http_gets": 0,
            "production_file_writes": 0,
            "city_count": 23, "neon_branch": BRANCH,
            "c2_corpus_sha256": CORPUS,
            "candidate_files": {n: self.source_files[PATHS[n]] for n in NAMES},
        }
        self.proof = {
            "verdict.json": encode(verdict),
            "readback_proof.json": encode(readback),
            "historical_freshness_binding.json": encode(binding),
            "historical_freshness_gate.json": encode(freshness),
            "source_gates.json": encode({city: {"full_historical_receipt_verified": True}
                                         for city in CITIES}),
        }
        for n in production_contract().WORK_A_EVIDENCE - set(self.proof):
            self.proof[n] = encode({"evidence": n})
        self.proof.update({"candidate/" + n: (self.research/PATHS[n]).read_bytes()
                           for n in NAMES})
        self.proof["sha256_manifest.json"] = encode({
            "schema": "isolated-neon-shadow-proof-v1",
            "files": {n: digest(raw) for n, raw in self.proof.items()}})
        (self.art/"run.json").write_bytes(encode({
            "id": 123, "run_attempt": 1, "head_sha": RUN_SHA,
            "status": "completed", "conclusion": "success",
            "event": "schedule", "path": ".github/workflows/update-netlify-site.yml"}))
        self.env = {"GITHUB_REPOSITORY": "olegbalakin-cmyk/kyiv-air-alerts-grafana",
                    "C6_RELEASE_OWNER_APPROVED": "true",
                    "C6_RUN_ID": "123", "C6_ATTEMPT": "1",
                    "APPROVED_GENERATION": self.gen,
                    "APPROVED_BINDING_SHA": self.result["release_manifest_sha256"],
                    "OWNER_BINDING_SHA": self.result["release_manifest_sha256"],
                    "OWNER_FINAL_FILES_JSON": json.dumps(self.result["files"]),
                    "APPROVED_KPI_SHA": self.result["files"][ROOT]}
        self.repack()

    def repack(self):
        zip_bytes(self.candidate, self.art/"artifact.zip")
        zip_bytes(self.proof, self.art/"work-a-artifact.zip")
        zip_bytes(self.final_zip, self.art/"final-release-artifact.zip")
        a = digest((self.art/"artifact.zip").read_bytes())
        w = digest((self.art/"work-a-artifact.zip").read_bytes())
        f = digest((self.art/"final-release-artifact.zip").read_bytes())
        self.env.update({"C6_ARTIFACT_SHA": a, "WORK_A_ARTIFACT_SHA": w,
                         "OWNER_WORK_A_ARTIFACT_SHA": w,
                         "FINAL_ARTIFACT_SHA": f, "OWNER_FINAL_ARTIFACT_SHA": f})

    def run_contract(self):
        # Execute the same module invoked by production workflow, with frozen fixtures.
        return production_contract().run(self.art, self.env, now=self.now)

    def must_block(self, reason):
        with self.assertRaisesRegex((ValueError, KeyError, TypeError), reason):
            self.run_contract()
        self.assertFalse((self.root/ROOT).exists(), "invalid artifact wrote Netlify root")

    def test_end_to_end_pr95_to_pr104_to_pr100(self):
        prior_research = digest((self.art/"artifact.zip").read_bytes())
        prior_proof = digest((self.art/"work-a-artifact.zip").read_bytes())
        result = self.run_contract()
        raw = self.final_zip["candidate/" + ROOT]
        self.assertEqual((self.root/ROOT).read_bytes(), raw)
        self.assertEqual(digest(raw), self.result["files"][ROOT])
        self.assertNotEqual(digest(raw), self.source_files[ROOT])
        self.assertTrue(result["dashboard_data.json"]["meta"]["publication_authority"]["publication_allowed"])
        self.assertFalse(json.loads(self.candidate["candidate/" + PATHS["dashboard_data.json"]])
                         ["meta"]["publication_authority"]["publication_allowed"])
        self.assertEqual(prior_research, digest((self.art/"artifact.zip").read_bytes()))
        self.assertEqual(prior_proof, digest((self.art/"work-a-artifact.zip").read_bytes()))
        self.verify_actual_frontend(result)

    def verify_actual_frontend(self, final):
        app = PR100 / "kyiv-air-alerts-grafana/pages-preview/app.js"
        self.assertTrue(app.is_file(), "Exact PR100 checkout required")
        if os.environ.get("WORK_H_LOCAL_FRONTEND_FRAGMENT") != "1":
            self.assertEqual(subprocess.check_output(["git", "hash-object", str(app)],
                             text=True).strip(), "bc869cb71b7ddb39489c989323b59fdb5b87d6b3")
        else:
            # Only for the offline container that cannot reach GitHub;
            # CI must use full PR100 app.js with its exact Git blob SHA.
            self.assertIn("const approvedNeonGitRelease", app.read_text())
        dash = self.root/"final-dashboard.json"
        dash.write_bytes(encode(final["dashboard_data.json"]))
        original_dash = self.root/"original-dashboard.json"
        original_dash.write_bytes(self.candidate["candidate/" + PATHS["dashboard_data.json"]])
        code = r'''
const assert=require('node:assert/strict'), fs=require('node:fs'), vm=require('node:vm');
const [appFile, dashFile, originalFile, kpiFile]=process.argv.slice(1);
const src=fs.readFileSync(appFile,'utf8');
const guard=src.match(/  const isolatedNeonPreview =[\s\S]*?;\n  const validIndex = index =>[\s\S]*?;\n/);
const staticGuard=src.match(/  const matchesDashboardGeneration = index =>[\s\S]*?;\n/);
assert.ok(guard && staticGuard,'Actual PR100 predicates missing');
const dash=JSON.parse(fs.readFileSync(dashFile)), old=JSON.parse(fs.readFileSync(originalFile));
const index=JSON.parse(fs.readFileSync(kpiFile));
const base='https://raw.githubusercontent.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/site-prod/kyiv-air-alerts-grafana/data/';
const check=(d,i,b=base)=>vm.runInNewContext(guard[0]+staticGuard[0]+
  '\nvalidIndex(index) && matchesDashboardGeneration(index)', {
  index:i, state:{data:d}, window:{}, RAW_DATA_BASE:b,
  sourceGeneratedAt:d.meta.generated_at});
assert.equal(check(dash,index),true,'Authorized final KPI rejected');
assert.equal(check(old,index),false,'Research proof self-authorized');
assert.equal(check(dash,index,'./data/legacy/'),false,'Arbitrary frontend URL allowed');
assert.equal(check({...dash,meta:{...dash.meta,generated_at:'2026-10-23T00:00:00Z'}},index),false,
  'Static stale generation was accepted');
console.log('PR100_EXACT_FRONTEND_RELEASE_CONSUMER_PASS');
'''
        proc = subprocess.run(["node", "-e", code, str(app), str(dash),
                               str(original_dash), str(self.root/ROOT)],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def check_workflow_run_metadata(self, *, bad_final_attempt=False):
        # Execute the real GH metadata Python in the existing workflow, offline.
        yaml_data = yaml.safe_load(WORKFLOW.read_text())
        step = next(x for x in yaml_data["jobs"]["deploy-production"]["steps"]
                    if x.get("name", "").startswith("Select approved exact Neon KPI"))
        scripts = re.findall(r"python - <<'PY'\n(.*?)\nPY", step["run"], flags=re.S)
        self.assertEqual(len(scripts), 1)
        metadata = [
            ("artifact.json", {"id": 333, "name": "c6-neon-git-preparation-123-1",
                               "workflow_run": {"id": 123}, "expired": False,
                               "digest": "sha256:" + self.env["C6_ARTIFACT_SHA"]}),
            ("work-a-run.json", {"id": 456, "status": "completed", "conclusion": "success",
                                 "path": ".github/workflows/c6-neon-shadow-isolated-proof.yml"}),
            ("work-a-artifact.json", {"id": 444, "workflow_run": {"id": 456},
                                      "expired": False,
                                      "digest": "sha256:" + self.env["WORK_A_ARTIFACT_SHA"]}),
            ("final-run.json", {"id": 789, "run_attempt": 2 if bad_final_attempt else 1,
                                "head_sha": "f"*40,
                                "status": "completed", "conclusion": "success",
                                "path": ".github/workflows/owner-approved-final-release.yml"}),
            ("final-artifact.json", {"id": 888, "name": "owner-approved-workh-fixture",
                                     "workflow_run": {"id": 789}, "expired": False,
                                     "digest": "sha256:" + self.env["FINAL_ARTIFACT_SHA"]}),
        ]
        for n, value in metadata:
            (self.art/n).write_bytes(encode(value))
        meta_env = os.environ.copy()
        meta_env.update(self.env)
        meta_env.update({
            "C6_ARTIFACT_ID": "333", "WORK_A_RUN_ID": "456",
            "WORK_A_ARTIFACT_ID": "444", "FINAL_RUN_ID": "789",
            "FINAL_ATTEMPT": "1", "FINAL_ARTIFACT_ID": "888",
            "C6_APPROVED_FINAL_HEAD_SHA": "f"*40,
            "C6_APPROVED_FINAL_WORKFLOW": ".github/workflows/owner-approved-final-release.yml",
            "C6_APPROVED_FINAL_NAME": "owner-approved-workh-fixture",
        })
        return subprocess.run([sys.executable, "-c", scripts[0]], cwd=self.root,
                              env=meta_env, capture_output=True, text=True)

    def test_exact_github_artifact_run_receipts(self):
        outcome = self.check_workflow_run_metadata()
        self.assertEqual(outcome.returncode, 0, outcome.stdout + outcome.stderr)

    def test_wrong_final_run_attempt_receipt_fails_closed(self):
        outcome = self.check_workflow_run_metadata(bad_final_attempt=True)
        self.assertNotEqual(outcome.returncode, 0)
        self.assertFalse((self.root/ROOT).exists())

    def test_wrong_final_sha_fails_closed(self):
        files = json.loads(self.env["OWNER_FINAL_FILES_JSON"])
        files[ROOT] = "f" * 64
        self.env["OWNER_FINAL_FILES_JSON"] = json.dumps(files)
        self.env["APPROVED_KPI_SHA"] = "f" * 64
        self.must_block("FINAL_BINDING_OR_MANIFEST_MISMATCH")

    def test_changed_work_a_proof_fails_closed(self):
        v = json.loads(self.proof["verdict.json"])
        v["c2_corpus_sha256"] = "f" * 64
        self.proof["verdict.json"] = encode(v)
        m = json.loads(self.proof["sha256_manifest.json"])
        m["files"]["verdict.json"] = digest(self.proof["verdict.json"])
        self.proof["sha256_manifest.json"] = encode(m)
        self.repack()   # even a newly owner-pinned ZIP cannot break lineage
        self.must_block("WORK_A_C2_RUN_ATTEMPT_OR_CORPUS_MISMATCH")

    def test_invalid_final_manifest_fails_closed(self):
        m = json.loads(self.final_zip["RELEASE_MANIFEST.json"])
        m["source_files"][ROOT] = "c" * 64
        self.final_zip["RELEASE_MANIFEST.json"] = encode(m)
        self.repack()
        self.must_block("FINAL_BINDING_OR_MANIFEST_MISMATCH")

    def test_generation_mismatch_fails_closed(self):
        self.env["APPROVED_GENERATION"] = "2026-10-23T12:00:00+00:00"
        self.must_block("FINAL_SOURCE_OR_GENERATION_MISMATCH")

    def test_changed_c2_attempt_fails_closed(self):
        r = json.loads(self.proof["readback_proof.json"])
        r["capture_run_identity"]["github_run_attempt"] = 2
        self.proof["readback_proof.json"] = encode(r)
        m = json.loads(self.proof["sha256_manifest.json"])
        m["files"]["readback_proof.json"] = digest(self.proof["readback_proof.json"])
        self.proof["sha256_manifest.json"] = encode(m)
        self.repack()
        self.must_block("WORK_A_C2_RUN_ATTEMPT_OR_CORPUS_MISMATCH")

    def test_research_authority_stays_false(self):
        original = json.loads(self.candidate["candidate/" + PATHS["dashboard_data.json"]])
        self.assertFalse(original["meta"]["publication_authority"]["publication_allowed"])
        self.assertFalse(json.loads(self.proof["verdict.json"])["publication_allowed"])
        self.assertFalse(json.loads(self.proof["historical_freshness_gate.json"])["publication_allowed"])

    def test_owner_approval_mandatory(self):
        self.env["C6_RELEASE_OWNER_APPROVED"] = "false"
        self.must_block("OWNER_APPROVAL_REQUIRED")

    def test_missing_final_release_artifact_fails_closed(self):
        (self.art/"final-release-artifact.zip").unlink()
        with self.assertRaises((FileNotFoundError, ValueError)):
            self.run_contract()
        self.assertFalse((self.root/ROOT).exists())

    def test_git_only_default_off_and_no_frontend_mutations(self):
        a = yaml.safe_load(WORKFLOW.read_text())
        steps = a["jobs"]["deploy-production"]["steps"]
        default = next(x for x in steps if "Git-only default" in x.get("name", ""))
        neon = next(x for x in steps if "Select approved exact Neon KPI" in x.get("name", ""))
        self.assertIn("!inputs.neon_release_mode", default["if"])
        self.assertIn("build_preview_historical_daily.py", default["run"])
        self.assertIn("inputs.neon_release_mode", neon["if"])
        self.assertIn("C6_NEON_RELEASE_OWNER_APPROVED", str(neon))
        self.assertIn("c3_final_neon_kpi_contract.py", neon["run"])
        self.assertIn("C6_NEON_APPROVED_FINAL_FILES_JSON", str(neon))
        self.assertNotIn("git push", neon["run"])
        self.assertNotIn("netlify deploy", neon["run"])


if __name__ == "__main__":
    unittest.main()
