"""Versioned historical calculation exception. No database, HTTP or fallback.

Only the accepted frozen corpus is eligible. Witness intervals are calculation
inputs, never invented Neon episode UUIDs or source observations.
"""
from __future__ import annotations

import copy
import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

VERSION = 'c6-dst-projection-v1'
ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / 'research/c6_dst_projection_2026_11_09'
LINEAGE_SHA = 'c7afdaa9729952d312347ac81dc80af59d928e52dfad6bc162fd5145ec2e203d'
BINDING_SHA = 'f049bf9a6c4bc58abcf9587dc00e364aa268a3bd7a23d8ec9e548dcfd4514778'
EVIDENCE = {
 'research/c6_dst_final_readonly_2026_11_08/after_grant_evidence.json': '84c9250c8a564baab63d757e8de5a9e556db80a693507ec5af7af700a3878dfe',
 'research/c6_dst_four_case_preflight_2026_10_31/fixtures/historical_correction_candidates.json': 'c365f42905b2968f1848d5bf8972c269b7a32eb524e036a483cec1d303915e8b',
 'research/neon_cutover_work_2026_10_30/proof/verification02/dst_source_witnesses.json': '6d762e8572680f4d09f67ff05b6c0c257a275c32c7c13edad5ecc95ac199cef3',
 'research/c6_dst_projection_2026_11_09/source_witnesses.json': 'ae3f5ff3d4dd300ef806203770a45a3f11ca0d66d62f76beecaeaee2abab17c5',
}
AFFECTED = {'kharkiv', 'poltava', 'zhytomyr', 'cherkasy'}


class Blocked(ValueError):
    pass


def require(ok, reason):
    if not ok:
        raise Blocked('DST_CORRECTION:' + reason)


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':'), default=str).encode()).hexdigest()


def utc(value):
    result = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    require(result.tzinfo is not None, 'NAIVE_TIME')
    return result.astimezone(timezone.utc)


def token(row):
    return row['city_key'], utc(row['start_utc']), utc(row['end_utc'])


def duration(rows):
    return sum((utc(r['end_utc']) - utc(r['start_utc'])) //
               timedelta(microseconds=1) for r in rows)


def evidence(root=ROOT):
    values = []
    for path, expected in EVIDENCE.items():
        raw = (root / path).read_bytes()
        require(hashlib.sha256(raw).hexdigest() == expected, 'EVIDENCE_DRIFT:' + path)
        values.append(json.loads(raw))
    readback, candidates, accepted, source = values
    wanted = {(v['city'], v['legacy_episode_id'], v['start_utc'], v['end_utc'])
              for v in accepted['proposed_intervals_found_exactly_in_pinned_source']}
    witnessed = {(v['event']['city_key'], v['legacy_episode_id'], v['event']['start'],
                  v['event']['end']) for v in source['witnesses']}
    proposed = {(case['city_key'], v['legacy_episode_id'], v['start_utc'], v['end_utc'])
                for case in candidates['candidate_records'] for v in case['new_candidate_utc_intervals']}
    physical_check = {(v['city_key'], v['legacy_episode_id'], v['start_utc'], v['end_utc'])
                      for v in readback['candidates']}
    require(len(wanted) == 7 and wanted == witnessed == proposed == physical_check,
            'INSUFFICIENT_OR_CONFLICTING_WITNESSES')
    require(all(v['event']['alert_type'] == 'AIR' for v in source['witnesses']), 'SOURCE_TYPE')
    require(all(v['existing_legacy_hits'] == v['existing_exact_interval_hits'] == 0
                for v in readback['candidates']), 'CANDIDATE_ALREADY_PHYSICAL')
    return readback, candidates, source


def binding_from_snapshot(snap, corpus_sha256):
    """Use actual unmodified reader rows, before calculation corrections."""
    names = ('episodes', 'observations', 'checkpoints', 'runs', 'classifications',
             'source_links', 'events')
    return {'counts': {n: len(snap[n]) for n in names},
            'table_sha256': {n: fingerprint(snap[n]) for n in names},
            'c2_corpus_sha256': corpus_sha256}


def apply(lineage, binding, *, version=VERSION, root=ROOT):
    require(version == VERSION, 'UNKNOWN_VERSION')
    readback, candidates, source = evidence(root)
    require(fingerprint(binding) == BINDING_SHA, 'INPUT_CORPUS_OR_SCHEMA_DRIFT')
    require(fingerprint(lineage) == LINEAGE_SHA, 'PROJECTION_CORPUS_OR_SCHEMA_DRIFT')
    require(all(set(r) == {'city_key', 'start_utc', 'end_utc', 'physical_uids', 'selection'}
                and utc(r['start_utc']) < utc(r['end_utc']) for r in lineage), 'LINEAGE_SCHEMA')
    wrong = {r['episode_uid']: r for r in readback['old_episode_checks']}
    protected = readback['protected_cherkasy']
    for uid, expected in [*wrong.items(), (protected['episode_uid'], protected)]:
        matches = [r for r in lineage if uid in r['physical_uids']]
        require(len(matches) == 1 and matches[0]['physical_uids'] == [uid]
                and token(matches[0]) == token(expected if uid in wrong else
                    {**expected, 'city_key': 'cherkasy'}), 'UUID_OR_BOUNDARY_DRIFT:' + uid)
    before = copy.deepcopy(lineage)
    result = [copy.deepcopy(r) for r in lineage if not set(r['physical_uids']) & set(wrong)]
    replacement = []
    for witness in source['witnesses']:
        event = witness['event']
        case = next(c for c in candidates['candidate_records'] if c['city_key'] == event['city_key'])
        old = case['existing_incorrect_physical_record']
        row = {'city_key': event['city_key'], 'start_utc': event['start'], 'end_utc': event['end'],
               'physical_uids': [], 'selection': 'ACCEPTED_SOURCE_WITNESS_CALCULATION_ONLY',
               'correction': {'version': VERSION, 'legacy_episode_id': witness['legacy_episode_id'],
                              'excluded_physical_uids': [old['episode_uid']] if old else [],
                              'physical_neon_observation': False,
                              'witness_sha256': fingerprint(witness),
                              'source_git_blob': source['source_git_blob']}}
        require(all(token(row) != token(r) for r in result), 'CANDIDATE_ALREADY_PROJECTED')
        require(all(r['city_key'] != row['city_key'] or utc(row['end_utc']) < utc(r['start_utc'])
                    or utc(r['end_utc']) < utc(row['start_utc']) for r in result),
                'CORRECTION_OVERLAPS_OR_TOUCHES_EXISTING_INTERVAL')
        result.append(row); replacement.append(row)
    result.sort(key=lambda r: token(r))
    require(len(result) - len(before) == 4 and duration(result) - duration(before) == -9059359958,
            'ARITHMETIC_MISMATCH')
    unchanged = [r for r in result if 'correction' not in r]
    expected = [r for r in before if not set(r['physical_uids']) & set(wrong)]
    require(sorted(unchanged, key=token) == sorted(expected, key=token), 'UNRELATED_CHANGE')
    require(lineage == before, 'INPUT_MUTATED')
    receipt = {'version': VERSION, 'accepted_dst_commit': '7265e40af6d012267ada515e9cac415f3e1e24b7',
               'source_witness_commit': '741f277f73d1dde1325069d25fa00b44a42d6f03',
               'readback_commit': '9ba2c04ca7cf187bacf35efa05e5c267be6dc6cb',
               'evidence_sha256': EVIDENCE, 'input_binding_sha256': fingerprint(binding),
               'input_projection_sha256': fingerprint(before),
               'output_projection_sha256': fingerprint(result),
               'excluded_physical_uids': sorted(wrong), 'replacement_intervals': replacement,
               'physical_neon_observations_created': 0, 'net_episode_delta': 4,
               'duration_delta_microseconds': -9059359958, 'other_intervals_changed': 0,
               'publication_allowed': False, 'global_cutover': 'NO'}
    return result, receipt


def rebuild_affected(payload, alerts, lineage, adapter, mods, now):
    """Reuse precisely the accepted adapter's city builders and coverage policy."""
    update, rolling = mods['update_data'], mods['apply_site_rolling_7d']
    for key in sorted(AFFECTED):
        alerts[key] = [update.Alert(start=utc(r['start_utc']).astimezone(update.TZ),
                                   end=utc(r['end_utc']).astimezone(update.TZ),
                                   source='neon_projection_with_explicit_dst_witnesses')
                       for r in sorted(lineage, key=token) if r['city_key'] == key]
        meta = adapter._safe_meta(payload['cities'][key], payload['multicity_meta'], key)
        fresh = update.build_outputs(alerts[key], now.astimezone(update.TZ), meta)
        if key in adapter.EXACT:
            mods['add_duration_unit_switch'].enrich_weekly(fresh, alerts[key])
            mods['add_duration_unit_switch'].trim_first_partial_periods(fresh, date.fromisoformat(adapter.COVERAGE[key]))
        else:
            mods['expand_multicity_production'].enrich_weekly(fresh, alerts[key])
            mods['expand_multicity_production'].trim_to_complete_coverage(fresh, date.fromisoformat(adapter.COVERAGE[key]))
        rolling.update_city_rolling(fresh, alerts[key])
        payload['cities'][key] = fresh
