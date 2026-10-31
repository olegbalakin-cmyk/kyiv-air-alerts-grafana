#!/usr/bin/env python3
"""Independent offline audit of this experiment's artifact, not a parity replay."""
import argparse
import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

def digest(b): return hashlib.sha256(b).hexdigest()
def moment(v): return datetime.fromisoformat(v.replace('Z','+00:00')).astimezone(timezone.utc)

def audit(path,expected_zip_digest):
    raw=path.read_bytes(); zip_sha=digest(raw)
    if expected_zip_digest:
        assert zip_sha==expected_zip_digest.removeprefix('sha256:'),'ARTIFACT_ZIP_DIGEST'
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None
        names=z.namelist()
        assert len(names)==len(set(names))
        assert all(not Path(n).is_absolute() and '..' not in Path(n).parts for n in names)
        read=lambda name:json.loads(z.read(name))
        manifest=read('sha256_manifest.json')
        assert manifest['schema']=='c6-two-cycle-continuity-v1'
        for name,want in manifest['files'].items():assert digest(z.read(name))==want,name
        machine=read('machine_verdict.json'); http=read('http_requests.json')
        assert len(http)==machine['http_gets_attempted']<=60
        assert machine['elapsed_seconds']<=70*60 and not machine['publication_allowed']
        assert machine['production_mutations']==0 and not machine['automatic_scheduler_installed']
        assert not any(n.startswith('publish/') for n in names)
        assert [h['request'] for h in http]==list(range(1,len(http)+1))
        blocked_providers={}; previous={}
        for h in http:
            assert h['method']=='GET' and h['automatic_retries']==0 and h['redirects_followed']==0
            assert h['provider'] not in blocked_providers,'REQUEST_AFTER_PROVIDER_STOP'
            if h['status'] in (403,429):blocked_providers[h['provider']]=h['status']
            if h.get('raw_path'):
                b=z.read(h['raw_path']);assert digest(b)==h['raw_sha256'] and len(b)==h['entity_bytes']
            if h['provider'] in previous:
                prev=previous[h['provider']]
                gap=(moment(h['started_at_utc'])-moment(prev['finished_at_utc'])).total_seconds()
                assert gap>=(70 if h['provider']=='ukrainealarm' else 1500)-0.1,'POLL_RATE_FLOOR'
            previous[h['provider']]=h
        comparisons=read('cycle_comparison.json') if 'cycle_comparison.json' in names else {'cycles':[]}
        cycles=comparisons['cycles']; assert len(cycles)==2
        city_results={}
        for key in read('source_matrix.json'):
            pairs=[c.get(key,{}) for c in cycles]
            passed=all(c.get('persistence_readback')=='PASS' for c in pairs)
            uuid_count=0; seq=[]; checkpoint_ids=[]
            if passed:
                receipts=[]
                for cycle in (1,2):
                    matches=[n for n in names if n.startswith(f'cycle-{cycle}/sql/{key}-') and n.endswith('.json')
                             and read(n)['checkpoint']['source_key']!='c6_ukrainealarm_current_status_http']
                    assert len(matches)==1,(key,matches)
                    r=read(matches[0]);receipts.append(r)
                    ck=r['checkpoint']; prior=r['prior_checkpoint']; run=r['run']; writer=r['writer']
                    assert run['status']=='succeeded' and run['db_branch']=='br-crimson-star-b59u7ge3'
                    assert str(ck['created_by_run_id'])==writer['run_id']==run['run_id']
                    capture=next(h for h in http if h['request']==ck['metadata']['http_request'])
                    assert ck['metadata']['new_http_sha256']==capture['raw_sha256']
                    assert moment(ck['checked_at'])==moment(capture['captured_at_utc'])
                    assert moment(ck['checked_at'])<=moment(run['ingest_committed_at'])<=moment(r['readback_at_utc'])
                    assert ck['checkpoint_seq']==(prior['checkpoint_seq']+1 if prior else 1)
                    assert ck['previous_checkpoint_id']==(prior['checkpoint_id'] if prior else None)
                    assert r['exact_duplicate_groups']==0
                    for s in r['source_rows']:assert s['last_seen_by_run_id']==writer['run_id']
                    seq.append(ck['checkpoint_seq']); checkpoint_ids.append(str(ck['checkpoint_id']))
                assert receipts[1]['prior_checkpoint']['checkpoint_id']==receipts[0]['checkpoint']['checkpoint_id']
                assert receipts[1]['checkpoint']['checkpoint_seq']==receipts[0]['checkpoint']['checkpoint_seq']+1
                first={s['source_record_key']:s for s in receipts[0]['source_rows']}
                second={s['source_record_key']:s for s in receipts[1]['source_rows']}
                common=set(first)&set(second);uuid_count=len(common)
                for k in common:
                    for f in ('episode_uid','source_observation_id','first_persisted_by_run_id','raw_sha256','source_retrieved_at'):
                        assert first[k][f]==second[k][f],(key,k,f)
                assert all(r['readback_transaction']=='READ ONLY separate connection' for r in receipts)
            city_results[key]={'checkpoint_persistence_two_cycles':passed,'shared_episode_and_source_uuid_pairs':uuid_count,
                'air_episode_uuid_two_cycle_proof':bool(passed and uuid_count),'checkpoint_sequence':seq,'checkpoint_ids':checkpoint_ids,
                'history_record_counts':[c.get('records_parsed') for c in pairs],
                'capture_times_utc':[c.get('captured_at_utc') for c in pairs],
                'current_active_state':'NOT_PROVEN','full_current_source_currency':'NOT_PROVEN',
                'raw_cycle_reasons':[c.get('reason') for c in pairs]}
        generation=[]
        for cycle in (1,2):
            prefix=f'cycle-{cycle}/generation/'
            candidate=prefix+'candidate/dashboard_data.json'
            if candidate not in names:continue
            dashboard=read(candidate);authority=dashboard['meta']['publication_authority']
            snapshot=read(prefix+'neon_readback.json')
            assert len(dashboard['cities'])==23 and not authority['publication_allowed']
            assert authority['source_fallback'] is False
            for key,c in dashboard['cities'].items():
                assert c['meta']['current_source_verified'] is False
                assert authority['source_as_of_utc_by_city'][key]==cycles[cycle-1][key].get('captured_at_utc')
            generation.append({'cycle':cycle,'cities':23,'candidate_json_files':len([n for n in names if n.startswith(prefix+'candidate/') and n.endswith('.json')]),
                'physical_air_parents':len(snapshot['episodes']),'physical_source_observations':len(snapshot['observations']),
                'database_read_at_utc':authority['database_read_at_utc'],'site_generated_at_utc':authority['site_generated_at_utc']})
        decision=read('publication_decision.json')
        assert decision['decision']=='PUBLICATION_BLOCKED' and decision['publication_allowed'] is False
        return {'schema':'c6-two-cycle-independent-review-v1','source_run_id':int(machine['github_run_id']),
            'artifact_zip_sha256':zip_sha,'verified_manifest_members':len(manifest['files']),
            'manifest_sha256':digest(z.read('sha256_manifest.json')),'elapsed_seconds':machine['elapsed_seconds'],
            'upstream_gets_including_docs':len(http),'history_source_gets':sum(h['cycle']>0 for h in http),
            'documentation_gets':sum(h['cycle']==0 for h in http),'github_environment_preflight_gets':machine['control_plane_gets'],
            'http_status_matrix':[{k:h.get(k) for k in ('request','provider','cycle','city','url','status','raw_sha256','captured_at_utc','error')} for h in http],
            'environment_preflight':read('environment_preflight.json'),'active_contract':read('active_contract.json'),
            'cities':city_results,'fresh_http_observed_twice_cities':[k for k,v in city_results.items() if v['checkpoint_persistence_two_cycles']],
            'air_episode_uuid_verified_twice_cities':[k for k,v in city_results.items() if v['air_episode_uuid_two_cycle_proof']],
            'full_current_source_currency_confirmed_cities':[],'generation':generation,
            'publication_decision':decision,'provider_stop_respected':True,'automatic_recurring_scheduler':False,
            'failed_403_response_body_preserved':False,
            'limitations':['Two captures do not establish long-term continuity.','A page checkpoint with zero AIR pairs does not prove episode persistence or inactivity.',
                'A documentation preflight error is not an executed regionHistory availability test.',
                'The failed 403 body was hashed by the runner but not retained; its raw digest cannot be independently recomputed. Successful response entities are retained and verified.',
                'Active-state completeness, upstream cache currency, separate DST/Kyiv release dependencies and production preflight remain open.']}

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('zip',type=Path);ap.add_argument('--expected-zip-sha256');ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    report=audit(a.zip,a.expected_zip_sha256);a.output.write_text(json.dumps(report,sort_keys=True,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('source_run_id','verified_manifest_members','upstream_gets_including_docs','fresh_http_observed_twice_cities','air_episode_uuid_verified_twice_cities','generation')},ensure_ascii=False))
