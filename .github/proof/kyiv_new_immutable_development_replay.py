#!/usr/bin/env python3
"""Offline, two-process same-corpus classifier replay. No evidence networking."""
from __future__ import annotations
import argparse, copy, hashlib, importlib.util, json, os, socket, sys, tempfile, shutil, subprocess
from collections import Counter, defaultdict
from pathlib import Path
from datetime import timedelta
from urllib.parse import urlparse

ROOT=Path(__file__).resolve().parents[2]
PILOT=ROOT/'.github/proof/kyiv_historical_discovery_calibration_pilot.py'
INPUT=ROOT/'research/kyiv_historical_discovery_development_classifier_input_2026-10-08.json'
STAMP='2026-10-09'
POS={'STRICT_EVENT_POSITIVE','SENSITIVITY_EVENT_POSITIVE'}
A={'BBC_Ukrainian','Radio_Svoboda','Suspilne_National'}
STAGE2=['24_Kanal','5.ua','Fakty_ICTV','Focus','Kyiv24','bigkyiv.com.ua','kyiv.novyny.live','vikna.tv','war.telegraf.com.ua','Glavcom','Novynarnia','zaxid.net','ye.ua']
EXPECTED={'discovery':'kyiv_historical_runner_discovery_snapshot_'+STAMP+'.json','native':'kyiv_historical_runner_native_corpus_'+STAMP+'.json','normalized':'kyiv_historical_runner_normalized_evidence_'+STAMP+'.json'}
def canonical(o):return (json.dumps(o,sort_keys=True,ensure_ascii=False,separators=(',',':'))+'\n').encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def load(path,name):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def load_verified(path):
 b=path.read_bytes();doc=json.loads(b);recorded=doc.pop('payload_sha256',None)
 if not recorded or sha(canonical(doc))!=recorded:raise RuntimeError('CORPUS_HASH_MISMATCH:'+path.name)
 doc['payload_sha256']=recorded
 return doc
def disable_evidence_network():
 import requests
 def blocked(*args,**kwargs):raise RuntimeError('EVIDENCE_NETWORK_FORBIDDEN')
 requests.sessions.Session.request=blocked
 socket.create_connection=blocked
 socket.socket.connect=blocked
 socket.getaddrinfo=blocked
 os.environ['NO_PROXY']='*'
def admission(p,native,episode):
 if not native or not native.get('text'):return 'NO_TEXT'
 if not native.get('published_at'):return 'NO_PUBLICATION_TIMESTAMP'
 start=p.parse_dt(episode['alert_start'])-timedelta(hours=6)
 end=p.parse_dt(episode['alert_end'])+timedelta(hours=24)
 if not p.native_in_window(native,start,end):return 'OUTSIDE_PUBLICATION_WINDOW'
 combined=f"{native.get('title','')} {native.get('text','')}"
 if not p.ATTACK_RE.search(combined):return 'NO_ATTACK_VOCABULARY'
 import re
 if not re.search(r'\bКи(їв|єв)',combined,re.I):return 'NO_EXACT_CITY'
 return 'PASS'
def quality(records):
 if not records:return 'REJECT','NO_FROZEN_NATIVE_RESULTS'
 good=[r for r in records if r.get('native') and r['native'].get('title') and r['native'].get('text')]
 if len(good)<2 or len(good)/len(records)<.5:return 'REJECT','NATIVE_RETRIEVABILITY'
 if sum(len(r['native']['text'])>=200 for r in good)/len(good)<.7:return 'REJECT','FULL_ARTICLE_BODY'
 if sum(bool(r['native'].get('published_at')) for r in good)/len(good)<.7:return 'REJECT','PUBLICATION_TIMESTAMP'
 return 'PASS',None
def run(corpus_dir):
 for n in ('DATABASE_URL','PGPASSWORD','PGHOST','NEON_DATABASE_URL'):
  if os.getenv(n):raise RuntimeError('DB_CREDENTIAL_PRESENT:'+n)
 discovery=load_verified(corpus_dir/EXPECTED['discovery'])
 native=load_verified(corpus_dir/EXPECTED['native'])
 normalized=load_verified(corpus_dir/EXPECTED['normalized'])
 nmap={r['requested_native_url']:r for r in native['records']}
 evidence_map={r['requested_native_url']:r for r in normalized['records']}
 for url,rec in nmap.items():
  if rec.get('native') and rec['native'].get('text'):
   frozen=evidence_map.get(url)
   if not frozen or rec['native']['text']!=frozen['exact_normalized_text'] or sha(rec['native']['text'].encode())!=frozen['normalized_text_sha256']:raise RuntimeError('NORMALIZED_TEXT_IDENTITY_MISMATCH')
 cohort=discovery['development_episodes']
 if len(cohort)!=67:raise RuntimeError('COHORT_NOT_67')
 truths={r['episode_id']:r['truth_label'] for r in json.loads(INPUT.read_text())['episodes']}
 if sum(x in POS for x in truths.values())!=48 or sum(x=='HOLD_CONTROL' for x in truths.values())!=19:raise RuntimeError('DEVELOPMENT_COHORT_LABELS_INVALID')
 p=load(PILOT,'unchanged_pilot')
 # Build only from frozen result-to-native associations.
 discovered=defaultdict(list)
 for hit in discovery['search_hits']:
  url=hit.get('native_url')
  if url in nmap:
   row=nmap[url]
   if row.get('native'):
    discovered[hit['episode_id']].append((hit,row))
 by_family=defaultdict(dict)
 for hit,row in (pair for pairs in discovered.values() for pair in pairs):
  fam=row.get('normalized_source_family')
  by_family[fam][row['requested_native_url']]=row
 gate={family:dict(zip(('verdict','reason'),quality(list(by_family[family].values())))) for family in STAGE2}
 pass_families=[f for f in STAGE2 if gate[f]['verdict']=='PASS']
 variants=[('SOURCE SET 0',set()),('VARIANT A',set(A))]
 variants.extend((f'STAGE2 SINGLE {f}',set(A)|{f}) for f in pass_families)
 for size in range(1,min(3,len(pass_families))+1):variants.append((f'CUMULATIVE STAGE2 {size}',set(A)|set(pass_families[:size])))
 assert len(variants)<=18
 # prepare_authoritative_monitor loads frozen classifier in detached worktree
 tmp=Path(tempfile.mkdtemp(prefix='kyiv-runner-proof-'))
 wt=None
 try:
  mon,wt=p.prepare_authoritative_monitor(tmp)
  all_ep=p.load_full_kyiv_episodes()
  # After fixed local git preparation, all evidence network is forbidden.
  disable_evidence_network()
  results={}
  forensic={}
  selected=None
  new_holds=[]
  for name,added in variants:
   rows=[]
   hold_proof=[]
   for ep in cohort:
    eid=ep['episode_id']
    candidates={}
    for hit,rec in discovered.get(eid,[]):
     family=rec['normalized_source_family']
     if family not in {x[0] for x in p.SOURCE_ORDER if x[0]!='generic_search'}|added:continue
     if admission(p,rec['native'],ep)!='PASS':continue
     row,meta=p.make_candidate(family,rec['native'],'frozen_runner_search',{
      'query_family':hit['query_family'],'result_rank':hit['result_rank'],
      'wrapper_url':hit['wrapper_url']})
     candidates[(family,row['candidate_id'])]=(row,meta,rec)
    entries=list(candidates.values())
    final,records,composition,count=p.classify_episode(mon,all_ep,ep,[(x[0],x[1]) for x in entries])
    candidate_rows=[]
    for x in entries:
     row,meta,rec=x
     candrecord=next((r for r in records if r.get('candidate_url')==row['url'] and r.get('source_family')==meta['source_family']),{})
     candidate_rows.append({
      'candidate_id':row['candidate_id'],'family':meta['source_family'],
      'url':row['url'],'text_sha256':rec['extracted_text_sha256'],
      'classifier_outcome':candrecord.get('classifier_outcome'),
      'classifier_episode_id':candrecord.get('classifier_episode_id'),
      'reason_codes':candrecord.get('reason_codes') or [],
      'temporal_binding':candrecord.get('temporal_binding') or {},
      'classifier_error':candrecord.get('classifier_error')})
    candidate_rows.sort(key=lambda x:(x['family'],x['candidate_id']))
    rows.append({'episode_id':eid,'truth_label':truths[eid],'final':final,
     'candidate_count':len(entries),'candidates':candidate_rows,'composition':composition})
    if truths[eid]=='HOLD_CONTROL' and final in POS:
     hold_proof.append({'episode_id':eid,'final':final,'evidence':candidate_rows,
      'forensic_status':'NOT PRE-CLEARED WITHOUT EXACT IDENTITY'})
   positives=[r for r in rows if r['truth_label'] in POS]
   holds=[r for r in rows if r['truth_label']=='HOLD_CONTROL']
   results[name]={
    'candidate_positives':sum(r['candidate_count']>0 for r in positives),
    'final_positives':sum(r['final'] in POS for r in positives),
    'hold_promotions':[r['episode_id'] for r in holds if r['final'] in POS],
    'per_episode':rows}
   forensic[name]=hold_proof
  baseline=set(results['SOURCE SET 0']['hold_promotions'])
  for name,rec in results.items():
   fresh=set(rec['hold_promotions'])-baseline
   if fresh:
    for hold in forensic[name]:
     if hold['episode_id'] in fresh:new_holds.append({'variant':name,**hold})
  # No earlier-cleared SHA evidence supplied: all novel promotions require review.
  candidates=[(name,r) for name,r in results.items() if name not in {'SOURCE SET 0'} and not (set(r['hold_promotions'])-baseline)]
  if not new_holds and candidates:
   selected=max(candidates,key=lambda item:(item[1]['final_positives'],item[1]['candidate_positives']))[0]
  # Counters are not derived from network promises; sandbox forbids all such requests.
  return {'schema':'kyiv-runner-offline-replay-v1',
   'corpus_hashes':{k:v['payload_sha256'] for k,v in (('discovery',discovery),('native',native),('normalized',normalized))},
   'quality_gates':gate,'stage2_pass_families':pass_families,
   'variants_tested':list(results),'results':results,'forensic_holds':forensic,
   'new_uncleared_holds':new_holds,'selected_development_baseline':selected,
   'evidence_network_fetches':{'publisher':0,'search':0,'telegram':0},
   'blind_per_episode_data_inspected':False,'blind_wrapper_decode_attempts':0,
   'historical_backfill_started':False,'neon_writes':0,'production_mutations':0}
 finally:
  if wt:
   subprocess.run(['git','worktree','remove','--force',str(wt)],capture_output=True)
  shutil.rmtree(tmp,ignore_errors=True)
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--corpus-dir',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);a=parser.parse_args()
 try:
  data=run(a.corpus_dir);a.output.write_bytes(canonical(data))
  print('JOB_B_REPLAY_SHA256='+sha(canonical(data)),flush=True)
  print('JOB_B_SUMMARY='+json.dumps({
   'stage2_evaluated':len(STAGE2),'stage2_pass':data['stage2_pass_families'],
   'variant_count':len(data['variants_tested']),
   'source_0':{k:data['results']['SOURCE SET 0'][k] for k in ('candidate_positives','final_positives')},
   'variant_a':{k:data['results']['VARIANT A'][k] for k in ('candidate_positives','final_positives')},
   'new_holds':len(data['new_uncleared_holds']),'selected':data['selected_development_baseline']
  },sort_keys=True),flush=True)
 except Exception as exc:
  print('JOB_B_FAILURE='+type(exc).__name__+':'+str(exc),file=sys.stderr,flush=True);raise
