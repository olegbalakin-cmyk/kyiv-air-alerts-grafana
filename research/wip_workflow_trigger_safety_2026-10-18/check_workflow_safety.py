#!/usr/bin/env python3
"""Read-only WIP workflow hold proof. No service clients or monitor invocation."""
import copy, hashlib, json, os, subprocess
from pathlib import Path
import yaml
from wcmatch import glob

BASE = '1a8b57553ba66319db326d65080ade93ae6ca01c'
BRANCH = 'multicity-wip-2026-09-16'
HOLD = '$' + '{{ false }}'
DIR = Path('.github/workflows')
TEST = 'research/wip_workflow_trigger_safety_2026-10-18/check_workflow_safety.py'
PROOF = '.github/workflows/proof-wip-workflow-trigger-safety-2026-10-18.yml'
JOBS = {
 'full-site-wip.yml': ['build'],
 'test-explosion-monitor-wip.yml': ['smoke'],
 'historical-replay-qa.yml': ['plan', 'qa', 'aggregate'],
 'historical-replay-qa-finalize.yml': ['plan', 'finalize', 'aggregate'],
 'historical-source-retention-repair-preflight.yml': ['plan', 'preflight', 'aggregate'],
 'attack-event-classifier-hardening.yml': ['control-replay'],
 'explosion-monitor-wip.yml': ['monitor'],
}
OLD_BLOBS = {
 'full-site-wip.yml': '8cf4060913959c527266366fc980f448ebe90df9',
 'test-explosion-monitor-wip.yml': '5b7f9361444bc0ebddf4c9c3651bdd7de81eec4e',
 'historical-replay-qa.yml': '78645e41ae5fa73298365a635844a41fca39fe9e',
 'historical-replay-qa-finalize.yml': '2beba4d52da70dc342f7e516a11db96050ee6284',
 'historical-source-retention-repair-preflight.yml': 'c1d7ac74cfa90a2c6007dcd41a96d01dc6fe3ce5',
 'attack-event-classifier-hardening.yml': '3210978aef01a69118137de802d3341496bfee0b',
 'explosion-monitor-wip.yml': 'dfb98ce13ecfe76675eb32e204670f835096e1dc',
}
S1 = ['.github/workflows/' + n for n in JOBS]
S2 = ['kyiv-air-alerts-grafana/scripts/' + n for n in ('monitor_explosion_candidates.py','cached_alert_source_gate.py')]
EXPECT = {
 'S1_repair_push': set(JOBS) - {'full-site-wip.yml','explosion-monitor-wip.yml'},
 'S2_code_push': set(JOBS) - {'explosion-monitor-wip.yml'},
}

def git(*x):
 return subprocess.run(['git', *x], check=True, text=True, capture_output=True).stdout.rstrip('\n') if x[0]!='show' else subprocess.run(['git', *x], check=True, text=True, capture_output=True).stdout

def load(s, name):
 x=yaml.load(s, Loader=yaml.BaseLoader)
 assert isinstance(x, dict) and isinstance(x.get('on'),dict) and isinstance(x.get('jobs'),dict), name
 return x

def patmatch(path, pats):
 if not isinstance(pats,list): pats=[pats]
 outcome=False
 for p in pats:
  neg=p.startswith('!')
  if glob.globmatch(path, p[1:] if neg else p, flags=glob.GLOBSTAR|glob.DOTMATCH): outcome=not neg
 return outcome

def matches(x, branch, changed):
 on=x['on']; p=on.get('push')
 if 'push' not in on: return False
 if not isinstance(p,dict): return True
 if 'branches' in p and not patmatch(branch,p['branches']): return False
 if 'branches-ignore' in p and patmatch(branch,p['branches-ignore']): return False
 if 'paths' in p and not any(patmatch(f,p['paths']) for f in changed): return False
 if 'paths-ignore' in p and all(patmatch(f,p['paths-ignore']) for f in changed): return False
 return True

def strip_holds(x,bridge=False):
 x=copy.deepcopy(x)
 for job in x['jobs'].values():
  job.pop('if',None)
  if bridge:
   for step in job.get('steps',[]):
    if isinstance(step,dict) and step.get('name')=='Apply verified Alerts.in.ua and UkraineAlarm bridge': step.pop('if',None)
 return x

def main():
 assert git('rev-parse','HEAD~2') == BASE
 orig=git('ls-tree','-r',BASE,str(DIR)).splitlines()
 latest=git('ls-tree','-r','HEAD',str(DIR)).splitlines()
 assert len(orig)==54 and len(latest)==55, (len(orig),len(latest))
 expected_changed={str(DIR / n) for n in JOBS} | {TEST,PROOF}
 changed=set(git('diff','--name-only',BASE,'HEAD').splitlines())
 assert changed==expected_changed, (changed-expected_changed,expected_changed-changed)
 blob={line.split('\t')[1]:line.split('\t')[0].split()[2] for line in orig}
 parsed={}; oldmanifest={}; newmanifest={}
 for line in orig:
  path=line.split('\t',1)[1]; name=Path(path).name
  txt=Path(path).read_text(encoding='utf-8')
  parsed[name]=load(txt,name)
  oldmanifest[name]=blob[path]
  newmanifest[name]={'blob':git('rev-parse','HEAD:'+path),'sha256':hashlib.sha256(txt.encode()).hexdigest()}
  if name not in JOBS: continue
  assert blob[path]==OLD_BLOBS[name],name
  before=load(git('show',BASE+':'+path),name+':before'); after=parsed[name]
  assert set(before['jobs'])==set(after['jobs'])==set(JOBS[name]),name
  assert before['on']==after['on'],name
  assert all(after['jobs'][j].get('if')==HOLD for j in JOBS[name]),name
  assert strip_holds(before)==strip_holds(after,bridge=(name=='full-site-wip.yml')),name
  assert txt.count('WIP-PRE-PROMOTION-TRIGGER-SAFETY-HOLD-2026-10-18')>=len(JOBS[name]),name
 bridge=parsed['full-site-wip.yml']['jobs']['build']['steps']
 tok=[s for s in bridge if isinstance(s,dict) and isinstance(s.get('env'),dict) and s['env'].get('UKRAINEALARM_API_TOKEN')]
 assert len(tok)==1 and tok[0]['if']==HOLD
 assert 'workflow_dispatch' in parsed['explosion-monitor-wip.yml']['on']
 assert patmatch('src/a/b.py',['src/**'])
 assert not patmatch('src/a/b.py',['src/**','!src/a/**'])
 assert patmatch('src/a/b.py',['src/**','!src/a/**','src/a/b.py'])
 assert not patmatch('feature/x',['main','release/**'])
 assert patmatch('release/x',['main','release/**'])
 scenarios={}
 for title,files in (('S1_repair_push',S1),('S2_code_push',S2)):
  triggered={name for name,x in parsed.items() if matches(x,BRANCH,files)}
  assert triggered==EXPECT[title],(title,triggered)
  assert all(all(v.get('if')==HOLD for v in parsed[n]['jobs'].values()) for n in triggered)
  scenarios[title]={'triggered':sorted(triggered),'executable_jobs':0}
 edges=[]
 for name,x in parsed.items():
  w=x['on'].get('workflow_run')
  if isinstance(w,dict):
   for upstream in w.get('workflows',[]): edges.append({'from':upstream,'to':x.get('name',name),'file':name})
 assert len(edges)>=4,edges
 scenarios['S3_manual_wip_dispatch']={'executable_monitor_jobs':0,'main_guard':'separately pinned/verified'}
 scenarios['S4_workflow_run']={'completed_conclusions':['success','failure','skipped'],
    'downstream_edges':edges,'old_upstream_inflight':'must be independently checked via GitHub API',
    'wip_only_workflow_run_consumers':'not present on default main'}
 scenarios['S5_unrelated']={'main_or_site_prod_modified':False,'runtime_or_persistent_data_modified':False}
 receipt={'status':'PASS_OFFLINE_ISOLATED_SCOPE','base_sha':BASE,'proof_sha':git('rev-parse','HEAD'),
  'changed_files':sorted(changed),'guarded_jobs':JOBS,'guarded_job_count':sum(map(len,JOBS.values())),
  'original_blobs':oldmanifest,'new_blobs_and_hashes':newmanifest,'scenarios':scenarios,
  'real_ukrainealarm_requests':0,'real_monitor_executions':0,'neon_connections':0}
 target=Path(os.environ.get('RUNNER_TEMP','/tmp'))/'wip-workflow-trigger-safety-receipt.json'
 target.write_text(json.dumps(receipt,sort_keys=True,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
 print(json.dumps({'status':receipt['status'],'scenario_summary':scenarios,'guarded_jobs':receipt['guarded_job_count']},indent=2))
 print('PROOF_RECEIPT='+str(target))

if __name__=='__main__': main()
