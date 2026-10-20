#!/usr/bin/env python3
"""Freeze the EXACT original GitHub Actions A/B ZIPs for accepted bounded PG18 experiment.

Research-branch-only, offline DB-wise. Accesses GitHub Actions artifact bytes
with ephemeral built-in GITHUB_TOKEN, never any Neon/production/secret service.
Does not create / replace ZIP envelopes, only downloads byte-exact originals.
"""
import hashlib, io, json, os, pathlib, urllib.request, zipfile
from datetime import datetime, timezone

OWNER_REPO="olegbalakin-cmyk/kyiv-air-alerts-grafana"
RUN_ID=39499796916
TESTED_SHA="780348a2a5a2ae294871bf10bf60c5e394f4afb6"
JOBS={"A":118894090566,"B":118894090309}
ORIGINALS={
 "A":{"id":12298879609,"name":"h2-integrated-h11-r09-A","bytes":4774,
      "sha256":"7ca5ccaf557f738261f141b1d0ff7a4f55e89ecfa7a545aefb891cc9820686de"},
 "B":{"id":12299242947,"name":"h2-integrated-h11-r09-B","bytes":4778,
      "sha256":"4507eb69b6524aae9412fbbe4f0115c521f0e6476726d1422da8e95fd4349c28"},
}
DEST=pathlib.Path(__file__).resolve().parent/"original_ab"
def sha(data): return hashlib.sha256(data).hexdigest()
def request(url):
    token=os.environ.get("GITHUB_TOKEN")
    if not token:raise RuntimeError("GITHUB_TOKEN_REQUIRED")
    headers={"Authorization":"Bearer "+token,"Accept":"application/vnd.github+json",
             "X-GitHub-Api-Version":"2022-11-28","User-Agent":"h2-offline-evidence-freeze"}
    with urllib.request.urlopen(urllib.request.Request(url,headers=headers),timeout=60) as r:
        return r.read()
def api(path):
    return json.loads(request("https://api.github.com/repos/"+OWNER_REPO+"/"+path))
def main():
    run=api("actions/runs/"+str(RUN_ID))
    assert run["head_sha"]==TESTED_SHA and run["conclusion"]=="success",run["head_sha"]
    jobs=api("actions/runs/"+str(RUN_ID)+"/jobs?per_page=100")["jobs"]
    artifacts=api("actions/runs/"+str(RUN_ID)+"/artifacts?per_page=100")["artifacts"]
    assert len(jobs)>=2 and len(artifacts)>=2
    by_job={j["id"]:j for j in jobs}
    by_artifact={a["id"]:a for a in artifacts}
    DEST.mkdir(parents=True,exist_ok=True)
    manifest={"schema":"h2-integrated-h11-r09-original-actions-zip-freeze-v1",
         "repository":OWNER_REPO,"run_id":RUN_ID,"tested_sha":TESTED_SHA,
         "created_utc":datetime.now(timezone.utc).isoformat(),
         "originals":{}}
    for copy,known in ORIGINALS.items():
        job=by_job[JOBS[copy]]
        assert job["conclusion"]=="success" and ("("+copy+")" in job["name"]),job
        meta=by_artifact[known["id"]]
        assert meta["name"]==known["name"] and meta["expired"] is False
        assert meta["size_in_bytes"]==known["bytes"] and meta["digest"]=="sha256:"+known["sha256"],meta
        data=request("https://api.github.com/repos/"+OWNER_REPO+"/actions/artifacts/"+str(known["id"])+"/zip")
        assert len(data)==known["bytes"] and sha(data)==known["sha256"],copy
        members=[]
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            assert z.testzip() is None
            for info in z.infolist():
                if info.is_dir():continue
                assert info.filename.endswith(".json") and ".." not in info.filename
                raw=z.read(info)
                obj=json.loads(raw)
                assert obj.get("copy")==copy,info.filename
                # Preserve failures faithfully; success of the run alone is not a substitute
                # for report-level checks on both integrated and old CAS.
                if "integrated_preflight" in info.filename:
                    assert obj["verdict"]=="PASS_BOUNDED" and obj["passed"]==20 and obj["total"]==20
                elif "integrated_007" in info.filename:
                    assert obj["verdict"]=="PASS" and obj["passed"]==144 and obj["total"]==144
                else:
                    raise AssertionError("UNKNOWN_REPORT: "+info.filename)
                members.append({"name":info.filename,"uncompressed_bytes":len(raw),
                                "crc32":info.CRC,"sha256":sha(raw),"verdict":obj["verdict"],
                                "passed":obj["passed"],"total":obj["total"]})
        assert len(members)==2,(copy,members)
        (DEST/(copy+".zip")).write_bytes(data)
        manifest["originals"][copy]={
           "job_id":job["id"],"job_name":job["name"],
           "artifact_id":meta["id"],"artifact_name":meta["name"],
           "size_in_bytes":len(data),"sha256":sha(data),
           "sha_from_actions_metadata":meta["digest"],
           "members":sorted(members,key=lambda a:a["name"])}
    (DEST/"manifest.json").write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"result":"PASS_EXACT_ORIGINAL_ZIPS","run":RUN_ID,
                      "tested_sha":TESTED_SHA,"copies":list(ORIGINALS),
                      "artifact_sha256":{x:v["sha256"] for x,v in manifest["originals"].items()}}))
if __name__=="__main__":main()
