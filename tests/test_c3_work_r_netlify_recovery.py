#!/usr/bin/env python3
"""Work R: isolated identity/approval negatives for the exact Netlify recovery."""
import copy
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from scripts import c3_final_neon_kpi_contract as contract

P = contract.RECOVERY_PINS
NOW = datetime(2026, 11, 13, 12, 0, tzinfo=timezone.utc)
BINDING = "a" * 64
KPI = "b" * 64


def fixture(root):
    grant = {
        "schema": "c3-work-l-work-m-netlify-release-v1",
        "decision": "APPROVE_EXACT_NEON_NETLIFY_RELEASE",
        "repository": contract.RECOVERY_REPO,
        "publication_allowed": True, "dst_correction": "OFF",
        "c2_run_id": P["c2_run_id"],
        "work_l_run_id": P["work_l_run_id"],
        "work_m_run_id": P["work_m_run_id"],
        "final_artifact_id": P["work_m_artifact_id"],
        "final_artifact_sha256": P["work_m_artifact_sha256"],
        "binding_sha256": BINDING, "kpi_sha256": KPI,
        "generation": "2026-11-13T09:00:00+00:00",
        "expires_at": (NOW + timedelta(hours=2)).isoformat(),
    }
    env = {
        "C6_WORK_L_RECOVERY_MODE": "true",
        "C6_WORK_L_RECOVERY_ENABLED": "true",
        "C6_RELEASE_OWNER_APPROVED": "true",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_ACTOR": "olegbalakin-cmyk",
        "GITHUB_REPOSITORY": contract.RECOVERY_REPO,
        "APPROVED_BINDING_SHA": BINDING, "OWNER_BINDING_SHA": BINDING,
        "APPROVED_KPI_SHA": KPI,
        "APPROVED_GENERATION": grant["generation"],
        "C6_RECOVERY_OWNER_RELEASE_GRANT_JSON": json.dumps(grant),
        "C6_RUN_ID": str(P["c2_run_id"]), "C6_ATTEMPT": "1",
        "C6_ARTIFACT_ID": str(P["c2_artifact_id"]),
        "C6_ARTIFACT_SHA": P["c2_artifact_sha256"],
        "WORK_A_RUN_ID": str(P["work_l_run_id"]),
        "WORK_A_ARTIFACT_ID": str(P["work_l_artifact_id"]),
        "WORK_A_ARTIFACT_SHA": P["work_l_artifact_sha256"],
        "FINAL_RUN_ID": str(P["work_m_run_id"]), "FINAL_ATTEMPT": "1",
        "FINAL_ARTIFACT_ID": str(P["work_m_artifact_id"]),
        "FINAL_ARTIFACT_SHA": P["work_m_artifact_sha256"],
        "OWNER_FINAL_ARTIFACT_SHA": P["work_m_artifact_sha256"],
        "OWNER_WORK_A_ARTIFACT_SHA": P["work_l_artifact_sha256"],
        "C6_APPROVED_WORK_A_RUN": str(P["work_l_run_id"]),
        "C6_APPROVED_FINAL_RUN": str(P["work_m_run_id"]),
        "C6_APPROVED_FINAL_ATTEMPT": "1",
        "C6_APPROVED_FINAL_ARTIFACT_ID": str(P["work_m_artifact_id"]),
        "C6_APPROVED_FINAL_HEAD_SHA": P["work_m_head_sha"],
        "C6_APPROVED_FINAL_WORKFLOW": ".github/workflows/update-netlify-site.yml",
        "C6_APPROVED_FINAL_NAME": "c6-neon-final-release-43403595621-1",
    }
    runs = [
        ("run.json", "c2", "failure", "main",
         ".github/workflows/update-netlify-site.yml"),
        ("work-a-run.json", "work_l", "success",
         "research-c6-work-l-recover-2026-11-13",
         ".github/workflows/c6-neon-shadow-isolated-proof.yml"),
        ("final-run.json", "work_m", "success",
         "research-c6-work-m-release-recovery-2026-11-13",
         ".github/workflows/update-netlify-site.yml"),
    ]
    for filename, prefix, conclusion, branch, workflow in runs:
        (root / filename).write_text(json.dumps({
            "id": P[prefix + "_run_id"], "run_attempt": 1,
            "head_sha": P[prefix + "_head_sha"], "head_branch": branch,
            "path": workflow, "event": "workflow_dispatch",
            "status": "completed", "conclusion": conclusion,
        }))
    jobs = []
    for name, (job_id, conclusion) in contract.RECOVERY_JOBS.items():
        jobs.append({
            "name": name, "id": job_id, "run_id": P["c2_run_id"],
            "status": "completed", "conclusion": conclusion,
            "steps": [{"name": "ran"}] if name == "update-site" else [],
            "runner_id": 0, "runner_name": "",
            "created_at": "2026-11-12T23:08:37Z",
            "started_at": "2026-11-12T23:08:37Z",
        })
    (root / "c2-jobs.json").write_text(json.dumps({
        "total_count": 4, "jobs": jobs,
    }))
    zip_map = {}
    for metadata, zipname, prefix, name, run_id in (
        ("artifact.json", "artifact.zip", "c2",
         "c2-shadow-inputs-43321997695-1", P["c2_run_id"]),
        ("work-a-artifact.json", "work-a-artifact.zip", "work_l",
         "isolated-neon-shadow-43390770985-1", P["work_l_run_id"]),
        ("final-artifact.json", "final-release-artifact.zip", "work_m",
         "c6-neon-final-release-43403595621-1", P["work_m_run_id"]),
        ("work-m-report-artifact.json", "work-m-report-artifact.zip",
         "work_m_report", "c6-neon-final-prepare-report-43403595621-1",
         P["work_m_run_id"]),
    ):
        raw = ("synthetic " + zipname).encode()
        (root / zipname).write_bytes(raw)
        zip_map[raw] = P[prefix + "_artifact_sha256"]
        (root / metadata).write_text(json.dumps({
            "id": P[prefix + "_artifact_id"], "name": name,
            "digest": "sha256:" + P[prefix + "_artifact_sha256"],
            "expired": False, "workflow_run": {"id": run_id},
        }))
    return env, zip_map


class RecoveryIdentityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.env, self.zip_map = fixture(self.root)
        # Synthetic outer ZIP fixture only; production code uses real SHA-256.
        self.patcher = patch.object(contract, "digest",
                                    side_effect=lambda raw: self.zip_map.get(raw, "0" * 64))
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def check(self):
        return contract.validate_recovery_identity(self.root, self.env, now=NOW)

    def edit(self, file, change):
        path = self.root / file
        obj = json.loads(path.read_text())
        change(obj)
        path.write_text(json.dumps(obj))

    def assert_blocked(self, reason=None):
        with self.assertRaises(ValueError) as error:
            self.check()
        if reason:
            self.assertIn(reason, str(error.exception))

    def test_exact_c2_work_l_work_m_identity_positive(self):
        self.assertEqual(self.check()["decision"], "APPROVE_EXACT_NEON_NETLIFY_RELEASE")

    def test_missing_separate_owner_approval(self):
        self.env.pop("C6_RECOVERY_OWNER_RELEASE_GRANT_JSON")
        self.assert_blocked("NEW_EXACT_OWNER_RELEASE_GRANT_REQUIRED")

    def test_work_m_prepare_only_is_not_owner_grant(self):
        self.env["C6_RECOVERY_OWNER_RELEASE_GRANT_JSON"] = json.dumps({
            "schema": "c6-final-release-prepare-only-work-l-v1",
            "publication_allowed": False})
        self.assert_blocked("RELEASE_GRANT")

    def test_default_off(self):
        self.env["C6_WORK_L_RECOVERY_ENABLED"] = "false"
        self.assert_blocked("APPROVAL")

    def test_wrong_run_id(self):
        self.env["WORK_A_RUN_ID"] = "43390770986"
        self.assert_blocked("EXACT_RECOVERY_INPUT_CHANGED")

    def test_wrong_attempt(self):
        self.edit("final-run.json", lambda x: x.update(run_attempt=2))
        self.assert_blocked("RUN_IDENTITY")

    def test_wrong_workflow_sha(self):
        self.edit("work-a-run.json", lambda x: x.update(head_sha="0" * 40))
        self.assert_blocked("RUN_IDENTITY")

    def test_c2_update_site_not_success(self):
        self.edit("c2-jobs.json", lambda x: x["jobs"][0].update(conclusion="failure"))
        self.assert_blocked("C2_EXACT_JOB_STATUS")

    def test_failed_job_had_runner(self):
        self.edit("c2-jobs.json", lambda x: x["jobs"][1].update(runner_id=123))
        self.assert_blocked("PRERUN_FAILURE")

    def test_replaced_artifact(self):
        (self.root / "work-a-artifact.zip").write_bytes(b"changed")
        self.assert_blocked("ARTIFACT_CHANGED")

    def test_swapped_artifact_metadata(self):
        self.edit("final-artifact.json", lambda x: x.update(id=14025629655))
        self.assert_blocked("ARTIFACT_CHANGED")

    def test_wrong_sha(self):
        self.env["FINAL_ARTIFACT_SHA"] = "0" * 64
        self.assert_blocked("OWNER_PIN_CHANGED")

    def test_expired_grant(self):
        grant = json.loads(self.env["C6_RECOVERY_OWNER_RELEASE_GRANT_JSON"])
        grant["expires_at"] = (NOW - timedelta(minutes=1)).isoformat()
        self.env["C6_RECOVERY_OWNER_RELEASE_GRANT_JSON"] = json.dumps(grant)
        self.assert_blocked("EXPIRED")

    def test_research_cannot_authorize(self):
        grant = json.loads(self.env["C6_RECOVERY_OWNER_RELEASE_GRANT_JSON"])
        grant["publication_allowed"] = False
        self.env["C6_RECOVERY_OWNER_RELEASE_GRANT_JSON"] = json.dumps(grant)
        self.assert_blocked("RELEASE_GRANT")

    def test_legacy_entrypoint_still_present(self):
        import inspect
        body = inspect.getsource(contract.run)
        self.assertIn('original.read("REPORT.json")', body)
        self.assertIn('"ORIGINAL_RESEARCH_NOT_FROZEN"', body)
        self.assertIn('"FINAL_NOT_EXACT_PR95_RELEASE_TRANSFORMATION"', body)

    def test_no_production_mutation_in_identity_check(self):
        before = {x.name: x.read_bytes() for x in self.root.iterdir()}
        self.check()
        self.assertEqual(before, {x.name: x.read_bytes() for x in self.root.iterdir()})


if __name__ == "__main__":
    unittest.main()
