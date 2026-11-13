"""Short, isolated Work K tests: final bytes before Netlify/Git, default OFF."""
import copy
import hashlib
import json
import tempfile
import unittest
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import yaml
from scripts import c6_neon_final_prepare as prep
from scripts import c6_neon_git_candidate as candidate
from scripts import c6_neon_one_shot_publisher as publisher

from test_c6_neon_release_binding import FinalBindingTests


def encode(x):
    return (json.dumps(x, sort_keys=True) + "\n").encode()


def zip_items(path, items):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, raw in sorted(items.items()):
            z.writestr(name, raw)


class WorkK(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        base = FinalBindingTests("test_positive_contract_and_no_research_mutation")
        base.setUp()
        self.addCleanup(base.doCleanups)
        self.fixture = base
        self.now = datetime.now(timezone.utc)
        self.generation = base.dash["meta"]["generated_at"]
        self.report = base.report.copy()
        self.report["files"] = base.report["files"].copy()
        (base.prepared/"REPORT.json").write_bytes(encode(self.report))
        self.c2 = {"id": 123, "run_attempt": 1, "head_sha": "b"*40,
                   "status": "completed", "conclusion": "success",
                   "path": prep.C2_WORKFLOW, "event": "schedule"}
        self.work = {"id": 456, "run_attempt": 1, "head_sha": "d"*40,
                     "status": "completed", "conclusion": "success",
                     "path": prep.WORK_A_WORKFLOW, "event": "workflow_dispatch"}
        self.code = "f"*40
        self.receipt = {
            "schema": prep.SCHEMA, "decision": prep.DECISION,
            "repository": prep.REPO, "publication_allowed": False,
            "global_cutover": "NO", "dst_correction": "OFF",
            "prepare_code_sha": self.code, "release_id": "release-workk-offline-01",
            "expires_at": (self.now+timedelta(hours=2)).isoformat(),
            "c2_run_id": 123, "c2_run_attempt": 1, "c2_head_sha": "b"*40,
            "work_a_run_id": 456, "work_a_run_attempt": 1,
            "work_a_head_sha": "d"*40, "c2_input_sha": "c"*40,
            "c2_corpus_sha256": "e"*64, "c2_bundle_sha256": "d"*64,
            "neon_branch": "br-bold-mode-b5rub8pq", "expected_cities": 23,
            "generation": self.generation,
        }
        self.work_readback = {
            "capture_run_identity": {"github_run_id": 123, "github_run_attempt": 1,
                                     "workflow_sha": "b"*40, "input_sha": "c"*40},
            "c2_corpus_sha256": "e"*64
        }
        self.work_binding = {"db_branch": "br-bold-mode-b5rub8pq",
                             "corpus_sha256": "e"*64,
                             "city_keys": list(base.cities)}
        self.archives = {}
        self.artifacts = {}
        items = {"REPORT.json": (base.prepared/"REPORT.json").read_bytes()}
        items.update({"candidate/"+p: (base.research/p).read_bytes()
                      for p in candidate.FILES.values()})
        self.make_archive("c2", items, self.c2,
                          "c6-neon-git-preparation-123-1")
        self.make_archive("work_a", {
            "sha256_manifest.json": encode({"schema":"test"}),
            "readback_proof.json": encode(self.work_readback),
            "historical_freshness_binding.json": encode(self.work_binding)
        }, self.work, "isolated-neon-shadow-456-1")
        original = self.root/"source.zip"
        original.write_bytes(b"offline sealed fake C2 used only with mock verification")
        archive_items = {"c2-shadow-inputs.zip": original.read_bytes(),
                         "c2-shadow-inputs.zip.sha256":
                         b"d"*64 + b"  c2-shadow-inputs.zip"}
        self.make_archive("c2_bundle", archive_items, self.c2,
                          "c2-shadow-inputs-123-1")
        self.manifest = {
            "github_run_attempt":1, "corpus_sha256":"e"*64,
            "historical_capture_receipts":{"complete_cities": list(base.cities)}
        }
        self.proof_result = {
            "status":"PASS_SCOPED_PROOF_NO_PUBLICATION",
            "production_publication_allowed":False,
            "city_count":23,
            "candidate_files": {name: self.report["files"][path]
                                for name,path in candidate.FILES.items()}
        }
        self.final = self.root/"final"
        self.audit = self.root/"audit.json"

    def make_archive(self, key, items, run, name):
        archive = self.root/(key+".zip")
        zip_items(archive, items)
        self.archives[key] = archive
        digest = prep.sha(archive)
        self.receipt[key+"_artifact_id"] = {"c2":111,"c2_bundle":222,"work_a":333}[key]
        self.receipt[key+"_artifact_sha256"] = digest
        self.artifacts[key] = {
            "id":self.receipt[key+"_artifact_id"], "name":name,
            "digest":"sha256:"+digest,
            "workflow_run":{"id":run["id"]}, "expired":False}

    def perform(self):
        with patch.object(prep, "verify_archive", return_value=self.manifest):
            with patch.object(prep.proof_gate, "inspect", return_value=self.proof_result):
                return prep.prepare(
                    receipt=self.receipt, c2_run=self.c2, work_a_run=self.work,
                    artifacts=self.artifacts, archives=self.archives,
                    output=self.final, audit=self.audit,
                    actor="olegbalakin-cmyk", run_id=789,
                    run_attempt=1, code_sha=self.code, now=self.now)

    def blocked(self):
        with self.assertRaises((candidate.Blocked, ValueError, KeyError)):
            self.perform()
        self.assertFalse(self.final.exists())

    def test_positive_final_zip_exact_bytes_and_immutable_research(self):
        prior = {k:prep.sha(v) for k,v in self.archives.items()}
        result = self.perform()
        self.assertEqual(len(result["files"]), 6)
        self.assertEqual(len([p for p in self.final.rglob("*") if p.is_file()]), 8)
        self.assertEqual(prep.sha(self.final/"RELEASE_BINDING.json"),
                         result["release_manifest_sha256"])
        self.assertEqual(prep.load(self.audit)["status"],
                         "FINAL_BYTES_PREPARED_NOT_PUBLISHED")
        self.assertFalse(prep.load(self.audit)["publication_allowed"])
        self.assertEqual(prior, {k:prep.sha(v) for k,v in self.archives.items()})
        self.assertFalse(prep.load(self.fixture.research/candidate.FILES["dashboard_data.json"])
                         ["meta"]["publication_authority"]["publication_allowed"])
        self.assertEqual(prep.load(self.final/"candidate"/candidate.FILES["dashboard_data.json"])
                         ["meta"]["publication_authority"]["scope"],
                         "PRODUCTION_NEON_GIT_RELEASE")
        self.assertEqual(result["generation"],self.generation)

    def test_wrong_work_a_sha(self):
        self.receipt["work_a_artifact_sha256"] = "0"*64
        self.blocked()

    def test_wrong_c2_attempt(self):
        self.receipt["c2_run_attempt"] = 2
        self.blocked()

    def test_wrong_c2_run(self):
        self.receipt["c2_run_id"] = 999
        self.blocked()

    def test_wrong_neon_branch(self):
        self.receipt["neon_branch"] = "br-fake-branch"
        self.blocked()

    def test_wrong_corpus(self):
        self.receipt["c2_corpus_sha256"] = "0"*64
        self.blocked()

    def test_wrong_generation(self):
        self.receipt["generation"] = "2026-11-13T20:00:00Z"
        self.blocked()

    def test_missing_owner_approval(self):
        self.receipt.pop("decision")
        self.blocked()

    def test_not_exact_23_city_keys(self):
        self.receipt["expected_cities"] = 22
        self.blocked()

    def test_wrong_research_sha(self):
        self.proof_result["candidate_files"]["dashboard_data.json"] = "0"*64
        self.blocked()

    def test_final_pinned_sha_and_byte_identity(self):
        result = self.perform()
        final_zip = self.root/"approved.zip"
        zip_items(final_zip,{p.relative_to(self.final).as_posix():p.read_bytes()
                             for p in self.final.rglob("*") if p.is_file()})
        approval = {
            "final_release_artifact_id":444,
            "final_release_artifact_sha256":prep.sha(final_zip),
            "final_release_run_attempt":1,
            "final_release_code_sha":self.code,
            "release_manifest_sha256":result["release_manifest_sha256"]
        }
        run = {"id":789,"run_attempt":1,"head_sha":self.code,
               "status":"completed","conclusion":"success","path":prep.C2_WORKFLOW}
        artifact={"id":444,"digest":"sha256:"+prep.sha(final_zip),
                  "workflow_run":{"id":789}, "expired":False,
                  "name":"c6-neon-final-release-789-1"}
        publisher.verify_pinned_final_zip(final_zip,self.final,result,approval,artifact,run)
        approval["final_release_artifact_sha256"]="0"*64
        with self.assertRaisesRegex(candidate.Blocked,"PINNED_FINAL_ZIP_NOT_VERIFIED"):
            publisher.verify_pinned_final_zip(final_zip,self.final,result,approval,artifact,run)
        approval["final_release_artifact_sha256"]=prep.sha(final_zip)
        (self.final/"RELEASE_MANIFEST.json").write_text("{}")
        with self.assertRaisesRegex(candidate.Blocked,"FINAL_RELEASE_NOT_BYTE_IDENTICAL"):
            publisher.verify_pinned_final_zip(final_zip,self.final,result,approval,artifact,run)

    def test_final_run_api_fetch_only_after_publisher_id_and_before_use(self):
        """The final run does not yet exist during prepare-only dispatch."""
        wf = yaml.safe_load(Path(".github/workflows/update-netlify-site.yml").read_text())
        jobs = wf["jobs"]
        prepare = jobs["c6-neon-final-prepare-only"]
        publisher = jobs["c6-neon-owner-gated-git-release"]
        final_api = 'gh api "repos/$GITHUB_REPOSITORY/actions/runs/$FINAL_RUN_ID" > "$root/final-run.json"'
        final_id = 'FINAL_RUN_ID="$(python -c '
        final_consumer = '--final-run "$root/final-run.json"'

        # Recheck ALL steps, not merely the intended evidence-fetch step.
        prep_commands = "\\n".join(str(s.get("run", "")) for s in prepare["steps"])
        publish_commands = "\\n".join(str(s.get("run", "")) for s in publisher["steps"])
        self.assertNotIn(final_api, prep_commands)
        self.assertNotIn("$FINAL_RUN_ID", prep_commands)
        self.assertNotIn("final-run.json", prep_commands)
        self.assertEqual(publish_commands.count(final_api), 1)

        evidence = [step for step in publisher["steps"]
                    if 'FINAL_RUN_ID="$(python -c ' in str(step.get("run", ""))]
        self.assertEqual(len(evidence), 1)
        fetch_step = evidence[0]["run"]
        self.assertIn(final_id, fetch_step)
        self.assertIn(final_api, fetch_step)
        self.assertLess(fetch_step.index(final_id), fetch_step.index(final_api))
        self.assertIn('gh api "repos/$GITHUB_REPOSITORY/actions/runs/$WORK_A_RUN_ID"',
                      fetch_step)
        self.assertLess(fetch_step.index(final_api),
                        fetch_step.index('curl --fail --silent --show-error --location --retry 3'))
        self.assertIn(final_consumer, publish_commands)
        self.assertLess(publish_commands.index(final_api),
                        publish_commands.index(final_consumer))
        self.assertEqual(prepare["permissions"], {"contents": "read", "actions": "read"})
        self.assertFalse(wf[True]["workflow_dispatch"]["inputs"]["c6_final_prepare_only"]["default"])
        self.assertFalse(wf[True]["workflow_dispatch"]["inputs"]["c6_neon_git_release"]["default"])

    def test_workflow_prepare_only_is_exclusive_and_default_off(self):
        path=Path(".github/workflows/update-netlify-site.yml")
        content=path.read_text()
        wf=yaml.safe_load(content)
        inputs=wf[True]["workflow_dispatch"]["inputs"]
        self.assertIs(inputs["c6_final_prepare_only"]["default"],False)
        self.assertIs(inputs["c6_neon_git_release"]["default"],False)
        jobs=wf["jobs"]
        standard=jobs["update-site"]["if"]
        special=jobs["c6-neon-final-prepare-only"]
        publish=jobs["c6-neon-owner-gated-git-release"]["if"]
        self.assertIn("!inputs.c6_final_prepare_only",standard)
        self.assertIn("!inputs.c6_neon_git_release",special["if"])
        self.assertIn("!inputs.c6_final_prepare_only",publish)
        self.assertIn("!inputs.c6_final_prepare_only",
                      jobs["c6-neon-six-json-prepare"]["if"])
        self.assertEqual(special["permissions"],{"contents":"read","actions":"read"})
        for step in special["steps"]:
            self.assertNotIn("git push",str(step.get("run","")).lower())
            self.assertNotIn("netlify deploy",str(step.get("run","")).lower())
            self.assertNotIn("neon_json_shadow_physical_proof",str(step.get("run","")))
        self.assertIn("group: update-netlify-site", content)
        self.assertIn("vars.C6_GIT_ONLY_PUBLISHER_PAUSED != 'true'",content)



class WorkMExactPairContract(unittest.TestCase):
    """Narrow Work L exception cannot weaken normal original-artifact validation."""

    def setUp(self):
        self.fixture = WorkK("test_missing_owner_approval")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.receipt = copy.deepcopy(self.fixture.receipt)
        self.c2 = copy.deepcopy(self.fixture.c2)
        self.work = copy.deepcopy(self.fixture.work)
        self.receipt.pop("c2_artifact_id")
        self.receipt.pop("c2_artifact_sha256")
        self.receipt["schema"] = prep.RECOVERY_SCHEMA
        self.receipt["provenance_contract"] = prep.RECOVERY_CONTRACT
        self.receipt.update(prep.RECOVERY_PINS)
        self.c2.update({
            "id": prep.RECOVERY_PINS["c2_run_id"],
            "run_attempt": prep.RECOVERY_PINS["c2_run_attempt"],
            "head_sha": prep.RECOVERY_PINS["c2_head_sha"],
            "head_branch": "main", "conclusion": "failure",
        })
        self.work.update({
            "id": prep.RECOVERY_PINS["work_a_run_id"],
            "run_attempt": prep.RECOVERY_PINS["work_a_run_attempt"],
            "head_sha": prep.RECOVERY_PINS["work_a_head_sha"],
            "head_branch": "research-c6-work-l-recover-2026-11-13",
        })
        self.jobs = {"total_count": 4, "jobs": []}
        for name, (job_id, conclusion) in prep.RECOVERY_JOB_RESULTS.items():
            self.jobs["jobs"].append({
                "name": name, "id": job_id, "run_id": self.c2["id"],
                "status": "completed", "conclusion": conclusion,
                "runner_id": 0 if name == "c6-neon-six-json-prepare" else 123,
                "runner_name": "" if name == "c6-neon-six-json-prepare" else "runner",
                "steps": [] if name != "update-site" else [{"name": "ran"}],
                "created_at": "2026-11-12T23:08:37Z",
                "started_at": "2026-11-12T23:08:37Z",
            })

    def check(self):
        prep.validate_receipt(
            self.receipt, self.c2, self.work, actor="olegbalakin-cmyk",
            run_id=789, run_attempt=1, code_sha=self.fixture.code,
            now=self.fixture.now, c2_jobs=self.jobs)

    def test_exact_recovery_receipt_and_prerun_shape(self):
        self.check()

    def test_recovery_wrong_c2_run_id_blocks(self):
        self.receipt["c2_run_id"] += 1
        with self.assertRaisesRegex(candidate.Blocked, "UNAPPROVED_WORK_L_RECOVERY_PAIR|PINNED_RUN_IDENTITY_MISMATCH"):
            self.check()

    def test_recovery_wrong_work_l_sha_blocks(self):
        self.receipt["work_a_artifact_sha256"] = "0" * 64
        with self.assertRaisesRegex(candidate.Blocked, "UNAPPROVED_WORK_L_RECOVERY_PAIR"):
            self.check()

    def test_recovery_original_c2_artifact_claim_blocks(self):
        self.receipt["c2_artifact_id"] = 111
        with self.assertRaisesRegex(candidate.Blocked, "UNAPPROVED_WORK_L_RECOVERY_PAIR"):
            self.check()

    def test_recovery_prep_failure_with_runner_blocks(self):
        failed = next(j for j in self.jobs["jobs"]
                      if j["name"] == "c6-neon-six-json-prepare")
        failed["runner_id"] = 122
        failed["steps"] = [{"name": "ran"}]
        with self.assertRaisesRegex(candidate.Blocked, "C2_FAILED_JOB_WAS_NOT_PRERUN"):
            self.check()

    def test_recovery_release_job_not_skipped_blocks(self):
        release = next(j for j in self.jobs["jobs"]
                       if j["name"] == "c6-neon-owner-gated-git-release")
        release["conclusion"] = "success"
        with self.assertRaisesRegex(candidate.Blocked, "C2_JOB_NOT_PINNED"):
            self.check()

    def test_recovery_missing_owner_gate_blocks(self):
        self.receipt.pop("decision")
        with self.assertRaisesRegex(candidate.Blocked, "OWNER_PREPARE_ONLY_APPROVAL_REQUIRED"):
            self.check()

    def test_old_schema_still_rejects_failed_c2(self):
        self.receipt["schema"] = prep.SCHEMA
        with self.assertRaisesRegex(candidate.Blocked, "PINNED_RUN_IDENTITY_MISMATCH"):
            self.check()

    def test_prepare_workflow_default_off_and_recovery_explicit(self):
        wf = yaml.safe_load(
            Path(".github/workflows/update-netlify-site.yml").read_text())
        inputs = wf[True]["workflow_dispatch"]["inputs"]
        self.assertIs(inputs["c6_final_prepare_only"]["default"], False)
        self.assertIs(inputs["c6_neon_git_release"]["default"], False)
        job = wf["jobs"]["c6-neon-final-prepare-only"]
        script = "\\n".join(str(step.get("run", "")) for step in job["steps"])
        self.assertIn("RECOVERY_SCHEMA", script)
        self.assertIn("RECOVERY_PINS", script)
        self.assertIn("--c2-jobs", script)
        self.assertNotIn("git push", script)
        self.assertNotIn("netlify deploy", script)
        self.assertEqual(job["permissions"], {"contents": "read", "actions": "read"})


if __name__ == "__main__":
    unittest.main()
