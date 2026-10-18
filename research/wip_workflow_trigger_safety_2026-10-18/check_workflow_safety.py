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
 out = subprocess.run(['git', *x], check=True, text=True, capture_output=True).stdout
 # IMPORTANT: strip() changes YAML literal-block scalars at EOF. Preserve raw git show output.
 return out if x and x[0] == 'show' else out.strip()

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

def object_diff(left, right, path='

def main():
 assert git('rev-parse','HEAD^') == BASE
 orig=git('ls-tree','-r','HEAD^',str(DIR)).splitlines()
 latest=git('ls-tree','-r','HEAD',str(DIR)).splitlines()
 assert len(orig)==54 and len(latest)==55, (len(orig),len(latest))
 expected_changed={str(DIR / n) for n in JOBS} | {TEST,PROOF}
 changed=set(git('diff','--name-only','HEAD^','HEAD').splitlines())
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
  before_text=git('show',BASE+':'+path)
  restored_text=revert_authorized_text(txt,name)
  restored_object=restored_semantics(before,after,bridge=(name=='full-site-wip.yml'))
  if restored_text!=before_text or restored_object!=before:
   fail_diff(name,before_text,restored_text,before,restored_object,'unauthorized textual or parsed YAML change')
  assert txt.count('WIP-PRE-PROMOTION-TRIGGER-SAFETY-HOLD-2026-10-18')==len(JOBS[name])+(1 if name=='full-site-wip.yml' else 0),name
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
 # Independently fetch current main in the isolated workflow before running this script.
 main_files=git('ls-tree','-r','origin/main',str(DIR)).splitlines()
 assert len(main_files)==17,('main workflow count',len(main_files))
 main_parsed={}
 main_manifest={}
 for line in main_files:
  main_path=line.split('\t',1)[1]; main_name=Path(main_path).name
  main_manifest[main_name]=line.split('\t',1)[0].split()[2]
  main_parsed[main_name]=load(git('show','origin/main:'+main_path),main_name+':main')
 assert main_manifest['explosion-monitor-wip.yml']=='1bf3385b3438a0ed471375db446ab08132d5bd87'
 assert main_parsed['explosion-monitor-wip.yml']['jobs']['monitor']['if']==HOLD
 assert main_manifest['live-due-orchestration-readback.yml']=='b7ccf6c9468e70b68fb6d00b5a1c6f422ea23b61'
 assert main_parsed['live-due-orchestration-readback.yml']['jobs']['prove']['if'].find('2c16b69dd3261a16cb08c9cf825a4f150cf76d11')>=0
 wip_edges=workflow_run_edges(parsed,'WIP-nondefault')
 main_edges=workflow_run_edges(main_parsed,'main')
 edges=sorted(wip_edges+main_edges,key=lambda e:(e['scope'],e['upstream'],e['consumer']))
 assert len(wip_edges)>=4 and len(main_edges)>=1,edges
 direct_names={k:set(parsed[x]['name'] for x in EXPECT[k]) for k in EXPECT}
 S4={}
 for scenario,names in sorted(direct_names.items()):
  for status in ('success','failure','skipped'):
   S4[scenario+':'+status]=simulate_default_cascade(names,main_parsed,main_edges,
       git('rev-parse','HEAD'),status)
 for manual_ref,sha in [('main',git('rev-parse','origin/main')),('WIP',BASE)]:
  for status in ('success','failure','skipped'):
   S4['S3_'+manual_ref+':'+status]=simulate_default_cascade(
      {'Monitor explosion metric WIP'},main_parsed,main_edges,sha,status)
 # Verify 13 jobs are held even when a dependency failed and aggregate if originally contained always().
 for workflow_name in JOBS:
  for job_name in JOBS[workflow_name]:
   assert parsed[workflow_name]['jobs'][job_name].get('if')==HOLD,(workflow_name,job_name)
 scenarios['S3_manual_main_and_wip']={'main_monitor_job_condition':HOLD,
      'wip_monitor_job_condition':HOLD,
      'older_ref_dispatch_exposure':'NOT_COVERED; independently report reachable older refs'}
 scenarios['S4_workflow_run']={'downstream_edges':edges,
      'default_branch_semantics':'only main-defined workflow_run consumers are runnable',
      'scenarios':S4,
      'prepublication_inflight':'check GitHub API immediately before guarded WIP ref update'}
 scenarios['S5_unrelated']={'main_guard_blob':main_manifest['explosion-monitor-wip.yml'],
      'main_due_blob':main_manifest['live-due-orchestration-readback.yml'],
      'main_workflow_count':len(main_parsed),
      'production_or_site_prod_modified_by_proof':False,
      'runtime_or_persistent_data_modified_by_proof':False}
 reusable=[]
 for scope,collection in [('WIP',parsed),('main',main_parsed)]:
  for name,x in collection.items():
   for jobname,job in x['jobs'].items():
    if isinstance(job,dict) and 'uses' in job:
     reusable.append({'scope':scope,'file':name,'job':jobname,'uses':job['uses']})
 trigger_graph={'workflow_run':edges,'reusable_call_sites':reusable,
  'main_workflow_names':sorted(x['name'] for x in main_parsed.values()),
  'wip_workflow_names':sorted(x['name'] for x in parsed.values())}
 receipt={'status':'PASS_OFFLINE_ISOLATED_SCOPE','base_sha':BASE,'proof_sha':git('rev-parse','HEAD'),
  'changed_files':sorted(changed),'guarded_jobs':JOBS,'guarded_job_count':sum(map(len,JOBS.values())),
  'original_blobs':oldmanifest,'new_blobs_and_hashes':newmanifest,'scenarios':scenarios,
  'trigger_graph':trigger_graph,
  'main_sha_checked':git('rev-parse','origin/main'),
  'real_ukrainealarm_requests':0,'real_monitor_executions':0,'neon_connections':0}
 target=Path(os.environ.get('RUNNER_TEMP','/tmp'))/'wip-workflow-trigger-safety-receipt.json'
 target.write_text(json.dumps(receipt,sort_keys=True,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
 print(json.dumps({'status':receipt['status'],'scenario_summary':scenarios,'guarded_jobs':receipt['guarded_job_count']},indent=2))
 print('PROOF_RECEIPT='+str(target))

if __name__=='__main__': main()
):
 """Deterministic field-level differences; prevents silently relaxed equivalence."""
 if type(left) is not type(right):
  return [{'path':path,'before':repr(left),'after':repr(right),'kind':'type'}]
 if isinstance(left,dict):
  result=[]
  for key in sorted(set(left) | set(right)):
   child=path+'.'+str(key)
   if key not in left: result.append({'path':child,'before':'<ABSENT>','after':repr(right[key])})
   elif key not in right: result.append({'path':child,'before':repr(left[key]),'after':'<ABSENT>'})
   else: result.extend(object_diff(left[key],right[key],child))
  return result
 if isinstance(left,list):
  result=[]
  if len(left)!=len(right): result.append({'path':path+'.length','before':len(left),'after':len(right)})
  for i in range(min(len(left),len(right))): result.extend(object_diff(left[i],right[i],path+'['+str(i)+']'))
  return result
 return [] if left==right else [{'path':path,'before':repr(left),'after':repr(right)}]

def fail_diff(name, before_text, after_text, before, after, reason):
 from difflib import unified_diff
 diff = {'status':'FAIL','workflow':name,'reason':reason,
         'field_level_differences':object_diff(before,after),
         'text_diff':list(unified_diff(before_text.splitlines(keepends=True),
             after_text.splitlines(keepends=True),fromfile=name+':original',tofile=name+':restored'))}
 target=Path(os.environ.get('RUNNER_TEMP','/tmp'))/'workflow-structural-diff.json'
 target.write_text(json.dumps(diff,sort_keys=True,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(diff,sort_keys=True))
 raise AssertionError(name+': '+reason)

def revert_authorized_text(text, name):
 """Exact reversible edit: no differences except the 13 holds and bridge hold."""
 lines=text.splitlines(keepends=True)
 restored=[]; i=0; jobs=0; bridge=0
 marker='WIP-PRE-PROMOTION-TRIGGER-SAFETY-HOLD-2026-10-18'
 while i<len(lines):
  line=lines[i]
  if marker not in line:
   restored.append(line); i+=1; continue
  if 'no live tokenized bridge' in line:
   assert i+1<len(lines) and lines[i+1].strip()=='if: '+HOLD,(name,'bridge hold')
   bridge+=1; i+=2; continue
  assert i+2<len(lines),(name,'missing guard lines')
  assert 'Removal requires a separately authorized, independently proven transition.' in lines[i+1],name
  assert lines[i+2].strip()=='if: '+HOLD,(name,'not unconditional hold')
  jobs+=1; i+=3
  if i<len(lines) and '# PRE-HOLD ORIGINAL JOB CONDITION: ' in lines[i]:
   restored.append(lines[i].replace('# PRE-HOLD ORIGINAL JOB CONDITION: ','',1)); i+=1
 assert jobs==len(JOBS[name]),(name,'hold count',jobs,len(JOBS[name]))
 assert bridge==(1 if name=='full-site-wip.yml' else 0),(name,'bridge count',bridge)
 return ''.join(restored)

def restored_semantics(original, patched, bridge=False):
 """Preserve every original field, including prior job conditions and all steps."""
 revised=copy.deepcopy(patched)
 assert set(original['jobs'])==set(revised['jobs'])
 for name,job in revised['jobs'].items():
  assert job.get('if')==HOLD,(name,'missing unconditional guard')
  original_job=original['jobs'][name]
  if 'if' in original_job: job['if']=copy.deepcopy(original_job['if'])
  else: job.pop('if',None)
  if bridge:
   for step in job.get('steps',[]):
    if isinstance(step,dict) and step.get('name')=='Apply verified Alerts.in.ua and UkraineAlarm bridge':
     assert step.get('if')==HOLD
     oldsteps=original_job['steps']
     previous=[x for x in oldsteps if isinstance(x,dict) and x.get('name')==step.get('name')]
     assert len(previous)==1
     if 'if' in previous[0]: step['if']=previous[0]['if']
     else: step.pop('if',None)
 return revised

def workflow_run_edges(collection,scope):
 edges=[]
 for name,x in collection.items():
  w=x['on'].get('workflow_run')
  if isinstance(w,dict):
   for upstream in w.get('workflows',[]):
    edges.append({'scope':scope,'upstream':upstream,
       'consumer':x.get('name',name),'file':name,
       'default_branch_executable':scope=='main',
       'types':w.get('types',[])})
 return sorted(edges,key=lambda e:(e['scope'],e['upstream'],e['consumer']))

def simulate_default_cascade(names, main_parsed, main_edges, possible_sha, conclusion):
 """Only workflow_run definitions on default main are dispatched by GitHub."""
 assert conclusion in ('success','failure','skipped')
 visited=set(names); result=[]; frontier=list(names)
 while frontier:
  upstream=frontier.pop(0)
  for edge in main_edges:
   if edge['upstream']!=upstream or edge['consumer'] in visited: continue
   consumer=main_parsed[edge['file']]
   jobs=consumer['jobs']
   executable=[]
   for j,body in jobs.items():
    condition=body.get('if','')
    if condition==HOLD: continue
    # The existing main due read-back has an old exact commit SHA and success gate.
    if edge['file']=='live-due-orchestration-readback.yml':
     pin='2c16b69dd3261a16cb08c9cf825a4f150cf76d11'
     assert pin in condition and 'conclusion' in condition and 'success' in condition
     assert possible_sha!=pin,(edge,'old pinned SHA could execute')
     continue
    executable.append(j)
   result.append({'upstream':upstream,'consumer':edge['consumer'],
     'conclusion':conclusion,'trigger_created_on_completed':True,
     'executable_jobs':executable})
   assert not executable,('UNSAFE DEFAULT WORKFLOW_RUN',edge,executable)
   visited.add(edge['consumer'])
   frontier.append(edge['consumer'])
 return result

def main():
 assert git('rev-parse','HEAD^') == BASE
 orig=git('ls-tree','-r','HEAD^',str(DIR)).splitlines()
 latest=git('ls-tree','-r','HEAD',str(DIR)).splitlines()
 assert len(orig)==54 and len(latest)==55, (len(orig),len(latest))
 expected_changed={str(DIR / n) for n in JOBS} | {TEST,PROOF}
 changed=set(git('diff','--name-only','HEAD^','HEAD').splitlines())
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
