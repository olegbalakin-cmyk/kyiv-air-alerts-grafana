#!/usr/bin/env python3
"""Read-only child Neon -> existing 23-city builders -> fail-closed research gate.
No HTTP source capture, canonical writer, production publication or DB mutation.
"""
from __future__ import annotations
import argparse
import base64
import collections
import copy
import hashlib
import importlib
import io
import json
import os
import shutil
import socket
import sys
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse, unquote, parse_qs
from uuid import UUID

UTC = timezone.utc
CHILD = 'br-crimson-star-b59u7ge3'
PARENT = 'br-bold-mode-b5rub8pq'
HOST = 'ep-wild-dust-b5efhza1.c-7.us-east-2.aws.neon.tech'
ROLE = 'c6_writer_probe'
TTL = '2026-11-01T12:20:00Z'
SITE_SHA = '0ecbb291e8f443f7ab366bc4ac033d096f2c44f4'
ACCEPTED_SHA = '741f277f73d1dde1325069d25fa00b44a42d6f03'
FRESH_SHA = '1cf607b3ca00568f416fa5fc8a087ff53f4b9190'
FRESH_ROOT = Path(__file__).resolve().parent.parent / 'neon_live_writer_freshness_2026_10_31/proof/physical_04/runs/41204874911'
ARCHIVE_SHA = 'f6dda060a0ed48b01b4726625b36c33b472955f687be6877aef918fc3c8bddf2'
PINNED_ACCEPTED = {
 'c6_23city_integrated_shadow_2026_10_30/approved_22city_archive.b64': '992ddda36a25fd7072575fbdd08920e5c00db851',
 'c6_oct184_b1_source_priority_2026_10_29/source_priority_reader.py': '890769995627aa15e43743ef7cd5b24d54b1c59c',
 'c6_oct184_b1_source_priority_2026_10_29/frozen_october_382_198_bundle.json': 'fbad2b5318818b9c4bc9940e691de5f32fcdf283',
 'neon_cutover_work_2026_10_30/derived_successor.py': 'df56d32e3cd1b58915cf785e958dadc49e4c1c2c',
}
FRESH_HASHES = {
 'http_capture.json':'bb3c494713d67fbf0fd5c970a6ab55dbff10fffb11069393a3df7057377c6e41',
 'independent_readback.json':'578eaf650b0e530ad27ec8595a60ffffa827da3e6cd0317b9d89d77a65833878',
 'machine_verdict.json':'386e37050ece9d6bf772e373045ccae4f7e3c158ed49b8e2da2c4adacfa41956',
 'canonical_candidate.json':'502a8074ca108c9f96d6bbb29c4ba34eed92a9dc90ab914560d5b05c744070e7',
}
class Closed(RuntimeError): pass

def require(ok, reason):
    if not ok: raise Closed(reason)

def aware(value):
    d = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace('Z','+00:00'))
    require(d.tzinfo is not None, 'NAIVE_TIMESTAMP')
    return d.astimezone(UTC)

def iso(value):
    return aware(value).isoformat(timespec='microseconds').replace('+00:00','Z') if value is not None else None

def sha(raw): return hashlib.sha256(raw).hexdigest()
def blob(raw): return hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
def load(path): return json.loads(Path(path).read_text())
def save(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, default=str, allow_nan=False)+'\n')
def fingerprint(value):
    return sha(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',',':'),default=str).encode())

def prepare(args, out):
    import subprocess
    require(subprocess.check_output(['git','-C',str(args.site),'rev-parse','HEAD'],text=True).strip()==SITE_SHA,'SITE_REF_DRIFT')
    require(subprocess.check_output(['git','-C',str(args.accepted),'rev-parse','HEAD'],text=True).strip()==ACCEPTED_SHA,'ACCEPTED_REF_DRIFT')
    research = args.accepted/'research'
    for name,want in PINNED_ACCEPTED.items(): require(blob((research/name).read_bytes())==want,'ACCEPTED_BLOB_DRIFT:'+name)
    for name,want in FRESH_HASHES.items(): require(sha((FRESH_ROOT/name).read_bytes())==want,'FRESH_PROOF_HASH_DRIFT:'+name)
    archive=base64.b64decode((research/'c6_23city_integrated_shadow_2026_10_30/approved_22city_archive.b64').read_bytes())
    require(sha(archive)==ARCHIVE_SHA,'ADAPTER_ARCHIVE_HASH')
    adapter_dir=out/'approved-adapter'
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        manifest=json.loads(z.read('C6-22CITY-READER-01/sha256_manifest.json'))['files']
        require(z.testzip() is None and len(manifest)==17,'ADAPTER_ARCHIVE_INVALID')
        for name,want in manifest.items():
            require(sha(z.read('C6-22CITY-READER-01/'+name))==want,'ADAPTER_FILE_HASH')
        for name in z.namelist(): require((adapter_dir/name).resolve().is_relative_to(adapter_dir.resolve()),'ARCHIVE_PATH')
        z.extractall(adapter_dir)
    sys.path[:0]=[str((adapter_dir/'C6-22CITY-READER-01').resolve()),str((research/'c6_oct184_b1_source_priority_2026_10_29').resolve()),str((research/'neon_cutover_work_2026_10_30').resolve())]
    import adapter, source_priority_reader as b2
    for path,want in adapter.PINNED_SOURCE_BLOBS.items():
        if path.startswith('scripts/'): require(blob((args.site/path).read_bytes())==want,'BUILDER_CODE_DRIFT:'+path)
    bundle_bytes=(research/'c6_oct184_b1_source_priority_2026_10_29/frozen_october_382_198_bundle.json').read_bytes()
    bundle=b2.verify_approved_frozen_bundle(bundle_bytes,bundle_bytes)
    return adapter,b2,bundle

def snapshot(url, b2, bundle):
    import psycopg
    from psycopg.rows import dict_row
    p=urlparse(url)
    require(p.scheme in ('postgres','postgresql') and p.hostname==HOST,'CHILD_HOST_MISMATCH')
    require(unquote(p.username or '')==ROLE and p.path=='/neondb' and p.password,'CHILD_ROLE_MISMATCH')
    q=parse_qs(p.query)
    require(set(q)<= {'sslmode','channel_binding','connect_timeout','application_name'},'UNEXPECTED_DSN_OPTIONS')
    require(q.get('sslmode',[''])[0] in ('require','verify-ca','verify-full'),'TLS_REQUIRED')
    require(datetime.now(UTC)<aware(TTL),'CHILD_EXPIRED')
    with psycopg.connect(url,autocommit=True,connect_timeout=20,row_factory=dict_row,options='-c default_transaction_read_only=on') as cn:
        cn.execute('BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        try:
            meta=cn.execute("SELECT current_user AS role,current_database() AS database,current_setting('transaction_read_only') AS read_only,current_setting('transaction_isolation') AS isolation,pg_current_snapshot()::text AS snapshot,transaction_timestamp() AS read_at,pg_is_in_recovery() AS recovery").fetchone()
            require(meta['role']==ROLE and meta['database']=='neondb' and meta['read_only']=='on' and meta['isolation']=='repeatable read','READ_ONLY_SNAPSHOT_NOT_PROVEN')
            episodes=cn.execute("SELECT episode_uid::text AS uid,episode_uid::text,legacy_episode_id,city_key,alert_type,episode_state,start_at,end_at,created_at,updated_at,created_by_run_id::text,updated_by_run_id::text FROM public.alert_episodes WHERE alert_type='AIR' ORDER BY city_key,start_at,episode_uid").fetchall()
            observations=cn.execute("SELECT s.*,s.source_observation_id::text AS observation_uuid,s.episode_uid::text AS parent_uid FROM public.alert_episode_sources s JOIN public.alert_episodes e ON e.episode_uid=s.episode_uid WHERE e.alert_type='AIR' ORDER BY s.city_key,s.source_observation_id").fetchall()
            checkpoints=cn.execute('SELECT * FROM public.current_ingestion_checkpoints ORDER BY city_key,source_key,stream_key').fetchall()
            # All referenced runs, including inherited source commits: no new COMMIT timestamp is invented.
            runs=cn.execute("SELECT run_id::text,db_branch,status,ingest_committed_at,parameters,source_key,city_key,stats FROM public.ingestion_runs WHERE run_id IN (SELECT created_by_run_id FROM public.alert_episodes WHERE alert_type='AIR' UNION SELECT updated_by_run_id FROM public.alert_episodes WHERE alert_type='AIR' UNION SELECT first_persisted_by_run_id FROM public.alert_episode_sources UNION SELECT last_seen_by_run_id FROM public.alert_episode_sources UNION SELECT created_by_run_id FROM public.current_ingestion_checkpoints) ORDER BY run_id").fetchall()
            uids=[r['uid'] for r in bundle['source_rows']]
            classes=cn.execute(b2.CLASSIFICATIONS_SQL,(uids,)).fetchall()
            links=cn.execute(b2.SOURCE_LINKS_SQL,([r['uid'] for r in classes],)).fetchall()
            events=cn.execute(b2.EVENTS_SQL,(uids,)).fetchall()
        finally: cn.execute('ROLLBACK')
    return {'meta':meta,'episodes':episodes,'observations':observations,'checkpoints':checkpoints,'runs':runs,'classifications':classes,'source_links':links,'events':events}

def verify_snapshot(snap, adapter):
    expected=set(adapter.CITY_KEYS)|{'kyiv'}
    rows=snap['episodes']; index={r['uid']:r for r in rows}
    require(len(index)==len(rows) and {r['city_key'] for r in rows}==expected,'CITY_OR_UID_CONTRACT')
    cutoff=aware(snap['meta']['read_at']); closed=[]; active=[]
    for row in rows:
        UUID(row['uid']); require(aware(row['start_at'])<=cutoff and aware(row['created_at'])<=cutoff,'FUTURE_EPISODE')
        if row['episode_state']=='closed':
            require(row['end_at'] is not None and aware(row['start_at'])<aware(row['end_at'])<=cutoff,'CLOSED_INTERVAL_INVALID')
            closed.append(row)
        else:
            require(row['end_at'] is None,'ACTIVE_STATE_CONFLICT'); active.append(row)
    for row in snap['observations']:
        UUID(str(row['observation_uuid']))
        require(row['parent_uid'] in index and row['city_key']==index[row['parent_uid']]['city_key'],'DANGLING_SOURCE_OBSERVATION')
    return closed,active

def source_report(snap, keys, reference):
    now=datetime.now(UTC); runs={r['run_id']:r for r in snap['runs']}; report={}
    fresh_http=load(FRESH_ROOT/'http_capture.json'); fresh_read=load(FRESH_ROOT/'independent_readback.json')
    fresh_accepted=fresh_read['episode_source']; fresh_ck=fresh_read['checkpoint']
    for key in keys:
        rows=[r for r in snap['episodes'] if r['city_key']==key]
        observations=[r for r in snap['observations'] if r['city_key']==key]
        cks=[r for r in snap['checkpoints'] if r['city_key']==key]
        reasons=[]; captured=None; committed=None; verified=False
        latest=max(cks,key=lambda c:aware(c['checked_at'])) if cks else None
        # Only a hash/UUID/run/clock match to the accepted physical HTTP evidence
        # is a verified source capture. Generic checkpoint time alone is not one.
        if key=='kyiv' and latest:
            matching=[o for o in observations if str(o['observation_uuid'])==fresh_accepted['observation_uuid'] and o['parent_uid']==fresh_accepted['episode_uuid'] and o['source_record_key']==fresh_accepted['source_record_key'] and o['raw_sha256']==fresh_http['raw_sha256']]
            run=runs.get(str(latest['created_by_run_id']),{})
            verified=bool(len(matching)==1 and str(latest['checkpoint_id'])==fresh_ck['checkpoint_id'] and latest['metadata'].get('new_http_sha256')==fresh_http['raw_sha256'] and aware(latest['checked_at'])==aware(fresh_http['captured_at_utc']) and run.get('status')=='succeeded' and run.get('db_branch')==CHILD and str(matching[0]['last_seen_by_run_id'])==run.get('run_id'))
            if verified:
                captured=aware(fresh_http['captured_at_utc']); committed=run['ingest_committed_at']
                require(captured<=aware(committed)<=aware(snap['meta']['read_at']),'SOURCE_COMMIT_READ_ORDER')
        age=(now-captured).total_seconds() if captured else None
        if not cks: reasons.append('NO_SOURCE_CHECKPOINT')
        if not verified: reasons.append('NO_VERIFIED_SOURCE_CAPTURE')
        if captured and not 0<=age<=21600: reasons.append('STALE_SOURCE_CAPTURE')
        if latest and (now-aware(latest['checked_at'])).total_seconds()>21600: reasons.append('STALE_SOURCE_CHECKPOINT')
        if not latest or latest['continuity_verified'] is not True: reasons.append('CONTINUITY_NOT_PROVEN')
        reasons.append('CURRENT_ACTIVE_STATUS_NOT_CERTIFIED')
        if key=='kyiv': reasons += ['SOURCE_CONTRACT_PROSPECTIVE','UPSTREAM_CACHE_CURRENCY_NOT_CERTIFIED','KYIV_CURRENT_SELECTION_PROVENANCE_OPEN']
        linked={o['parent_uid'] for o in observations if o['binding_state']=='bound'}
        historical_note='INCOMPLETE_ACCEPTED_FROZEN_BASELINE_NOT_A_NEW_FULL_BACKFILL_REQUIREMENT' if len(linked)<len(rows) else 'LINKED'
        if key in ('kharkiv','poltava','zhytomyr','cherkasy'): reasons.append('PHYSICAL_DST_REPAIR_OPEN')
        mm=reference['multicity_meta']['cities'][key]
        report[key]={'city_key':key,'label':mm['label'],'source_type':mm['source_type'],'proxy_raion':mm.get('proxy_raion'),'source_provenance':mm.get('source_provenance'),'physical_episodes':len(rows),'active_rows':sum(r['end_at'] is None for r in rows),'source_observations':len(observations),'linked_parents':len(linked),'historical_source_coverage_note':historical_note,'source_capture_verified':verified,'source_captured_at_utc':iso(captured),'source_checked_at_utc':iso(latest['checked_at']) if latest else None,'database_committed_at_utc':iso(committed),'latest_episode_db_updated_at_utc':iso(max(r['updated_at'] for r in rows)),'latest_completed_end_utc':iso(max(r['end_at'] for r in rows if r['end_at'] is not None)),'source_age_seconds':age,'within_six_hour_bound':bool(captured and 0<=age<=21600),'continuity_verified':latest['continuity_verified'] if latest else False,'evidence_level':'ONE_PHYSICAL_KYIV_CAPTURE_NOT_CONTINUOUS' if verified else 'HISTORICAL_PERSISTED_OR_FROZEN_ONLY','publication_verdict':'BLOCKED','reasons':reasons,'required_live_source':'Kyiv municipal history + Kyiv Digital completed history + separately certified current AIR status' if key=='kyiv' else 'occupation-administration exact city source + current status' if key=='sevastopol' else 'exact city AIR history + current status' if mm['source_type']=='exact_city' else 'configured raion AIR history + current status','checkpoint_sources':[{'source_key':c['source_key'],'stream_key':c['stream_key'],'seq':int(c['checkpoint_seq'])} for c in cks]}
    return report

def generate(args, out, adapter, b2, bundle, snap, closed, active, cities):
    # Completed-alert builders cannot safely close an active row using build time.
    # Preserve active rows unchanged in evidence and keep active/publication gate OPEN.
    now=aware(snap['meta']['read_at']); reference=load(args.site/'data/dashboard_data.json')
    reference_derived=load(args.site/'data/site_derived.json')
    payload,diagnostics,alerts=adapter.build_projection_from_site([r for r in closed if r['city_key']!='kyiv'],reference,now,args.site)
    mods=adapter.import_site_modules(args.site); update=mods['update_data']; rolling=mods['apply_site_rolling_7d']; bridge=mods['apply_ukrainealarm_bridge']
    frozen_uids={r['uid'] for r in bundle['source_rows']}
    b2snapshot={k:snap[k] for k in ('classifications','source_links','events')}
    b2snapshot['episodes']=[r for r in closed if r['uid'] in frozen_uids]
    selected=b2.run_bundle(bundle,b2snapshot)
    require(selected['enrichment']['rebinds']==0,'UNAUTHORIZED_CLASSIFICATION_REBIND')
    save(out/'kyiv_selection.json',selected)
    by_token=collections.defaultdict(list)
    for row in closed:
        if row['city_key']=='kyiv': by_token[(aware(row['start_at']),aware(row['end_at']))].append(row)
    kyiv=[]; lineage=[]; excluded=[]; existing=set()
    def append(row,source,selection):
        token=(aware(row['start_at']),aware(row['end_at']))
        if token in existing: return
        existing.add(token)
        kyiv.append({'start':token[0].astimezone(update.TZ).isoformat(),'end':token[1].astimezone(update.TZ).isoformat(),'source':source})
        lineage.append({'city_key':'kyiv','start_utc':iso(token[0]),'end_utc':iso(token[1]),'physical_uids':[row['uid']],'selection':selection})
    index={r['uid']:r for r in closed}
    rows_by_city=collections.defaultdict(list)
    for row in closed: rows_by_city[row['city_key']].append(row)
    for item in selected['display_alerts']: append(index[item['uid']],item['source_kind'],'ACCEPTED_B2_FROZEN_VIEW')
    boundary=aware('2026-09-30T21:00:00Z')
    # Git selects historical display membership only; interval values come from Neon.
    # Ambiguous/missing parents are excluded and explicitly block current selection.
    for row in load(args.site/'data/alerts_combined.json'):
        token=(aware(row['start']),aware(row['end']))
        if token in existing: continue
        matches=by_token[token]
        if len(matches)==1 and (token[0]<boundary or matches[0]['uid'] not in frozen_uids):
            append(matches[0],row['source'],'PINNED_GIT_SELECTION_EXACT_NEON_INTERVAL_NOT_SOURCE_RECEIPT')
        else: excluded.append({'start':row['start'],'end':row['end'],'reason':'NO_UNIQUE_ELIGIBLE_PHYSICAL_PARENT','matches':[m['uid'] for m in matches]})
    # Include the already accepted new physical UUID; it remains a prospective
    # research observation, never approved as Kyiv production source priority.
    accepted_read=load(FRESH_ROOT/'independent_readback.json')['episode_source']
    require(accepted_read['episode_uuid'] in index,'ACCEPTED_NEW_UUID_MISSING')
    append(index[accepted_read['episode_uuid']],'kyiv_digital_live','ACCEPTED_SINGLE_CAPTURE_RESEARCH_ONLY')
    kyiv.sort(key=lambda r:aware(r['start']))
    alerts['kyiv']=update.parse_committed_alerts(kyiv)
    raw=update.build_outputs(alerts['kyiv'],now.astimezone(update.TZ),copy.deepcopy(reference['cities']['kyiv']['meta']))
    k=copy.deepcopy(raw)
    mods['add_duration_unit_switch'].trim_first_partial_periods(k,min(a.start.astimezone(update.TZ).date() for a in alerts['kyiv']))
    rolling.update_city_rolling(k,alerts['kyiv']); payload['cities']['kyiv']=k
    for section in ('kpis','monthly','weekly','daily28','rolling30','rolling90'):
        if section in raw: payload[section]=k[section] if section=='weekly' else raw[section]
    keys=payload['multicity_meta']['production_city_keys']
    complete=copy.deepcopy(payload['cities'])
    for city in complete.values(): city['monthly']=[r for r in city['monthly'] if not r.get('is_partial_period')]
    payload['comparison']['monthly']=bridge.generic_comparison(complete,keys,'monthly')
    payload['comparison']['weekly']=bridge.generic_comparison(payload['cities'],keys,'weekly')
    coverage={key:rolling.first_coverage_day(payload['cities'][key],alerts[key]) for key in keys}
    ends={key:rolling.analysis_end(payload['cities'][key]) for key in keys}
    common_start=datetime.fromisoformat(reference['all_cities_table']['meta']['common_start']).date(); common_end=min(ends.values())
    payload['all_cities_table']['meta']['common_end']=common_end.isoformat()
    reference_derived['all_cities_table_test']['meta']['common_end']=common_end.isoformat()
    for key in keys:
        payload['time_of_day_profile']['cities'][key]={'coverage_start':coverage[key].isoformat(),'analysis_end':ends[key].isoformat(),'source_type':payload['multicity_meta']['cities'][key]['source_type'],'periods':{p:rolling.time_profile(alerts[key],coverage[key],ends[key],n) for p,n in rolling.PROFILE_PERIODS.items()}}
        payload['all_cities_table']['cities'][key]={'periods':{label:rolling.period_summary(alerts[key],common_start if n is None else max(common_start,common_end-timedelta(days=n-1)),common_end) for label,n in (('7d',7),('30d',30),('90d',90),('year',365),('common',None))}}
        mm=payload['multicity_meta']['cities'][key]
        mm['latest_rolling_7d_end']=ends[key].isoformat()
        require(mm['source_type']==('exact_city' if key in ('kyiv','kharkiv','zaporizhzhia','sevastopol') else 'raion_proxy'),'SOURCE_TYPE_CHANGED')
        require(mm.get('proxy_raion')==reference['multicity_meta']['cities'][key].get('proxy_raion'),'PROXY_CHANGED')
        if key!='kyiv':
            physical=rows_by_city[key]; cursor=0
            for a in alerts[key]:
                uids=[]
                while cursor<len(physical) and aware(physical[cursor]['start_at'])<=aware(a.end):
                    row=physical[cursor]
                    require(aware(a.start)<=aware(row['start_at']) and aware(row['end_at'])<=aware(a.end),'UNION_LINEAGE_CONFLICT')
                    uids.append(row['uid']); cursor+=1
                require(bool(uids),'MISSING_UNION_MEMBERS')
                lineage.append({'city_key':key,'start_utc':iso(a.start),'end_utc':iso(a.end),'physical_uids':uids,'selection':'ACCEPTED_UTC_UNION_OF_PHYSICAL_PARENTS'})
    derived=importlib.import_module('derived_successor').create_derived(payload,reference_derived,alerts,now,args.site,mods)
    payload['historical_daily_kpi']=mods['build_preview_historical_daily'].produce(args.site,None,generated_at=now.isoformat(),source_override=payload,sources_override=alerts)
    generated=datetime.now(UTC)
    authority={'branch_id':CHILD,'database_read_at_utc':iso(now),'site_generated_at_utc':iso(generated),'source_as_of_utc_by_city':{key:cities[key]['source_captured_at_utc'] for key in keys},'publication_allowed':False,'scope':'RESEARCH_CANDIDATE_NOT_CURRENT_DATA_CERTIFICATION','dst_simulation':False,'active_status':'UNKNOWN_UNCERTIFIED','source_fallback':False,'prior_accepted_browser_proof':'66f872413f67668c9bd23b94cff17520fea705f9'}
    payload['meta'].update(k['meta']); payload['meta']['generated_at']=generated.astimezone(update.TZ).isoformat()
    payload['meta']['publication_authority']=authority
    for key in keys:
        payload['cities'][key]['meta']['generated_at']=generated.astimezone(update.TZ).isoformat()
        payload['cities'][key]['meta']['source_captured_at_utc']=cities[key]['source_captured_at_utc']
        payload['cities'][key]['meta']['current_source_verified']=False
    derived.setdefault('meta',{})['publication_authority']=authority
    # Keep source-specific historical KPI index exactly aligned with dashboard's
    # actual generation time; no older source or Git-data fallback is introduced.
    payload['historical_daily_kpi']['meta'].update(generated_at=payload['meta']['generated_at'],source_dashboard_generated_at=payload['meta']['generated_at'],source_ref='neon:'+CHILD,source_commit=None,generator_commit=os.getenv('GITHUB_SHA'))
    candidate=out/'candidate'
    save(candidate/'dashboard_data.json',payload); save(candidate/'site_derived.json',derived); save(candidate/'alerts_combined.json',kyiv)
    save(candidate/'historical-daily-kpi.json',payload['historical_daily_kpi'])
    dependencies=[]
    for name in ('kyiv_threat_mix.json','sevastopol_events.json'):
        src=args.site/'data'/name; shutil.copyfile(src,candidate/name)
        dependencies.append({'path':name,'kind':'PINNED_GIT_AUXILIARY_NOT_NEON_FRESHNESS','commit':SITE_SHA,'git_blob':blob(src.read_bytes()),'sha256':sha(src.read_bytes())})
    dependencies += [{'path':'alerts_combined.json display selection + frozen B2 bundle','kind':'GIT_MEMBERSHIP_ONLY_INTERVALS_FROM_NEON','site_commit':SITE_SHA,'accepted_commit':ACCEPTED_SHA},{'path':'inherited dashboard/derived non-AIR and casualty metadata','kind':'PINNED_GIT_AUXILIARY_SEPARATE_TRACK_NOT_REGENERATED','commit':SITE_SHA}]
    # Current frontend contract verification only; accepted browser/CSV proof is not rerun.
    require(len(payload['cities'])==23 and set(payload['cities'])==set(keys),'FRONTEND_CITY_SHAPE')
    for key in keys:
        require(payload['cities'][key]['meta']['timezone']=='Europe/Kyiv','TIMEZONE_CHANGED')
        for section in ('kpis','monthly','weekly','daily28','rolling30','rolling90'): require(isinstance(payload['cities'][key].get(section),list),'FRONTEND_ROWS_SHAPE:'+key+':'+section)
        require(key in derived['explorations']['daily28_current']['cities'],'FRONTEND_DERIVED_CITY_MISSING')
    require(payload['historical_daily_kpi']['meta']['verified_count']==23,'HISTORICAL_INDEX_STRUCTURE')
    require(payload['historical_daily_kpi']['meta']['source_dashboard_generated_at']==payload['meta']['generated_at'],'HISTORICAL_INDEX_DASHBOARD_TIME_MISMATCH')
    save(out/'projection_lineage.json',lineage); save(out/'active_rows_unmodified.json',active)
    save(out/'git_dependencies.json',dependencies); save(out/'kyiv_excluded_git_memberships.json',excluded)
    save(out/'utc_union_diagnostics.json',diagnostics)
    return {'cities':len(keys),'selected_display_intervals':{key:len(alerts[key]) for key in keys},'generated_files':4,'copied_auxiliary_files':2,'candidate_files':6,'generated_at_utc':iso(generated),'kyiv_excluded_git_memberships':len(excluded),'suppressed_parent_rebinds':0,'dst_simulation':False,'candidate_sha256':{p.name:sha(p.read_bytes()) for p in sorted(candidate.iterdir())},'source_as_of_utc_by_city':authority['source_as_of_utc_by_city']}

def publication_gates(cities, result, repeat):
    def g(status,reason,kind='physical'): return {'verdict':status,'reason':reason,'evidence_kind':kind}
    return {
      'isolated_branch_readonly':g('PASS','Exact child hostname/role/TTL and REPEATABLE READ READ ONLY transaction'),
      '23city_generation':g('PASS','Existing accepted adapter/B2/pure builders; six consumer files; no DST simulation'),
      'frontend_structure':g('PASS','23 city keys, timezone, exact/proxy semantics and required arrays; earlier browser proof remains pinned'),
      'source_observation_integrity':g('PASS','Every existing observation UUID/parent/city link validated and retained; historical coverage gaps reported, not converted into a new full-backfill gate'),
      'source_capture_freshness':g('PASS' if all(c['within_six_hour_bound'] for c in cities.values()) else 'BLOCKED','Require verified source captures <=21600s for all required cities; JSON/COMMIT time cannot refresh capture'),
      'source_continuity':g('OPEN','Kyiv current checkpoint continuity_verified=false; no repeat source capture authorized','not_proven'),
      'current_active_status':g('OPEN','Closed-history-only builders; zero open DB rows does not certify no active AIR alerts','not_proven'),
      'source_contract_and_currency':g('OPEN','Kyiv source identity prospective; upstream cache currency and all-city source completeness uncertified','not_proven'),
      'physical_dst_repairs':g('OPEN','Four separately tracked physical repairs remain; this runner makes no repair','accepted_open_dependency'),
      'kyiv_current_provenance':g('OPEN','B2 frozen view reused; later exact Git selections/prospective UUID are research-only; suppressed classifications unchanged','accepted_open_dependency'),
      'explicit_git_auxiliaries':g('PASS','Git dependency SHA-256/blob/commit manifest; no Neon-error fallback'),
      'read_only_repeatability':g('PASS' if repeat else 'BLOCKED','Second independent read-only snapshot fingerprint equals first; no writer invoked'),
      'continuous_writer_operation':g('OPEN','No scheduler/capture/writer launched; earlier single COMMIT/crash/retry proof remains bounded','not_proven'),
      'production_preflight':g('OPEN','Operational source switch/rollback and release readiness require separate preflight','not_proven'),
      'production_cutover_authorization':g('OPEN','No explicit production cutover authorization in this task','owner_decision'),
    }

def write_report(out, cities, gates):
    lines=['# 23-city persisted Neon publication candidate','',f'Branch `{CHILD}`, parent `{PARENT}`, TTL `{TTL}`. No new HTTP capture or DB write.','', 'Generation success is distinct from source freshness. A blocked candidate is never copied into the publish directory.','', '| City | Semantics | Episodes | Observations | Verified capture UTC | Source checkpoint UTC | Evidence |','| --- | --- | ---: | ---: | --- | --- | --- |']
    for k,c in cities.items(): lines.append(f"| {k} | {c['source_type']} | {c['physical_episodes']} | {c['source_observations']} | {c['source_captured_at_utc'] or 'UNPROVEN'} | {c['source_checked_at_utc'] or 'NONE'} | {c['evidence_level']} |")
    lines += ['', 'All cities remain publication-blocked. Kyiv has one genuine HTTP capture; it does not certify continuous updates, active status or upstream payload currency. Lviv has historical checkpoint evidence; its observations lack source retrieval timestamps. The other 21 cities have persisted historical episodes without current source observation/checkpoint proof. Incomplete historical source-link coverage is disclosed; accepted frozen baseline evidence is retained, and no new full historical backfill is required by this gate.', '', '## Publication gates','']
    lines += [f"- `{k}`: **{g['verdict']}** — {g['reason']}" for k,g in gates.items()]
    lines += ['', '## Next owner decision','', 'Authorize a bounded, isolated 23-city source-continuity run: explicit source request budget (history plus current status), at least two observation rounds, durable existing writer/readback, same-source retries and fixed end time. Reuse the existing child before TTL; after expiry, a new child requires explicit authority. No capture runner is enabled by this read-only workflow. Source scope/contracts and budget must be settled before execution. DST/Kyiv repairs remain separate dependencies.', '', '## Proof boundaries','', 'New physical evidence: current child readback, existing UUID/source links, complete historical 23-city regeneration, independent repeated read and fail-closed publication decision. No live-source continuity or physical active-to-closed transition was executed. No new broad parity, browser, CSV, synthetic freshness or rollback tests. Historical C4/backfill/casualty tracks were not modified.']
    (out/'REPORT.md').write_text('\n'.join(lines)+'\n')

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--site',type=Path,required=True); ap.add_argument('--accepted',type=Path,required=True); ap.add_argument('--output',type=Path,required=True); args=ap.parse_args()
    out=args.output.resolve(); require(not out.exists(),'OUTPUT_MUST_BE_NEW'); out.mkdir(parents=True)
    require(not out.is_relative_to(args.site.resolve()) and not out.is_relative_to(args.accepted.resolve()),'OUTPUT_OVERWRITES_PINNED_INPUT')
    verdict={'checkpoint':'C6-23CITY-PUBLICATION-01','branch_id':CHILD,'parent_id':PARENT,'branch_expires_at':TTL,'github_sha':os.getenv('GITHUB_SHA'),'github_run_id':os.getenv('GITHUB_RUN_ID'),'http_source_requests':0,'neon_mutations':0,'production_mutations':0,'publication_allowed':False,'decision':'PUBLICATION_BLOCKED','C6':'PARTIAL','C3':'PARTIAL','GLOBAL_CUTOVER':'NO','production_preflight_ready':False}
    exit_code=1
    try:
        adapter,b2,bundle=prepare(args,out)
        url=os.environ.pop('NEON_ISOLATED_PROOF_DATABASE_URL',''); require(bool(url),'MISSING_CHILD_SECRET')
        snap=snapshot(url,b2,bundle); closed,active=verify_snapshot(snap,adapter)
        repeat=snapshot(url,b2,bundle); url=''
        datasets=('episodes','observations','checkpoints','runs','classifications','source_links','events')
        first_hash=fingerprint({k:snap[k] for k in datasets}); repeat_hash=fingerprint({k:repeat[k] for k in datasets})
        repeat_ok=first_hash==repeat_hash
        save(out/'neon_readback.json',snap)
        save(out/'repeat_read_receipt.json',{'first':snap['meta'],'second':repeat['meta'],'first_content_sha256':first_hash,'second_content_sha256':repeat_hash,'same_content':repeat_ok,'writes_invoked':0,'claim':'Read-only repeatability, not repeated live writer continuity'})
        # Generators may not perform network IO. PostgreSQL readback is complete.
        def no_network(*a,**k): raise Closed('SOURCE_HTTP_OR_OTHER_NETWORK_NOT_AUTHORIZED')
        socket.socket.connect=no_network; socket.create_connection=no_network
        import requests
        requests.sessions.Session.request=no_network
        keys=load(args.site/'data/dashboard_data.json')['multicity_meta']['production_city_keys']
        cities=source_report(snap,keys,load(args.site/'data/dashboard_data.json'))
        save(out/'cities.json',cities)
        generated=generate(args,out,adapter,b2,bundle,snap,closed,active,cities)
        gates=publication_gates(cities,generated,repeat_ok)
        # Separate atomic promotion boundary. The research authorization gate is
        # OPEN; no successful generation can authorize publication.
        allowed=all(g['verdict']=='PASS' for g in gates.values())
        require(not allowed,'RESEARCH_MUST_NOT_PUBLISH')
        verdict.update(pipeline='PASS_PHYSICAL_READ_TO_23CITY_JSON',physical_episode_count=len(snap['episodes']),closed_episodes=len(closed),active_episodes=len(active),source_observations=len(snap['observations']),cities=23,generation=generated,gates=gates,unclosed_gates=[k for k,g in gates.items() if g['verdict']!='PASS'],decision='PUBLICATION_BLOCKED',publication_allowed=False,source_freshness_gate=gates['source_capture_freshness']['verdict'],failure_reason='MISSING_OR_STALE_REQUIRED_CITY_SOURCE_PROOF_AND_OPEN_RELEASE_GATES',fallback_to_git_json=False,read_only_repeatability=repeat_ok,source_as_of_utc_by_city=generated['source_as_of_utc_by_city'])
        save(out/'publication_decision.json',{'decision':verdict['decision'],'publication_allowed':False,'gates':gates,'candidate_sha256':generated['candidate_sha256'],'publish_directory_created':False})
        write_report(out,cities,gates); exit_code=0
    except Exception as error:
        # Never substitute Git intervals after connection/read/generator failure.
        verdict.update(pipeline='BLOCKED',error_code=str(error) if isinstance(error,Closed) else type(error).__name__,sqlstate=getattr(error,'sqlstate',None),fallback_to_git_json=False)
        save(out/'publication_decision.json',{'decision':'PUBLICATION_BLOCKED','publication_allowed':False,'reason':verdict['error_code'],'publish_directory_created':False})
    finally:
        verdict['evaluated_at_utc']=iso(datetime.now(UTC)); save(out/'machine_verdict.json',verdict)
        save(out/'sha256_manifest.json',{'schema':'c6-23city-publication-01-v1','files':{str(p.relative_to(out)):sha(p.read_bytes()) for p in sorted(out.rglob('*')) if p.is_file() and p.name!='sha256_manifest.json'}})
        print(json.dumps({k:verdict.get(k) for k in ('pipeline','decision','source_freshness_gate','cities','physical_episode_count','source_observations','error_code')},sort_keys=True))
    return exit_code
if __name__=='__main__': raise SystemExit(main())
