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
if __name__=="__main__":unittest.main(verbosity=2)
