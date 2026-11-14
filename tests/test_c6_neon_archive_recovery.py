"""Exact failed-run archive recovery fail-closed tests; no Neon/HTTP/push."""
import copy
import json
import unittest
from scripts import c6_neon_auto_git as auto
from scripts import c6_neon_archive_recovery as recovery


def fixture():
    p = auto.RECOVERY_PINS
    run = {"id": p["run_id"], "run_attempt": 1,
           "head_sha": p["workflow_sha"], "head_branch": "main",
           "path": ".github/workflows/update-netlify-site.yml",
           "status": "completed", "conclusion": "failure",
           "repository": {"full_name": auto.REPOSITORY}}
    jobs = {"total_count": 5, "jobs": []}
    for name, conclusion in auto.RECOVERY_JOB_CONCLUSIONS.items():
        j = {"name": name, "run_id": p["run_id"], "status": "completed",
             "conclusion": conclusion}
        if name == "update-site":
            j["steps"] = [
                {"name": n, "conclusion": c}
                for n, c in [
                    ("Validate verified UkraineAlarm bridge checkpoint", "success"),
                    ("Run multicity canonical DB shadow", "success"),
                    ("Upload C2 canonical publication status", "success"),
                    ("Export verified same-run C2 shadow bundle", "success"),
                    ("Upload verified C2 shadow inputs", "success"),
                    ("Freeze same-run C2 checkpoint delta (no commit/push)", "failure"),
                    ("Upload same-run C2 delta for one Git-only commit", "skipped"),
                    ("Commit updated production data and verified UkraineAlarm bridge checkpoint", "skipped"),
                ]]
        jobs["jobs"].append(j)
    artifacts = {
        "bundle": {"id": p["bundle_artifact_id"],
                   "name": "c2-shadow-inputs-43523629106-1",
                   "digest": "sha256:" + p["bundle_outer_sha256"],
                   "workflow_run": {"id": p["run_id"]}, "expired": False},
        "status": {"id": p["status_artifact_id"],
                   "name": "c2-publication-status-43523629106-1",
                   "digest": "sha256:" + p["status_outer_sha256"],
                   "workflow_run": {"id": p["run_id"]}, "expired": False},
    }
    manifest = {
        "github_run_id": p["run_id"], "github_run_attempt": 1,
        "workflow_sha": p["workflow_sha"], "input_sha": p["input_sha"],
        "db_branch": auto.NEON_BRANCH, "db_endpoint": p["db_endpoint"],
        "canonical_run_id": p["writer_run_uuid"],
        "corpus_sha256": p["corpus_sha256"],
        "historical_capture_receipts": {
            "complete_cities": ["city" + str(n) for n in range(23)]},
    }
    status = {"canonical_persistence_status": "NEON_SUCCEEDED",
              "canonical_db_commit": "CONFIRMED",
              "canonical_receipt_validated": True,
              "input_sha": p["input_sha"], "workflow_sha": p["workflow_sha"]}
    receipt = {"run_id": p["writer_run_uuid"], "status": "succeeded",
               "persistence_status": "persisted", "workflow_sha": p["workflow_sha"],
               "input_sha": p["input_sha"], "corpus_sha256": p["corpus_sha256"],
               "db_branch": auto.NEON_BRANCH, "canonical_episode_count": 33450,
               "episodes_inserted": 6, "episodes_updated": 0,
               "city_count": 23, "production_output_mutation": False}
    return [run, jobs, artifacts, manifest, status, receipt]


class ExactRecoveryTests(unittest.TestCase):
    def check(self, f):
        return auto.verify_exact_failed_c2_archive(*f)

    def test_pinned_positive_only(self):
        self.assertEqual(self.check(fixture())["status"],
                         "EXACT_FAILED_C2_ARCHIVE_PASS")

    def test_failed_run_never_generalized(self):
        for idx, field, changed in [
            (0,"id",43510482714), (0,"conclusion","success"),
            (0,"head_sha","a"*40), (0,"run_attempt",2),
            (0,"path","different.yml"),
            (3,"corpus_sha256","0"*64),
            (3,"db_branch","br-other"),
            (3,"github_run_id",43510482714),
            (4,"canonical_persistence_status","NEON_FAILED"),
            (4,"canonical_receipt_validated",False),
            (5,"canonical_episode_count",33449),
            (5,"production_output_mutation",True)]:
            with self.subTest(field=field):
                f=fixture()
                f[idx][field]=changed
                with self.assertRaises(auto.Blocked):
                    self.check(f)

    def test_no_job_or_artifact_substitution(self):
        for edit in ("missing_job", "prepare_succeeded", "wrong_artifact",
                     "wrong_digest", "stale_artifact", "wrong_capture_step"):
            with self.subTest(edit=edit):
                f=fixture()
                if edit=="missing_job":
                    f[1]["jobs"].pop()
                elif edit=="prepare_succeeded":
                    for job in f[1]["jobs"]:
                        if job["name"]=="c6-neon-six-json-prepare":
                            job["conclusion"]="success"
                elif edit=="wrong_artifact":
                    f[2]["bundle"]["id"]=0
                elif edit=="wrong_digest":
                    f[2]["status"]["digest"]="sha256:"+"f"*64
                elif edit=="stale_artifact":
                    f[2]["bundle"]["expired"]=True
                else:
                    f[1]["jobs"][0]["steps"][5]["conclusion"]="success"
                with self.assertRaises(auto.Blocked):
                    self.check(f)

    def test_reconstruction_never_publishes(self):
        self.assertEqual(recovery.NAMES, ("alerts_combined.json",
            "dashboard_data.json", "site_derived.json",
            "kyiv_threat_mix.json", "sevastopol_events.json"))
        self.assertEqual(auto.RECOVERY_PINS["run_id"],43523629106)
        with open(".github/workflows/c6-neon-shadow-isolated-proof.yml") as f:
            workflow=f.read()
        assert "inputs.archive_recovery" in workflow
        assert "c6-neon-shadow-readonly" in workflow
        assert "persist-credentials: false" in workflow
        assert "--status-outer evidence/14085756162.zip" in workflow
        assert "c6_neon_publication_gate" in workflow
        assert "--c2-run-id 43523629106" in workflow
        assert "c6_neon_release_binding import release_candidate" in workflow
        assert "netlify deploy" not in workflow.lower()
        assert "git push" not in workflow.lower()


if __name__=="__main__":
    unittest.main()
