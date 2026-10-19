#!/usr/bin/env python3
"""Git-only exact-byte verifier for preserved E1-E15 PG18 A/B JSON reports."""
import base64
import hashlib
import json
import lzma
from pathlib import Path

BASE=Path(__file__).resolve().parent
MANIFEST=BASE/'h2_observed_neon_partial_pg18_AB_retention_manifest_2026-10-19.json'
ARCHIVE=BASE/'h2_observed_neon_partial_pg18_AB_reports_2026-10-19.json.xz.b64'

def digest(b):
    return hashlib.sha256(b).hexdigest()

def verify(archive_text, manifest):
    raw=archive_text.encode('ascii')
    assert len(raw)==manifest['archive_text_bytes']
    assert digest(raw)==manifest['archive_text_sha256']
    compressed=base64.b64decode(raw,validate=False)
    assert len(compressed)==manifest['xz_bytes']
    assert digest(compressed)==manifest['xz_sha256']
    assert compressed[:6]==b'\xfd7zXZ\x00'
    map_raw=lzma.decompress(compressed)
    assert len(map_raw)==manifest['json_map_bytes']
    assert digest(map_raw)==manifest['json_map_sha256']
    members=json.loads(map_raw)
    assert set(members)==set(manifest['member_sha256'])
    for name,meta in manifest['member_sha256'].items():
        data=base64.b64decode(members[name],validate=True)
        assert len(data)==meta['bytes'] and digest(data)==meta['sha256'],name
        parsed=json.loads(data)
        assert parsed['verdict']==meta['verdict'],name
        if name.endswith('h2_observed_result.json'):
            assert all(parsed['cases']['E'+str(i)]['status']=='PASS' for i in range(1,16))
    return {name:meta['sha256'] for name,meta in manifest['member_sha256'].items()}

if __name__=='__main__':
    m=json.loads(MANIFEST.read_bytes())
    s=ARCHIVE.read_text('ascii')
    passed=verify(s,m)
    assert len(passed)==6
    for i in (0,len(s)//2,len(s)-2):
        mutated=s[:i]+('B' if s[i]!='B' else 'C')+s[i+1:]
        try: verify(mutated,m)
        except Exception: pass
        else: raise AssertionError('corruption wrongly accepted')
    print('GIT_ONLY_AB_RETENTION_VERIFIED 6/6 members; 3/3 corruption rejected')
    print(json.dumps(passed,sort_keys=True))