#!/usr/bin/env python3
"""Independent source-pinned static review of H2 inspector allowlist (NO network/SQL)."""
import copy
import hashlib
import json
import pathlib
import re

HERE = pathlib.Path(__file__).resolve().parent
PINS = {
'G01':'ce813119fd93e85000ed6fedd426eace5f3427f9b96e0580d4aa1b5e3626e061',
'G02':'939aa087f3989273869a0ee8e0d1a4ce97fe090dccb19ef48d237aab1f4ecb80',
'G03':'3935fdb92b3e4ec081b68ac204a2bd0af9419fe91ee4d880a64665470ce29e40',
'G04':'ed9f526db60557e19d7a6f2b489f1afcd55cc877a57ce3af708082d17452d89a',
'G05':'fbc7343ee2d7a011397526517bbaa1f4e401c1a58a6efbb62b1d5610b9d3bf8c',
'G06':'a342759e5e4e889da12e96e7270b38421becb7601bb90f82f3db47632c779b4d',
'G07':'3f74d91f46d32db0d40d65eba5cbd1c84b7c1fb757c741fd1692c7de1ecd240b',
'G08':'01cde324fd932071fd682f1928e78a0dbfd2fd1d76c34ad8e142bb9e4fcd33ce',
'G09':'e708c9fa96bc84b7003fd4798a8226c015dbee1b0c2dd7eace7a40c6f6899a38',
'G10':'498be7a1b8fe07b87675d4624521e1aff35d965789623393ab00e4d1a05f0a19',
'G11':'33a57845c359e82a6ba895a92eb94730756882eb791a270107bc0c2ecc4e0607',
'G12':'1baf7cdfeb807ca2682de3ae2a5619db3681ce2c571e690855fae5a10db8e4b8',
'G13':'cb4fe8636e72a1fce46a0c36da569061ef186e63ae20edaf3bddbf23ef84d738',
'G14':'0d819ea8ce6e3de65b1e13eeeca8bd7d68b2bf33a990a25298a8ba0c1895c932'
}
OBJECTS = {'alert_episode_sources','alert_episodes','attack_event_classifications',
           'attack_event_sources','attack_events','current_ingestion_checkpoints',
           'ingestion_checkpoints','ingestion_runs'}


def review(m):
    assert isinstance(m, dict)
    assert m['kind'] == 'H2_NEON_CATALOG_INSPECTOR_OFFLINE_PROPOSAL'
    assert m['authorization_state']=='NOT_AUTHORIZED_NO_CONNECTION'
    assert m['source']['main_head']=='b5e9b078f171a15ffcf1cb197b61018cd76ca611'
    assert m['source']['accepted_eligibility_research']=='576ac42b7734106ccc0edc858173c90f82537d85'
    assert m['source']['accepted_coordination']=='66fbabf20644797bd67d3790893b4103a5dcb8ef'
    assert m['source']['old_catalog_raw_blob']=='e550b35578283b2af4e0e8fba956e98c4bcc0f03'
    assert m['target']=={'project_id':'green-cake-44216048','branch_id':'br-bold-mode-b5rub8pq',
      'database':'neondb','historical_endpoint_id':'ep-calm-rice-b5073ypp',
      'current_endpoint_id':None,'endpoint_hostname':None,
      'host_branch_mapping_verified':False,'control_plane_evidence_age_hours':None}
    assert m['inspector']=={'proposed_role':'h2_catalog_inspector_ro','actual_role_verified':False,
      'least_privilege_verified':False,'role_provisioned_here':False,'owner_role_alternative_approved':False}
    assert all(v is None for v in m['approval'].values())
    assert m['limits']=={'connections':1,'transactions':1,'unique_selects':14,
      'max_catalog_select_executions':15,'max_sql_statement_executions':21,
      'max_result_rows_total':180,'max_sanitized_bytes_total':65536,
      'max_cell_bytes':8192,'statement_timeout_ms':15000,'lock_timeout_ms':5000,
      'idle_in_transaction_timeout_ms':30000,'transaction_timeout_ms':45000,'client_wall_clock_ms':60000}
    assert len(m['session_sql_order'])==21
    assert m['session_sql_order'][0]=='BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;'
    assert m['session_sql_order'][1:5]==["SET LOCAL statement_timeout = '15s';",
      "SET LOCAL lock_timeout = '5s';","SET LOCAL idle_in_transaction_session_timeout = '30s';",
      "SET LOCAL transaction_timeout = '45s';"]
    assert m['session_sql_order'][5]=='G01' and m['session_sql_order'][-2:] == ['G01','ROLLBACK;']
    assert m['session_sql_order'][6:-2]==[f'G{i:02d}' for i in range(2,15)]
    assert m['sql_policy']=={'allow_certain_builtin_pg_catalog_functions_only':True,
      'allow_user_defined_function_calls':False,'allow_application_row_selects':False,
      'allow_role_switch':False,'allow_data_modification':False,'allow_connection_fallback':False,
      'allow_neon_api':False,'capture_secrets_or_dsns':False,
      'ignore_or_normalize_raw_relacl':False}
    assert list(PINS)==[q['id'] for q in m['queries']]
    assert sum(q['max_rows'] for q in m['queries'])+1 <=180
    for q in m['queries']:
        sql=q['sql']
        digest=hashlib.sha256(sql.encode('utf-8')).hexdigest()
        assert digest == q['sha256'] == PINS[q['id']]
        assert sql.startswith('SELECT ') and sql.endswith(';') and sql.count(';')==1
        assert q['max_rows']<=33 and q['max_cell_bytes']==8192
        assert q['contract_ids'] and q['purpose'] and q['columns']
        outside_literals=re.sub(r"'(?:[^']|'')*'", "''", sql)
        assert not re.search(r'\b(from|join)\s+public\.',outside_literals,re.I)
        assert not re.search(r'\b(update|insert|delete|truncate|alter|drop|create|grant|revoke|execute|call|copy)\b',outside_literals,re.I)
        assert not re.search(r'\bpg_catalog\.dblink\b|\bpublic\.\w+\s*\(',outside_literals,re.I)
    assert 'raw_relacl_is_null' in m['queries'][3]['columns']
    assert 'raw_relacl_text' in m['queries'][3]['columns']
    for obj in OBJECTS:
        assert "'"+obj+"'" in m['queries'][3]['sql']
    assert m['unchanged_hard_holds']=={
      'H2_READONLY_NEON_PREFLIGHT_READINESS':'BLOCKED/NO-GO',
      'H2_DISPOSABLE_NEON_TEST_READINESS':'BLOCKED/NO-GO',
      'NEON_AUTHORITY_ACTIVE':'NO','PRODUCTION_CUTOVER_EXECUTED':'NO',
      'WIP_ACTIVATION':'NO-GO','H2_ACL_OPTION_B':'BLOCKED / PROPOSAL_ONLY'}
    raw=json.dumps(m,ensure_ascii=True)
    assert not re.search(r'(?i)postgres(?:ql)?://|password\s*[:=]|bearer\s+[a-z0-9_-]{8,}',raw)
    return True


def negatives(m):
    case=[]
    def t(name,mutate):
        copy_m=copy.deepcopy(m);mutate(copy_m)
        try: review(copy_m)
        except (AssertionError, KeyError, TypeError, ValueError): case.append(name)
        else: raise AssertionError('negative escaped independent review: '+name)
    t('S01_rehashed_query',lambda x:x['queries'][3].update(sql='SELECT * FROM public.attack_events;',sha256=hashlib.sha256(b'SELECT * FROM public.attack_events;').hexdigest()))
    t('S02_extra_query',lambda x:x['queries'].append(copy.deepcopy(x['queries'][2])))
    t('S03_invalid_role',lambda x:x['inspector'].update(proposed_role='neondb_owner'))
    t('S04_injected_secret',lambda x:x['approval'].update(DSN='postgresql://example'))
    t('S05_unsafe_endpoint',lambda x:x['target'].update(endpoint_hostname='invented.neon.tech'))
    t('S06_wrong_branch',lambda x:x['target'].update(branch_id='br-wandering-sunset-b5835alw'))
    t('S07_live_authorized',lambda x:x.update(authorization_state='AUTHORIZED'))
    t('S08_remove_null_acl',lambda x:x['queries'][3]['columns'].remove('raw_relacl_is_null'))
    t('S09_remove_canonical_object',lambda x:x['queries'][3].update(sql=x['queries'][3]['sql'].replace("'attack_events'", "'not_a_table'")))
    t('S10_write_tx',lambda x:x['session_sql_order'].__setitem__(0,'BEGIN READ WRITE;'))
    t('S11_missing_rollback',lambda x:x['session_sql_order'].__setitem__(-1,'COMMIT;'))
    t('S12_relaxed_limit',lambda x:x['limits'].update(max_result_rows_total=99999))
    t('S13_missing_coord',lambda x:x['source'].update(accepted_coordination='0'*40))
    t('S14_role_switch',lambda x:x['sql_policy'].update(allow_role_switch=True))
    t('S15_wrong_hash',lambda x:x['queries'][0].update(sha256='0'*64))
    t('S16_fake_role_attested',lambda x:x['inspector'].update(actual_role_verified=True))
    return case


def main():
    m=json.loads((HERE/'H2_READONLY_QUERY_MANIFEST.json').read_text(encoding='utf-8'))
    assert review(m)
    tests=negatives(m)
    out={'kind':'H2_INDEPENDENT_CODE_SEALED_OFFLINE_REVIEW','source':'separate pinned-hash and policy implementation',
         'checks':'PASS','pinned_queries':len(PINS),'rejected_negative_controls':len(tests),
         'names':tests,'real_neon_access':False,'real_role_attestation':False,
         'coordinator_accepted':False,'actual_readonly_gate':'BLOCKED/NO-GO'}
    (HERE/'H2_INSPECTOR_INDEPENDENT_REVIEW.json').write_text(json.dumps(out,indent=2)+'\n')
    print('PASS INDEPENDENT OFFLINE: 14/14 sealed query hashes; '+str(len(tests))+'/'+str(len(tests))+' mutations rejected; NO NEON')

if __name__=='__main__':
    main()
