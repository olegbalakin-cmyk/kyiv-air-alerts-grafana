#!/usr/bin/env python3
"""Independent, no-network verification of ORIGINAL 2026-10-21 H2 A/B ZIPs.

Does not import producer/freezer; pins external source run, ZIP byte digests,
A/B job and artifact identities and exact enclosed JSON SHA-256 independently.
Also checks executed Git source bytes equal frozen source on this research head.
"""
import copy, hashlib, io, json, pathlib, subprocess, zipfile

DIR=pathlib.Path(__file__).resolve().parent
ROOT=DIR.parents[1]
BUNDLE=DIR/"original_ab"
RUN=39499796916
TESTED="780348a2a5a2ae294871bf10bf60c5e394f4afb6"
PINS={
 "A":{"job_id":118894090566,"job_name":"pg18 (A)","artifact_id":12298879609,
    "artifact_name":"h2-integrated-h11-r09-A","size":4774,
    "sha":"7ca5ccaf557f738261f141b1d0ff7a4f55e89ecfa7a545aefb891cc9820686de",
    "members":{
      "h2_integrated_preflight_A.json":("5d1d6dd5ba6ac5ea34e137290e9c82db4cf062be7990d9c31a9f23e5ef42ffa3","PASS_BOUNDED",20),
      "h2_integrated_007_A.json":("5873c8165d4e4ecb170ec7e6765291dc7f4057490c5f5b220d7f0989d0855758","PASS",144)}},
 "B":{"job_id":118894090309,"job_name":"pg18 (B)","artifact_id":12299242947,
    "artifact_name":"h2-integrated-h11-r09-B","size":4778,
    "sha":"4507eb69b6524aae9412fbbe4f0115c521f0e6476726d1422da8e95fd4349c28",
    "members":{
      "h2_integrated_preflight_B.json":("5565775159c05c3592c5cb008019313cc6399b909992f26cf14a41ca3f32dd79","PASS_BOUNDED",20),
      "h2_integrated_007_B.json":("ca44488292d30feb9c6742d6686d2ae9bce666c2487f780926d7d49b56766778","PASS",144)}}
}
EXECUTED=[
"research/h2_integrated_preflight_2026-10-21/build_gate.py",
"research/h2_integrated_preflight_2026-10-21/test_gate.py",
".github/workflows/h2-integrated-h11-r09-2026-10-21.yml",
"research/h2_security_closure_2026-10-20/h11_head_history_check.sql",
"research/h2_security_closure_2026-10-20/r09_effective_role_preflight.sql",
"research/h2_non_superuser_guard_acl_2026-10-20/007_non_superuser_guard_transfer.sql",
"research/h2_full_cas_007_2026-10-20/test_integrated_007_cas.py"]
def sha(data):return hashlib.sha256(data).hexdigest()
def git(*args):
    x=subprocess.run(["git",*args],cwd=ROOT,check=True,capture_output=True)
    return x.stdout
def verify(m,blobs):
    assert m["run_id"]==RUN and m["tested_sha"]==TESTED
    assert m["repository"]=="olegbalakin-cmyk/kyiv-air-alerts-grafana"
    assert set(m["originals"])==set(PINS)
    for copy,pin in PINS.items():
        entry=m["originals"][copy]
        assert entry["job_id"]==pin["job_id"]
        assert entry["job_name"]==pin["job_name"]
        assert entry["artifact_id"]==pin["artifact_id"]
        assert entry["artifact_name"]==pin["artifact_name"]
        assert entry["size_in_bytes"]==pin["size"]
        assert entry["sha256"]==pin["sha"]
        assert entry["sha_from_actions_metadata"]=="sha256:"+pin["sha"]
        zbytes=blobs[copy]
        assert len(zbytes)==pin["size"] and sha(zbytes)==pin["sha"]
        with zipfile.ZipFile(io.BytesIO(zbytes)) as z:
            assert z.testzip() is None
            actual={item.filename:item for item in z.infolist() if not item.is_dir()}
            assert set(actual)==set(pin["members"])
            manifest_members={x["name"]:x for x in entry["members"]}
            assert set(manifest_members)==set(actual)
            for fname,(want_sha,want_verdict,want_count) in pin["members"].items():
                info=actual[fname]
                raw=z.read(info)
                data=json.loads(raw)
                x=manifest_members[fname]
                assert data["copy"]==copy
                assert data["verdict"]==want_verdict
                assert data["passed"]==want_count and data["total"]==want_count
                assert len(raw)==x["uncompressed_bytes"]
                assert info.CRC==x["crc32"]
                assert sha(raw)==want_sha==x["sha256"]
                if "preflight" in fname:
                    assert len(data["cases"])==20
                    assert all(y["status"]=="PASS" for y in data["cases"])
                    assert data["tested_commit"]==TESTED
                else:
                    assert not data.get("errors")
                    assert data["verdict"]=="PASS"
    return True

def main():
    manifest=json.loads((BUNDLE/"manifest.json").read_bytes())
    blobs={copy:(BUNDLE/(copy+".zip")).read_bytes() for copy in PINS}
    assert verify(manifest,blobs)
    source={}
    for path in EXECUTED:
        tested=git("show",TESTED+":"+path)
        current=git("show","HEAD:"+path)
        assert tested==current,("EXECUTED_SOURCE_CHANGED",path)
        source[path]=sha(tested)
    # The source references embedded in the gate generator MUST remain pinned.
    negative=[]
    def reject(label,mutate):
        m=copy.deepcopy(manifest);data=dict(blobs)
        mutate(m,data)
        try: verify(m,data)
        except (AssertionError,ValueError,KeyError,zipfile.BadZipFile,UnicodeDecodeError,json.JSONDecodeError):
            negative.append(label);return
        raise AssertionError("NEGATIVE_NOT_REJECTED:"+label)
    reject("wrong_job",lambda m,z:m["originals"]["A"].__setitem__("job_id",PINS["B"]["job_id"]))
    reject("wrong_copy",lambda m,z:m["originals"]["B"].__setitem__("job_name","pg18 (A)"))
    reject("wrong_artifact",lambda m,z:m["originals"]["A"].__setitem__("artifact_id",PINS["B"]["artifact_id"]))
    reject("wrong_source_sha",lambda m,z:m.__setitem__("tested_sha","0"*40))
    reject("wrong_zip_hash",lambda m,z:m["originals"]["B"].__setitem__("sha256","0"*64))
    reject("wrong_manifest_json_hash",lambda m,z:m["originals"]["A"]["members"][0].__setitem__("sha256","0"*64))
    reject("wrong_verdict",lambda m,z:m["originals"]["B"]["members"][1].__setitem__("verdict","FAIL"))
    reject("wrong_size",lambda m,z:m["originals"]["B"].__setitem__("size_in_bytes",0))
    reject("zip_bitflip",lambda m,z:z.__setitem__("A",z["A"][:-1]+bytes([z["A"][-1]^1])))
    def json_edit(m,z):
        with zipfile.ZipFile(io.BytesIO(z["B"])) as zi:
            files={item.filename:zi.read(item) for item in zi.infolist()}
        target="h2_integrated_preflight_B.json"
        obj=json.loads(files[target])
        obj["verdict"]="FAIL"
        files[target]=json.dumps(obj).encode()
        buff=io.BytesIO()
        with zipfile.ZipFile(buff,"w",compression=zipfile.ZIP_DEFLATED) as w:
            for name,payload in files.items(): w.writestr(name,payload)
        z["B"]=buff.getvalue()
    reject("repacked_json",json_edit)
    assert len(negative)==10
    print(json.dumps({"verdict":"PASS_GIT_ONLY_ORIGINAL","source_to_execution":"PASS",
     "runs":1,"original_zip":2,"enclosed_json":4,
     "negatives":len(negative),"negative_names":negative,"tested_sha":TESTED,
     "current_head":git("rev-parse","HEAD").decode().strip(),
     "source_sha256":source},sort_keys=True))
if __name__=="__main__":main()
