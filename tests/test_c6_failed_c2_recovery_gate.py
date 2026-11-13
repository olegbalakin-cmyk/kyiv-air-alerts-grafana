"""Negative tests for the one-run C2 recovery gate; no network or Neon."""
import copy
import unittest
from scripts import c6_failed_c2_recovery_gate as g

def fixtures():
    run = dict(id=g.RUN, run_attempt=1, workflow_id=g.WORKFLOW_ID,
               path=g.WORKFLOW_PATH, head_branch="main", head_sha=g.WORKFLOW_SHA,
               event="workflow_dispatch", status="completed",
               conclusion="failure", repository={"full_name":g.REPO})
    jobs = []
    for name, (id_, conclusion) in g.JOBS.items():
        jobs.append(dict(id=id_, run_id=g.RUN, run_attempt=1,
                         name=name, conclusion=conclusion, status="completed",
                         runner_id=1234 if name == "update-site"
                         else 0 if name == "c6-neon-six-json-prepare" else None,
                         runner_name="gh-runner" if name == "update-site" else "",
                         steps=[{"conclusion": "success"}] * 49
                         if name == "update-site" else [],
                         created_at="2026-11-12T23:08:37Z",
                         started_at="2026-11-12T23:08:37Z",
                         completed_at="2026-11-12T23:08:39Z"))
    artifact = dict(id=g.ARTIFACT_ID, name=g.ARTIFACT_NAME,
                    expired=False, digest="sha256:" + g.OUTER_SHA,
                    workflow_run={"id":g.RUN, "head_sha":g.WORKFLOW_SHA,
                                  "head_branch":"main"})
    return run, {"total_count":4, "jobs":jobs}, artifact

class RecoveryGateTest(unittest.TestCase):
    def setUp(self):
        self.run, self.jobs, self.artifact = fixtures()

    def assert_blocked(self, reason):
        with self.assertRaisesRegex(g.RecoveryBlocked, reason):
            g.verify_metadata(self.run, self.jobs, self.artifact)

    def test_exact_job_only_recovery(self):
        self.assertEqual(len(g.verify_metadata(self.run, self.jobs, self.artifact)), 4)

    def test_wrong_run_id(self):
        self.run["id"] += 1
        self.assert_blocked("PINNED_C2")

    def test_attempt_two_not_allowed(self):
        self.run["run_attempt"] = 2
        self.assert_blocked("PINNED_C2")

    def test_wrong_workflow_sha(self):
        self.run["head_sha"] = "a"*40
        self.assert_blocked("PINNED_C2")

    def test_overall_success_is_not_this_recovery(self):
        self.run["conclusion"] = "success"
        self.assert_blocked("PINNED_C2")

    def test_unapproved_job_also_failed(self):
        self.jobs["jobs"][2]["conclusion"] = "failure"
        self.assert_blocked("PINNED_JOB")

    def test_c2_failed(self):
        self.jobs["jobs"][0]["conclusion"] = "failure"
        self.assert_blocked("PINNED_JOB")

    def test_c6_runner_was_assigned(self):
        self.jobs["jobs"][1]["runner_id"] = 223
        self.assert_blocked("C6_FAILURE_MAY_HAVE_EXECUTED")

    def test_c6_steps_executed(self):
        self.jobs["jobs"][1]["steps"] = [{"conclusion":"failure"}]
        self.assert_blocked("C6_FAILURE_MAY_HAVE_EXECUTED")

    def test_release_job_executed(self):
        self.jobs["jobs"][2]["steps"] = [{"conclusion":"success"}]
        self.assert_blocked("OTHER_JOB")

    def test_extra_job_rejected(self):
        self.jobs["jobs"].append({"name":"unapproved"})
        self.jobs["total_count"] += 1
        self.assert_blocked("UNEXPECTED_C2_JOB_SET")

    def test_wrong_job_attempt(self):
        self.jobs["jobs"][1]["run_attempt"] = 2
        self.assert_blocked("PINNED_JOB")

    def test_missing_original_artifact(self):
        self.artifact["id"] = 1
        self.assert_blocked("IMMUTABLE_C2")

    def test_artifact_expired(self):
        self.artifact["expired"] = True
        self.assert_blocked("IMMUTABLE_C2")

    def test_wrong_artifact_digest(self):
        self.artifact["digest"] = "sha256:"+"0"*64
        self.assert_blocked("IMMUTABLE_C2")

    def test_wrong_artifact_source_run(self):
        self.artifact["workflow_run"]["id"] = 123
        self.assert_blocked("IMMUTABLE_C2")

    def test_wrong_repository(self):
        self.run["repository"]["full_name"] = "other/repo"
        self.assert_blocked("PINNED_C2")

    def test_writer_has_no_runner(self):
        self.jobs["jobs"][0]["runner_id"] = 0
        self.assert_blocked("C2_UPDATER_DID_NOT_FINISH")

    def test_writer_step_failed(self):
        self.jobs["jobs"][0]["steps"][0]["conclusion"] = "failure"
        self.assert_blocked("C2_UPDATER_DID_NOT_FINISH")

    def test_outer_bytes_fail_closed(self):
        with self.assertRaisesRegex(g.RecoveryBlocked, "OUTER_ZIP_SHA_MISMATCH"):
            g.verify_outer(b"definitely-not-an-approved-archive")

if __name__ == "__main__":
    unittest.main()
