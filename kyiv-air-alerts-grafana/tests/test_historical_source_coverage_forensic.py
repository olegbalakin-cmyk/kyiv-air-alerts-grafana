import importlib.util,json,subprocess,sys,tempfile,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
SPEC=importlib.util.spec_from_file_location('forensic',HERE.parent/'scripts'/'audit_historical_source_coverage.py');M=importlib.util.module_from_spec(SPEC);sys.modules[SPEC.name]=M;SPEC.loader.exec_module(M)

def sh(cwd,*args):
 p=subprocess.run(list(args),cwd=cwd,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 if p.returncode:raise RuntimeError(p.stderr)
 return p.stdout.strip()

class Controls(unittest.TestCase):
 def test_complete_narrow_is_partial_rule(self):self.assertTrue(M.has('status complete; narrow search',M.PARTIAL));self.assertFalse(M.has('status complete; narrow search',M.FULL))
 def test_inaccessible_is_blocker(self):self.assertTrue(M.has('source input inaccessible',M.BLOCK))
 def test_connector_size_limit_is_blocker(self):self.assertTrue(M.has('source blob exceeds its size limit',M.BLOCK))
 def test_retention_contract_is_not_full_ledger(self):self.assertTrue(M.has('keep only numerator-relevant evidence; do not include all rejected candidates',M.RETNEG))
 def test_denominator_search_dimensions_separate(self):self.assertNotEqual('PROVEN_COMPLETE','PARTIAL')
 def test_kherson_fixture_passes(self):
  r={'canonical_coverage':'PROVEN_COMPLETE','search_coverage':'PARTIAL','result_retention':'NOT_PROVEN','strict_adjudication':'PROVEN_COMPLETE','canonical_episodes':1412,'original_strict':9,'current_strict':2,'slices':[{'part':'P1','search_coverage':'PARTIAL'},{'part':'P2','search_coverage':'BLOCKED'},{'part':'P3','search_coverage':'PARTIAL'}]};self.assertTrue(M.calibrate(r)[0])
 def test_kherson_wrong_p2_fails(self):
  r={'canonical_coverage':'PROVEN_COMPLETE','search_coverage':'PARTIAL','result_retention':'NOT_PROVEN','strict_adjudication':'PROVEN_COMPLETE','canonical_episodes':1412,'original_strict':9,'current_strict':2,'slices':[{'part':'P1','search_coverage':'PARTIAL'},{'part':'P2','search_coverage':'PARTIAL'},{'part':'P3','search_coverage':'PARTIAL'}]};self.assertFalse(M.calibrate(r)[0])

class History(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.repo=Path(self.t.name);sh(self.repo,'git','init','-q');sh(self.repo,'git','config','user.email','qa@example.test');sh(self.repo,'git','config','user.name','QA')
 def tearDown(self):self.t.cleanup()
 def test_deleted_blob_history_lookup(self):
  p=self.repo/'research/kherson_old_blind_qa.json';p.parent.mkdir();p.write_text('{"city":"kherson","decision":"CONFIRMED_FALSE_NEGATIVE","failure_stage":"SOURCE_NOT_COVERED"}\n');sh(self.repo,'git','add','.');sh(self.repo,'git','commit','-qm','add');p.unlink();sh(self.repo,'git','add','-u');sh(self.repo,'git','commit','-qm','delete');rows=M.history(self.repo,'kherson');self.assertTrue(any('SOURCE_NOT_COVERED' in x[2] for x in rows))
 def test_provenance_returns_historical_commit(self):
  p=self.repo/'research/kherson_source_recovery.json';p.parent.mkdir();p.write_text('{"city":"kherson"}');sh(self.repo,'git','add','.');sh(self.repo,'git','commit','-qm','add');sha=sh(self.repo,'git','rev-parse','HEAD:research/kherson_source_recovery.json');commit,ref=M.provenance(self.repo,sha);self.assertNotEqual(commit,'UNKNOWN')

class Aggregation(unittest.TestCase):
 def test_order_and_manifest(self):
  with tempfile.TemporaryDirectory() as td:
   inp=Path(td)/'in';out=Path(td)/'out';inp.mkdir()
   for c in M.CITIES:
    r={'city':c,'canonical_episodes':1412 if c=='kherson' else 100,'original_strict':9 if c=='kherson' else 5,'current_strict':2 if c=='kherson' else 5,'canonical_coverage':'PROVEN_COMPLETE','search_coverage':'PARTIAL','result_retention':'NOT_PROVEN','strict_adjudication':'PROVEN_COMPLETE','blind_qa_confirmed_misses':0,'source_not_covered_misses':0,'reaudit_needed':True,'recommended_scope':'bounded','slices':[{'part':'P1','search_coverage':'PARTIAL'},{'part':'P2','search_coverage':'BLOCKED'},{'part':'P3','search_coverage':'PARTIAL'}] if c=='kherson' else [{'part':'P1','search_coverage':'PARTIAL'}]};(inp/f'{c}.json').write_text(json.dumps(r));(inp/f'{c}.md').write_text(c)
   s,ok=M.aggregate(inp,out,'abc','CLEAN');self.assertTrue(ok);self.assertEqual([x['city'] for x in s['cities']],M.CITIES);self.assertTrue((out/'manifest.json').exists())
if __name__=='__main__':unittest.main()
