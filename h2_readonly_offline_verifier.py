#!/usr/bin/env python3
"""H2 inspector proposal: completely offline manifest, shape, and negative validation.

No database, API, socket, credential, or environment access. Python stdlib only.
This is not an authorized SQL executor or a runtime attestation verifier.
"""
import argparse
import copy
import hashlib
import json
import pathlib
import sys

MAIN = 'b5e9b078f171a15ffcf1cb197b61018cd76ca611'
COORD = '66fbabf20644797bd67d3790893b4103a5dcb8ef'
MATRIX = '576ac42b7734106ccc0edc858173c90f82537d85'
PROJECT = 'green-cake-44216048'
BRANCH = 'br-bold-mode-b5rub8pq'
ENDPOINT = 'ep-calm-rice-b5073ypp'
ROLE = 'h2_catalog_inspector_ro'  # proposed, NOT provisioned or verified
TABLES = ('alert_episode_sources', 'alert_episodes', 'attack_event_classifications',
          'attack_event_sources', 'attack_events', 'current_ingestion_checkpoints',
          'ingestion_checkpoints', 'ingestion_runs')
STATUS = {'H2_READONLY_NEON_PREFLIGHT_READINESS': 'BLOCKED/NO-GO',
          'H2_DISPOSABLE_NEON_TEST_READINESS': 'BLOCKED/NO-GO',
          'NEON_AUTHORITY_ACTIVE': 'NO', 'PRODUCTION_CUTOVER_EXECUTED': 'NO',
          'WIP_ACTIVATION': 'NO-GO', 'H2_ACL_OPTION_B': 'BLOCKED / PROPOSAL_ONLY'}


def sha(t):
    return hashlib.sha256(t.encode('utf-8')).hexdigest()


def query(id, sql, columns, max_rows, contracts, reason):
    sql = sql.strip()
    return {'id': id, 'sql': sql, 'sha256': sha(sql), 'columns': columns,
            'max_rows': max_rows, 'max_cell_bytes': 8192,
            'contract_ids': contracts, 'purpose': reason}


def expected_queries():
    names = ', '.join("'" + t + "'" for t in TABLES)
    return [
      query('G01', '''SELECT pg_catalog.current_database() AS database_name,
  current_user AS current_role, session_user AS session_role,
  pg_catalog.current_setting('transaction_read_only') AS transaction_read_only,
  pg_catalog.current_setting('transaction_isolation') AS isolation,
  pg_catalog.current_setting('statement_timeout') AS statement_timeout,
  pg_catalog.current_setting('lock_timeout') AS lock_timeout,
  pg_catalog.current_setting('idle_in_transaction_session_timeout') AS idle_timeout,
  pg_catalog.current_setting('transaction_timeout') AS transaction_timeout,
  pg_catalog.current_setting('server_version_num') AS server_version_num,
  pg_catalog.pg_current_snapshot()::text AS snapshot_token;''',
            ['database_name','current_role','session_role','transaction_read_only','isolation',
             'statement_timeout','lock_timeout','idle_timeout','transaction_timeout',
             'server_version_num','snapshot_token'], 1, ['I1','I2','I3','I6','211'],
            'Run exactly twice: after timeout setup and immediately before ROLLBACK; identical snapshot and guard values.'),
      query('G02', f'''SELECT r.rolname, r.rolsuper, r.rolinherit, r.rolcreaterole,
  r.rolcreatedb, r.rolcanlogin, r.rolreplication, r.rolbypassrls
FROM pg_catalog.pg_roles AS r
WHERE r.rolname = '{ROLE}' LIMIT 2;''',
            ['rolname','rolsuper','rolinherit','rolcreaterole','rolcreatedb','rolcanlogin','rolreplication','rolbypassrls'],
            2, ['I2','206','READ-03'], 'Exactly one LOGIN inspector with all elevated flags false; no owner fallback.'),
      query('G03', f'''SELECT parent.rolname AS granted_role, member.rolname AS member_role,
  m.admin_option, m.inherit_option, m.set_option
FROM pg_catalog.pg_auth_members AS m
JOIN pg_catalog.pg_roles AS parent ON parent.oid = m.roleid
JOIN pg_catalog.pg_roles AS member ON member.oid = m.member
WHERE parent.rolname = '{ROLE}' OR member.rolname = '{ROLE}'
ORDER BY parent.rolname, member.rolname LIMIT 17;''',
            ['granted_role','member_role','admin_option','inherit_option','set_option'],
            17, ['I2','206','READ-03'], 'Fail closed on any direct inspector role membership; no SET or inherited authority.'),
      query('G04', f'''SELECT n.nspname AS schema_name, c.relname AS object_name,
  c.relkind, owner.rolname AS owner_name,
  (c.relacl IS NULL) AS raw_relacl_is_null, c.relacl::text AS raw_relacl_text
FROM pg_catalog.pg_class AS c
JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
JOIN pg_catalog.pg_roles AS owner ON owner.oid = c.relowner
WHERE n.nspname = 'public' AND c.relname IN ({names})
ORDER BY c.relname LIMIT 9;''',
            ['schema_name','object_name','relkind','owner_name','raw_relacl_is_null','raw_relacl_text'],
            9, ['I4','183','190','193','196','197','206','213','ACL-01'],
            'Eight selected canonical relations; preserve literal NULL-versus-explicit ACL, no normalization.'),
      query('G05', '''SELECT n.nspname AS schema_name, owner.rolname AS owner_name,
  (n.nspacl IS NULL) AS raw_acl_is_null, n.nspacl::text AS raw_acl_text
FROM pg_catalog.pg_namespace AS n
JOIN pg_catalog.pg_roles AS owner ON owner.oid = n.nspowner
WHERE n.nspname = 'public' LIMIT 2;''',
            ['schema_name','owner_name','raw_acl_is_null','raw_acl_text'], 2,
            ['I2','206','READ-01'], 'Raw public schema owner and privileges only.'),
      query('G06', '''SELECT a.attnum AS ordinal, a.attname AS column_name,
  pg_catalog.format_type(a.atttypid, a.atttypmod) AS data_type,
  a.attnotnull AS not_null
FROM pg_catalog.pg_attribute AS a
JOIN pg_catalog.pg_class AS c ON c.oid = a.attrelid
JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relname = 'current_ingestion_checkpoints'
  AND a.attnum > 0 AND NOT a.attisdropped
ORDER BY a.attnum LIMIT 19;''',
            ['ordinal','column_name','data_type','not_null'], 19, ['I4','190'],
            '18-column checkpoint view contract, 19th row detects drift; no application rows.'),
      query('G07', '''SELECT c.relname AS view_name, pg_catalog.pg_get_viewdef(c.oid, false) AS view_sql
FROM pg_catalog.pg_class AS c
JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relname = 'current_ingestion_checkpoints'
  AND c.relkind = 'v' LIMIT 2;''',
            ['view_name','view_sql'], 2, ['I4','190'],
            'Catalog view definition of the single named checkpoint view, built-in pg_catalog introspector.'),
      query('G08', '''SELECT t.relname AS table_name, idx.relname AS index_name,
  i.indisunique AS is_unique, i.indisprimary AS is_primary,
  i.indisvalid AS is_valid, pg_catalog.pg_get_indexdef(idx.oid) AS index_sql
FROM pg_catalog.pg_index AS i
JOIN pg_catalog.pg_class AS t ON t.oid = i.indrelid
JOIN pg_catalog.pg_class AS idx ON idx.oid = i.indexrelid
JOIN pg_catalog.pg_namespace AS n ON n.oid = t.relnamespace
WHERE n.nspname = 'public'
  AND t.relname IN ('alert_episodes', 'attack_event_classifications')
ORDER BY t.relname, idx.relname LIMIT 33;''',
            ['table_name','index_name','is_unique','is_primary','is_valid','index_sql'],
            33, ['I4','183','193','197','213'],
            'Index metadata only: parent identity, revision successor and tip enforcement.'),
      query('G09', '''SELECT t.relname AS table_name, k.conname AS constraint_name,
  k.contype AS constraint_type, k.condeferrable AS is_deferrable,
  k.condeferred AS initially_deferred,
  pg_catalog.pg_get_constraintdef(k.oid, false) AS constraint_sql
FROM pg_catalog.pg_constraint AS k
JOIN pg_catalog.pg_class AS t ON t.oid = k.conrelid
JOIN pg_catalog.pg_namespace AS n ON n.oid = t.relnamespace
WHERE n.nspname = 'public'
  AND t.relname IN ('alert_episodes', 'attack_event_classifications', 'ingestion_checkpoints')
ORDER BY t.relname, k.conname LIMIT 33;''',
            ['table_name','constraint_name','constraint_type','is_deferrable',
             'initially_deferred','constraint_sql'], 33,
            ['I4','183','193','197','211','213'], 'Selected constraint and deferrability metadata.'),
      query('G10', f'''SELECT c.relname AS object_name,
  pg_catalog.has_table_privilege(current_user, c.oid, 'SELECT') AS can_select,
  pg_catalog.has_table_privilege(current_user, c.oid, 'INSERT') AS can_insert,
  pg_catalog.has_table_privilege(current_user, c.oid, 'UPDATE') AS can_update,
  pg_catalog.has_table_privilege(current_user, c.oid, 'DELETE') AS can_delete
FROM pg_catalog.pg_class AS c
JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relname IN ({names})
ORDER BY c.relname LIMIT 9;''',
            ['object_name','can_select','can_insert','can_update','can_delete'], 9,
            ['I2','206','READ-03'],
            'Effective inspector privileges; any application-table access or DML privilege is a stop.'),
      query('G11', '''SELECT owner.rolname AS default_acl_owner,
  COALESCE(n.nspname, '') AS default_acl_schema,
  d.defaclobjtype AS object_kind, (d.defaclacl IS NULL) AS raw_acl_is_null,
  d.defaclacl::text AS raw_acl_text
FROM pg_catalog.pg_default_acl AS d
JOIN pg_catalog.pg_roles AS owner ON owner.oid = d.defaclrole
LEFT JOIN pg_catalog.pg_namespace AS n ON n.oid = d.defaclnamespace
WHERE n.nspname = 'public' OR (n.oid IS NULL AND owner.rolname = 'neondb_owner')
ORDER BY owner.rolname, n.nspname, d.defaclobjtype LIMIT 13;''',
            ['default_acl_owner','default_acl_schema','object_kind','raw_acl_is_null','raw_acl_text'],
            13, ['I4','206','ACL-01'], 'Public schema/known historical owner default ACL; stop if cap exceeded.'),
      query('G12', '''SELECT n.nspname AS schema_name, p.proname AS function_name,
  p.oid::pg_catalog.regprocedure::text AS signature,
  p.provolatile AS volatility, p.prosecdef AS security_definer,
  pg_catalog.has_function_privilege(current_user, p.oid, 'EXECUTE') AS can_execute
FROM pg_catalog.pg_proc AS p
JOIN pg_catalog.pg_namespace AS n ON n.oid = p.pronamespace
WHERE n.nspname = 'pg_catalog'
  AND p.proname IN ('pg_advisory_xact_lock', 'hashtextextended', 'gen_random_uuid')
ORDER BY p.proname, p.oid LIMIT 9;''',
            ['schema_name','function_name','signature','volatility','security_definer','can_execute'],
            9, ['I4','210','212'], 'Catalog-only signatures and builtin execute flags; does not invoke target functions.'),
      query('G13', '''SELECT e.extname AS extension_name, e.extversion AS extension_version,
  n.nspname AS installed_schema
FROM pg_catalog.pg_extension AS e
JOIN pg_catalog.pg_namespace AS n ON n.oid = e.extnamespace
WHERE e.extname = 'plpgsql' LIMIT 2;''',
            ['extension_name','extension_version','installed_schema'], 2,
            ['I4','212'], 'Only historically observed plpgsql extension; other extensions explicitly out of scope.'),
      query('G14', '''SELECT s.name AS setting_name, s.setting AS setting_value,
  s.unit AS unit, s.source AS source
FROM pg_catalog.pg_settings AS s
WHERE s.name IN ('default_transaction_read_only', 'default_transaction_isolation', 'search_path')
ORDER BY s.name LIMIT 4;''',
            ['setting_name','setting_value','unit','source'], 4,
            ['I3','211','212'], 'Only three relevant session defaults; not the application writer defaults.'),
    ]


def canonical_manifest():
    qs = expected_queries()
    return {
      'schema_version': 1,
      'kind': 'H2_NEON_CATALOG_INSPECTOR_OFFLINE_PROPOSAL',
      'authorization_state': 'NOT_AUTHORIZED_NO_CONNECTION',
      'source': {'main_head': MAIN, 'accepted_eligibility_research': MATRIX,
                 'accepted_coordination': COORD,
                 'old_catalog_raw_blob': 'e550b35578283b2af4e0e8fba956e98c4bcc0f03',
                 'old_catalog_audit_commit': '380e16f4d8e861a30ba899921a7dbc33d5077bd5',
                 'historical_target_design_commit': 'eabdd380694abe045bf2cd15b7b83d7d1bb0d965'},
      'target': {'project_id': PROJECT, 'branch_id': BRANCH, 'database': 'neondb',
                 'historical_endpoint_id': ENDPOINT, 'current_endpoint_id': None,
                 'endpoint_hostname': None, 'host_branch_mapping_verified': False,
                 'control_plane_evidence_age_hours': None},
      'inspector': {'proposed_role': ROLE, 'actual_role_verified': False,
                    'least_privilege_verified': False, 'role_provisioned_here': False,
                    'owner_role_alternative_approved': False},
      'approval': {'operator': None, 'independent_reviewer': None,
                   'route_scope_approval': None, 'explicit_user_access_authorization': None},
      'limits': {'connections': 1, 'transactions': 1, 'unique_selects': len(qs),
                 'max_catalog_select_executions': len(qs)+1,
                 'max_sql_statement_executions': len(qs)+7, 'max_result_rows_total': 180,
                 'max_sanitized_bytes_total': 65536, 'max_cell_bytes': 8192,
                 'statement_timeout_ms': 15000, 'lock_timeout_ms': 5000,
                 'idle_in_transaction_timeout_ms': 30000, 'transaction_timeout_ms': 45000,
                 'client_wall_clock_ms': 60000},
      'session_sql_order': [
        'BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;',
        "SET LOCAL statement_timeout = '15s';",
        "SET LOCAL lock_timeout = '5s';",
        "SET LOCAL idle_in_transaction_session_timeout = '30s';",
        "SET LOCAL transaction_timeout = '45s';",
        'G01', *[q['id'] for q in qs if q['id'] != 'G01'], 'G01', 'ROLLBACK;'
      ],
      'sql_policy': {'allow_certain_builtin_pg_catalog_functions_only': True,
                     'allow_user_defined_function_calls': False,
                     'allow_application_row_selects': False,
                     'allow_role_switch': False, 'allow_data_modification': False,
                     'allow_connection_fallback': False, 'allow_neon_api': False,
                     'capture_secrets_or_dsns': False,
                     'ignore_or_normalize_raw_relacl': False},
      'queries': qs,
      'receipt_contract': {
        'required_fields': ['scope_and_authorization', 'routing_attestation',
          'session_guards_before_after', 'effective_inspector_role', 'query_hashes',
          'exact_result_column_names', 'per_query_row_byte_counts_and_truncation',
          'sanitized_catalog_rows_and_digests', 'raw_relacl_null_bits_and_text',
          'source_commits_and_old_catalog_digest', 'timestamps_and_snapshot',
          'cancellation_and_rollback_status', 'zero_attempted_write_and_api_attestation',
          'unresolved_and_partial_contracts'],
        'disallowed_content': ['DSN', 'password', 'token', 'application_row',
          'function_body', 'external_non_catalog_payload'],
        'required_runtime_coverage': ['I1','I2','I3','I4','I5','I6','I7'],
        'retention': 'owner-approve separately; do not publish raw credentials or connection logs'
      },
      'unchanged_hard_holds': STATUS,
    }


def canonical_bytes(obj):
    return (json.dumps(obj, sort_keys=True, ensure_ascii=True, separators=(',', ':'))+'\n').encode('ascii')


def validate_manifest(doc):
    expected = canonical_manifest()
    if type(doc) is not dict or canonical_bytes(doc) != canonical_bytes(expected):
        # Reject even mutually rehashed SQL or a self-declared approval flip.
        raise ValueError('manifest differs from separately code-pinned canonical offline policy')
    qs = doc['queries']
    if len({q['id'] for q in qs}) != len(qs):
        raise ValueError('duplicate ID')
    for q in qs:
        if sha(q['sql']) != q['sha256']:
            raise ValueError('SQL hash mismatch: '+q['id'])
        if q['max_rows'] <= 0 or q['max_rows'] > 33:
            raise ValueError('unbounded rows')
        if q['sql'].count(';') != 1 or not q['sql'].endswith(';'):
            raise ValueError('not single-statement')
    return True


def synthetic_receipt(doc):
    """Non-executable, explicitly synthetic *shape* for negative tests only."""
    return {'mode': 'SYNTHETIC_OFFLINE_ONLY',
            'manifest_sha256': hashlib.sha256(canonical_bytes(doc)).hexdigest(),
            'route': {'project_id': PROJECT, 'branch_id': BRANCH, 'database': 'neondb',
                      'endpoint_id': ENDPOINT, 'attestation_kind': 'SYNTHETIC_TEST_ONLY'},
            'role': {'current_role': ROLE, 'session_role': ROLE, 'elevated_flags': False,
                     'direct_membership_edges': 0, 'data_privilege_detected': False},
            'session': {'begin_read_only': 'on', 'end_read_only': 'on',
                        'begin_isolation': 'repeatable read', 'end_isolation': 'repeatable read',
                        'begin_snapshot': 'FAKE_SNAPSHOT', 'end_snapshot': 'FAKE_SNAPSHOT',
                        'statement_timeout_ms': 15000, 'lock_timeout_ms': 5000,
                        'idle_timeout_ms': 30000, 'transaction_timeout_ms': 45000,
                        'rollback_observed': True, 'cancel_failed_closed': True},
            'results': [{'id': q['id'], 'sql_sha256': q['sha256'],
                         'columns': q['columns'], 'row_count': 0, 'bytes': 0,
                         'truncated': False, 'sanitized': True, 'raw_acl_preserved': True}
                        for q in doc['queries']],
            'actions': {'connections': 1, 'sql_statement_executions': len(doc['session_sql_order']),
                        'catalog_select_executions': len(doc['queries'])+1,
                        'attempted_writes': 0, 'neon_api_calls': 0,
                        'role_switches': 0, 'application_rows': 0,
                        'secrets_in_output': 0, 'sanitized_bytes_total': 0,
                        'elapsed_ms': 1000},
            'claim': 'LAYOUT_TEST_ONLY; NEVER RUNTIME I1-I7 PASS'}


def validate_synthetic_receipt(doc, r):
    """Tests fail-closed logical receipt invariants, NOT actual Neon evidence."""
    validate_manifest(doc)
    fail = lambda reason: (_ for _ in ()).throw(ValueError(reason))
    if r.get('mode') != 'SYNTHETIC_OFFLINE_ONLY' or r.get('claim') != 'LAYOUT_TEST_ONLY; NEVER RUNTIME I1-I7 PASS':
        fail('not a synthetic-only test receipt')
    if r.get('manifest_sha256') != hashlib.sha256(canonical_bytes(doc)).hexdigest():
        fail('receipt does not pin exact manifest')
    if r.get('route') != {'project_id': PROJECT, 'branch_id': BRANCH, 'database': 'neondb',
                           'endpoint_id': ENDPOINT, 'attestation_kind': 'SYNTHETIC_TEST_ONLY'}:
        fail('I1 fake routing mismatch')
    if r.get('role') != {'current_role': ROLE, 'session_role': ROLE, 'elevated_flags': False,
                          'direct_membership_edges': 0, 'data_privilege_detected': False}:
        fail('I2 role/authority mismatch')
    s = r.get('session', {})
    if s != synthetic_receipt(doc)['session']:
        fail('I3 inconsistent guards, limits, rollback or cancellation')
    if not isinstance(r.get('results'), list) or len(r['results']) != len(doc['queries']):
        fail('I4 missing or extra query result')
    for actual, expected in zip(r['results'], doc['queries']):
        if (actual.get('id') != expected['id'] or actual.get('sql_sha256') != expected['sha256']
                or actual.get('columns') != expected['columns']):
            fail('I4/I6 unexpected query, hash or result schema')
        if (not isinstance(actual.get('row_count'), int) or isinstance(actual['row_count'], bool)
                or not 0 <= actual['row_count'] <= expected['max_rows']):
            fail('I5 query row cap')
        if (not isinstance(actual.get('bytes'), int) or isinstance(actual['bytes'], bool)
                or actual['bytes'] < 0 or actual['bytes'] > doc['limits']['max_sanitized_bytes_total']
                or actual.get('truncated') is not False or actual.get('sanitized') is not True
                or actual.get('raw_acl_preserved') is not True):
            fail('I4/I5 bytes, truncation, sanitation or physical ACL')
    a = r.get('actions', {})
    if a != synthetic_receipt(doc)['actions']:
        fail('I5/I7 mutation, extra session, exfiltration, wall-clock or query budget')
    if sum(x['row_count'] for x in r['results']) > doc['limits']['max_result_rows_total']:
        fail('I5 total rows')
    if sum(x['bytes'] for x in r['results']) > doc['limits']['max_sanitized_bytes_total']:
        fail('I5 total bytes')
    return True


def negative_cases(manifest):
    cases = []
    def change(name, fn):
        x = copy.deepcopy(manifest); fn(x); cases.append((name,x,False))
    change('N01_sql_update_rehashed', lambda m: m['queries'][0].update(sql='UPDATE public.attack_events SET x=1;', sha256=sha('UPDATE public.attack_events SET x=1;')))
    change('N02_sql_app_rows', lambda m: m['queries'][3].update(sql='SELECT * FROM public.attack_events;', sha256=sha('SELECT * FROM public.attack_events;')))
    change('N03_extra_query', lambda m: m['queries'].append(copy.deepcopy(m['queries'][0])))
    change('N04_missing_guard', lambda m: m['queries'].pop(0))
    change('N05_role_owner', lambda m: m['inspector'].update(proposed_role='neondb_owner'))
    change('N06_route_branch', lambda m: m['target'].update(branch_id='br-wandering-sunset-b5835alw'))
    change('N07_unverified_endpoint', lambda m: m['target'].update(current_endpoint_id='some-host'))
    change('N08_fake_role_verified', lambda m: m['inspector'].update(actual_role_verified=True))
    change('N09_claim_authorized', lambda m: m.update(authorization_state='AUTHORIZED'))
    change('N10_raise_rows', lambda m: m['limits'].update(max_result_rows_total=999999))
    change('N11_drop_reacl_bit', lambda m: m['queries'][3]['columns'].remove('raw_relacl_is_null'))
    change('N12_owner_alternative', lambda m: m['inspector'].update(owner_role_alternative_approved=True))
    change('N13_sql_function_side_effect', lambda m: m['queries'][4].update(sql='SELECT public.do_something();'))
    change('N14_add_sql_comment', lambda m: m['queries'][0].update(sql=m['queries'][0]['sql']+' -- harmless'))
    change('N15_replace_original_catalog_blob', lambda m: m['source'].update(old_catalog_raw_blob='0'*40))
    change('N16_flip_authority_hold', lambda m: m['unchanged_hard_holds'].update(NEON_AUTHORITY_ACTIVE='YES'))
    change('N17_remove_repeat_guard', lambda m: m['session_sql_order'].remove('G01'))
    change('N18_commit_not_rollback', lambda m: m['session_sql_order'].__setitem__(-1,'COMMIT;'))
    change('N19_disable_timeout', lambda m: m['session_sql_order'].__setitem__(1,"SET LOCAL statement_timeout = '0';"))
    change('N20_add_secret', lambda m: m['target'].update(dsn='postgresql://secret@invalid.invalid/'))
    return cases


def receipt_negative_cases(doc):
    cases = []
    def change(name, fn):
        x=synthetic_receipt(doc); fn(x); cases.append((name,x))
    change('R01_wrong_branch', lambda r: r['route'].update(branch_id='br-wandering-sunset-b5835alw'))
    change('R02_owner_login', lambda r: r['role'].update(current_role='neondb_owner'))
    change('R03_set_role_path', lambda r: r['role'].update(direct_membership_edges=1))
    change('R04_rw_transaction', lambda r: r['session'].update(begin_read_only='off'))
    change('R05_read_committed', lambda r: r['session'].update(begin_isolation='read committed'))
    change('R06_snapshot_drift', lambda r: r['session'].update(end_snapshot='DIFFERENT'))
    change('R07_timeout_off', lambda r: r['session'].update(statement_timeout_ms=0))
    change('R08_missing_rollback', lambda r: r['session'].update(rollback_observed=False))
    change('R09_missing_query_result', lambda r: r['results'].pop())
    change('R10_query_rehash_wrong', lambda r: r['results'][0].update(sql_sha256='0'*64))
    change('R11_column_schema', lambda r: r['results'][3]['columns'].remove('raw_relacl_text'))
    change('R12_truncation', lambda r: r['results'][3].update(truncated=True))
    change('R13_raw_acl_normalized', lambda r: r['results'][3].update(raw_acl_preserved=False))
    change('R14_query_row_overflow', lambda r: r['results'][2].update(row_count=999))
    change('R15_secret_exposure', lambda r: r['actions'].update(secrets_in_output=1))
    change('R16_data_mutation', lambda r: r['actions'].update(attempted_writes=1))
    change('R17_extra_connection', lambda r: r['actions'].update(connections=2))
    change('R18_control_plane_api', lambda r: r['actions'].update(neon_api_calls=1))
    change('R19_no_cancel', lambda r: r['session'].update(cancel_failed_closed=False))
    change('R20_actual_neon_claim', lambda r: r.update(mode='LIVE_NEON_PASS'))
    change('R21_extra_query', lambda r: r['actions'].update(sql_statement_executions=999))
    change('R22_wrong_manifest_hash', lambda r: r.update(manifest_sha256='0'*64))
    change('R23_catalog_budget_drift', lambda r: r['actions'].update(catalog_select_executions=99))
    return cases


def execute_checks(doc):
    validate_manifest(doc)
    if not validate_synthetic_receipt(doc, synthetic_receipt(doc)):
        raise RuntimeError('synthetic positive failed')
    negatives = []
    for name, candidate, _ in negative_cases(doc):
        try:
            validate_manifest(candidate)
        except ValueError:
            negatives.append({'case':name, 'expected':'REJECT', 'observed':'REJECT'})
        else:
            raise AssertionError('negative unexpectedly passed: '+name)
    for name, receipt in receipt_negative_cases(doc):
        try:
            validate_synthetic_receipt(doc, receipt)
        except ValueError:
            negatives.append({'case':name, 'expected':'REJECT', 'observed':'REJECT'})
        else:
            raise AssertionError('receipt negative unexpectedly passed: '+name)
    return {'kind':'H2_OFFLINE_INSPECTOR_NEGATIVE_CONTROL_EVIDENCE',
            'mode':'OFFLINE_STATIC_AND_SYNTHETIC_ONLY',
            'manifest_sha256': hashlib.sha256(canonical_bytes(doc)).hexdigest(),
            'positive': 'CANONICAL_MANIFEST_AND_SYNTHETIC_RECEIPT_SHAPE_PASS',
            'negative_count':len(negatives), 'negative_controls':negatives,
            'runtime_neon_queries':0, 'role_provisioning':0,
            'authorization_consumed':0, 'actual_i1_to_i7_runtime_verdict':'UNVERIFIED_NO_GO',
            'accepted_readonly_gate':'BLOCKED/NO-GO'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--emit', action='store_true', help='write offline manifest and evidence beside this script')
    p.add_argument('--verify', action='store_true', help='verify existing manifest, synthetic receipt and negatives')
    a=p.parse_args()
    directory=pathlib.Path(__file__).resolve().parent
    mf=directory/'H2_READONLY_QUERY_MANIFEST.json'
    ev=directory/'H2_INSPECTOR_NEGATIVE_CONTROLS.json'
    if a.emit:
        doc=canonical_manifest()
        mf.write_text(json.dumps(doc,indent=2,ensure_ascii=False)+'\n', encoding='utf-8')
        ev.write_text(json.dumps(execute_checks(doc),indent=2)+'\n',encoding='utf-8')
        print('CREATED canonical offline proposal; no Neon access')
    if a.verify:
        doc=json.loads(mf.read_text(encoding='utf-8'))
        validate_manifest(doc)
        results=execute_checks(doc)
        recorded=json.loads(ev.read_text(encoding='utf-8'))
        if recorded!=results:
            raise RuntimeError('evidence does not match independently computed expected negative outcomes')
        print('PASS OFFLINE: '+str(len(doc['queries']))+' literal catalog queries; '
              +str(results['negative_count'])+'/'+str(results['negative_count'])
              +' mutated cases rejected; synthetic receipt only; Neon NO-GO')
        print('MANIFEST_SHA256 '+results['manifest_sha256'])
    if not a.emit and not a.verify:
        p.print_help()


if __name__ == '__main__':
    main()
