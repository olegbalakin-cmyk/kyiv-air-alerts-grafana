#!/usr/bin/env python3
"""Extract immutable existing snapshots; no HTTP/source collection; run offline reviewer.
Requires the three Git commits below already present in the local repository.
"""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SCRIPTS = ROOT / 'kyiv-air-alerts-grafana/scripts'
sys.path.insert(0, str(SCRIPTS))
from casualty_auto_review import fingerprint, run_offline

DIAG = '388c7d48ced2c593e0e5cad016f6654f65afc9d6'
WIP = 'fb7ba0b8997cb14dc3f7fb77f4101a611d3a955a'
PROD = '1157c81ba5a5395636d3b4719d7bdf47ea9a86f5'
P = 'kyiv-air-alerts-grafana/data/casualties/'


def blob(ref, path):
    return subprocess.check_output(['git', 'show', f'{ref}:{path}'], cwd=ROOT, env={**os.environ, 'GIT_NO_LAZY_FETCH': '1'})


def main():
    import tempfile
    with tempfile.TemporaryDirectory(prefix='casualty-offline-') as temp:
        temp = Path(temp)
        queue_bytes = blob(WIP, P + 'multicity_review_queue.json')
        queue = json.loads(queue_bytes)
        revisions = blob(PROD, P + 'revisions.csv')
        cases_bytes = blob(DIAG, 'research/casualty_root_cause_2026_11_10/cases.json')
        cases = json.loads(cases_bytes)
        by = {x['candidate_id']: x for x in queue}
        # Reuse the completed diagnostic's case membership and facts. This is a
        # one-time evidence adapter, NOT automated extraction from article bodies.
        slots = {
            'DN-1103': ('residential-buildings', 'morning', 'missile'),
            'OD-1107': ('infrastructure', 'evening-repeat', 'drone'),
            'OD-1109': ('food-warehouse', 'morning', 'jet-drone'),
            'ZP-1103': ('infrastructure-object', 'reported-2026-11-04', 'drone'),
            'DN-1108': ('private-house-boundary-unresolved', 'reported-2026-11-08', 'air-attack'),
            'KY-LATE': ('obolon', 'attack-2026-10-10', 'air-attack'),
        }
        reports = []
        for case in cases:
            place, slot, weapon = slots[case['id']]
            # Strict primary-control status is not explicit proof of civilian
            # status. Do not turn a research sample label into an eligibility gate.
            facts = {'city_boundary': None if case['id'] == 'DN-1108' else True,
                     'russian_air_attack': True, 'civilian': None,
                     'attack_date': True, 'incident_identity': True, 'death_count': True}
            sources = [{'url': case['source_url'], 'origin_id': case['id'] + ':underlying-official-report',
                        'basis': case['death_confirmation'] + ' ' + case['geography'],
                        'supports': [k for k,v in facts.items() if v is True]}]
            if case.get('additional_source_url'):
                # Unless the diagnostic proves independence, treat both media
                # as ONE underlying source, even though the domains differ.
                sources.append({**sources[0], 'url': case['additional_source_url']})
            if case.get('official_link'):
                sources.append({**sources[0], 'url': case['official_link']})
            reports.append({'case_id': case['id'], 'candidate_ids': case['candidate_ids'],
                            'candidate_fingerprints': {cid: fingerprint(by[cid]) for cid in case['candidate_ids']},
                            'incident': {'city_key': case['city_key'], 'attack_date': case['attack_date'],
                                         'place': place, 'attack_slot': slot, 'attack_type': weapon},
                            'facts': facts,
                            'count': {'kind': 'increment' if case['id'] == 'KY-LATE' else 'total',
                                      'value': case['deaths']},
                            'observed_at': case['report_date'], 'sources': sources,
                            'provenance': {'kind': 'prior_diagnostic_fact_summary', 'commit': DIAG,
                                           'path': 'research/casualty_root_cause_2026_11_10/cases.json',
                                           'case_id': case['id']}})
        # The one genuinely pre-existing, explicit human confirmation is already
        # in the ledger. Verify its structure using the original review validator.
        from review_casualty_candidates import _validated_confirmed_disposition
        for candidate in queue:
            if candidate['status'] != 'confirmed':
                continue
            d = _validated_confirmed_disposition(candidate)
            facts = dict.fromkeys(['city_boundary', 'russian_air_attack', 'civilian',
                                   'attack_date', 'incident_identity', 'death_count'], True)
            reports.append({'case_id': 'EXISTING-SUMY', 'candidate_ids': [candidate['candidate_id']],
                'candidate_fingerprints': {candidate['candidate_id']: fingerprint(candidate)},
                'incident': {'city_key': d['city_key'], 'attack_date': d['attack_date'],
                             'place': 'zarichnyi-apartment-entrance', 'attack_slot': 'fpv-double-strike',
                             'attack_type': 'fpv-drone'},
                'facts': facts, 'count': {'kind': 'total', 'value': d['deaths_delta']},
                'observed_at': d['reviewed_at'][:10],
                'sources': [{'url': d['source_url'], 'origin_id': 'national-police:sumy:2026-09-20',
                             'contract': 'existing-human-confirmed-police-v1',
                             'supports': list(facts), 'basis': d['note']}],
                'provenance': {'kind': 'existing_confirmed_disposition', 'commit': WIP,
                               'record_id': d['record_id']}})
        # Explicit baseline end dates, from the pinned validated manifests / Kyiv
        # partial month, never inferred from the absence of a future monthly row.
        manifest = json.loads(blob(PROD, P + 'master_20cities_manifest.json'))
        baseline = {c['slug']: {'through': manifest['imported_at'], 'commit': PROD,
                              'path': P + 'master_20cities_manifest.json'} for c in manifest['cities']}
        baseline['kyiv'] = {'through': '2026-09-15', 'commit': PROD, 'path': P + 'baseline_monthly.csv'}
        for city in ('odesa', 'zaporizhzhia', 'kherson'):
            m = json.loads(blob(PROD, P + f'cities/{city}/manifest.json'))
            baseline[city] = {'through': m['validated_through'], 'commit': PROD,
                              'path': P + f'cities/{city}/manifest.json'}
        for name, data in [('queue.json',queue_bytes), ('revisions.csv',revisions)]:
            (temp / name).write_bytes(data)
        evidence = {'schema_version': 1, 'reports': reports}
        (temp / 'evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
        (temp / 'baseline.json').write_text(json.dumps(baseline,ensure_ascii=False,indent=2)+'\n')
        # Retain small evidence inputs so the factual limits are inspectable.
        (HERE / 'cached_evidence.json').write_bytes((temp / 'evidence.json').read_bytes())
        (HERE / 'baseline_coverage.json').write_bytes((temp / 'baseline.json').read_bytes())
        summary = run_offline(temp/'queue.json', temp/'revisions.csv', temp/'evidence.json',
                              temp/'baseline.json', HERE/'results')
        # Make the run manifest reproducible across temporary directories.
        mp = HERE/'results/manifest.json'
        m = json.loads(mp.read_text())
        m['input_sha256'] = {Path(k).name:v for k,v in m['input_sha256'].items()}
        m['immutable_inputs'] = {'queue_commit': WIP, 'revisions_commit': PROD, 'diagnostic_commit': DIAG,
                                'queue_git_blob': subprocess.check_output(['git','rev-parse',f'{WIP}:{P}multicity_review_queue.json'],cwd=ROOT,text=True).strip()}
        mp.write_text(json.dumps(m,indent=2)+'\n')
        replay = run_offline(temp/'queue.json',temp/'revisions.csv',temp/'evidence.json',
                             temp/'baseline.json',temp/'replay', HERE/'results/proposals.csv')
        assert replay['unique_proposals'] == 0
        assert summary['messages_processed'] == 1654
        (HERE/'results/replay.json').write_text(json.dumps(replay,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__ == '__main__':
    main()
