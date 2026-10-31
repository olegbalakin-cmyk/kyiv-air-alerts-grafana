#!/usr/bin/env python3
"""One owner-authorized, bounded, two-cycle experiment. Never a publisher."""
from __future__ import annotations
import argparse
import ast
import collections
import hashlib
import importlib.util
import json
import os
import re
import signal
import sys
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlparse, urljoin, unquote, parse_qs

UTC = timezone.utc
ROOT = Path(__file__).resolve().parent
EXPERIMENT = 'c6-two-cycle-2026-10-31-owner-60get-70min'
BRANCH = 'research-neon-live-writer-freshness-2026-10-31'
CHILD = 'br-crimson-star-b59u7ge3'
HOST = 'ep-wild-dust-b5efhza1.c-7.us-east-2.aws.neon.tech'
ROLE = 'c6_writer_probe'
TTL = '2026-11-01T12:20:00Z'
SITE_SHA = '0ecbb291e8f443f7ab366bc4ac033d096f2c44f4'
UA = 'https://api.ukrainealarm.com'
PINS = {'db_phase1_core.py':'dda23c268e08f74367f33b189a8bafc1358aadd2',
        'db_phase1_persistence.py':'ed014e61fc6186fa9daf91c763c847e7df2f0306',
        'update_data.py':'cebc2b455fb08ee16e03b9e4fcdb17aa2d9d6833',
        'add_sevastopol_exact.py':'e4c091a677622eb28e504b0592a89e4d92d5fe02',
        'ukrainealarm_request_policy.py':'6fe5429a0abf93dbfb3bae009a9f0de4ef4f86b4'}

class Blocked(RuntimeError): pass
def need(ok, reason):
    if not ok: raise Blocked(reason)
def now(): return datetime.now(UTC)
def dt(v):
    d = v if isinstance(v,datetime) else datetime.fromisoformat(str(v).replace('Z','+00:00'))
    need(d.tzinfo is not None,'NAIVE_TIME'); return d.astimezone(UTC)
def iso(v): return dt(v).isoformat(timespec='microseconds').replace('+00:00','Z') if v else None
def sha(v): return hashlib.sha256(v).hexdigest()
def canonical(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str).encode()
def save(path,v):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(v,ensure_ascii=False,sort_keys=True,indent=2,default=str)+'\n')
def load(path): return json.loads(Path(path).read_text())
def gitblob(v): return hashlib.sha1(b'blob '+str(len(v)).encode()+b'\0'+v).hexdigest()
def module(path,name):
    spec=importlib.util.spec_from_file_location(name,path); m=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m); return m

class Requests:
    """No automatic retries/redirects; stop a provider after any failed request."""
    def __init__(self,out):
        import requests
        self.s=requests.Session(); self.s.mount('https://',requests.adapters.HTTPAdapter(max_retries=0))
        self.out=out; self.ledger=[]; self.last={}; self.stopped={}; self.started=time.monotonic()
        self.deadline=self.started+60*60
    def wait(self,seconds):
        end=time.monotonic()+max(0,seconds)
        need(end+50<self.deadline,'EXPERIMENT_TIME_BUDGET')
        while time.monotonic()<end: time.sleep(min(30,end-time.monotonic()))
    def get(self,url,provider,cycle,city,headers=None,params=None,min_interval=70):
        need(len(self.ledger)<60,'HTTP_GET_BUDGET')
        need(provider not in self.stopped,'PROVIDER_STOPPED:'+provider)
        # A full initial UkraineAlarm guard includes unknown concurrent operational traffic.
        prior=self.last.get(provider,self.started if provider=='ukrainealarm' else -1e20)
        self.wait(max(0,prior+min_interval-time.monotonic()))
        need(now()<dt(TTL),'CHILD_EXPIRED')
        entry={'request':len(self.ledger)+1,'method':'GET','url':url,'params':params,
               'provider':provider,'cycle':cycle,'city':city,'started_at_utc':iso(now()),
               'status':None,'automatic_retries':0,'redirects_followed':0}
        self.ledger.append(entry); save(self.out/'http_requests.json',self.ledger)
        try:
            with self.s.get(url,params=params,headers=headers or {},timeout=(10,35),
                            allow_redirects=False,stream=True) as r:
                body=r.raw.read(8*1024*1024+1,decode_content=True)
                captured=now(); entry.update(status=r.status_code,captured_at_utc=iso(captured),
                    entity_bytes=len(body),raw_sha256=sha(body),
                    headers={k:r.headers.get(k) for k in ('Date','Age','Last-Modified','Cache-Control','Content-Type','ETag','Retry-After')})
                if r.status_code==200 and 0<len(body)<=8*1024*1024:
                    raw_path=f'http/{entry["request"]:02d}-{provider}-{city}.bin'
                    (self.out/'http').mkdir(exist_ok=True); (self.out/raw_path).write_bytes(body)
                    entry['raw_path']=raw_path
                else:
                    self.stopped[provider]='HTTP_'+str(r.status_code)
                    raise Blocked('SOURCE_HTTP_'+str(r.status_code))
            return entry,body
        except Exception as e:
            entry['error']=str(e) if isinstance(e,Blocked) else type(e).__name__
            self.stopped.setdefault(provider,entry['error']); raise
        finally:
            self.last[provider]=time.monotonic(); entry['finished_at_utc']=iso(now())
            save(self.out/'http_requests.json',self.ledger)
            print('HTTP',entry['request'],provider,city,entry['status'],flush=True)

def connection(url,readonly=True):
    import psycopg
    from psycopg.rows import dict_row
    cn=psycopg.connect(url,autocommit=True,row_factory=dict_row,connect_timeout=20,
                       options='-c statement_timeout=30000 -c lock_timeout=15000'+(' -c default_transaction_read_only=on' if readonly else ''))
    if readonly: need(cn.execute('SHOW transaction_read_only').fetchone()['transaction_read_only']=='on','READBACK_NOT_READ_ONLY')
    return cn

def environment_preflight(url,out):
    import requests
    p=urlparse(url)
    need(p.hostname==HOST and unquote(p.username or '')==ROLE and p.path=='/neondb' and p.password,'CHILD_DSN_MISMATCH')
    q=parse_qs(p.query); need(set(q)<={'sslmode','channel_binding','connect_timeout','application_name'} and q.get('sslmode',[''])[0] in ('require','verify-ca','verify-full'),'TLS_OR_DSN_OPTIONS')
    need(now()<dt(TTL),'CHILD_EXPIRED')
    # Github control-plane GET is separate from the 60 upstream source GET ceiling.
    with requests.get('https://api.github.com/repos/olegbalakin-cmyk/kyiv-air-alerts-grafana/environments/c6-live-writer-proof',
            headers={'Authorization':'Bearer '+os.environ.get('GH_PREFLIGHT_TOKEN',''),'Accept':'application/vnd.github+json'},
            allow_redirects=False,timeout=20) as r:
        e=r.json() if r.status_code==200 else {}
        env={'control_plane_gets':1,'http_status':r.status_code,'name':e.get('name'),
             'id':e.get('id'),'protection_rules':e.get('protection_rules'),
             'deployment_branch_policy':e.get('deployment_branch_policy'),
             'child_hostname_verified':True,'expected_role':ROLE,'secret_value_omitted':True}
        save(out/'environment_preflight.json',env)
        need(r.status_code==200 and e.get('name')=='c6-live-writer-proof','ENVIRONMENT_CONFIGURATION_NOT_VERIFIABLE')
    with connection(url) as cn:
        ident=cn.execute('SELECT current_user AS role,current_database() AS database').fetchone()
        need(ident=={'role':ROLE,'database':'neondb'},'CHILD_DATABASE_IDENTITY')
        save(out/'child_identity.json',ident)
    old=load(ROOT.parent/'neon_live_writer_freshness_2026_10_31/proof/physical_03/role_scope.json')
    need(old['role_scope']=='new_child_only' and all(b['probe_role_present']==(b['branch_id']==CHILD) for b in old['branches']),'CHILD_SCOPE_ATTESTATION_MISSING')
    save(out/'scope_attestation_reference.json',{'accepted_commit':'0617e6818f34e4a807e535b35fa4a9281d8d0e0b','role_scope_sha256':sha(canonical(old)),'current_child':load(ROOT/'branch_attestation.json'),'parent_production_credentials_used':False})

def current_checkpoint(cn,source,city,stream):
    return cn.execute('SELECT * FROM public.current_ingestion_checkpoints WHERE source_key=%s AND city_key=%s AND stream_key=%s',(source,city,stream)).fetchone()

def claim_experiment(url,out):
    from db_phase1_persistence import persist_phase1_payload
    from db_phase1_core import CANONICALIZATION_VERSION
    source='c6_two_cycle_experiment_control'; stream=EXPERIMENT
    with connection(url) as cn: need(current_checkpoint(cn,source,'kyiv',stream) is None,'EXPERIMENT_ALREADY_CLAIMED_NO_NEW_HTTP_ALLOWED')
    ck={'source_key':source,'city_key':'kyiv','stream_key':stream,'checkpoint_kind':'bootstrap','checkpoint_seq':1,'previous_checkpoint_id':None,
        'checked_at':now(),'continuity_verified':False,'continuity_method':'control_claim_not_source_capture',
        'observed_record_count':0,'metadata':{'experiment':EXPERIMENT,'source_freshness_evidence':False,'max_gets':60,'max_minutes':70,'run_id':os.getenv('GITHUB_RUN_ID')}}
    with connection(url,False) as cn:
        result=persist_phase1_payload(cn,source_key=source,city_key='kyiv',stream_key=stream,db_branch=CHILD,
            run_provenance=provenance(CANONICALIZATION_VERSION,0,{'control_only':True}),episodes=[],source_observations=[],checkpoint_candidate=ck)
    save(out/'experiment_claim_receipt.json',result)

def provenance(version,cycle,parameters):
    return {'run_kind':'shadow_poll','schema_version':'001_phase1_core','canonicalization_version':version,
        'workflow_repository':'olegbalakin-cmyk/kyiv-air-alerts-grafana','workflow_name':'C6 two-cycle bounded continuity',
        'workflow_ref':BRANCH,'workflow_sha':os.getenv('GITHUB_SHA'),'github_run_id':os.getenv('GITHUB_RUN_ID'),'github_run_attempt':os.getenv('GITHUB_RUN_ATTEMPT'),
        'input_repository':'olegbalakin-cmyk/kyiv-air-alerts-grafana','input_ref':SITE_SHA,'input_sha':SITE_SHA,
        'parameters':{'experiment':EXPERIMENT,'cycle':cycle,'production_authorized':False,**parameters}}

def persist(url,city,source,version,stream,records,http,cycle,out,previous_capture=None,extra=None):
    from db_phase1_core import legacy_episode_id, CANONICALIZATION_VERSION
    from db_phase1_persistence import persist_phase1_payload
    captured=dt(http['captured_at_utc']); extra=extra or {}
    with connection(url) as cn:
        prior=current_checkpoint(cn,source,city,stream)
        before=cn.execute("SELECT episode_uid::text,legacy_episode_id,start_at,end_at,episode_state,canonicalization_version FROM public.alert_episodes WHERE city_key=%s AND alert_type='AIR'",(city,)).fetchall()
        baseline_duplicates=cn.execute("SELECT start_at,end_at,count(*) FROM public.alert_episodes WHERE city_key=%s AND alert_type='AIR' GROUP BY start_at,end_at HAVING count(*)>1",(city,)).fetchall()
    need(not baseline_duplicates,'PREEXISTING_EXACT_DUPLICATES')
    if prior: need(captured>dt(prior['checked_at']),'NONMONOTONIC_CAPTURE')
    by_interval=collections.defaultdict(list)
    for e in before:
        if e['end_at']: by_interval[(dt(e['start_at']),dt(e['end_at']))].append(e)
    episodes=[]; obs=[]; withheld=[]; keys=[]
    records=list({(iso(r['start']),iso(r['end'])):r for r in records}.values())
    for r in records:
        start,end=dt(r['start']),dt(r['end']); need(start<end<=captured,'INVALID_CLOSED_RECORD')
        exact=by_interval[(start,end)]
        # Do not invent an identity rebind or a second overlapping canonical parent.
        overlaps=[e for e in before if e['end_at'] and dt(e['start_at'])<end and start<dt(e['end_at'])]
        if not exact and overlaps:
            withheld.append({'start':iso(start),'end':iso(end),'reason':'OVERLAPPING_CANONICAL_PARENT_REQUIRES_SEPARATE_RECONCILIATION','physical_uuids':[e['episode_uid'] for e in overlaps]}); continue
        need(len(exact)<=1,'AMBIGUOUS_PARENT')
        legacy=exact[0]['legacy_episode_id'] if exact else legacy_episode_id(city,start,end)
        cv=exact[0]['canonicalization_version'] if exact else CANONICALIZATION_VERSION
        rk=r.get('record_key') or sha(canonical({'version':version,'city_key':city,'start':iso(start),'end':iso(end)}))
        keys.append(rk)
        episodes.append({'legacy_episode_id':legacy,'city_key':city,'alert_type':'AIR','start_at':start,'end_at':end,'episode_state':'closed','canonicalization_version':cv})
        obs.append({'episode_legacy_id':legacy,'source_key':source,'source_record_key_version':version,'source_record_key':rk,'source_native_id':r.get('native_id'),
            'city_key':city,'alert_type':'AIR','source_start_at':start,'source_end_at':end,'source_retrieved_at':captured,
            'binding_state':'bound','canonicalization_role':'canonical_input','contributes_start_boundary':True,'contributes_end_boundary':True,
            'raw_sha256':http['raw_sha256'],'raw_object_path':http.get('raw_path'),
            'provenance':{'research_only':True,'experiment':EXPERIMENT,'first_capture':iso(captured)}})
    allkeys={sha(canonical([iso(r['start']),iso(r['end'])])) for r in records}
    overlap=bool(previous_capture and allkeys & set(previous_capture['interval_keys']))
    reaches=bool(previous_capture and records and min(dt(r['start']) for r in records)<=dt(previous_capture['captured_at_utc']))
    bounded_continuity=overlap and reaches and not withheld
    ck={'source_key':source,'city_key':city,'stream_key':stream,'checkpoint_kind':'poll' if prior else 'bootstrap',
        'checked_at':captured,'continuity_verified':bounded_continuity,
        'continuity_method':'two_cycle_history_overlap_only' if bounded_continuity else 'bounded_capture_continuity_not_proven',
        'continuity_anchor_at':dt(previous_capture['captured_at_utc']) if bounded_continuity else None,
        'observed_oldest_start_at':min((dt(r['start']) for r in records),default=None),
        'observed_latest_end_at':max((dt(r['end']) for r in records),default=None),
        'observed_record_count':len(records),'metadata':{'experiment':EXPERIMENT,'cycle':cycle,'http_request':http['request'],
            'new_http_sha256':http['raw_sha256'],'source_captured_at_utc':iso(captured),'source_records_sha256':sha(canonical(records)),
            'persisted_record_keys':keys,'withheld_count':len(withheld),'long_term_continuity_proven':False,**extra}}
    if not prior: ck.update(checkpoint_seq=1,previous_checkpoint_id=None)
    with connection(url,False) as cn:
        result=persist_phase1_payload(cn,source_key=source,city_key=city,stream_key=stream,db_branch=CHILD,
            run_provenance=provenance(CANONICALIZATION_VERSION,cycle,{'http':http,'withheld_count':len(withheld)}),
            episodes=episodes,source_observations=obs,checkpoint_candidate=ck)
    with connection(url) as cn:
        after=current_checkpoint(cn,source,city,stream)
        need(int(after['checkpoint_seq'])==(int(prior['checkpoint_seq'])+1 if prior else 1),'CHECKPOINT_SEQUENCE')
        need(str(after['previous_checkpoint_id'])==(str(prior['checkpoint_id']) if prior else 'None'),'CHECKPOINT_CHAIN')
        need(str(after['created_by_run_id'])==result['run_id'] and after['metadata']['new_http_sha256']==http['raw_sha256'],'CHECKPOINT_RECEIPT_BINDING')
        run=cn.execute('SELECT run_id::text,status,db_branch,ingest_committed_at,parameters FROM public.ingestion_runs WHERE run_id=%s',(result['run_id'],)).fetchone()
        need(run['status']=='succeeded' and run['db_branch']==CHILD and captured<=dt(run['ingest_committed_at']),'COMMIT_RECEIPT')
        rows=cn.execute('SELECT e.episode_uid::text,e.legacy_episode_id,s.source_observation_id::text,s.source_record_key,s.raw_sha256,s.source_retrieved_at,s.first_persisted_by_run_id::text,s.last_seen_by_run_id::text,s.last_seen_at FROM public.alert_episode_sources s JOIN public.alert_episodes e USING(episode_uid) WHERE s.source_key=%s AND s.source_record_key_version=%s AND s.source_record_key=ANY(%s) ORDER BY s.source_record_key',(source,version,keys)).fetchall()
        need(len(rows)==len(keys) and all(r['last_seen_by_run_id']==result['run_id'] for r in rows),'UUID_SOURCE_READBACK')
        dup=cn.execute("SELECT start_at,end_at,count(*) FROM public.alert_episodes WHERE city_key=%s AND alert_type='AIR' GROUP BY start_at,end_at HAVING count(*)>1",(city,)).fetchall()
        need(not dup,'NEW_EXACT_DUPLICATES')
    receipt={'city':city,'cycle':cycle,'writer':result,'prior_checkpoint':prior,'checkpoint':after,'run':run,'source_rows':rows,'exact_duplicate_groups':len(dup),
        'raw_hash_rule':'Existing source raw_sha256/retrieved_at remain first-capture values; this poll HTTP hash is bound by the immutable checkpoint and ingestion run parameters.',
        'withheld':withheld,'readback_at_utc':iso(now()),'readback_transaction':'READ ONLY separate connection'}
    save(out/f'cycle-{cycle}/sql/{city}-{stream.replace(":","_")}.json',receipt)
    return {'city':city,'cycle':cycle,'persistence_readback':'PASS','captured_at_utc':iso(captured),
        'checkpoint_id':str(after['checkpoint_id']),'checkpoint_seq':int(after['checkpoint_seq']),
        'previous_checkpoint_id':str(after['previous_checkpoint_id']) if after['previous_checkpoint_id'] else None,
        'committed_at_utc':iso(run['ingest_committed_at']),'http_sha256':http['raw_sha256'],'http_request':http['request'],
        'interval_keys':sorted(allkeys),'uuid_by_source_record':{r['source_record_key']:[r['episode_uid'],r['source_observation_id']] for r in rows},
        'records_parsed':len(records),'records_persisted':len(rows),'withheld_count':len(withheld),
        'bounded_overlap':bounded_continuity,'no_exact_duplicates':True,'extra':extra}

def telegram_parser(site):
    import bs4
    path=site/'scripts/add_sevastopol_exact.py'; code=ast.parse(path.read_text())
    names={'normalize','strict_kind','parse_page','msg_diag','pair_recent'}
    selected=ast.Module(body=[n for n in code.body if isinstance(n,ast.FunctionDef) and n.name in names],type_ignores=[])
    scope={'re':re,'BeautifulSoup':bs4.BeautifulSoup,'datetime':datetime,'UTC':UTC,'CHANNEL':'razvozhaev'}
    exec(compile(selected,str(path),'exec'),scope); return scope

def source_contracts(site,out):
    import subprocess
    need(subprocess.check_output(['git','-C',str(site),'rev-parse','HEAD'],text=True).strip()==SITE_SHA,'SITE_REF_DRIFT')
    for name,want in PINS.items():
        need(gitblob((site/'scripts'/name).read_bytes())==want,'PIN_CHANGED:'+name)
    bridge=load(site/'data/ukrainealarm_bridge.json')['regions']
    meta=load(site/'data/dashboard_data.json')['multicity_meta']
    keys=meta['production_city_keys']; need(len(keys)==23 and len(bridge)==21,'CITY_CONFIGURATION')
    matrix={}
    for key in keys:
        mm=meta['cities'][key]
        if key=='kyiv':
            endpoint='https://kyiv.digital/storage/air-alert/stats.html'; provider='kyiv_digital'
            contract='Pinned operational completed-history parser; prospective source identity; does not certify active status or cache currency.'
        elif key=='sevastopol':
            endpoint='https://t.me/s/razvozhaev'; provider='telegram'
            contract='Pinned strict occupation-administration AIR signal parser; latest page only, no pagination or absence-of-active inference.'
        else:
            need(key in bridge and bridge[key]['region_id'],'MISSING_REGION_CONTRACT')
            endpoint=UA+'/api/v3/alerts/regionHistory'; provider='ukrainealarm'
            contract='Pinned production AIR regionHistory contract, exact selected region ID; preserves exact city / configured raion semantics.'
        matrix[key]={'city_key':key,'source_type':mm['source_type'],'proxy_raion':mm.get('proxy_raion'),'source_provenance':mm.get('source_provenance'),
            'history_endpoint':endpoint,'provider':provider,'region_id':bridge.get(key,{}).get('region_id'),
            'source_contract':contract,'minimum_same_provider_interval_seconds':70 if provider=='ukrainealarm' else 1500,
            'maximum_cycles':2,'current_active_contract':'NOT_PROVEN_UNTIL_OFFICIAL_OPENAPI_CONFIRMS_ENDPOINT'}
    save(out/'source_matrix.json',matrix)
    save(out/'source_code_contracts.json',{'site_commit':SITE_SHA,'scripts':{n:gitblob((site/'scripts'/n).read_bytes()) for n in PINS},
        'request_policy':'70-second provider floor, no retry or redirect, permanent provider stop on 429/403/401/transport error; cap 60 GET, deadline 60 minutes plus upload.'})
    return matrix

def discover_active_contract(http,token,out):
    """Documentation GETs are budgeted too. Never probe an uncertified data route."""
    try:
        h,b=http.get(UA+'/swagger/index.html','ukrainealarm',0,'documentation',min_interval=70)
        txt=b.decode('utf-8').replace('\\"','"').replace('\\/','/')
        found=re.findall(r'["\']url["\']\s*:\s*["\']([^"\']+\.json)["\']',txt)
        urls=[urljoin(UA+'/swagger/index.html',x) for x in found]
        urls=[u for u in urls if u.startswith(UA+'/swagger/')]
        need(len(set(urls))==1,'OFFICIAL_OPENAPI_LINK_NOT_FOUND')
        h,b=http.get(urls[0],'ukrainealarm',0,'openapi',min_interval=70)
        spec=json.loads(b); paths=spec.get('paths',{})
        hits=[p for p,v in paths.items() if p.rstrip('/').lower().endswith('/alerts') and 'get' in v]
        need(len(hits)==1,'OFFICIAL_ACTIVE_ROUTE_NOT_UNIQUE')
        p=hits[0]; op=paths[p]['get']; text=json.dumps({'op':op,'models':spec.get('components',spec.get('definitions',{}))},ensure_ascii=False)
        need('activeAlerts' in text,'OFFICIAL_ACTIVE_SCHEMA_MISSING')
        need(not [x for x in op.get('parameters',[]) if x.get('required')],'ACTIVE_ENDPOINT_HAS_REQUIRED_PARAMETERS')
        endpoint=UA+(p if p.startswith('/api/') else str(spec.get('basePath',''))+p)
        need(endpoint==UA+'/api/v3/alerts','OFFICIAL_ACTIVE_VERSION_NOT_MATCHED')
        contract={'status':'CONFIRMED_BOUNDED_POSITIVE_ROWS_ONLY','endpoint':endpoint,'openapi_sha256':h['raw_sha256'],
            'inactive_absence_inference_allowed':False,'description':op.get('description',op.get('summary')),
            'minimum_same_provider_interval_seconds':70}
        save(out/'active_contract.json',contract); return endpoint
    except Exception as e:
        save(out/'active_contract.json',{'status':'BLOCKED','reason':str(e) if isinstance(e,Blocked) else type(e).__name__,'uncertified_data_endpoint_requests':0})
        return None

def collect_history(http,url,site,matrix,cycle,out,prior):
    from update_data import parse_live_history
    tg=telegram_parser(site); results={}
    for key,c in matrix.items():
        provider=c['provider']
        if provider in http.stopped:
            results[key]={'city':key,'cycle':cycle,'persistence_readback':'BLOCKED','reason':http.stopped[provider]}; continue
        try:
            headers={'Accept-Encoding':'identity','User-Agent':'kyiv-air-alerts-grafana/research-two-cycle-bounded'}
            params=None
            if provider=='ukrainealarm':
                token=os.environ.get('UKRAINEALARM_API_TOKEN',''); need(bool(token),'MISSING_UKRAINEALARM_TOKEN')
                headers.update(Authorization=token,Accept='application/json'); params={'regionId':c['region_id']}
            h,b=http.get(c['history_endpoint'],provider,cycle,key,headers,params,c['minimum_same_provider_interval_seconds'])
            records=[]; extra={'current_active_state':'NOT_PROVEN_CLOSED_HISTORY_IS_NOT_CURRENT_STATUS'}
            if provider=='kyiv_digital':
                alerts,_=parse_live_history(b.decode('utf-8'))
                valid=sorted([a for a in alerts if a.start<a.end<=dt(h['captured_at_utc'])],key=lambda a:a.end)
                need(valid,'NO_COMPLETED_KYIV_RECORD')
                # Continue the accepted stream using its original stable record identity.
                a=valid[-1]; version='c6-kyiv-digital-html-observation-v1'; source='kyiv_digital_live_http_prospective'; stream='proof:kyiv_digital_html'
                rk=sha(canonical({'version':version,'source_key':source,'city_key':key,'alert_type':'AIR','source_native_id':None,
                    'source_start_at':iso(a.start),'source_end_at':iso(a.end)}))
                records=[{'start':iso(a.start),'end':iso(a.end),'record_key':rk}]
                extra['source_identity']='PROSPECTIVE_NOT_PRODUCTION'
            elif provider=='telegram':
                messages=tg['parse_page'](b.decode('utf-8')); need(messages,'TELEGRAM_NO_MESSAGES')
                pairs,anomalies=tg['pair_recent'](messages)
                records=[{'start':p['start'],'end':p['end'],'native_id':str(p['start_id'])} for p in pairs]
                extra.update(anomalies=anomalies,messages_loaded=len(messages),latest_message_at=iso(max(m['at'] for m in messages)),
                    latest_page_only=True,source_provenance='occupation_administration')
                source='c6_sevastopol_occupation_admin_http'; version='c6-sevastopol-strict-air-v1'; stream='proof:two_cycle_history'
            else:
                payload=json.loads(b); groups=[payload] if isinstance(payload,dict) else payload
                need(isinstance(groups,list),'REGION_HISTORY_SHAPE')
                unclosed=[]
                for group in groups:
                    need(isinstance(group,dict) and isinstance(group.get('alarms'),list),'REGION_HISTORY_CONTRACT_CHANGED')
                    if group.get('regionId') is not None: need(str(group['regionId'])==c['region_id'],'REGION_ID_CHANGED')
                    for a in group['alarms']:
                        if str(a.get('alertType','')).upper()!='AIR': continue
                        if a.get('startDate') and a.get('endDate'):
                            records.append({'start':iso(a['startDate']),'end':iso(a['endDate'])})
                        elif a.get('startDate'): unclosed.append(a)
                source='c6_ukrainealarm_history_http'; version='c6-ukrainealarm-region-history-v1'; stream='proof:two_cycle_history'
                extra['source_unclosed_rows']=unclosed
                extra['zero_unclosed_does_not_prove_inactive']=True
            save(out/f'cycle-{cycle}/parsed/{key}.json',{'http':h,'records':records,'extra':extra})
            results[key]=persist(url,key,source,version,stream,records,h,cycle,out,prior.get(key),extra)
            print('PERSIST_READBACK_PASS',cycle,key,len(records),results[key]['withheld_count'],flush=True)
        except Exception as e:
            results[key]={'city':key,'cycle':cycle,'persistence_readback':'BLOCKED','reason':str(e) if isinstance(e,Blocked) else type(e).__name__,'sqlstate':getattr(e,'sqlstate',None)}
            print('CITY_BLOCKED',cycle,key,results[key]['reason'],flush=True)
        save(out/f'cycle-{cycle}/summary.json',results)
    return results

def collect_active(http,url,endpoint,matrix,cycle,out):
    if not endpoint or 'ukrainealarm' in http.stopped: return {'verdict':'BLOCKED','reason':'NO_ACCESSIBLE_CONFIRMED_ACTIVE_SOURCE'}
    try:
        h,b=http.get(endpoint,'ukrainealarm',cycle,'current-active',{'Authorization':os.environ['UKRAINEALARM_API_TOKEN'],'Accept':'application/json'})
        rows=json.loads(b); need(isinstance(rows,list),'ACTIVE_PAYLOAD_CONTRACT_CHANGED')
        by_id={str(r.get('regionId')):r for r in rows if isinstance(r,dict)}
        all_status={}
        for key,c in matrix.items():
            rid=c.get('region_id') or ('31' if key=='kyiv' else None)
            row=by_id.get(rid)
            # Positive explicit AIR signals only. Ancestor applicability and absent
            # rows are never silently interpreted as inactive.
            airs=[a for a in (row.get('activeAlerts') or []) if isinstance(a,dict) and a.get('type',a.get('alertType'))=='AIR'] if row else []
            all_status[key]={'explicit_row_present':row is not None,'direct_region_id':rid,'direct_air_signals':airs,
                             'current_city_state':'ACTIVE_SOURCE_SIGNAL' if airs else 'NOT_PROVEN',
                             'ancestor_union_and_inactive_absence_certified':False}
        ck=persist(url,'kyiv','c6_ukrainealarm_current_status_http','c6-current-status-v1','proof:two_cycle_active',[],h,cycle,out,extra={'current_status_snapshot':all_status,'status_payload_sha256':h['raw_sha256']})
        result={'verdict':'BOUNDED_PASS_SNAPSHOT_PERSISTED','http':h,'checkpoint':ck,'cities':all_status}
        save(out/f'cycle-{cycle}/active_status.json',result); return result
    except Exception as e:
        result={'verdict':'BLOCKED','reason':str(e) if isinstance(e,Blocked) else type(e).__name__}
        save(out/f'cycle-{cycle}/active_status.json',result); return result

def build_candidate(args,out,cycle,results):
    p=module(ROOT.parent/'neon_23city_publication_2026_10_31/pipeline.py','accepted_pipeline')
    directory=out/f'cycle-{cycle}/generation'; directory.mkdir(parents=True,exist_ok=True)
    adapter,b2,bundle=p.prepare(args,directory)
    snap=p.snapshot(os.environ['NEON_ISOLATED_PROOF_DATABASE_URL'],b2,bundle)
    closed,active=p.verify_snapshot(snap,adapter)
    save(directory/'neon_readback.json',snap)
    cities={key:{'source_captured_at_utc':r.get('captured_at_utc')} for key,r in results.items()}
    generated=p.generate(args,directory,adapter,b2,bundle,snap,closed,active,cities)
    # Same accepted builder, new DB snapshot. No old capture hardcoded as current evidence.
    return generated

def gate(matrix,cycles,active,generation):
    cities={}
    for city,c in matrix.items():
        pair=[x.get(city,{}) for x in cycles]; physical=len(pair)==2 and all(r.get('persistence_readback')=='PASS' for r in pair)
        captures=physical and all(r.get('captured_at_utc') and 0<=(now()-dt(r['captured_at_utc'])).total_seconds()<=21600 for r in pair)
        chain=physical and pair[1]['checkpoint_seq']==pair[0]['checkpoint_seq']+1 and pair[1]['previous_checkpoint_id']==pair[0]['checkpoint_id']
        shared=set(pair[0].get('uuid_by_source_record',{}))&set(pair[1].get('uuid_by_source_record',{})) if len(pair)==2 else set()
        stable=bool(shared) and all(pair[0]['uuid_by_source_record'][k]==pair[1]['uuid_by_source_record'][k] for k in shared)
        reasons=['CURRENT_ACTIVE_AND_ANCESTOR_STATUS_NOT_FULLY_CERTIFIED','LONG_TERM_CONTINUITY_NOT_PROVEN']
        if not captures: reasons.append('MISSING_TWO_FRESH_PERSISTED_SOURCE_CAPTURES')
        if not chain: reasons.append('TWO_CYCLE_CHAIN_NOT_PROVEN')
        if not stable: reasons.append('SHARED_SOURCE_UUID_STABILITY_NOT_PROVEN')
        if any(r.get('withheld_count',0) for r in pair): reasons.append('CANONICAL_OVERLAP_RECONCILIATION_WITHHELD')
        if city in ('kyiv','sevastopol'): reasons.append('SOURCE_COMPLETENESS_OR_CACHE_CURRENCY_NOT_CERTIFIED')
        cities[city]={'two_cycle_physical_persistence':physical,'two_fresh_http_captures':captures,'checkpoint_chain':chain,
            'shared_uuid_stable':stable,'shared_uuid_count':len(shared),'bounded_history_overlap':bool(chain and pair[-1].get('bounded_overlap')),
            'current_active_status':'NOT_PROVEN','publication':'BLOCKED','reasons':reasons,
            'last_source_capture':pair[-1].get('captured_at_utc') if pair else None,'source_type':c['source_type']}
    missing={k:dict(v) for k,v in cities.items()}
    target=next(iter(missing),None)
    if target: missing[target]['two_fresh_http_captures']=False
    # Evaluate the publication predicate against the actual missing-source cities;
    # this is not a fabricated source timestamp or a repeat synthetic freshness suite.
    allowed=lambda rows: bool(rows) and all(v['two_fresh_http_captures'] and v['checkpoint_chain'] and v['current_active_status']=='CERTIFIED' for v in rows.values())
    return cities,{'decision':'PUBLICATION_BLOCKED','publication_allowed':allowed(cities),'publish_directory_created':False,
        'missing_required_source_fail_closed':not allowed(missing),'actual_missing_source_cities':[k for k,v in cities.items() if not v['two_fresh_http_captures']],
        'separate_release_dependencies':['PHYSICAL_DST_REPAIRS','KYIV_CURRENT_PROVENANCE','PRODUCTION_SWITCH_ROLLBACK_PREFLIGHT','PRODUCTION_AUTHORITY'],
        'generation_cycles_completed':len(generation),'active_snapshots':len([a for a in active if a.get('verdict','').startswith('BOUNDED_PASS')])}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--site',required=True,type=Path); ap.add_argument('--accepted',required=True,type=Path); ap.add_argument('--output',required=True,type=Path)
    args=ap.parse_args(); out=args.output.resolve(); need(not out.exists(),'OUTPUT_MUST_BE_NEW'); out.mkdir(parents=True)
    sys.path.insert(0,str((args.site/'scripts').resolve()))
    verdict={'checkpoint':'C6-23CITY-CONTINUITY-02','experiment':EXPERIMENT,'branch_id':CHILD,'github_sha':os.getenv('GITHUB_SHA'),'github_run_id':os.getenv('GITHUB_RUN_ID'),
        'started_at_utc':iso(now()),'publication_allowed':False,'GLOBAL_CUTOVER':'NO','production_mutations':0,'long_term_continuity':'NOT_PROVEN',
        'physical_pass':[],'bounded_pass':[],'blocked':[],'not_proven':['LONG_TERM_CONTINUITY','CANONICAL_ACTIVE_TO_CLOSED_TRANSITION','PRODUCTION_PREFLIGHT']}
    http=Requests(out); cycles=[]; active=[]; generated=[]; matrix={}; exit_code=0
    def stop(*_): raise Blocked('AUTOMATIC_TIME_LIMIT')
    signal.signal(signal.SIGTERM,stop); signal.signal(signal.SIGALRM,stop); signal.alarm(63*60)
    try:
        environment_preflight(os.environ.get('NEON_ISOLATED_PROOF_DATABASE_URL',''),out)
        matrix=source_contracts(args.site,out)
        claim_experiment(os.environ['NEON_ISOLATED_PROOF_DATABASE_URL'],out)
        endpoint=discover_active_contract(http,os.environ.get('UKRAINEALARM_API_TOKEN'),out)
        for cycle in (1,2):
            if cycle==2: http.wait(max(0,cycle_start+1500-time.monotonic()))
            cycle_start=time.monotonic()
            results=collect_history(http,os.environ['NEON_ISOLATED_PROOF_DATABASE_URL'],args.site,matrix,cycle,out,cycles[0] if cycles else {})
            cycles.append(results)
            active.append(collect_active(http,os.environ['NEON_ISOLATED_PROOF_DATABASE_URL'],endpoint,matrix,cycle,out))
            try:
                generated.append(build_candidate(args,out,cycle,results))
            except Exception as e:
                save(out/f'cycle-{cycle}/generation_error.json',{'reason':str(e) if isinstance(e,(Blocked,RuntimeError)) else type(e).__name__})
            save(out/'cycle_comparison.json',{'cycles':cycles,'active':active,'generation':generated})
        cities,decision=gate(matrix,cycles,active,generated); save(out/'cities.json',cities); save(out/'publication_decision.json',decision)
        verdict.update(cycles_completed=len(cycles),cities_with_two_fresh_captures=sum(v['two_fresh_http_captures'] for v in cities.values()),
            cities_with_two_persistence_readbacks=sum(v['two_cycle_physical_persistence'] for v in cities.values()),
            bounded_history_continuity_cities=sum(v['bounded_history_overlap'] for v in cities.values()),
            current_active_fully_certified_cities=0,candidate_generation_cycles=len(generated),decision=decision)
        verdict['physical_pass']=[k for k,v in cities.items() if v['two_cycle_physical_persistence'] and v['checkpoint_chain']]
        verdict['bounded_pass']=[k for k,v in cities.items() if v['bounded_history_overlap'] and v['shared_uuid_stable']]
        verdict['blocked']=[k for k,v in cities.items() if not v['two_fresh_http_captures']]+['PUBLICATION','CURRENT_ACTIVE_COMPLETENESS']
    except Exception as e:
        verdict['blocked'].append(str(e) if isinstance(e,Blocked) else type(e).__name__); exit_code=1
        if matrix:
            cities,decision=gate(matrix,cycles,active,generated); save(out/'cities.json',cities); save(out/'publication_decision.json',decision)
    finally:
        verdict.update(finished_at_utc=iso(now()),http_gets_attempted=len(http.ledger),source_gets=sum(x['cycle']>0 for x in http.ledger),
            documentation_gets=sum(x['cycle']==0 for x in http.ledger),control_plane_gets=1,provider_stops=http.stopped,
            elapsed_seconds=round(time.monotonic()-http.started,3),cycles_completed=len(cycles),automatic_scheduler_installed=False)
        save(out/'machine_verdict.json',verdict)
        save(out/'sha256_manifest.json',{'schema':'c6-two-cycle-continuity-v1','files':{str(p.relative_to(out)):sha(p.read_bytes()) for p in sorted(out.rglob('*')) if p.is_file() and p.name!='sha256_manifest.json'}})
        print(json.dumps(verdict,ensure_ascii=False,default=str),flush=True)
    return exit_code
if __name__=='__main__': raise SystemExit(main())
