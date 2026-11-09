#!/usr/bin/env python3
"""Same-run C2 -> read-only Neon snapshot -> accepted 23-city frontend builders.
No HTTP capture, Neon write, automatic freshness certification or publication.
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
# Immutable accepted C6 historical projection assets, vendored by Git blob hash.
# There is no child branch, TTL, fixed site checkout or proof-run dependency.
ACCEPTED_SHA = '741f277f73d1dde1325069d25fa00b44a42d6f03'
ASSETS = Path(__file__).resolve().parent / 'neon_shadow_c6_assets'
ARCHIVE_SHA = 'f6dda060a0ed48b01b4726625b36c33b472955f687be6877aef918fc3c8bddf2'
PINNED_ACCEPTED = {
 'approved_22city_archive.b64': '992ddda36a25fd7072575fbdd08920e5c00db851',
 'source_priority_reader.py': '890769995627aa15e43743ef7cd5b24d54b1c59c',
 'frozen_october_382_198_bundle.json': 'fbad2b5318818b9c4bc9940e691de5f32fcdf283',
 'derived_successor.py': 'df56d32e3cd1b58915cf785e958dadc49e4c1c2c',
}

# Exact receipt-only hook variants of three accepted collector blobs. The
# analytics/builders are unchanged; any other byte drift still fails closed.
CAPTURE_HOOK_BLOBS = {
 'scripts/update_data.py': ('cebc2b455fb08ee16e03b9e4fcdb17aa2d9d6833', '9649f75e5ed841ca5c855a7639eede9356af2766'),
 'scripts/apply_ukrainealarm_bridge.py': ('8b95c4b508b9a473240889603f593e399cf8815d', '1f912bca289035056cc8b19a086000ef8f24111a'),
 'scripts/add_sevastopol_exact.py': ('e4c091a677622eb28e504b0592a89e4d92d5fe02', 'f14437658cdb13f9464db63fc754db85c6447a86'),
}

# Exact site-prod collector hook blobs verified against PR #47 head
# 354ff3f84a2d87542f4af07ed63d585e9d5ea5f2 by narrow offline CI.
# Keep the original frozen variants; no wildcard or arbitrary source drift.
C6_INTEGRATION_HOOK_BLOBS = {
 'scripts/update_data.py': ('cebc2b455fb08ee16e03b9e4fcdb17aa2d9d6833', '45d4c3b656b91f927dc519cffdbd09f09ed00392'),
 'scripts/apply_ukrainealarm_bridge.py': ('8b95c4b508b9a473240889603f593e399cf8815d', 'aaedf36299bac69a76971d7e8399894e416d1643'),
 'scripts/add_sevastopol_exact.py': ('e4c091a677622eb28e504b0592a89e4d92d5fe02', '33568c607ebd6a25c3ff881ce7f365c42e362436'),
}

def accepted_builder_blob(path, raw, expected):
    actual = blob(raw)
    return (actual == expected or
            CAPTURE_HOOK_BLOBS.get(path) == (expected, actual) or
            C6_INTEGRATION_HOOK_BLOBS.get(path) == (expected, actual))

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
    """Load accepted projection code from immutable local assets, not research checkouts."""
    for name, want in PINNED_ACCEPTED.items():
        path = ASSETS / name
        require(path.is_file() and blob(path.read_bytes()) == want,
                'BLOCKED_GENERATOR_INPUT:ACCEPTED_ASSET:'+name)
    raw = base64.b64decode((ASSETS / 'approved_22city_archive.b64').read_bytes())
    require(sha(raw) == ARCHIVE_SHA, 'BLOCKED_GENERATOR_INPUT:ADAPTER_ARCHIVE_SHA')
    adapter_dir = out / 'approved-adapter'
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        manifest = json.loads(z.read('C6-22CITY-READER-01/sha256_manifest.json'))['files']
        require(z.testzip() is None and len(manifest) == 17,
                'BLOCKED_GENERATOR_INPUT:ADAPTER_ARCHIVE_INVALID')
        for name, want in manifest.items():
            require(sha(z.read('C6-22CITY-READER-01/'+name)) == want,
                    'BLOCKED_GENERATOR_INPUT:ADAPTER_FILE_SHA')
        for name in z.namelist():
            require((adapter_dir / name).resolve().is_relative_to(adapter_dir.resolve()),
                    'BLOCKED_GENERATOR_INPUT:ADAPTER_ARCHIVE_PATH')
        z.extractall(adapter_dir)
    sys.path[:0] = [str((adapter_dir/'C6-22CITY-READER-01').resolve()), str(ASSETS)]
    import adapter, source_priority_reader as b2
    for path, want in adapter.PINNED_SOURCE_BLOBS.items():
        if path.startswith('scripts/'):
            source = args.site/path
            require(source.is_file() and accepted_builder_blob(path, source.read_bytes(), want),
                    'BLOCKED_GENERATOR_INPUT:BUILDER_CODE_DRIFT:'+path)
    bundle_bytes = (ASSETS/'frozen_october_382_198_bundle.json').read_bytes()
    bundle = b2.verify_approved_frozen_bundle(bundle_bytes, bundle_bytes)
    return adapter, b2, bundle

# MEMBER intentionally over-approximates SET ROLE and inherited memberships.
# Inspect every reachable role, PUBLIC grants, column grants and ownership.
# TEMP (commonly granted through PUBLIC) is allowed for session-local objects;
# permanent CREATE, ownership, DML and escalation still fail closed. The snapshot
# independently requires REPEATABLE READ READ ONLY and always rolls back.
ROLE_SQL = """
WITH reachable AS (
  SELECT * FROM pg_roles
  WHERE oid = current_user::regrole OR pg_has_role(current_user, oid, 'MEMBER')
), schemas AS (
  SELECT * FROM pg_namespace WHERE nspname !~ '^pg_' AND nspname <> 'information_schema'
), relations AS (
  SELECT c.* FROM pg_class c JOIN schemas s ON s.oid = c.relnamespace
)
SELECT
  EXISTS (SELECT FROM reachable WHERE rolsuper OR rolcreatedb OR rolcreaterole
          OR rolreplication OR rolbypassrls) AS privileged_role,
  EXISTS (SELECT FROM reachable r, pg_database d
          WHERE d.datname = current_database() AND
          (d.datdba = r.oid OR has_database_privilege(r.oid, d.oid, 'CREATE'))) AS database_ddl,
  EXISTS (SELECT FROM reachable r, schemas s
          WHERE s.nspowner = r.oid OR has_schema_privilege(r.oid, s.oid, 'CREATE')) AS schema_ddl,
  EXISTS (SELECT FROM reachable r, relations c WHERE c.relowner = r.oid) AS object_owner,
  EXISTS (SELECT FROM reachable r, relations c
          WHERE c.relkind IN ('r','p','v','m','f') AND
          (has_table_privilege(r.oid, c.oid, 'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')
           OR has_any_column_privilege(r.oid, c.oid, 'INSERT,UPDATE,REFERENCES'))) AS table_dml,
  EXISTS (SELECT FROM reachable r, relations c WHERE c.relkind = 'S'
          AND has_sequence_privilege(r.oid, c.oid, 'USAGE,UPDATE')) AS sequence_write,
  EXISTS (SELECT FROM reachable r, pg_proc p JOIN schemas s ON s.oid = p.pronamespace
          WHERE p.proowner = r.oid OR
          (p.prosecdef AND has_function_privilege(r.oid, p.oid, 'EXECUTE'))) AS routine_escalation,
  EXISTS (SELECT FROM reachable r, pg_type t JOIN schemas s ON s.oid = t.typnamespace
          WHERE t.typowner = r.oid) AS type_owner,
  EXISTS (SELECT FROM reachable r, pg_tablespace t
          WHERE t.spcowner = r.oid OR has_tablespace_privilege(r.oid, t.oid, 'CREATE')) AS tablespace_ddl
"""

RISKS = ("privileged_role", "database_ddl", "schema_ddl", "object_owner", "table_dml",
         "sequence_write", "routine_escalation", "type_owner", "tablespace_ddl")


def verify_role(connection):
    result = connection.execute(ROLE_SQL).fetchone()
    require(result is not None and all(result.get(key) is False for key in RISKS),
            "READ_ONLY_ROLE_HAS_DML_DDL_OR_ESCALATION")
    return {"role_privilege_contract": "NO_DML_DDL_OR_ESCALATION", "role_risks": dict(result)}


def snapshot(url, b2, bundle, *, expected_host):
    """One transaction holds the complete 23-city AIR + B2 provenance + C2 corpus."""
    import psycopg
    from psycopg.rows import dict_row
    p = urlparse(url)
    require(p.scheme in ('postgres','postgresql') and bool(p.hostname),
            'NEON_READONLY_DSN_INVALID')
    require(p.hostname.lower().replace('-pooler.', '.') ==
            expected_host.lower().replace('-pooler.', '.'),
            'NEON_ENDPOINT_BRANCH_MISMATCH')
    require(bool(unquote(p.username or '')) and bool(p.password),
            'NEON_READONLY_CREDENTIAL_MISSING')
    q = parse_qs(p.query)
    require(set(q) <= {'sslmode','channel_binding','connect_timeout','application_name'},
            'NEON_DSN_OPTIONS_UNEXPECTED')
    require(q.get('sslmode',[''])[0] in ('require','verify-ca','verify-full'),
            'NEON_TLS_REQUIRED')
    with psycopg.connect(url,autocommit=True,connect_timeout=20,row_factory=dict_row,options='-c default_transaction_read_only=on') as cn:
        cn.execute('BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        try:
            meta=cn.execute("SELECT current_user AS role,current_database() AS database,current_setting('transaction_read_only') AS read_only,current_setting('transaction_isolation') AS isolation,pg_current_snapshot()::text AS snapshot,transaction_timestamp() AS read_at,pg_is_in_recovery() AS recovery,has_table_privilege(current_user,'public.alert_episodes','INSERT') AS can_insert").fetchone()
            require(meta['read_only']=='on' and meta['isolation']=='repeatable read' and meta['can_insert'] is False,'READ_ONLY_SNAPSHOT_NOT_PROVEN')
            meta.update(verify_role(cn))
            episodes=cn.execute("SELECT episode_uid::text AS uid,episode_uid::text,legacy_episode_id,city_key,alert_type,episode_state,start_at,end_at,created_at,updated_at,created_by_run_id::text,updated_by_run_id::text,canonicalization_version FROM public.alert_episodes WHERE alert_type='AIR' ORDER BY city_key,start_at,episode_uid").fetchall()
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


def source_report(snap, keys, reference, *, historical=None):
    """Do not mistake a C2 corpus receipt or DB COMMIT time for a fresh source capture."""
    report = {}
    for key in keys:
        rows = [r for r in snap['episodes'] if r['city_key'] == key]
        observations = [r for r in snap['observations'] if r['city_key'] == key]
        checkpoints = [r for r in snap['checkpoints'] if r['city_key'] == key]
        latest = max(checkpoints, key=lambda c: aware(c['checked_at'])) if checkpoints else None
        mm = reference['multicity_meta']['cities'][key]
        linked = {o['parent_uid'] for o in observations if o['binding_state'] == 'bound'}
        reasons = ['NO_INDEPENDENT_CURRENT_SOURCE_CAPTURE', 'ACTIVE_STATUS_NOT_CERTIFIED',
                   'CURRENT_SOURCE_CONTINUITY_NOT_CERTIFIED']
        if key in ('kharkiv','poltava','zhytomyr','cherkasy'):
            reasons.append('PHYSICAL_DST_REPAIR_OPEN')
        if key == 'kyiv':
            reasons.append('KYIV_CURRENT_SELECTION_PROVENANCE_OPEN')
        report[key] = {
            'city_key': key, 'label': mm['label'], 'source_type': mm['source_type'],
            'proxy_raion': mm.get('proxy_raion'), 'source_provenance': mm.get('source_provenance'),
            'physical_episodes': len(rows),
            'active_rows': sum(r['end_at'] is None for r in rows),
            'source_observations': len(observations), 'linked_parents': len(linked),
            'historical_source_coverage_note':
                'INCOMPLETE_ACCEPTED_BASELINE' if len(linked) < len(rows) else 'LINKED',
            'source_capture_verified': False, 'source_captured_at_utc': None,
            'source_checked_at_utc': iso(latest['checked_at']) if latest else None,
            'database_committed_at_utc': None,
            'latest_episode_db_updated_at_utc': iso(max(r['updated_at'] for r in rows)),
            'latest_completed_end_utc': iso(max(r['end_at'] for r in rows if r['end_at'] is not None)),
            'source_age_seconds': None, 'within_six_hour_bound': False,
            'continuity_verified': False, 'evidence_level': 'PERSISTED_HISTORY_ONLY',
            'publication_verdict': 'BLOCKED', 'reasons': reasons,
            'checkpoint_sources': [{'source_key':c['source_key'], 'stream_key':c['stream_key'],
                                    'seq': int(c['checkpoint_seq'])} for c in checkpoints],
        }
    if historical is not None:
        require(set(historical['cities']) == set(keys), 'HISTORY_SOURCE_REPORT_COVERAGE')
        for key in keys:
            history = historical['cities'][key]
            report[key]['historical_freshness'] = copy.deepcopy(history)
            report[key]['source_age_seconds'] = history['source_age_seconds']
            report[key]['within_36_hour_bound'] = history['within_36_hour_bound']
            report[key]['source_checked_at_utc'] = history['source_checked_at_utc']
            report[key]['source_captured_at_utc'] = history['source_checked_at_utc']
            report[key]['source_clock'] = 'source_history_last_checked_at'
            report[key]['historical_binding_verified'] = history['historical_binding_verified']
            report[key]['full_historical_receipt_verified'] = history.get('full_receipt_verified', False)
    return report

def refresh_analytics(payload, reference, reference_derived, alerts, now, site, mods):
    rolling=mods['apply_site_rolling_7d']; bridge=mods['apply_ukrainealarm_bridge']
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
    derived=importlib.import_module('derived_successor').create_derived(payload,reference_derived,alerts,now,site,mods)
    payload['historical_daily_kpi']=mods['build_preview_historical_daily'].produce(site,None,generated_at=now.isoformat(),source_override=payload,sources_override=alerts)
    return derived


def generate(args, out, adapter, b2, bundle, snap, closed, active, cities):
    # Completed-alert builders cannot safely close an active row using build time.
    # Preserve active rows unchanged in evidence and keep active/publication gate OPEN.
    now=aware(snap['meta']['read_at']); reference=load(args.site/'data/dashboard_data.json')
    reference_derived=load(args.site/'data/site_derived.json')
    frozen_uids={r['uid'] for r in bundle['source_rows']}
    b2snapshot={k:snap[k] for k in ('classifications','source_links','events')}
    b2snapshot['episodes']=[r for r in closed if r['uid'] in frozen_uids]
    selected=b2.run_bundle(bundle,b2snapshot)
    require(selected['enrichment']['rebinds']==0,'UNAUTHORIZED_CLASSIFICATION_REBIND')
    save(out/'kyiv_selection.json',selected)
    payload,diagnostics,alerts=adapter.build_projection_from_site([r for r in closed if r['city_key']!='kyiv'],reference,now,args.site)
    mods=adapter.import_site_modules(args.site); update=mods['update_data']; rolling=mods['apply_site_rolling_7d']; bridge=mods['apply_ukrainealarm_bridge']
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
        else:
            raise Closed('MISSING_OR_AMBIGUOUS_KYIV_CANONICAL_PARENT')
    # No research-only UUID is forced into a different branch. Historical B2
    # membership is retained; later Git membership requires one exact Neon parent.
    kyiv.sort(key=lambda r:aware(r['start']))
    alerts['kyiv']=update.parse_committed_alerts(kyiv)
    for key in payload['multicity_meta']['production_city_keys']:
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
    correction = None
    version = getattr(args, 'dst_correction', None)
    if version is not None:
        from scripts import c6_dst_projection as dst
        binding = dst.binding_from_snapshot(snap, args.c2_corpus_sha256)
        lineage, correction = dst.apply(lineage, binding, version=version)
        dst.rebuild_affected(payload, alerts, lineage, adapter, mods, now)
        save(out/'dst_correction.json', correction)
    raw=update.build_outputs(alerts['kyiv'],now.astimezone(update.TZ),copy.deepcopy(reference['cities']['kyiv']['meta']))
    k=copy.deepcopy(raw)
    mods['add_duration_unit_switch'].trim_first_partial_periods(k,min(a.start.astimezone(update.TZ).date() for a in alerts['kyiv']))
    rolling.update_city_rolling(k,alerts['kyiv']); payload['cities']['kyiv']=k
    for section in ('kpis','monthly','weekly','daily28','rolling30','rolling90'):
        if section in raw: payload[section]=k[section] if section=='weekly' else raw[section]
    keys=payload['multicity_meta']['production_city_keys']
    derived=refresh_analytics(payload, reference, reference_derived, alerts, now, args.site, mods)
    generated=aware(args.generated_at) if getattr(args, 'generated_at', None) else datetime.now(UTC)
    authority={'branch_id':args.branch_id,'database_read_at_utc':iso(now),'site_generated_at_utc':iso(generated),'source_as_of_utc_by_city':{key:cities[key]['source_captured_at_utc'] for key in keys},'publication_allowed':False,'scope':'RESEARCH_CANDIDATE_NOT_CURRENT_DATA_CERTIFICATION','dst_simulation':False,'active_status':'UNKNOWN_UNCERTIFIED','source_fallback':False,'prior_accepted_browser_proof':'66f872413f67668c9bd23b94cff17520fea705f9','physical_dst_repair_certified':False,'kyiv_current_provenance_certified':False}
    if getattr(args, 'historical_freshness', None) is not None:
        authority['historical_freshness'] = copy.deepcopy(args.historical_freshness)
    if correction is not None:
        authority['historical_dst_projection'] = correction
    payload['meta'].update(k['meta']); payload['meta']['generated_at']=generated.astimezone(update.TZ).isoformat()
    payload['meta']['publication_authority']=authority
    for key in keys:
        payload['cities'][key]['meta']['generated_at']=generated.astimezone(update.TZ).isoformat()
        payload['cities'][key]['meta']['source_captured_at_utc']=cities[key]['source_captured_at_utc']
        payload['cities'][key]['meta']['current_source_verified']=False
    derived.setdefault('meta',{})['publication_authority']=authority
    # Keep source-specific historical KPI index exactly aligned with dashboard's
    # actual generation time; no older source or Git-data fallback is introduced.
    payload['historical_daily_kpi']['meta'].update(generated_at=payload['meta']['generated_at'],source_dashboard_generated_at=payload['meta']['generated_at'],source_ref='neon:'+args.branch_id,source_commit=None,generator_commit=os.getenv('GITHUB_SHA'))
    if correction is not None:
        payload['historical_daily_kpi']['meta']['historical_dst_projection'] = {
            'version': version, 'receipt_sha256': fingerprint(correction),
            'physical_neon_observation': False, 'publication_allowed': False}
        for key in dst.AFFECTED:
            diagnostics[key]['historical_projection_version'] = version
            diagnostics[key]['corrected_calculation_intervals'] = len(alerts[key])
    candidate=out/'candidate'
    save(candidate/'dashboard_data.json',payload); save(candidate/'site_derived.json',derived); save(candidate/'alerts_combined.json',kyiv)
    save(candidate/'historical-daily-kpi.json',payload['historical_daily_kpi'])
    dependencies=[]
    for name in ('kyiv_threat_mix.json','sevastopol_events.json'):
        src=args.site/'data'/name; shutil.copyfile(src,candidate/name)
        dependencies.append({'path':name,'kind':'SAME_WORKFLOW_BUILT_GIT_AUXILIARY_NOT_NEON_FRESHNESS','site_input_sha':args.input_sha,'git_blob':blob(src.read_bytes()),'sha256':sha(src.read_bytes())})
    dependencies += [{'path':'alerts_combined.json display selection + frozen B2 bundle','kind':'GIT_MEMBERSHIP_ONLY_INTERVALS_FROM_NEON','site_commit':args.input_sha,'accepted_commit':ACCEPTED_SHA},{'path':'inherited dashboard/derived non-AIR and casualty metadata','kind':'PINNED_GIT_AUXILIARY_SEPARATE_TRACK_NOT_REGENERATED','site_input_sha':args.input_sha}]
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

