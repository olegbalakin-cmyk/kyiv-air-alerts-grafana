"""Inspect retained DST inputs only; never connect to Neon or source services.

Exit 2 means the required baseline is missing. This is a diagnostic, not a
rolling-corpus validator or permission to change the frozen guards.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts import c6_dst_projection as dst
from scripts import c6_dst_projection_offline as offline


def audit(older_fixture=None):
    data = offline.retained()  # Checks pinned ZIP, manifest and all 14 members.
    dst.evidence()  # Checks the four pinned evidence files and seven witnesses.
    proof = json.loads(data['readback_proof.json'])
    binding = {k: proof[k] for k in ('counts', 'table_sha256', 'c2_corpus_sha256')}
    dst.require(dst.fingerprint(binding) == dst.BINDING_SHA, 'BASELINE_BINDING_DRIFT')
    lineage = json.loads(data['projection_lineage.json'])
    dst.require(dst.fingerprint(lineage) == dst.LINEAGE_SHA, 'BASELINE_LINEAGE_DRIFT')
    tables = tuple(sorted(proof['counts']))
    # [] is recoverable without a retained row dump, because its exact pinned
    # count and digest both match. Nonempty table hashes do not reveal rows.
    recovered = {n: [] for n in tables if proof['counts'][n] == 0
                 and dst.fingerprint([]) == proof['table_sha256'][n]}
    older = None
    if older_fixture is not None:
        raw = Path(older_fixture).read_bytes()
        with zipfile.ZipFile(older_fixture) as archive:
            snap = json.loads(archive.read('neon_readback.original.json'))
        counts = {n: len(snap[n]) for n in tables}
        matches = {n: counts[n] == proof['counts'][n]
                   and dst.fingerprint(snap[n]) == proof['table_sha256'][n]
                   for n in tables}
        recovered.update({n: snap[n] for n in tables if matches[n]})
        older = {'archive_sha256': hashlib.sha256(raw).hexdigest(),
                 'counts': counts, 'exact_pinned_table_matches': matches,
                 'usable_as_complete_baseline': all(matches.values())}
    missing = [n for n in tables if n not in recovered]
    return {
        'status': 'BLOCKED',
        'reason': 'REQUIRED_RAW_BASELINE_NOT_RETAINED',
        'scope': 'retained physical artifact, pinned witnesses and optional older fixture',
        'base_commit': 'd99dc40f5b9135963f7ec876b21926813139a50b',
        'physical_run_id': 42487688608, 'physical_artifact_id': 13619973574,
        'physical_artifact_sha256': offline.ARTIFACT_SHA,
        'physical_manifest_sha256': offline.MANIFEST_SHA,
        'physical_members': sorted([*data, 'sha256_manifest.json']),
        'physical_member_hashes_verified': len(data),
        'readback_proof_keys': sorted(proof),
        'read_at': proof['meta']['read_at'],
        'snapshot_id': proof['meta']['snapshot'],
        'binding': binding,
        'binding_sha256': dst.fingerprint(binding),
        'projection_rows': len(lineage),
        'projection_row_fields': sorted({k for row in lineage for k in row}),
        'active_rows_retained': len(json.loads(data['active_rows_unmodified.json'])),
        'older_fixture': older,
        'recoverable_exact_tables': sorted(recovered),
        'missing_raw_tables': {n: proof['counts'][n] for n in missing},
        'required_input': 'Original ordered reader rows for missing tables, with all '
                          'fields/types, reproducing the pinned counts and SHA-256; '
                          'no reconstruction from calculation lineage or invented provenance.',
        'rolling_validation_implemented': False,
        'regular_new_corpus_allowed': False,
        'publication_allowed': False, 'GLOBAL_CUTOVER': 'NO',
        'new_sql': 0, 'new_source_http': 0, 'neon_writes': 0,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--older-fixture', type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.older_fixture), ensure_ascii=False, sort_keys=True, indent=2))
    raise SystemExit(2)
