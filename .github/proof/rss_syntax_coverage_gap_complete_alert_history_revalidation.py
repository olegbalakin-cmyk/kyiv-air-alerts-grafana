#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,os,subprocess,sys
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[2]; APP=ROOT/'kyiv-air-alerts-grafana'; sys.path.insert(0,str(APP/'scripts'))
import apply_ukrainealarm_bridge as ua
import monitor_explosion_candidates as mon
import update_data as kd
UTC=timezone.utc; KTZ=ZoneInfo('Europe/Kyiv')
DIAG='bf2efe5015a81ebc12fdac615dbdb801e947b5dd'; FROZEN_SHA='5ebd77a7a1066fa4a2dabe62c98ee5c6b30d60c817282d560e8908f482ff8ef8'
TARGETS={
'ecf26b3980c9dcac8234f689':('kyiv','Київ','syntax:kyiv:2026-10-03T22:30','ctx-001','2026-10-03T22:30:00+03:00','2026-10-03T19:30:00Z'),
'5b93c789ce785522030a51f4':('sumy','Суми','syntax:sumy:2026-10-04T08:00','ctx-001','2026-10-04T08:00:00+03:00','2026-10-04T05:00:00Z'),
'ccc799cf4b6706daac05f35e':('sumy','Суми','syntax:sumy:2026-10-04T08:00','ctx-002','2026-10-04T08:00:00+03:00','2026-10-04T05:00:00Z'),
'130a62ecc060e529737c7326':('sumy','Суми','syntax:sumy:2026-10-04T14:00','ctx-001','2026-10-04T14:00:00+03:00','2026-10-04T11:00:00Z'),
'7b99452890d6b851455983af':('sumy','Суми','syntax:sumy:2026-10-04T14:00','ctx-001','2026-10-04T14:00:00+03:00','2026-10-04T11:00:00Z')}
EXCLUDED='383e064c794bece60e20d4ca'
BLOBS={'kyiv-air-alerts-grafana/scripts/update_data.py':'3b1a2ad87011c3f984d4fcddd85c29f158e56ed8','kyiv-air-alerts-grafana/scripts/apply_ukrainealarm_bridge.py':'b59df2335c32a7b28fd81e7adabaec5d37f8f653','kyiv-air-alerts-grafana/scripts/monitor_explosion_candidates.py':'b007d32ba49c7934bce978877f7b2a29cc364f1b','kyiv-air-alerts-grafana/data/alerts_combined.json':'ab9babd3527055256017867869bc62b96a6ebffc'}

def git(*a): return subprocess.check_output(['git',*a],cwd=ROOT,text=True).strip()
def dt(v):
 x=datetime.fromisoformat(str(v).replace('Z','+00:00')); return (x if x.tzinfo else x.replace(tzinfo=UTC)).astimezone(UTC)
def iso(x): return x.astimezone(UTC).isoformat().replace('+00:00','Z')
def response_meta(r,a,b,params=None):
 return {'requested_at_utc':iso(a),'completed_at_utc':iso(b),'method':'GET','requested_url':str(r.request.url if r.request else r.url),'final_url':str(r.url),'request_parameters':params or {},'status_code':r.status_code,'reason':r.reason,'content_type':r.headers.get('Content-Type'),'response_bytes':len(r.content),'response_sha256':hashlib.sha256(r.content).hexdigest(),'etag':r.headers.get('ETag'),'last_modified':r.headers.get('Last-Modified'),'date_header':r.headers.get('Date')}
def epv(e): return {k:e.get(k) for k in ('episode_id','city_key','city','alert_source','alert_start','alert_end')}
def target_row(r,c): return {'candidate_id':r['candidate_id'],'city_key':r['city'],'city':r.get('city_label'),'title':r.get('rss_title') or '','snippet':r.get('rss_snippet') or '','publisher':r.get('publisher') or '','url':r.get('rss_url') or '','published_at':r.get('publication_timestamp'),'discovery_basis':'publisher_fulltext','matched_text_excerpt':c.get('source_excerpt') or '','status':'needs_review'}
def official_iv(r):
 if not isinstance(r,dict) or r.get('type')!='Повітряна тривога' or not r.get('dateTimeStart') or not r.get('dateTimeEnd'): return None
 try: s=kd.localize_naive(datetime.fromisoformat(str(r['dateTimeStart']))).astimezone(UTC); e=kd.localize_naive(datetime.fromisoformat(str(r['dateTimeEnd']))).astimezone(UTC)
 except ValueError: return None
 return (s,e) if e>s else None
def intersects(s,e,a,b): return s<b and e>=a
def active(s,e,t): return s<=t<=e

def fetch_kyiv():
 src={'available':False,'identity':'kyiv_combined_exact_city','authoritative_components':[{'name':'Kyiv municipal open data official JSON','url':kd.OFFICIAL_JSON_URL},{'name':'Kyiv Digital live history','url':kd.LIVE_HISTORY_URL}],'normalization':'update_data.parse_official + update_data.parse_live_history + update_data.merge_sources; monitor.make_episode','timezone':'Europe/Kyiv'}
 try:
  ses=kd.http_session(); a=datetime.now(UTC); ro=ses.get(kd.OFFICIAL_JSON_URL,timeout=30); b=datetime.now(UTC); mo=response_meta(ro,a,b); ro.raise_for_status(); po=ro.json(); official=kd.parse_official(po)
  a=datetime.now(UTC); rl=ses.get(kd.LIVE_HISTORY_URL,timeout=30); b=datetime.now(UTC); ml=response_meta(rl,a,b); rl.raise_for_status(); live,events=kd.parse_live_history(rl.text)
  if not events: raise RuntimeError('Kyiv Digital live history returned no parsable events')
  merged,added=kd.merge_sources(official,live); episodes={}; source_by_id={}
  for x in merged:
   e=mon.make_episode('kyiv',x.start.astimezone(UTC),x.end.astimezone(UTC),source='kyiv_combined_exact_city'); episodes[e['episode_id']]=e; source_by_id[e['episode_id']]=x.source
  eps=sorted(episodes.values(),key=lambda x:x['alert_start']); ws=datetime(2026,10,2,tzinfo=KTZ).astimezone(UTC); we=datetime(2026,10,5,tzinfo=KTZ).astimezone(UTC)
  off=[]
  for r in po if isinstance(po,list) else []:
   iv=official_iv(r)
   if iv and intersects(*iv,ws,we): off.append(r)
  le=[{'start_local':x.start.isoformat(),'end_local':x.end.isoformat(),'start_utc':iso(x.start),'end_utc':iso(x.end),'source':x.source} for x in live if intersects(x.start.astimezone(UTC),x.end.astimezone(UTC),ws,we)]
  ev=[{'timestamp_local':x.isoformat(),'timestamp_utc':iso(x),'kind':k} for x,k in events if ws<=x.astimezone(UTC)<we]
  latest=max((dt(x['alert_end']) for x in eps),default=None); cov=bool(latest and latest>=dt('2026-10-03T19:30:00Z'))
  src.update({'available':True,'fetch_timestamp_utc':iso(datetime.now(UTC)),'requests':{'official_json':mo,'live_history':ml},'raw_relevant_records':{'window_start_utc':iso(ws),'window_end_utc_exclusive':iso(we),'official_json_rows':off,'kyiv_digital_parsed_event_rows':ev,'kyiv_digital_completed_alert_rows':le},'normalization_metadata':{'official_completed_alerts':len(official),'live_completed_alerts_parsed':len(live),'live_alerts_added_after_official_cutoff':added,'combined_completed_alerts':len(merged),'combined_episode_count':len(eps),'latest_combined_end_utc':iso(latest) if latest else None,'coverage_sufficient_for_target':cov,'merged_raw_source_by_episode_id':source_by_id}})
  return src,eps,{'official':po,'live':live}
 except Exception as e: src['error']=f'{type(e).__name__}: {e}'; return src,[],{}

class Replay:
 def __init__(self,r): self.r=r
 def get(self,url,*,params=None,context=''):
  assert url==ua.HISTORY_URL and params=={'regionId':'114'}; return self.r

def raw_sumy(payload,ws,we):
 groups=[payload] if isinstance(payload,dict) else [x for x in payload if isinstance(x,dict)] if isinstance(payload,list) else []; out=[]
 for gi,g in enumerate(groups):
  meta={k:v for k,v in g.items() if k!='alarms'}
  for ai,a in enumerate(g.get('alarms') or []):
   if not isinstance(a,dict) or str(a.get('alertType') or '').upper()!='AIR': continue
   s=ua.parse_dt(a.get('startDate')); e=ua.parse_dt(a.get('endDate'))
   if s and e and e>s and intersects(s,e,ws,we): out.append({'group_index':gi,'alarm_index':ai,'group_metadata':meta,'raw_source_id':a.get('id') or a.get('alarmId') or a.get('alertId'),'start_utc':iso(s),'end_utc':iso(e),'raw_record':a})
 return out

def fetch_sumy():
 src={'available':False,'identity':'ukrainealarm_regionHistory:Сумський район:114','authoritative_component':{'name':'UkraineAlarm regionHistory','url':ua.HISTORY_URL,'region_id':'114','region_name':'Сумський район'},'normalization':'apply_ukrainealarm_bridge.history_rows (AIR only, valid completed start/end, exact-pair dedup) + monitor.make_episode','timezone':'Europe/Kyiv'}
 token=os.getenv(ua.TOKEN_ENV,'').strip()
 if not token: src['error']=f'{ua.TOKEN_ENV} not configured'; return src,[],{}
 try:
  c=ua.UkraineAlarmClient(token); params={'regionId':'114'}; a=datetime.now(UTC); r=c.get(ua.HISTORY_URL,params=params,context='coverage-gap revalidation Sumy (114)'); b=datetime.now(UTC); meta=response_meta(r,a,b,params); payload=r.json(); rows=ua.history_rows(Replay(r),'114','Сумський район')
  eps={}
  for x in rows:
   e=mon.make_episode('sumy',x['start'],x['end'],source='ukrainealarm_regionHistory'); eps[e['episode_id']]=e
  eps=sorted(eps.values(),key=lambda x:x['alert_start']); ws=datetime(2026,10,3,tzinfo=KTZ).astimezone(UTC); we=datetime(2026,10,6,tzinfo=KTZ).astimezone(UTC); rr=raw_sumy(payload,ws,we)
  starts=[dt(e['alert_start']) for e in eps]; ends=[dt(e['alert_end']) for e in eps]; earliest=min(starts) if starts else None; latest=max(ends) if ends else None; day=datetime(2026,10,4,tzinfo=KTZ).astimezone(UTC); target=dt('2026-10-04T11:00:00Z'); cov=bool(earliest and latest and earliest<=day and latest>=target)
  groups=[payload] if isinstance(payload,dict) else [x for x in payload if isinstance(x,dict)] if isinstance(payload,list) else []
  src.update({'available':True,'fetch_timestamp_utc':iso(datetime.now(UTC)),'request':meta,'response_shape':{'top_level_type':type(payload).__name__,'group_count':len(groups),'alarm_count_all_types':sum(len(g.get('alarms') or []) for g in groups)},'raw_relevant_records':{'window_start_utc':iso(ws),'window_end_utc_exclusive':iso(we),'rows':rr},'normalization_metadata':{'normalized_completed_air_rows':len(rows),'normalized_episode_count':len(eps),'earliest_normalized_start_utc':iso(earliest) if earliest else None,'latest_normalized_end_utc':iso(latest) if latest else None,'coverage_reaches_start_of_target_local_day':bool(earliest and earliest<=day),'coverage_reaches_beyond_latest_target_instant':bool(latest and latest>=target),'coverage_sufficient_for_targets':cov}}); return src,eps,{'rows':rr}
 except Exception as e: src['error']=f'{type(e).__name__}: {e}'; return src,[],{}

def kyiv_raw(t,active_eps,ctx,src):
 ids={e['episode_id'] for e in active_eps}; out=[]; sb=src.get('normalization_metadata',{}).get('merged_raw_source_by_episode_id') or {}
 for r in ctx.get('official') or []:
  iv=official_iv(r)
  if not iv or not active(*iv,t): continue
  e=mon.make_episode('kyiv',*iv,source='kyiv_combined_exact_city')
  if e['episode_id'] in ids: out.append({'raw_source':'kyiv_municipal_official_json','raw_source_id':r.get('id') or r.get('_id') or r.get('alertId'),'start_utc':iso(iv[0]),'end_utc':iso(iv[1]),'used_by_combined_normalization':sb.get(e['episode_id'])=='official_json','raw_record':r})
 for x in ctx.get('live') or []:
  s=x.start.astimezone(UTC); e=x.end.astimezone(UTC)
  if not active(s,e,t): continue
  ep=mon.make_episode('kyiv',s,e,source='kyiv_combined_exact_city')
  if ep['episode_id'] in ids: out.append({'raw_source':'kyiv_digital_live_history','raw_source_id':None,'start_utc':iso(s),'end_utc':iso(e),'used_by_combined_normalization':sb.get(ep['episode_id'])=='kyiv_digital_live','raw_record':{'start':x.start.isoformat(),'end':x.end.isoformat(),'source':x.source}})
 return out

def main():
 if len(sys.argv)!=4: return 2
 frozen_p,syntax_p,out_p=map(Path,sys.argv[1:]); before=git('status','--porcelain'); actual={}
 for p,exp in BLOBS.items():
  got=git('hash-object',p); actual[p]=got
  if got!=exp: raise AssertionError(f'blob drift {p}: {got}')
 raw=frozen_p.read_bytes(); assert hashlib.sha256(raw).hexdigest()==FROZEN_SHA; doc=json.loads(raw); ledger=doc['candidate_level_durability_ledger']; assert len(ledger)==228; rows={x['candidate_id']:x for x in ledger}; assert set(TARGETS)<=set(rows) and EXCLUDED in rows
 syn=json.loads(syntax_p.read_text()); assert syn['verdict']=='RSS TEMPORAL SYNTAX-GAP REPAIR = PARTIAL' and syn['after']['parser_usable_candidates']==12; st={x['candidate_id']:x for x in syn['target_results']}
 for cid in TARGETS: assert st[cid]['syntax_recognized_after'] is True and st[cid]['classifier_disposition']=='needs_review' and st[cid]['active_episode_count_in_accepted_frozen_state']==0
 diag=json.loads((ROOT/'research/rss_syntax_postparse_episode_binding_diagnosis_2026-10-05.json').read_text()); assert diag['verdict']=='RSS SYNTAX POST-PARSE BINDING DIAGNOSIS = COMPLETE'
 ks,ke,kctx=fetch_kyiv(); ss,se,sctx=fetch_sumy(); sources={'kyiv':ks,'sumy':ss}; episodes={'kyiv':ke,'sumy':se}; cand=[]; recovered=set(); clusters=set(); strict=set()
 for cid,(city,label,cluster,ctxid,local,utc) in TARGETS.items():
  r=rows[cid]; c=next(x for x in r.get('audit_contexts') or [] if x.get('context_id')==ctxid); probe=target_row(r,c); src=sources[city]; eps=episodes[city]; t=dt(utc); cov=bool(src.get('available') and src.get('normalization_metadata',{}).get('coverage_sufficient_for_target' if city=='kyiv' else 'coverage_sufficient_for_targets')); ae=mon.exact_active_episodes_at(t,eps) if src.get('available') else []; sup=mon.logical_episode_support(ae) if ae else {'logical_episode_groups':[]}; groups=list(sup.get('logical_episode_groups') or [])
  rawactive=kyiv_raw(t,ae,kctx,src) if city=='kyiv' and src.get('available') else [x for x in sctx.get('rows') or [] if active(dt(x['start_utc']),dt(x['end_utc']),t)] if city=='sumy' and src.get('available') else []
  if not src.get('available') or not cov: disp='AUTHORITATIVE_HISTORY_UNAVAILABLE'
  elif rawactive and not ae: disp='NORMALIZATION_OR_GROUPING_BLOCKER'
  elif not groups: disp='NO_ALERT_PRESENT_IN_COMPLETE_HISTORY'
  elif len(groups)>1: disp='MULTIPLE_LOGICAL_EPISODES_PRESENT'
  elif len(groups)==1: disp='UNIQUE_EPISODE_PRESENT_IN_COMPLETE_HISTORY'
  else: disp='NORMALIZATION_OR_GROUPING_BLOCKER'
  matching=mon.match_candidate_to_episodes(probe,eps) if src.get('available') else {'outcome':'no_match','matched_episode_ids':[],'logical_episode_groups':[],'matched_episode_id':None,'reason':'authoritative_history_unavailable'}; dec=mon.classify_candidate(probe,city,eps,matching) if src.get('available') else None; temporal=((dec or {}).get('candidate_evidence') or {}).get('temporal_binding') or {}; usable=bool(temporal.get('present') and temporal.get('episode_specific') and temporal.get('episode_id')); isstrict=bool(dec and dec.get('proposed_outcome')=='approved_strict')
  if usable: recovered.add(cid); clusters.add(cluster)
  if isstrict: strict.add(cid)
  crit='AUTHORITATIVE_HISTORY_UNAVAILABLE' if disp=='AUTHORITATIVE_HISTORY_UNAVAILABLE' else 'REAL_ALERT_ABSENCE' if disp=='NO_ALERT_PRESENT_IN_COMPLETE_HISTORY' else 'PROOF_SNAPSHOT_STALENESS_ONLY' if disp=='UNIQUE_EPISODE_PRESENT_IN_COMPLETE_HISTORY' and usable else 'NORMALIZATION_OR_REPRESENTATION_PROBLEM'
  cand.append({'candidate_id':cid,'city':label,'city_key':city,'logical_attack_cluster_id':cluster,'retained_context_id':ctxid,'retained_event_context':c.get('source_excerpt'),'attack_time_local':local,'attack_time_utc':utc,'timezone':'Europe/Kyiv','syntax_recognized_in_accepted_predecessor':True,'before_frozen_state_disposition':{'classifier_disposition':st[cid]['classifier_disposition'],'parser_code':st[cid]['parser_code_after'],'active_episode_count':st[cid]['active_episode_count_in_accepted_frozen_state'],'interpretation':'PROOF_SNAPSHOT_STALENESS_ONLY'},'authoritative_source_available':bool(src.get('available')),'authoritative_history_coverage_sufficient':cov,'raw_alert_records_active_at_instant':rawactive,'normalized_alert_episodes_active_at_instant':[epv(e) for e in ae],'logical_alert_groups_active_at_instant':groups,'exactly_one_logical_episode_supported':len(groups)==1,'complete_history_disposition':disp,'critical_interpretation':crit,'counterfactual':{'matching':matching,'temporal_binding':temporal,'classifier_disposition':dec.get('proposed_outcome') if dec else 'needs_review','classifier_episode_id':dec.get('proposed_matched_episode_id') if dec else None,'reason_codes':dec.get('reason_codes') if dec else ['AUTHORITATIVE_HISTORY_UNAVAILABLE'],'parser_usable_under_unchanged_semantics':usable,'would_become_STRICT':isstrict,'semantic_change_required':False}})
 by=defaultdict(list)
 for x in cand: by[x['logical_attack_cluster_id']].append(x)
 cl=[]
 for k,v in sorted(by.items()):
  gs=[]
  for x in v:
   for g in x['logical_alert_groups_active_at_instant']:
    if g not in gs: gs.append(g)
  cl.append({'logical_attack_cluster_id':k,'candidate_ids':[x['candidate_id'] for x in v],'attack_time_local':v[0]['attack_time_local'],'attack_time_utc':v[0]['attack_time_utc'],'candidate_dispositions':sorted({x['complete_history_disposition'] for x in v}),'logical_alert_groups':gs,'recovered_under_unchanged_semantics':any(x['counterfactual']['parser_usable_under_unchanged_semantics'] for x in v),'strict_candidate_count':sum(x['counterfactual']['would_become_STRICT'] for x in v)})
 complete=sum(x['complete_history_disposition']!='AUTHORITATIVE_HISTORY_UNAVAILABLE' for x in cand); unavailable=5-complete; verdict='RSS SYNTAX COVERAGE-GAP REVALIDATION = COMPLETE' if complete==5 else 'RSS SYNTAX COVERAGE-GAP REVALIDATION = PARTIAL' if complete else 'RSS SYNTAX COVERAGE-GAP REVALIDATION = BLOCKED'; after=git('status','--porcelain'); assert after==before
 impact={'accepted_baseline_usable_candidates':12,'denominator':228,'additional_parser_usable_candidates':len(recovered),'additional_STRICT_candidates':len(strict),'additional_recovered_logical_attack_clusters':len(clusters),'counterfactual_usable_candidates':12+len(recovered),'counterfactual_usable_fraction':f'{12+len(recovered)}/228','recovered_candidate_ids':sorted(recovered),'strict_candidate_ids':sorted(strict),'recovered_cluster_ids':sorted(clusters),'exclusions':{'sumy_2026_09_27_candidate_id':EXCLUDED,'original_representation_gap_candidates_included':0,'new_live_discoveries_included':0}}
 mut={'production_alert_state_mutations':0,'historical_alert_state_mutations':0,'logical_grouping_mutations':0,'temporal_parser_mutations':0,'temporal_representation_mutations':0,'classifier_mutations':0,'source_configuration_mutations':0,'queues_mutations':0,'canonical_alerts_mutations':0,'neon_db_mutations':0,'deployments':0,'worktree_status_before':before,'worktree_status_after':after}
 result={'schema':'rss_syntax_coverage_gap_complete_alert_history_revalidation_v1','verdict':verdict,'generated_at_utc':iso(datetime.now(UTC)),'role':'READ_ONLY_AUTHORITATIVE_ALERT_HISTORY_REVALIDATION','predecessor_identities':{'diagnostic_verdict':'RSS SYNTAX POST-PARSE BINDING DIAGNOSIS = COMPLETE','diagnostic_branch':'rss-syntax-postparse-binding-diagnosis-2026-10-05','diagnostic_commit':DIAG,'syntax_proof_head':'f891ec51fac9f2614a8e286e75e4ddc14a7e8c00','syntax_proof_artifact_id':11356189561,'syntax_proof_artifact_digest':'sha256:d5d156d3cc436816b23ad91e4f2c2ae8c54acd80f755fa03d352c0730514083c','frozen_228_artifact_id':11329769176,'frozen_228_source_sha256':FROZEN_SHA,'accepted_usable_baseline':'12 / 228'},'code_identity':{'expected_and_actual_blob_shas':actual,'production_semantics_changed':False},'scope':{'candidate_ids':list(TARGETS),'candidate_count':5,'logical_attack_cluster_count':3,'excluded_candidate_ids':[EXCLUDED],'public_web_search':False,'news_reports_as_alert_truth':False,'telegram_or_rss_as_alert_truth':False,'phase_a_truth_urls':False,'manual_reconstructed_alert_intervals':False},'authoritative_alert_sources':{'kyiv':ks,'sumy':ss},'normalized_episode_inventory':{'kyiv_relevant_active_union':sorted({e['episode_id']:epv(e) for x in cand if x['city_key']=='kyiv' for e in mon.exact_active_episodes_at(dt(x['attack_time_utc']),ke)}.values(),key=lambda x:x['episode_id']),'sumy_relevant_active_union':sorted({e['episode_id']:epv(e) for x in cand if x['city_key']=='sumy' for e in mon.exact_active_episodes_at(dt(x['attack_time_utc']),se)}.values(),key=lambda x:x['episode_id'])},'five_candidate_ledger':cand,'three_cluster_deduplicated_result':cl,'impact_from_12_of_228':impact,'interpretation_counts':{k:sum(x['critical_interpretation']==k for x in cand) for k in ['PROOF_SNAPSHOT_STALENESS_ONLY','REAL_ALERT_ABSENCE','NORMALIZATION_OR_REPRESENTATION_PROBLEM','AUTHORITATIVE_HISTORY_UNAVAILABLE']},'mutation_confirmation':mut}
 out_p.parent.mkdir(parents=True,exist_ok=True); out_p.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+'\n')
 summary={'authoritative_source_used':{'kyiv':ks.get('identity'),'sumy':ss.get('identity')},'five_candidates_checked':5,'three_logical_attack_clusters_checked':3,'candidates_with_unique_alert_episode':sum(x['complete_history_disposition']=='UNIQUE_EPISODE_PRESENT_IN_COMPLETE_HISTORY' for x in cand),'candidates_with_multiple_episodes':sum(x['complete_history_disposition']=='MULTIPLE_LOGICAL_EPISODES_PRESENT' for x in cand),'candidates_with_no_alert':sum(x['complete_history_disposition']=='NO_ALERT_PRESENT_IN_COMPLETE_HISTORY' for x in cand),'candidates_blocked_by_unavailable_history':unavailable,'additional_STRICT_candidates':len(strict),'additional_recovered_logical_attack_clusters':len(clusters),'counterfactual_usable_total_out_of_228':impact['counterfactual_usable_fraction'],'verdict':verdict,'mutation_confirmation':mut}; print('REVALIDATION_SUMMARY='+json.dumps(summary,ensure_ascii=False,sort_keys=True)); return 0
if __name__=='__main__': raise SystemExit(main())
