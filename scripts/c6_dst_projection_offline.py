"""Apply the new correction to retained physical projection artifacts, offline.

This is a calculation-layer check, not another physical JSON/readback proof.
The saved projection is the input; no physical snapshot is reconstructed.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import io
import json
from pathlib import Path
import shutil
import socket
import tempfile
from types import SimpleNamespace
from unittest.mock import patch
import zipfile

from scripts import c6_dst_projection as dst
from scripts import neon_json_shadow_generator as gen

ARTIFACT = dst.RESEARCH / 'evidence/physical-proof-13619973574.zip'
ARTIFACT_SHA = 'b0aa64392cb2b682eae14faf15df5df45da3fc208d8c45323dffab63b3d4245e'
MANIFEST_SHA = '588700a49a5af6d19df2784ce6ded8e143db9128661b2be30f6886dff6fb97f7'
FILES = ('dashboard_data.json', 'site_derived.json', 'historical-daily-kpi.json',
         'alerts_combined.json', 'kyiv_threat_mix.json', 'sevastopol_events.json')


def retained(artifact=ARTIFACT):
    raw = Path(artifact).read_bytes()
    dst.require(hashlib.sha256(raw).hexdigest() == ARTIFACT_SHA, 'PHYSICAL_ARTIFACT_DRIFT')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        manifest_raw = archive.read('sha256_manifest.json')
        dst.require(hashlib.sha256(manifest_raw).hexdigest() == MANIFEST_SHA, 'PHYSICAL_MANIFEST_DRIFT')
        hashes = json.loads(manifest_raw)['files']
        dst.require(len(hashes) == 14 and set(archive.namelist()) == {*hashes, 'sha256_manifest.json'},
                    'PHYSICAL_ARTIFACT_SCHEMA')
        data = {name: archive.read(name) for name in hashes}
        dst.require(all(hashlib.sha256(data[n]).hexdigest() == h for n, h in hashes.items()),
                    'PHYSICAL_MEMBER_DRIFT')
    return data


def calculate(site, work, data):
    """Exercise the same correction, city builders and analytics phase as generate()."""
    base = json.loads(data['candidate/dashboard_data.json'])
    old_derived = json.loads(data['candidate/site_derived.json'])
    lineage = json.loads(data['projection_lineage.json'])
    proof = json.loads(data['readback_proof.json'])
    binding = {k: proof[k] for k in ('counts', 'table_sha256', 'c2_corpus_sha256')}
    corrected, receipt = dst.apply(lineage, binding)
    adapter, _, _ = gen.prepare(SimpleNamespace(site=site), work)
    mods = adapter.import_site_modules(site)
    update = mods['update_data']
    keys = base['multicity_meta']['production_city_keys']
    alerts = {key: [update.Alert(start=dst.utc(r['start_utc']).astimezone(update.TZ),
                                end=dst.utc(r['end_utc']).astimezone(update.TZ),
                                source='neon_canonical_utc_union')
                    for r in sorted(lineage, key=dst.token) if r['city_key'] == key]
              for key in keys}
    # Preserve Kyiv's original display ordering and source labels exactly.
    alerts['kyiv'] = update.parse_committed_alerts(json.loads(data['candidate/alerts_combined.json']))
    payload = copy.deepcopy(base)
    now = dst.utc(proof['meta']['read_at'])
    dst.rebuild_affected(payload, alerts, corrected, adapter, mods, now)
    derived = gen.refresh_analytics(payload, base, copy.deepcopy(old_derived), alerts, now, site, mods)
    for key in dst.AFFECTED:
        for field in ('generated_at', 'source_captured_at_utc', 'current_source_verified'):
            payload['cities'][key]['meta'][field] = base['cities'][key]['meta'][field]
    # Historical/build clocks retain the saved snapshot's clocks. This layer
    # does not make a stale input current or assert a new physical readback.
    payload['historical_daily_kpi']['meta'] = copy.deepcopy(base['historical_daily_kpi']['meta'])
    authority = payload['meta']['publication_authority']
    authority['historical_dst_projection'] = receipt
    derived['meta']['publication_authority'] = copy.deepcopy(authority)
    payload['historical_daily_kpi']['meta']['historical_dst_projection'] = {
        'version': dst.VERSION, 'receipt_sha256': dst.fingerprint(receipt),
        'physical_neon_observation': False, 'publication_allowed': False}
    dst.require(len(alerts['kyiv']) == 2819, 'KYIV_COUNT_CHANGED')
    dst.require(all(payload['cities'][k] == base['cities'][k] for k in keys if k not in dst.AFFECTED),
                'UNRELATED_CITY_ANALYTICS_CHANGED')
    dst.require(all(payload.get(k) == base.get(k) for k in ('casualties', 'casualties_by_city')),
                'CASUALTY_CHANGED')
    return payload, derived, corrected, receipt


def run(site, output, *, correction=None, artifact=ARTIFACT):
    dst.require(correction in (None, dst.VERSION), 'UNKNOWN_VERSION')
    site, output = Path(site).resolve(), Path(output).absolute()
    dst.require(not output.exists(), 'OUTPUT_EXISTS')
    dst.require(not output.is_relative_to(site), 'OUTPUT_INSIDE_SOURCE')
    data = retained(artifact)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='dst-projection-', dir=output.parent) as temp:
        temp = Path(temp); build = temp / 'result'; build.mkdir()
        candidate = build / 'candidate'; candidate.mkdir()
        for name in FILES:
            (candidate / name).write_bytes(data['candidate/' + name])
        receipt = None
        # Block networking throughout the calculation, including imported builders.
        with (patch.object(socket.socket, 'connect', side_effect=AssertionError('NO_NETWORK')),
              patch.object(socket, 'create_connection', side_effect=AssertionError('NO_NETWORK'))):
            if correction is not None:
                payload, derived, lineage, receipt = calculate(site, temp, data)
                for name, value in (('dashboard_data.json', payload), ('site_derived.json', derived),
                                    ('historical-daily-kpi.json', payload['historical_daily_kpi'])):
                    gen.save(candidate / name, value)
                gen.save(build / 'projection_lineage.json', lineage)
                gen.save(build / 'dst_correction.json', receipt)
            else:
                (build / 'projection_lineage.json').write_bytes(data['projection_lineage.json'])
        result = {'version': correction, 'publication_allowed': False, 'global_cutover': 'NO',
                  'physical_proof_rerun': False, 'new_sql': 0, 'new_source_http': 0,
                  'input_artifact_id': 13619973574, 'input_artifact_sha256': ARTIFACT_SHA,
                  'candidate_sha256': {n: gen.sha((candidate / n).read_bytes()) for n in FILES}}
        gen.save(build / 'offline_result.json', result)
        shutil.move(str(build), str(output))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--dst-correction', choices=[dst.VERSION], default=None)
    args = parser.parse_args()
    print(json.dumps(run(args.site, args.output, correction=args.dst_correction), sort_keys=True))


if __name__ == '__main__':
    main()
