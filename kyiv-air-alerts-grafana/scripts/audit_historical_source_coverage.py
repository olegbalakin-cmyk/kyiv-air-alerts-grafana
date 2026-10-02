#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,hashlib,json,re,subprocess
from pathlib import Path
from urllib.parse import urlparse

CITIES=['kherson','zaporizhzhia','chernihiv','sevastopol','sumy','kyiv']
TOKENS={'kherson':['kherson','херсон'],'zaporizhzhia':['zaporizhzhia','запоріж'],'chernihiv':['chernihiv','чернігів'],'sevastopol':['sevastopol','севастопол'],'sumy':['sumy','суми'],'kyiv':['kyiv','київ']}
ROOT='kyiv-air-alerts-grafana'; H=f'{ROOT}/data/explosion_metric_handoff'; R=f'{ROOT}/data/explosion_research'
PARENTS=f'{H}/RESEARCH_SLICES_2026-09-18.csv'; CHILDREN=f'{H}/RESEARCH_SUBSLICES_2026-09-19.csv'; REPAIRS=f'{H}/REPAIR_SUBSLICES_2026-09-20.csv'
SLICE=f'{H}/SLICE_MICROTASK.md'; SUBSLICE=f'{H}/SUBSLICE_MICROTASK.md'; STATUS='research/historical_replay_status_current.json'
BLOCK=[r'could not be re-enumerated',r'source blob exceeds.*size limit',r'source[_ ]slice[_ ]missing',r'source[_ ]slice[_ ]mismatch',r'input inaccessible',r'connector.*(?:limit|failed|blocked|unavailable)']
PARTIAL=[r'\bnarrow\b',r'\btargeted\b',r'archive not used',r'telegram archive not used',r'gap_audit_not_full_backfill',r'gap audit',r'candidate[- ]driven',r'source discovery gap',r'source coverage gap',r'not exhaustive',r'\bpilot\b',r'web_telegram_reresearch["\']?\s*[:=]\s*false']
FULL=[r'exhaustive source scan',r'full source history pass',r'entire source history.*scanned',r'complete source archive',r'per-episode search ledger',r'successful bounded source coverage over the entire']
RETNEG=[r'keep only numerator-relevant evidence',r'do not include all rejected candidates']
HINTS=('blind','source_recovery','gap_audit','historical_replay','source_retention','formalization','attack_event','source_coverage','replay','explosion_metric','discovery_pilot')
EXT={'.json','.md','.csv','.txt','.yml','.yaml'}

def run(repo,*args,check=True):
 p=subprocess.run(['git',*args],cwd=repo,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,errors='replace')
 if check and p.returncode: raise RuntimeError('git '+' '.join(args)+': '+p.stderr.strip())
 return p.stdout

def show(repo,head,path):
 p=subprocess.run(['git','show',f'{head}:{path}'],cwd=repo,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,errors='replace'); return p.stdout if p.returncode==0 else None

def blob(repo,head,path): return run(repo,'rev-parse',f'{head}:{path}',check=False).strip() or 'UNKNOWN'
def jload(s):
 try:return json.loads(s) if s else None
 except:return None
def rows(s): return list(csv.DictReader((s or '').splitlines()))
def has(s,ps): return any(re.search(p,s or '',re.I|re.S) for p in ps)
def citytext(city,s): return any(t in (s or '').lower() for t in TOKENS[city])
def ex(s,m,n=190): return re.sub(r'\s+',' ',s[max(0,m.start()-n):min(len(s),m.end()+n)]).strip()[:800]
def firstint(d,*ks):
 for k in ks:
  v=d.get(k) if isinstance(d,dict) else None
  if isinstance(v,int) and not isinstance(v,bool): return v
 return None

def current_json(repo,head,paths):
 for p in paths:
  x=jload(show(repo,head,p))
  if isinstance(x,dict): return x,p
 return None,None

def history(repo,city):
 out=[]; seen=set()
 for line in run(repo,'rev-list','--objects','--all').splitlines():
  if ' ' not in line: continue
  sha,path=line.split(' ',1); pl=path.lower()
  if Path(path).suffix.lower() not in EXT: continue
  if not(city in pl or any(h in pl for h in HINTS)): continue
  if (sha,path) in seen:continue
  seen.add((sha,path))
  size=run(repo,'cat-file','-s',sha,check=False).strip()
  try:
   if int(size)>1800000:continue
  except:continue
  raw=subprocess.run(['git','cat-file','-p',sha],cwd=repo,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
  if raw.returncode or b'\x00' in raw.stdout[:1000]:continue
  text=raw.stdout.decode('utf-8','replace')
  if city not in pl and not citytext(city,text):continue
  out.append((sha,path,text))
 return out

def provenance(repo,sha):
 c=run(repo,'log','--all','--format=%H','-n','1',f'--find-object={sha}',check=False).strip().splitlines(); commit=c[0] if c else 'UNKNOWN'
 refs=run(repo,'branch','-r','--contains',commit,'--format=%(refname:short)',check=False).strip().splitlines() if commit!='UNKNOWN' else []
 return commit,(refs[0].strip() if refs else 'HISTORICAL_ALL_REFS')

def evid(repo,head,path,text,interp,sha=None):
 sha=sha or blob(repo,head,path); commit,ref=(head,head) if sha==blob(repo,head,path) else provenance(repo,sha)
 return {'path':path,'blob':sha,'commit':commit,'ref':ref,'excerpt':re.sub(r'\s+',' ',text).strip()[:1000],'interpretation':interp}

def marker_evidence(repo,head,city,hist):
 out=[]; seen=set()
 pats=BLOCK+PARTIAL+[r'CONFIRMED_FALSE_NEGATIVE',r'PROBABLE_FALSE_NEGATIVE',r'SOURCE_NOT_COVERED',r'confirmed additional miss',r'source recovery']
 for sha,path,text in hist:
  for pat in pats:
   m=re.search(pat,text,re.I|re.S)
   if not m:continue
   x=ex(text,m); k=(path,x,pat)
   if k in seen:continue
   seen.add(k); commit,ref=provenance(repo,sha)
   interp='historical warning/source-coverage evidence'
   out.append({'path':path,'blob':sha,'commit':commit,'ref':ref,'excerpt':x,'interpretation':interp})
   if len(out)>=40:return out
 return out

def domains(obj):
 found=set()
 def walk(x):
  if isinstance(x,str) and x.startswith(('http://','https://')):
   h=urlparse(x).hostname or ''; found.add(h[4:] if h.startswith('www.') else h)
  elif isinstance(x,dict):
   for v in x.values():walk(v)
  elif isinstance(x,list):
   for v in x:walk(v)
 walk(obj);return sorted(x for x in found if x)

def slice_result(repo,head,city,part,children,repairs):
 paths=[f'{R}/{city}/{city}_P{part}_result.json',f'{R}/{city}/{city}-P{part}_result.json',f'{H}/{city}_P{part}_result.json']
 x,p=current_json(repo,head,paths)
 if x:return x,p
 objs=[]
 parent=f'{city}-P{part}'
 for r in children+repairs:
  if r.get('parent_task_id')!=parent:continue
  sub=r.get('subpart') or r.get('task_id','').replace(parent,'').lstrip('-')
  y,q=current_json(repo,head,[f'{R}/{city}/{city}_P{part}{sub}_result.json',f'{R}/{city}/{city}-P{part}{sub}_result.json'])
  if y:objs.append((y,q))
 if not objs:return None,None
 strict=sum(firstint(y,'strict_n') or 0 for y,_ in objs); sens=sum(firstint(y,'sensitivity_n') or 0 for y,_ in objs)
 return {'status':'complete','strict_n':strict,'sensitivity_n':sens,'review_events':[z for y,_ in objs for z in y.get('review_events',[])], 'children':[y for y,_ in objs]},','.join(q for _,q in objs)

def audit(repo,head,city,outdir):
 parents=[r for r in rows(show(repo,head,PARENTS)) if r.get('city_key')==city]
 parents.sort(key=lambda r:int(r.get('part','0'))); children=[r for r in rows(show(repo,head,CHILDREN)) if r.get('city_key')==city]; repairs=[r for r in rows(show(repo,head,REPAIRS)) if r.get('city_key')==city]
 contract=(show(repo,head,SLICE) or '')+'\n'+(show(repo,head,SUBSLICE) or '')
 statusall=jload(show(repo,head,STATUS)) or {}; replay=(statusall.get('cities') or {}).get(city,{})
 final,finalpath=current_json(repo,head,[f'{R}/{city}/final_evidence.json'])
 slices=[]; support=[]
 for p in parents:
  part=p.get('part'); obj,path=slice_result(repo,head,city,part,children,repairs); txt=json.dumps(obj,ensure_ascii=False) if obj else ''
  if has(txt,BLOCK): sc='BLOCKED'
  elif has(txt,FULL): sc='PROVEN_COMPLETE'
  elif obj and (has(txt,PARTIAL) or re.search(r'search exact-city web/local sources narrowly',contract,re.I)): sc='PARTIAL'
  else: sc='NOT_PROVEN'
  blockers=[]
  for pat in BLOCK:
   m=re.search(pat,txt,re.I|re.S)
   if m:blockers.append(ex(txt,m))
  archive='UNKNOWN'
  if re.search(r'archive not used|telegram archive not used',txt,re.I):archive=False
  elif re.search(r'targeted archive check|archive.*(?:used|checked|searched)',txt,re.I):archive=True
  rv=len(obj.get('review_events',[])) if isinstance(obj,dict) and isinstance(obj.get('review_events'),list) else 0
  slices.append({'part':f'P{part}','date_from':p.get('episode_start_date_from','UNKNOWN'),'date_to':p.get('episode_start_date_to','UNKNOWN'),'episodes':int(p.get('frozen_denominator','0')),'strict_found':firstint(obj or {},'strict_n'),'sensitivity_found':firstint(obj or {},'sensitivity_n'),'review_found':rv,'search_method':'narrow exact-city web/local source search under governing worker contract','source_families':domains(obj or {}),'archive_used':archive,'access_blockers':blockers,'search_coverage':sc,'result_retention':'NOT_PROVEN','notes':(obj or {}).get('qa','UNKNOWN'),'result_path':path or 'UNKNOWN'})
  if path and txt:
   for pat in BLOCK+PARTIAL:
    m=re.search(pat,txt,re.I|re.S)
    if m:support.append(evid(repo,head,path,ex(txt,m),'slice blocker/partial-search evidence'))
 try: den=sum(int(x['frozen_denominator']) for x in parents); cityden=int(parents[0]['city_frozen_denominator']); denom_ok=den==cityden
 except: cityden='UNKNOWN';denom_ok=False
 replay_ok=(replay.get('expected_alert_episodes')==cityden and replay.get('reconstructed_alert_episodes')==cityden)
 canonical='PROVEN_COMPLETE' if denom_ok and replay_ok else ('PARTIAL' if parents else 'NOT_PROVEN')
 hist=history(repo,city); red=marker_evidence(repo,head,city,hist)
 source_miss=any(re.search(r'SOURCE_NOT_COVERED|source[- ]coverage miss',e['excerpt'],re.I) for e in red)
 gap=any(re.search(r'gap_audit_not_full_backfill|confirmed additional miss|source discovery miss',e['excerpt'],re.I) for e in red)
 ss=[x['search_coverage'] for x in slices]
 search='PROVEN_COMPLETE' if ss and all(x=='PROVEN_COMPLETE' for x in ss) and not source_miss and not gap else ('BLOCKED' if ss and all(x=='BLOCKED' for x in ss) else ('PARTIAL' if any(x in ('PARTIAL','BLOCKED') for x in ss) or source_miss or gap else 'NOT_PROVEN'))
 retention='NOT_PROVEN' if has(contract,RETNEG) else 'NOT_PROVEN'
 if replay.get('status')=='READY' and int(replay.get('manual_qa_count',0) or 0)==0 and int(replay.get('error_count',0) or 0)==0 and int((replay.get('reconciliation_counts') or {}).get('UNREPLAYABLE_MISSING_EVIDENCE',0) or 0)==0: adjud='PROVEN_COMPLETE'
 elif replay.get('status')=='QA_REQUIRED' or int(replay.get('manual_qa_count',0) or 0)>0: adjud='PARTIAL'
 else: adjud='NOT_PROVEN'
 original_strict=sum(x['strict_found'] for x in slices if isinstance(x['strict_found'],int)) if any(isinstance(x['strict_found'],int) for x in slices) else 'UNKNOWN'
 original_sens=sum(x['sensitivity_found'] for x in slices if isinstance(x['sensitivity_found'],int)) if any(isinstance(x['sensitivity_found'],int) for x in slices) else 'UNKNOWN'
 current=firstint(replay,'baseline_strict_episodes')
 if current is None and isinstance(final,dict): current=firstint(final.get('final_counts') or final,'strict_n')
 current=current if current is not None else 'UNKNOWN'
 current_review=len(final.get('review_events',[])) if isinstance(final,dict) and isinstance(final.get('review_events'),list) else 0
 cfn=sum(1 for e in red if re.search(r'CONFIRMED_FALSE_NEGATIVE',e['excerpt'],re.I)); pfn=sum(1 for e in red if re.search(r'PROBABLE_FALSE_NEGATIVE',e['excerpt'],re.I)); snc=sum(1 for e in red if re.search(r'SOURCE_NOT_COVERED|source[- ]coverage miss',e['excerpt'],re.I))
 if parents:support.append(evid(repo,head,PARENTS,' | '.join(','.join(r.get(k,'') for k in ('task_id','episode_start_date_from','episode_start_date_to','frozen_denominator','city_frozen_denominator','status')) for r in parents),'frozen denominator/slice table'))
 if replay:support.append(evid(repo,head,STATUS,json.dumps({k:replay.get(k) for k in ('source_status','expected_alert_episodes','reconstructed_alert_episodes','status','manual_qa_count','baseline_strict_episodes','replayed_strict_episodes','reconciliation_counts')},ensure_ascii=False),'current replay/adjudication state'))
 if isinstance(final,dict):support.append(evid(repo,head,finalpath,json.dumps({'status':final.get('status'),'frozen_denominator':final.get('frozen_denominator'),'final_counts':final.get('final_counts'),'qa':final.get('qa'),'normalization_provenance':final.get('normalization_provenance')},ensure_ascii=False),'current retained count/evidence state'))
 for p in (SLICE,SUBSLICE):
  t=show(repo,head,p) or ''
  m=re.search(r'keep only numerator-relevant evidence|do not include all rejected candidates',t,re.I)
  if m:support.append(evid(repo,head,p,ex(t,m),'governing retention contract limits broad negative/rejection persistence'))
 support.extend(red)
 uniq=[];seen=set()
 for e in support:
  k=(e['path'],e['blob'],e['excerpt'],e['interpretation'])
  if k not in seen:seen.add(k);uniq.append(e)
 reaudit=search in ('PARTIAL','BLOCKED') or (search=='NOT_PROVEN' and bool(red)) or source_miss or gap
 bad=[s for s in slices if s['search_coverage']!='PROVEN_COMPLETE']; bp=', '.join(s['part'] for s in bad)
 if city=='kherson':scope='Full existing-source history pass across P1-P3 current non-strict episodes, prioritizing blocked P2 (2026-02-15..2026-06-21); reconcile retained positives only; no new-source discovery.'
 elif gap:scope=f'Reconcile proven gap-audit/source-discovery misses, then run a bounded full existing-source history pass over unresolved/current non-strict episodes in {bp or "affected interval"}.'
 elif source_miss:scope=f'Re-audit source coverage for {bp or "affected slices"} using existing source families, expanding from SOURCE_NOT_COVERED QA cases to the bounded interval rather than only known candidates.'
 else:scope=f'Run a bounded full existing-source history pass for {bp or "the audited interval"} over current non-strict episodes and persist a search/rejection ledger.'
 result={'schema_version':1,'kind':'historical_source_coverage_forensic','city':city,'input_head':head,'canonical_episodes':cityden,'coverage_start':parents[0].get('episode_start_date_from','UNKNOWN') if parents else 'UNKNOWN','coverage_end':parents[-1].get('episode_start_date_to','UNKNOWN') if parents else 'UNKNOWN','canonical_coverage':canonical,'search_coverage':search,'result_retention':retention,'strict_adjudication':adjud,'original_strict':original_strict,'original_sensitivity':original_sens,'original_review_count':sum(x['review_found'] for x in slices),'current_strict':current,'current_replayed_strict_candidate':firstint(replay,'replayed_strict_episodes') or 'UNKNOWN','current_review_unbound_count':current_review,'blind_qa_confirmed_misses':cfn,'blind_qa_probable_misses':pfn,'source_not_covered_misses':snc,'known_gap_audit_unresolved':gap,'slices':slices,'red_flags':red,'supporting_evidence':uniq[:80],'orphan_candidates':[],'per_episode_negatives_persisted':False if has(contract,RETNEG) else 'UNKNOWN','full_source_history_scanned':search=='PROVEN_COMPLETE','reaudit_needed':reaudit,'recommended_scope':scope,'verdict':f'CANONICAL={canonical}; SEARCH={search}; RETENTION={retention}; ADJUDICATION={adjud}; RE_AUDIT_NEEDED={"YES" if reaudit else "NO"}'}
 outdir.mkdir(parents=True,exist_ok=True); (outdir/f'{city}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 md=[f'# Historical source-coverage forensic — {city}','',f'Input head: `{head}`','',f'- CANONICAL_COVERAGE: **{canonical}**',f'- SEARCH_COVERAGE: **{search}**',f'- RESULT_RETENTION: **{retention}**',f'- STRICT_ADJUDICATION: **{adjud}**',f'- canonical episodes: **{cityden}**',f'- original strict: **{original_strict}**',f'- current strict: **{current}**',f'- re-audit: **{"YES" if reaudit else "NO"}**','','## Slices','']
 for s in slices:md.append(f"- {s['part']} {s['date_from']}..{s['date_to']}: episodes={s['episodes']} strict={s['strict_found']} search={s['search_coverage']} retention={s['result_retention']}")
 md+=['','## Recommended scope','',scope,'','## Evidence','']+[f"- `{e['path']}` @ `{e['commit']}` blob `{e['blob']}` — {e['interpretation']}: {e['excerpt']}" for e in uniq[:30]]
 (outdir/f'{city}.md').write_text('\n'.join(md)+'\n')
 return result

K={'canonical_coverage':'PROVEN_COMPLETE','search_coverage':'PARTIAL','result_retention':'NOT_PROVEN','strict_adjudication':'PROVEN_COMPLETE','canonical_episodes':1412,'original_strict':9,'current_strict':2}
def calibrate(r):
 err=[f'{k}: expected {v!r}, got {r.get(k)!r}' for k,v in K.items() if r.get(k)!=v]; sm={s['part']:s['search_coverage'] for s in r.get('slices',[])}
 for p,v in {'P1':'PARTIAL','P2':'BLOCKED','P3':'PARTIAL'}.items():
  if sm.get(p)!=v:err.append(f'{p}: expected {v}, got {sm.get(p)}')
 return not err,err

def aggregate(inp,out,head,protected):
 rs={c:json.loads(next(inp.rglob(c+'.json')).read_text()) for c in CITIES}; ok,errs=calibrate(rs['kherson']); items=[]
 for c in CITIES:
  r=rs[c]; items.append({k:r[k] for k in ('city','canonical_episodes','original_strict','current_strict','canonical_coverage','search_coverage','result_retention','strict_adjudication','blind_qa_confirmed_misses','source_not_covered_misses','reaudit_needed','recommended_scope')})
 s={'schema_version':1,'kind':'historical_source_coverage_forensic_summary','input_head':head,'kherson_calibration':'PASS' if ok else 'FAIL','kherson_calibration_errors':errs,'forensic_workflow':'TRUSTED' if ok else 'NOT_TRUSTED','protected_project_data_status':protected,'cities':items}; out.mkdir(parents=True,exist_ok=True)
 (out/'summary.json').write_text(json.dumps(s,ensure_ascii=False,indent=2)+'\n');
 with (out/'summary.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(items[0]));w.writeheader();w.writerows(items)
 md=['# Six-city historical source-coverage forensic','',f'Input head: `{head}`',f'Kherson calibration: **{s["kherson_calibration"]}**',f'Forensic workflow: **{s["forensic_workflow"]}**','','| city | canonical | original strict | current strict | canonical | search | retention | adjudication | re-audit |','|---|---:|---:|---:|---|---|---|---|---|']
 for r in items:md.append(f"| {r['city']} | {r['canonical_episodes']} | {r['original_strict']} | {r['current_strict']} | {r['canonical_coverage']} | {r['search_coverage']} | {r['result_retention']} | {r['strict_adjudication']} | {'YES' if r['reaudit_needed'] else 'NO'} |")
 md+=['','## Re-audit queue','']; n=1
 for r in items:
  if r['reaudit_needed']:md.append(f"{n}. **{r['city']}** — {r['recommended_scope']}");n+=1
 (out/'summary.md').write_text('\n'.join(md)+'\n')
 man={'schema_version':1,'input_head':head,'city_order':CITIES,'kherson_calibration':s['kherson_calibration'],'forensic_workflow':s['forensic_workflow'],'protected_project_data_status':protected,'files':{}}
 for p in list(inp.rglob('*.json'))+list(inp.rglob('*.md'))+[out/'summary.json',out/'summary.csv',out/'summary.md']:
  if p.exists():b=p.read_bytes();man['files'][p.name]={'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)}
 (out/'manifest.json').write_text(json.dumps(man,indent=2)+'\n');return s,ok

def main():
 ap=argparse.ArgumentParser();sp=ap.add_subparsers(dest='cmd',required=True);c=sp.add_parser('city');c.add_argument('--repo',default='.');c.add_argument('--city',choices=CITIES,required=True);c.add_argument('--authoritative-head',required=True);c.add_argument('--output-dir',required=True);a=sp.add_parser('aggregate');a.add_argument('--input-dir',required=True);a.add_argument('--output-dir',required=True);a.add_argument('--authoritative-head',required=True);a.add_argument('--protected-state',default='UNKNOWN');a.add_argument('--fail-on-calibration',action='store_true');x=ap.parse_args()
 if x.cmd=='city':r=audit(Path(x.repo).resolve(),x.authoritative_head,x.city,Path(x.output_dir).resolve());print(json.dumps({k:r[k] for k in ('city','canonical_coverage','search_coverage','result_retention','strict_adjudication','original_strict','current_strict','reaudit_needed')}));return
 s,ok=aggregate(Path(x.input_dir).resolve(),Path(x.output_dir).resolve(),x.authoritative_head,x.protected_state);print(json.dumps({'kherson_calibration':s['kherson_calibration'],'forensic_workflow':s['forensic_workflow']}));raise SystemExit(2 if x.fail_on_calibration and not ok else 0)
if __name__=='__main__':main()
