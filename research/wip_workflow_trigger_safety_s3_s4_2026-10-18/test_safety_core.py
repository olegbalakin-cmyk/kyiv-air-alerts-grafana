import unittest
from safety_core import parse, evaluate, event_context, can_run, run_event, flag, UNKNOWN
class SafetyCoreTests(unittest.TestCase):
 def wf(self,ifval):
  return parse("name: test\non:\n  workflow_dispatch:\njobs:\n  monitor:\n    if: "+ifval+"\n    runs-on: ubuntu-latest\n")
 def test_candidate_hold(self):
  self.assertEqual(can_run(self.wf("false"),default_registered=True)["executable"],[])
 def test_unguarded_positive(self):
  self.assertEqual(can_run(self.wf("true"),default_registered=True)["executable"],["monitor"])
 def test_missing_workflow(self):
  self.assertFalse(can_run(None,default_registered=True)["eligible"])
 def test_unregistered(self):
  self.assertFalse(can_run(self.wf("true"),default_registered=False)["eligible"])
 def test_unsupported_fail_closed(self):
  self.assertEqual(flag(evaluate("hashFiles('x') == 'y'",event_context())[0]),"UNKNOWN")
 def test_sha_condition(self):
  ctx=event_context("workflow_run",head_sha="sha1")
  self.assertTrue(evaluate("github.event.workflow_run.head_sha == 'sha1' && github.event.workflow_run.conclusion == 'success'",ctx)[0])
  ctx=event_context("workflow_run",head_sha="sha2")
  self.assertFalse(evaluate("github.event.workflow_run.head_sha == 'sha1' && github.event.workflow_run.conclusion == 'success'",ctx)[0])
 def test_conclusion_mutation(self):
  self.assertFalse(evaluate("github.event.workflow_run.conclusion == 'success'",event_context("workflow_run",conclusion="failure"))[0])
 def test_always_aggregate(self):
  w=parse("name: aggregate\non:\n  workflow_run:\n    workflows: [upstream]\n    types: [completed]\njobs:\n  plan:\n    if: false\n    runs-on: ubuntu-latest\n  finalize:\n    needs: plan\n    if: always()\n    runs-on: ubuntu-latest\n")
  self.assertEqual(run_event(w,"upstream",{"head_branch":"test","head_sha":"a","conclusion":"failure"})["jobs_executable"],["finalize"])
  w["jobs"]["finalize"]["if"]="false"
  self.assertEqual(run_event(w,"upstream",{"head_branch":"test","head_sha":"a","conclusion":"failure"})["jobs_executable"],[])
 def test_default_absent(self):
  self.assertEqual(run_event(None,"upstream",{},default_present=False)["state"],"DOWNSTREAM_BLOCKED")
 def test_depth_four(self):
  w=parse("name: downstream\non:\n  workflow_run:\n    workflows: [upstream]\n    types: [completed]\njobs:\n  monitor:\n    runs-on: ubuntu-latest\n")
  self.assertEqual(run_event(w,"upstream",{"head_branch":"test","head_sha":"a","conclusion":"success"},depth=4)["state"],"DOWNSTREAM_BLOCKED")

 def test_actual_outcome_not_assumed_success(self):
  w=parse("name: outcomes\non:\n  workflow_dispatch:\njobs:\n  first:\n    runs-on: ubuntu-latest\n  second:\n    needs: first\n    runs-on: ubuntu-latest\n")
  from safety_core import job_matrix
  ctx=event_context()
  jobs=job_matrix(w,ctx)
  self.assertEqual(jobs["first"]["state"],"JOB_EXECUTABLE")
  self.assertEqual(jobs["first"]["modeled_job_result"],"unknown")
  self.assertEqual(jobs["second"]["state"],"UNKNOWN")
  self.assertEqual(job_matrix(w,ctx,job_results={"first":"success"})["second"]["state"],"JOB_EXECUTABLE")
  for result in ("failure","cancelled","skipped"):
   self.assertEqual(job_matrix(w,ctx,job_results={"first":result})["second"]["state"],"JOB_SKIPPED")
 def test_failure_and_cancelled_needs(self):
  from safety_core import job_matrix
  w=parse("name: outcomes\non:\n  workflow_dispatch:\njobs:\n  first:\n    runs-on: ubuntu-latest\n  failed:\n    needs: first\n    if: failure()\n    runs-on: ubuntu-latest\n  cancelled:\n    needs: first\n    if: cancelled()\n    runs-on: ubuntu-latest\n  aggregate:\n    needs: first\n    if: always()\n    runs-on: ubuntu-latest\n")
  for mode,which in (("failure","failed"),("cancelled","cancelled")):
   r=job_matrix(w,event_context(),job_results={"first":mode})
   self.assertEqual(r[which]["state"],"JOB_EXECUTABLE")
   self.assertEqual(r["aggregate"]["state"],"JOB_EXECUTABLE")
 def test_real_pinned_downstream(self):
  from safety_core import source,run_event,PIN
  wf=source("origin/main",".github/workflows/live-due-orchestration-readback.yml")
  self.assertIsNotNone(wf)
  def call(sha,conclusion):
   return run_event(wf,"Monitor explosion metric WIP",{"head_branch":"multicity-wip-2026-09-16","head_sha":sha,"conclusion":conclusion})
  good=call(PIN,"success")
  self.assertEqual(good["state"],"EVENT_CREATED")
  self.assertTrue(good["jobs_executable"])
  for sha,conclusion in ((PIN,"failure"),(PIN,"cancelled"),(PIN,"skipped"),(PIN,None),("wrong","success")):
   self.assertFalse(call(sha,conclusion)["jobs_executable"])
 def test_actual_main_vs_original_wip(self):
  from safety_core import source,can_run
  m=source("origin/main",".github/workflows/explosion-monitor-wip.yml")
  old=source("1a8b57553ba66319db326d65080ade93ae6ca01c",".github/workflows/explosion-monitor-wip.yml")
  protected=can_run(m,default_registered=True)
  exposed=can_run(old,default_registered=True)
  self.assertNotIn("monitor",protected["executable"])
  self.assertIn("monitor",exposed["executable"])
 def test_real_guarded_candidate(self):
  from safety_core import source,can_run
  w=source("HEAD",".github/workflows/explosion-monitor-wip.yml")
  self.assertFalse(can_run(w,default_registered=True)["executable"])
 def test_dispatch_without_trigger(self):
  self.assertEqual(can_run(parse("name: a\non:\n  push:\njobs:\n  x:\n    runs-on: ubuntu-latest\n"),default_registered=True)["reason"],"selected_workflow_has_no_dispatch")
 def test_no_default_run_consumer(self):
  w=parse("name: x\non:\n  workflow_run:\n    workflows: [old]\n    types: [completed]\njobs:\n  x:\n    runs-on: ubuntu-latest\n")
  self.assertEqual(run_event(w,"old",{},default_present=False)["state"],"DOWNSTREAM_BLOCKED")
 def test_wrong_upstream_name(self):
  w=parse("name: x\non:\n  workflow_run:\n    workflows: [old]\n    types: [completed]\njobs:\n  x:\n    runs-on: ubuntu-latest\n")
  self.assertEqual(run_event(w,"other",{"head_branch":"x"},default_present=True)["state"],"EVENT_NOT_CREATED")
 def test_guard_mutation(self):
  import copy
  a=self.wf("false")
  self.assertEqual(can_run(a,default_registered=True)["executable"],[])
  a["jobs"]["monitor"].pop("if")
  self.assertEqual(can_run(a,default_registered=True)["executable"],["monitor"])
 def test_sha_mutation(self):
  from safety_core import source,run_event,PIN
  import copy
  w=source("origin/main",".github/workflows/live-due-orchestration-readback.yml")
  old=run_event(w,"Monitor explosion metric WIP",{"head_branch":"multicity-wip-2026-09-16","head_sha":PIN,"conclusion":"success"})
  self.assertTrue(old["jobs_executable"])
  wf=copy.deepcopy(w)
  for j in wf["jobs"].values():
   if isinstance(j.get("if"),str):j["if"]=j["if"].replace(PIN,"a"*40)
  changed=run_event(wf,"Monitor explosion metric WIP",{"head_branch":"multicity-wip-2026-09-16","head_sha":PIN,"conclusion":"success"})
  self.assertFalse(changed["jobs_executable"])

if __name__=="__main__":unittest.main(verbosity=2)
