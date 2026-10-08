#!/usr/bin/env python3
from __future__ import annotations
import copy, hashlib, importlib.util, json, re, shutil, subprocess, tempfile
from collections import Counter
from datetime import timedelta
from pathlib import Path

PILOT=Path('.github/proof/kyiv_historical_discovery_calibration_pilot.py')
NET=Path('research/kyiv_historical_google_news_url_resolution_network_proof_2026-10-08.json')
STRAT=Path('research/kyiv_historical_discovery_frozen_strategy_2026-10-08.json')
OUT=Path('research/kyiv_historical_discovery_development_classifier_replay_2026-10-08.json')
FREEZE=Path('research/kyiv_historical_discovery_development_classifier_input_2026-10-08.json')
AUTH_COMMIT='71cb6f6fbe856cc7b96759310fe9cc9c71cc0453'
AUTH_PATH='kyiv-air-alerts-grafana/scripts/monitor_explosion_candidates.py'
AUTH_BLOB='778469b74c2aa807d851cf2c2ee35cf4aa785589'
RESOLVER_BLOB='2bd9b9ee2f6d9c797c816476cc25e72214584a86'
NET_BLOB='80a51565f940dcbf3824de04034d6c86416b52be'
STRAT_BLOB='333471f967e728fe185b8b751f0c1a5a1884c391'
POS={'STRICT_EVENT_POSITIVE','SENSITIVITY_EVENT_POSITIVE'}
OLD_EVID=13/145; OLD_FINAL=3/145

def run(args,check=True):
 p=subprocess.run(args,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 if check and p.returncode: raise RuntimeError('CMD:'+repr(args)+'\n'+p.stderr[-3000:])
 return p.stdout.strip()
def git(*a): return run(['git',*a])
def load(path,name):
 s=importlib.util.spec_from_file_location(name,path); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
def canon(o): return (json.dumps(o,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode()
def sha(b): return hashlib.sha256(b).hexdigest()
def present(x): return bool((x or {}).get('present'))

def freeze_input(p,net,strat):
 down=net['development_downstream_replay']; dev=list(strat['development_results'])
 assert len(dev)==67 and sum(r['truth_label'] in POS for r in dev)==48 and sum(r['truth_label']=='HOLD_CONTROL' for r in dev)==19
 assert down['episodes_replayed']==67 and down['usable_source_native_texts_recovered']==90 and down['publication_timestamps_recovered']==90 and down['candidates_materialized']==40
 by={str(x['episode_id']):x for x in down['episode_results']}; assert len(by)==67
 http=p.HTTP(); evidence=[]; episodes=[]; counts=Counter()
 for r in sorted(dev,key=lambda x:((x.get('result') or {}).get('alert_start') or '',x['episode_id'])):
  eid=str(r['episode_id']); tr=r['truth_label']; rr=r['result']; ep={'episode_id':eid,'city_key':'kyiv','alert_start':rr['alert_start'],'alert_end':rr['alert_end']}
  urls=list(by[eid].get('native_urls') or []); start=p.parse_dt(ep['alert_start'])-timedelta(hours=6); end=p.parse_dt(ep['alert_end'])+timedelta(hours=24)
  cmap={}; idxs=[]
  for url in urls:
   fi=p.fixed_family_for_url(url)
   if not fi: continue
   family,kind,handle=fi; counts['attempts']+=1
   native,err=(p.fetch_telegram_post(http,url,handle) if kind=='telegram' else p.extract_article(http,url))
   ev={'episode_id':eid,'truth_label':tr,'alert_start':ep['alert_start'],'alert_end':ep['alert_end'],'source_family':family,'native_url_from_frozen_recovery':url,'native_fetch_succeeded':bool(native),'native_fetch_error':err,'resolved_native_url':(native or {}).get('url'),'publication_time':(native or {}).get('published_at'),'title':(native or {}).get('title'),'source_native_text':(native or {}).get('text'),'admission_result':'REJECTED','admission_reason':None,'candidate_id':None}
   ix=len(evidence); idxs.append(ix)
   if not native: ev['admission_reason']='NATIVE_FETCH_FAILED'; evidence.append(ev); continue
   counts['fetch']+=1; text=str(native.get('text') or '')
   counts['text']+=bool(text); counts['time']+=bool(native.get('published_at'))
   if not text or not native.get('published_at'): ev['admission_reason']='OTHER_EXISTING_ADMISSION_RULE'; ev['admission_detail']='NO_USABLE_TEXT_OR_TIMESTAMP'; evidence.append(ev); continue
   if not p.native_in_window(native,start,end): ev['admission_reason']='OUTSIDE_PUBLICATION_WINDOW'; evidence.append(ev); continue
   combined=f"{native.get('title','')} {native.get('text','')}"
   if not p.ATTACK_RE.search(combined): ev['admission_reason']='ATTACK_VOCABULARY_NOT_MATCHED'; evidence.append(ev); continue
   if not re.search(r'\bКи(їв|єв)',combined,re.I): ev['admission_reason']='EXACT_KYIV_NOT_MATCHED'; evidence.append(ev); continue
   cand,meta=p.make_candidate(family,native,'retained_wrapper_native_replay',{'query_family':'frozen_development_wrapper'}); cid=cand['candidate_id']; ev['candidate_id']=cid
   if cid in cmap: ev['admission_reason']='DUPLICATE_CANDIDATE'; evidence.append(ev); continue
   ev['admission_result']='ADMITTED'; evidence.append(ev); meta={**meta,'candidate_id':cid,'evidence_record_index':ix}; cmap[cid]={'candidate':cand,'meta':meta,'evidence_record_index':ix}
  cands=[cmap[k] for k in sorted(cmap)]; counts['candidates']+=len(cands)
  episodes.append({**ep,'truth_label':tr,'frozen_native_urls':urls,'fixed_source_evidence_record_indices':idxs,'candidate_count':len(cands),'candidates':cands})
 got={'native_fetch_attempts':counts['attempts'],'native_fetch_successes':counts['fetch'],'usable_source_native_texts':counts['text'],'publication_timestamps':counts['time'],'admitted_candidates':counts['candidates']}
 exp={'native_fetch_attempts':down['native_fetch_attempts'],'native_fetch_successes':down['native_fetch_successes'],'usable_source_native_texts':90,'publication_timestamps':90,'admitted_candidates':40}
 return {'schema_version':1,'kind':'kyiv_historical_discovery_development_classifier_input','authoritative_classifier':{'commit':AUTH_COMMIT,'path':AUTH_PATH,'blob':AUTH_BLOB},'source_network_proof_blob':NET_BLOB,'source_strategy_blob':STRAT_BLOB,'reconstruction_counts':got,'expected_predecessor_counts':exp,'reconstruction_exact_count_match':got==exp,'evidence_records':evidence,'episodes':episodes,'blind_data_used':False,'google_news_queries_executed':0,'google_wrapper_decoding_attempts':0}

def enrich(p,mon,all_eps,fep):
 decisions={}; original=mon.classify_candidate
 def capture(row,city,eps,matching=None):
  d=original(row,city,eps,matching); decisions[str(row.get('candidate_id') or '')]=copy.deepcopy(d); return d
 mon.classify_candidate=capture
 try:
  pairs=[(copy.deepcopy(x['candidate']),copy.deepcopy(x['meta'])) for x in fep['candidates']]
  ep={k:fep[k] for k in ('episode_id','city_key','alert_start','alert_end')}
  final,records,composition,inv=p.classify_episode(mon,all_eps,ep,pairs)
 finally: mon.classify_candidate=original
 comp_ids=set((composition or {}).get('contributing_candidate_ids') or []); outs=[]
 for rec in records:
  cid=str(rec.get('candidate_id') or ''); d=decisions.get(cid) or {}; outcome=d.get('proposed_outcome'); matched=d.get('proposed_matched_episode_id')==ep['episode_id']
  if cid in comp_ids: contribution='COMPOSED_ALERT_LEVEL_POSITIVE_CONTRIBUTOR'
  elif outcome=='approved_strict' and matched: contribution='DIRECT_STRICT_ALERT_LEVEL_CONTRIBUTOR'
  elif outcome=='approved_sensitivity' and matched: contribution='DIRECT_SENSITIVITY_ALERT_LEVEL_CONTRIBUTOR'
  elif outcome=='needs_review' and final=='NEEDS_REVIEW': contribution='ALERT_LEVEL_REVIEW_CONTRIBUTOR'
  else: contribution='NO_FINAL_POSITIVE_CONTRIBUTION'
  outs.append({**rec,'episode_id':ep['episode_id'],'alert_start':ep['alert_start'],'alert_end':ep['alert_end'],'candidate_id':cid,'candidate_admission_result':'ADMITTED','authoritative_classifier_invoked':bool(d),'classifier_candidate_level_result':outcome,'classifier_episode_id':d.get('proposed_matched_episode_id'),'classifier_reason_codes':list(d.get('reason_codes') or []),'semantic_fields':{'explicit_attack_event_wording':d.get('strict_explosion_evidence') or {},'event_types':list(d.get('event_types') or []),'exact_kyiv_wording':d.get('exact_city_classification_evidence') or {},'air_context':d.get('air_military_context') or {},'usable_temporal_binding':d.get('temporal_binding') or {},'same_attack_linkage':d.get('same_attack_context') or {},'single_episode_day_inference':d.get('single_episode_day_inference') or {}},'final_contribution_to_alert_level_verdict':contribution})
 return {'episode_id':ep['episode_id'],'alert_start':ep['alert_start'],'alert_end':ep['alert_end'],'candidate_count':fep['candidate_count'],'authoritative_classifier_candidate_invocations':inv,'candidate_outputs':outs,'composition':composition,'final_alert_level_verdict':final}

def sem_presence(c):
 rows=c['candidate_outputs']
 def anyp(k): return any(present((r.get('semantic_fields') or {}).get(k)) for r in rows)
 temporal=False
 for r in rows:
  s=r.get('semantic_fields') or {}; t=s.get('usable_temporal_binding') or {}; n=t.get('near_boundary') or {}; i=s.get('single_episode_day_inference') or {}
  temporal|=bool((t.get('present') and t.get('episode_specific')) or (n.get('present') and n.get('episode_specific')) or i.get('present'))
 return {'explicit_attack_event_wording':anyp('explicit_attack_event_wording'),'exact_kyiv_wording':anyp('exact_kyiv_wording'),'air_context':anyp('air_context'),'usable_temporal_binding':temporal,'same_attack_linkage':anyp('same_attack_linkage')}

def classifier_miss(c):
 rows=[r for r in c['candidate_outputs'] if r.get('authoritative_classifier_invoked')]
 if not rows:return 'OTHER'
 if not any(present(r['semantic_fields']['explicit_attack_event_wording']) for r in rows):return 'CLASSIFIER_ATTACK_EVENT_INSUFFICIENT'
 if not any(present(r['semantic_fields']['exact_kyiv_wording']) for r in rows):return 'CLASSIFIER_EXACT_CITY_INSUFFICIENT'
 if not any(present(r['semantic_fields']['air_context']) for r in rows):return 'CLASSIFIER_AIR_CONTEXT_INSUFFICIENT'
 b3=[r for r in rows if present(r['semantic_fields']['explicit_attack_event_wording']) and present(r['semantic_fields']['exact_kyiv_wording']) and present(r['semantic_fields']['air_context'])]
 if b3 and not any(present(r['semantic_fields']['same_attack_linkage']) for r in b3):return 'CLASSIFIER_SAME_ATTACK_INSUFFICIENT'
 b4=[r for r in b3 if present(r['semantic_fields']['same_attack_linkage'])]
 def temp(r):
  s=r['semantic_fields']; t=s['usable_temporal_binding']; n=t.get('near_boundary') or {}; i=s.get('single_episode_day_inference') or {}
  return bool((t.get('present') and t.get('episode_specific')) or (n.get('present') and n.get('episode_specific')) or i.get('present'))
 if b4 and not any(temp(r) for r in b4):return 'CLASSIFIER_TEMPORAL_BINDING_INSUFFICIENT'
 if any(r.get('classifier_candidate_level_result')=='needs_review' for r in rows):return 'CLASSIFIER_REVIEW_OTHER'
 return 'OTHER'

def main():
 assert git('rev-parse',f'{AUTH_COMMIT}:{AUTH_PATH}')==AUTH_BLOB
 assert git('rev-parse',f'HEAD:{PILOT}')==RESOLVER_BLOB and git('rev-parse',f'HEAD:{NET}')==NET_BLOB and git('rev-parse',f'HEAD:{STRAT}')==STRAT_BLOB
 p=load(PILOT,'kyiv_dev_replay'); net=json.loads(NET.read_text()); strat=json.loads(STRAT.read_text()); assert net['verdict']=='KYIV HISTORICAL GOOGLE NEWS URL RESOLUTION = PROVEN'
 pm=net['mutation_confirmation']; assert pm['blind_per_episode_data_inspected'] is False and pm['blind_wrapper_decoding_attempts']==0
 frozen=freeze_input(p,net,strat); fb=canon(frozen); FREEZE.write_bytes(fb); fsha=sha(fb)
 tech=[]
 if not frozen['reconstruction_exact_count_match']:tech.append('FROZEN_NATIVE_INPUT_RECONSTRUCTION_COUNT_MISMATCH')
 tmp=Path(tempfile.mkdtemp(prefix='kyiv-dev-replay-'))
 try:
  mon,wt=p.prepare_authoritative_monitor(tmp); all_eps=p.load_full_kyiv_episodes(); rows=[]
  for fep in frozen['episodes']: rows.append({'episode_id':fep['episode_id'],'truth_label':fep['truth_label'],'candidate_count':fep['candidate_count'],'classification':enrich(p,mon,all_eps,fep)})
 finally:
  if 'wt' in locals():run(['git','worktree','remove','--force',str(wt)],False)
  shutil.rmtree(tmp,ignore_errors=True)
 if sha(FREEZE.read_bytes())!=fsha:raise RuntimeError('FROZEN_INPUT_MUTATED')
 by={e['episode_id']:e for e in frozen['episodes']}; pos=[r for r in rows if r['truth_label'] in POS]; holds=[r for r in rows if r['truth_label']=='HOLD_CONTROL']; verdict=lambda r:r['classification']['final_alert_level_verdict']
 pc=sum(r['candidate_count']>0 for r in pos); hc=sum(r['candidate_count']>0 for r in holds); strict=sum(verdict(r)=='STRICT_EVENT_POSITIVE' for r in pos); sens=sum(verdict(r)=='SENSITIVITY_EVENT_POSITIVE' for r in pos); reproduced=strict+sens; review=sum(verdict(r)=='NEEDS_REVIEW' for r in pos); no=sum(verdict(r)=='NO_CONFIRMED_EVENT' for r in pos); hs=sum(verdict(r)=='STRICT_EVENT_POSITIVE' for r in holds); hse=sum(verdict(r)=='SENSITIVITY_EVENT_POSITIVE' for r in holds); hr=sum(verdict(r)=='NEEDS_REVIEW' for r in holds); hn=sum(verdict(r)=='NO_CONFIRMED_EVENT' for r in holds); unsupported=hs+hse
 misses=[]; mc=Counter(); before=inside=0
 for r in pos:
  if verdict(r) in POS:continue
  fe=by[r['episode_id']]; detail=None
  if not r['candidate_count']:
   before+=1; idx=fe['fixed_source_evidence_record_indices']
   if not fe['frozen_native_urls']: cls='NO_NATIVE_URL'
   elif not idx: cls='OTHER'; detail='NATIVE_URLS_RESOLVED_BUT_NONE_BELONGED_TO_THE_FROZEN_FIXED_SOURCE_SET'
   else:
    ev=[frozen['evidence_records'][i] for i in idx]
    if all(not x['native_fetch_succeeded'] for x in ev):cls='NATIVE_FETCH_FAILED'
    elif all((not x.get('source_native_text')) or (not x.get('publication_time')) for x in ev):cls='NO_USABLE_TEXT'
    else:cls='CANDIDATE_ADMISSION_REJECTED'
  else: inside+=1; cls=classifier_miss(r['classification'])
  mc[cls]+=1; misses.append({'episode_id':r['episode_id'],'primary_first_failure_class':cls,'detail':detail})
 adm=Counter(); admp=Counter(); admh=Counter()
 for e in frozen['evidence_records']:
  if e['admission_result']=='REJECTED':
   k=e.get('admission_reason') or 'OTHER_EXISTING_ADMISSION_RULE'; adm[k]+=1; (admp if e['truth_label'] in POS else admh)[k]+=1
 dist=Counter(e['candidate_count'] for e in frozen['episodes']); multi=sum(e['candidate_count']>1 for e in frozen['episodes']); cap=sum(r['candidate_count'] for r in pos); cah=sum(r['candidate_count'] for r in holds)
 sem_rep=Counter(); sem_miss=Counter()
 for r in pos:
  if not r['candidate_count']:continue
  target=sem_rep if verdict(r) in POS else sem_miss
  for k,v in sem_presence(r['classification']).items():target[k]+=int(v)
 hold_safety=[]
 for r in holds:
  if not r['candidate_count']:continue
  fe=by[r['episode_id']]; refs=[{'evidence_record_index':i,'native_url':frozen['evidence_records'][i].get('resolved_native_url') or frozen['evidence_records'][i].get('native_url_from_frozen_recovery'),'publication_time':frozen['evidence_records'][i].get('publication_time'),'candidate_id':frozen['evidence_records'][i].get('candidate_id'),'admission_result':frozen['evidence_records'][i].get('admission_result'),'admission_reason':frozen['evidence_records'][i].get('admission_reason')} for i in fe['fixed_source_evidence_record_indices']]
  positive=verdict(r) in POS; hold_safety.append({'episode_id':r['episode_id'],'recovered_native_evidence':refs,'classifier_verdict':verdict(r),'safety_label':'POTENTIAL UNSUPPORTED PROMOTION' if positive else 'NON_POSITIVE','reason':'Historical hold control received a positive authoritative alert-level verdict; no mutation performed.' if positive else 'Authoritative classifier retained the hold as non-positive.'})
 inv=sum(r['classification']['authoritative_classifier_candidate_invocations'] for r in rows)
 if len(rows)!=67:tech.append('ALERT_LEVEL_VERDICT_COUNT_MISMATCH')
 if inv!=frozen['reconstruction_counts']['admitted_candidates']:tech.append('CANDIDATE_INVOCATION_COUNT_MISMATCH')
 blocker=bool(tech); crecall=pc/48; frecall=reproduced/48
 if blocker: rec='TECHNICAL BLOCKER'; final='KYIV HISTORICAL DEVELOPMENT CLASSIFIER REPLAY = BLOCKED'
 elif unsupported: rec='SAFETY FAILURE'; final='KYIV HISTORICAL DEVELOPMENT CLASSIFIER REPLAY = SAFETY FAILURE'
 elif frecall<.40: rec='DEVELOPMENT PERFORMANCE INSUFFICIENT'; final='KYIV HISTORICAL DEVELOPMENT CLASSIFIER REPLAY = PERFORMANCE INSUFFICIENT'
 else: rec='READY FOR NEW INDEPENDENT VALIDATION'; final='KYIV HISTORICAL DEVELOPMENT CLASSIFIER REPLAY = READY FOR INDEPENDENT VALIDATION'
 art={'schema_version':1,'kind':'kyiv_historical_discovery_development_classifier_replay','verdict':final,'authoritative_classifier':{'commit':AUTH_COMMIT,'path':AUTH_PATH,'blob':AUTH_BLOB,'semantics_modified':False},'frozen_classifier_input_sha256':fsha,'frozen_classifier_input':frozen,'episode_candidate_coverage':{'positive_episodes_with_at_least_one_candidate':pc,'hold_episodes_with_at_least_one_candidate':hc,'candidates_attached_to_positives':cap,'candidates_attached_to_holds':cah,'candidate_count_per_episode_distribution':{str(k):v for k,v in sorted(dist.items())},'episodes_with_multiple_candidates':multi,'candidate_episode_recall':crecall},'admission_90_to_40_accounting':{'usable_source_native_texts':frozen['reconstruction_counts']['usable_source_native_texts'],'publication_timestamps':frozen['reconstruction_counts']['publication_timestamps'],'admitted_candidates':frozen['reconstruction_counts']['admitted_candidates'],'recovered_texts_rejected_by_admission':sum(adm.values()),'rejection_reasons_all':dict(adm),'rejection_reasons_positive_episodes':dict(admp),'rejection_reasons_hold_episodes':dict(admh)},'per_candidate_authoritative_classifier_output':[x for r in rows for x in r['classification']['candidate_outputs']],'per_episode_final_verdict':[{'episode_id':r['episode_id'],'truth_label':r['truth_label'],'candidate_count':r['candidate_count'],'final_alert_level_verdict':verdict(r),'authoritative_classifier_candidate_invocations':r['classification']['authoritative_classifier_candidate_invocations'],'composition':r['classification']['composition']} for r in rows],'positive_miss_taxonomy':{'misses':misses,'counts':dict(mc),'dominant_positive_miss_class':mc.most_common(1)[0][0] if mc else None},'discovery_vs_classifier_loss':{'positives_lost_before_candidate_admission':before,'positives_with_candidate_but_lost_in_classifier':inside,'positives_successfully_reproduced':reproduced},'historical_positive_semantic_comparison':{'reproduced_positive_episode_count':reproduced,'missed_positive_with_candidate_episode_count':inside,'missed_before_admission_not_semantically_evaluated':before,'reproduced_positives':dict(sem_rep),'missed_positives_with_candidate':dict(sem_miss),'newly_recovered_evidence_only':True},'hold_safety_results':hold_safety,'development_metrics':{'development_episodes':67,'development_positives':48,'development_holds':19,'usable_native_texts':frozen['reconstruction_counts']['usable_source_native_texts'],'admitted_candidates':frozen['reconstruction_counts']['admitted_candidates'],'positive_episodes_with_candidate':pc,'hold_episodes_with_candidate':hc,'candidate_episode_recall':crecall,'authoritative_classifier_candidate_invocations':inv,'alert_level_verdicts_produced':len(rows),'known_positives_reproduced':reproduced,'final_positive_recall':frecall,'strict_reproduced':strict,'sensitivity_reproduced':sens,'known_positives_remaining_review':review,'known_positives_no_confirmed_event':no,'hold_strict_promotions':hs,'hold_sensitivity_promotions':hse,'hold_review':hr,'hold_no_confirmed_event':hn,'unsupported_hold_promotions':unsupported,'positives_lost_before_admission':before,'positives_lost_in_classifier':inside},'development_cohort_comparison':{'label':'DEVELOPMENT-COHORT COMPARISON','old_evidence_recall_baseline':OLD_EVID,'old_final_positive_baseline':OLD_FINAL,'development_candidate_episode_recall':crecall,'development_final_positive_recall':frecall,'candidate_or_evidence_recall_absolute_percentage_point_improvement':round((crecall-OLD_EVID)*100,3),'final_positive_recall_absolute_percentage_point_improvement':round((frecall-OLD_FINAL)*100,3),'independent_validation':False},'technical_execution':{'technical_blocker_remaining':blocker,'technical_errors':tech,'input_reconstruction_exact_count_match':frozen['reconstruction_exact_count_match'],'classifier_input_sha_unchanged_after_replay':sha(FREEZE.read_bytes())==fsha},'recommendation':rec,'mutation_confirmation':{'blind_per_episode_data_inspected':False,'blind_wrapper_decoding_attempts':0,'blind_queries_rerun':0,'historical_backfill_started':False,'unknown_alert_pilot_started':False,'Neon_writes':0,'production_mutations':0,'classifier_semantics_modified':False,'discovery_semantics_modified':False,'google_news_discovery_queries_executed':0,'proof_only_isolated_branch_artifacts':True}}
 OUT.write_text(json.dumps(art,ensure_ascii=False,indent=2,sort_keys=True)+'\n')
 print('DEVELOPMENT_CLASSIFIER_REPLAY_SUMMARY='+json.dumps({'verdict':final,'classifier_input_sha256':fsha,'texts':frozen['reconstruction_counts']['usable_source_native_texts'],'candidates':frozen['reconstruction_counts']['admitted_candidates'],'positive_candidate_episodes':pc,'hold_candidate_episodes':hc,'candidate_recall':crecall,'rejected_by_admission':sum(adm.values()),'admission_reasons':dict(adm),'classifier_invocations':inv,'alert_verdicts':len(rows),'reproduced':reproduced,'final_recall':frecall,'strict':strict,'sensitivity':sens,'review':review,'no_confirmed':no,'hold_strict':hs,'hold_sensitivity':hse,'unsupported_hold_promotions':unsupported,'lost_before_admission':before,'lost_in_classifier':inside,'dominant_miss':mc.most_common(1)[0][0] if mc else None,'miss_counts':dict(mc),'technical_blocker':blocker,'technical_errors':tech,'recommendation':rec},sort_keys=True))
 return 0
if __name__=='__main__':raise SystemExit(main())

# workflow trigger: development classifier replay proof only
