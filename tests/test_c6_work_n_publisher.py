"""Work N fail-closed and exact branch routing; no network or Git publication."""
import copy
import unittest
from pathlib import Path
from datetime import datetime, timezone, timedelta
from scripts import c6_neon_one_shot_publisher as p
from scripts import c6_neon_final_prepare as m
from scripts import c6_neon_git_candidate as candidate

REPO=m.REPO
class WorkN(unittest.TestCase):
    def setUp(self):
        now=datetime.now(timezone.utc)
        self.approval={"schema":p.WORK_N_SCHEMA,"decision":p.APPROVAL,
          "global_cutover":"OWNER_SEPARATELY_APPROVED","dst_correction":"OFF",
          "repository":REPO,"expires_at":(now+timedelta(hours=1)).isoformat(),
          "provenance_contract":m.RECOVERY_CONTRACT}
        self.c2={"id":m.RECOVERY_PINS["c2_run_id"],
          "head_sha":m.RECOVERY_PINS["c2_head_sha"],"run_attempt":1,
          "status":"completed","conclusion":"failure","path":p.GH_WORKFLOW,
          "event":"workflow_dispatch","head_branch":"main"}
        self.work={"id":m.RECOVERY_PINS["work_a_run_id"],
          "head_sha":m.RECOVERY_PINS["work_a_head_sha"],"run_attempt":1,
          "status":"completed","conclusion":"success","path":m.WORK_A_WORKFLOW,
          "event":"workflow_dispatch",
          "head_branch":"research-c6-work-l-recover-2026-11-13"}
        self.final={"id":p.WORK_M_RUN_ID,"head_sha":p.WORK_M_CODE_SHA,
          "run_attempt":1,"status":"completed","conclusion":"success",
          "path":p.GH_WORKFLOW,"event":"workflow_dispatch",
          "head_branch":"research-c6-work-m-release-recovery-2026-11-13"}
        self.jobs={"total_count":4,"jobs":[{
          "id":id,"name":name,"run_id":self.c2["id"],"conclusion":conclusion,
          "status":"completed","steps":[] if name!="update-site" else [{"name":"writer"}],
          "runner_id":0,"runner_name":"","started_at":"x","created_at":"x"}
          for name,(id,conclusion) in m.RECOVERY_JOB_RESULTS.items()]}
        for prefix,run in (("c2",self.c2),("work_a",self.work),
                           ("final_release",self.final)):
            self.approval[prefix+"_run_id"]=run["id"]
            self.approval[prefix+"_run_attempt"]=1
            self.approval[prefix+"_head_sha"]=run["head_sha"]

    def check(self):
        return p.validate_work_m(self.approval,{},Path("."),Path("."),
          c2_run=self.c2,work_a_run=self.work,final_run=self.final,
          c2_artifact={},work_a_artifact={},final_artifact={},
          report_artifact={},c2_jobs=self.jobs,repository=REPO)

    def test_wrong_schema_blocks_before_io(self):
        self.approval["schema"]=p.RECEIPT_SCHEMA
        with self.assertRaisesRegex(candidate.Blocked,"SEPARATE_WORK_N"):
            self.check()

    def test_prepare_only_grant_cannot_publish(self):
        self.approval["decision"]=m.DECISION
        with self.assertRaisesRegex(candidate.Blocked,"SEPARATE_WORK_N"):
            self.check()

    def test_original_c2_preparation_artifact_cannot_be_faked(self):
        self.approval["candidate_artifact_id"]=13991878472
        with self.assertRaisesRegex(candidate.Blocked,"MISSING_ORIGINAL"):
            self.check()

    def test_original_c2_overall_failure_must_remain_pinned(self):
        self.c2["conclusion"]="success"
        with self.assertRaisesRegex(candidate.Blocked,"EXACT_WORK_N_RUN"):
            self.check()

    def test_work_m_exact_sha_must_match(self):
        self.final["head_sha"]="a"*40
        with self.assertRaisesRegex(candidate.Blocked,"EXACT_WORK_N_RUN"):
            self.check()

    def test_failed_c2_job_cannot_have_runner_steps(self):
        self.jobs["jobs"][1]["steps"]=[{"name":"bad"}]
        with self.assertRaisesRegex(candidate.Blocked,"C2_FAILURE_NOT_KNOWN"):
            self.check()

    def test_distinct_release_grant_required_even_with_work_m(self):
        self.approval["expires_at"]="2020-01-01T00:00:00Z"
        with self.assertRaisesRegex(candidate.Blocked,"GRANT_EXPIRED"):
            self.check()

    def test_existing_legacy_path_not_removed(self):
        source=Path("scripts/c6_neon_one_shot_publisher.py").read_text()
        self.assertIn("decision = validate(",source)
        self.assertIn("verify_pinned_final_zip(",source)
        self.assertIn("release_binding.verify_final(approval, final)",source)
        self.assertIn("sha = publish(",source)

    def test_workflow_only_routes_work_m_under_owner_gate(self):
        workflow=Path(".github/workflows/update-netlify-site.yml").read_text()
        self.assertIn('C6_NEON_GIT_RELEASE_ENABLED',workflow)
        self.assertIn('C6_GIT_ONLY_PUBLISHER_PAUSED',workflow)
        self.assertIn('environment: c6-neon-git-release',workflow)
        self.assertIn('c6-approved-one-shot-neon-git-work-m-v1',workflow)
        self.assertIn('14025729121',workflow)
        self.assertIn('--c2-jobs "$root/c2-jobs.json"',workflow)
        self.assertIn('if: ${{ github.event_name == \'workflow_dispatch\' && inputs.c6_neon_git_release && !inputs.c6_final_prepare_only }}',workflow)
        self.assertIn('cancel-in-progress: false',workflow)

if __name__=="__main__": unittest.main()
