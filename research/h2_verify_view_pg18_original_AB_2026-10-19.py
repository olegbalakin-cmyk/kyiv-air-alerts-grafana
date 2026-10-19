#!/usr/bin/env python3
"""Git-only original H2 PG18 A/B report verifier. No external access."""
import base64, copy, hashlib, json, lzma, pathlib, zlib

HERE=pathlib.Path(__file__).resolve().parent
MANIFEST="h2_neon_view_pg18_original_AB_manifest_2026-10-19.json"
ARCHIVE="h2_neon_view_pg18_original_AB_reports_2026-10-19.json.xz.b64"
sha=lambda x: hashlib.sha256(x).hexdigest()
canonical=lambda x: json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()

def verify(m,b):
    s=m['source'];a=m['archive']
    assert s['workflow_run_id']==39241969351
    assert s['tested_commit']=='2735b0b50960b12178ef82337f11942d90bc994a'
    assert s['postgres_version'].startswith('18.6')
    assert sha(b)==a['sha256'] and len(b)==a['bytes'] and b.endswith(b'\n')
    x=base64.b64decode(b[:-1],validate=True)
    assert base64.b64encode(x)+b'\n'==b
    assert len(x)==a['compressed_bytes'] and sha(x)==a['compressed_sha256']
    d=lzma.LZMADecompressor(format=lzma.FORMAT_XZ)
    raw=d.decompress(x)
    assert d.eof and not d.unused_data and len(raw)==a['decompressed_map_bytes']
    assert sha(raw)==a['decompressed_map_sha256']
    data=json.loads(raw)
    assert data['format']==a['map_format']=='h2_pg18_view_AB_raw_map_v1'
    assert canonical(data)==raw
    items=data['files']; records=m['original_members']
    assert len(records)==4 and len(items)==4
    assert set(items)=={r['archive_path'] for r in records}
    proven={}
    for rec in records:
        c=rec['source_copy'];name=rec['original_zip_name'];path=rec['archive_path']
        assert path==c+'/'+name and c in ('A','B')
        body=base64.b64decode(items[path],validate=True)
        assert base64.b64encode(body).decode()==items[path]
        assert len(body)==rec['byte_size'] and sha(body)==rec['sha256']
        if rec.get('crc32') is not None:
            assert f"{zlib.crc32(body):08x}"==rec['crc32']
        obj=json.loads(body)
        assert obj['copy']==c
        if rec['kind']=='report':
            assert name==f'h2_neon_checkpoint_view_pg18_{c}.json'
            assert obj['verdict']=='PASS_PG18_OFFLINE_TARGETED'
            assert len(obj['checks'])==34 and all(v=='PASS' for v in obj['checks'].values())
            assert obj['postgres_version'].startswith('18.6')
            assert obj['pinned_phase1_blob']==m['source_git_blobs']['pinned_phase1_source']
            assert obj['matrix_counts']=={'MATCH':203,'MISMATCH':3,'UNVERIFIED':7}
            assert obj['schema']['tables']==7 and obj['schema']['table_columns']==167
            assert obj['schema']['constraints']==221 and obj['schema']['indexes']==30
            assert obj['schema']['views']==1 and obj['schema']['view_columns']==18
            assert obj['neon_connections']==obj['neon_writes']==obj['production_writes']==0
            proven[c]=sha(body)
        else:
            assert rec['kind']=='provenance' and name=='h2_neon_job_provenance.json'
            assert obj['tested_commit']==s['tested_commit'] and obj['run_id']==str(s['workflow_run_id'])
            assert obj['test_blob']==m['source_git_blobs']['test_script']
            assert obj['fixture_blob']==m['source_git_blobs']['original_fixture']
            assert obj['view_supplement_blob']==m['source_git_blobs']['checkpoint_view_supplement']
            assert obj['source_phase1_blob']==m['source_git_blobs']['pinned_phase1_source']
            assert obj['neon_connections']==obj['production_modifications']==0
            proven[c+'_provenance']=obj['report_sha256']
    assert proven['A']==proven['A_provenance'] and proven['B']==proven['B_provenance']
    assert set(proven)=={'A','B','A_provenance','B_provenance'}
    for c in ('A','B'):
        job=m['jobs'][c]
        assert job['conclusion']=='success' and job['zip_crc_pass'] is True
        assert job['artifact_id']=={'A':12180769759,'B':12181577406}[c]
        assert job['job_id']=={'A':118024700635,'B':118024700964}[c]
    return data

def reject(label,m,b):
    try:
        verify(m,b)
    except (AssertionError,ValueError,KeyError,TypeError,EOFError,lzma.LZMAError):
        print('NEGATIVE_REJECTED',label);return
    raise RuntimeError('CORRUPTION_ACCEPTED '+label)

def run():
    m=json.loads((HERE/MANIFEST).read_bytes());b=(HERE/ARCHIVE).read_bytes()
    data=verify(m,b)
    print('POSITIVE_PASS 4/4 members; A 34/34; B 34/34')
    reject('corrupted_archive',m,b'Z'+b[1:])
    bad=copy.deepcopy(m);bad['original_members'][0]['sha256']='0'*64
    reject('modified_member_hash',bad,b)
    bad=copy.deepcopy(m);bad['archive']['decompressed_map_sha256']='0'*64
    reject('modified_map_hash',bad,b)
    bad=copy.deepcopy(m);bad['original_members'][0]['archive_path']='B/h2_neon_checkpoint_view_pg18_A.json'
    reject('incorrect_AB_member_identity',bad,b)
    # Corrupted provenance with recalculated inner hashes and all outer layers.
    changed=copy.deepcopy(data);path='A/h2_neon_job_provenance.json'
    original=json.loads(base64.b64decode(changed['files'][path]))
    original['copy']='B'
    payload=canonical(original);changed['files'][path]=base64.b64encode(payload).decode()
    bad=copy.deepcopy(m)
    r=next(x for x in bad['original_members'] if x['archive_path']==path)
    r['byte_size']=len(payload);r['sha256']=sha(payload)
    raw=canonical(changed);packed=lzma.compress(raw,format=lzma.FORMAT_XZ,preset=9,check=lzma.CHECK_CRC64)
    new=base64.b64encode(packed)+b'\n'
    a=bad['archive'];a.update(bytes=len(new),sha256=sha(new),compressed_bytes=len(packed),compressed_sha256=sha(packed),decompressed_map_bytes=len(raw),decompressed_map_sha256=sha(raw))
    reject('forged_provenance_even_when_rehashed',bad,new)
    print('RESULT PASS_GIT_ONLY: 4/4 original JSON, 34/34 A+B, 5/5 negatives')

if __name__=='__main__':
    run()
