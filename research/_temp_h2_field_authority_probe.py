#!/usr/bin/env python3
"""Disposable read-only H2 immutable evidence inventory (not an audit verdict)."""
import collections,hashlib,json,subprocess,sys
from pathlib import Path
def git(*args):
    return subprocess.check_output(["git",*args],stderr=subprocess.PIPE)
def ensure(sha):
    try: git("cat-file","-e",sha+"^{commit}")
    except subprocess.CalledProcessError: subprocess.check_call(["git","fetch","--no-tags","origin",sha])
def raw(ref,path):
    ensure(ref)
    return git("show",ref+":"+path)
def summary(o,limit=450):
    return json.dumps(o,ensure_ascii=False,sort_keys=True)[:limit]
def main():
    root=Path("research")
    origins=[
      ("export","03a04d33f7616b77181741fd77a776c490391d07","research/attack_event_18city_persistence_identity_export_v2_2026-10-04.json","a240f1950748afcb9fc974c49ac58da07adfff65","a8440ab537e1b675c7223b7eb7b29c817c1a2e8fc26ba5cf494b5efb3caf662a"),
      ("target","3c39dabbf78ff9415213332023e6e6c4ee7e8225","research/attack_event_18city_accepted_target_map_2026-10-04.json","4211c5899f219c4561cd139afbbf48c36b6ea86f","a8f616ffc6b63dba16feb03738f1e12e86e2c4e532a939cd4e901cb252a7f06e"),
    ]
    obj={}
    for name,commit,path,blob,sha in origins:
        ensure(commit)
        assert git("rev-parse",commit+":"+path).decode().strip()==blob
        data=raw(commit,path)
        assert hashlib.sha256(data).hexdigest()==sha, (name,len(data),hashlib.sha256(data).hexdigest())
        obj[name]=json.loads(data)
        print("PINNED",name,len(data),blob,sha,flush=True)
    exp=obj["export"]; tar=obj["target"]
    print("EXPORT_TOP_KEYS",list(exp),"TARGET_TOP_KEYS",list(tar),flush=True)
    for kind in ("classifications","source_links","attack_events","events"):
        arr=exp.get(kind,[])
        print("KIND",kind,len(arr),"SAMPLE",summary(arr[:1],1200),flush=True)
    print("WORKERS",len(tar["workers"]),flush=True)
    bycity=collections.defaultdict(list)
    for link in exp["source_links"]: bycity[link.get("origin",{}).get("path","").split("/")[-2]].append(link)
    for w in tar["workers"]:
        ensure(w["tested_head"]);ensure(w["final_head"])
        assert git("rev-parse",w["final_head"]+":"+w["proof_artifact_path"]).decode().strip()==w["proof_artifact_blob"]
        assert git("rev-parse",w["tested_head"]+":"+w["proof_workflow_path"]).decode().strip()==w["proof_workflow_blob"]
        assert git("rev-parse",w["tested_head"]+":"+w["formalizer_path"]).decode().strip()==w["formalizer_blob"]
        proof=json.loads(raw(w["final_head"],w["proof_artifact_path"]))
        assert proof.get("tested_head")==w["tested_head"]
        print("WORKER",w["worker"],"TESTED",w["tested_head"],"FINAL",w["final_head"],"CITIES",w["cities"],flush=True)
        for city in w["cities"]:
            p="kyiv-air-alerts-grafana/data/explosion_research/"+city+"/final_evidence.json"
            blob=git("rev-parse",w["tested_head"]+":"+p).decode().strip()
            data=json.loads(raw(w["tested_head"],p))
            buckets={k:len(data[k]) for k in ("strict_events","sensitivity_only_events","review_events") if isinstance(data.get(k),list)}
            records=[x for k in ("strict_events","sensitivity_only_events","review_events") for x in data.get(k,[]) if isinstance(x,dict)]
            original_id=sum(bool(x.get("episode_id") or x.get("matched_episode_id")) for x in records)
            noid=len(records)-original_id
            origurl=sum(bool(x.get("source_url") or x.get("url")) for x in records)
            print("CITY",city,"BLOB",blob,"EVIDENCE",len(records),"EXPLICIT",original_id,"NO_ID",noid,"URLS",origurl,"BUCKETS",buckets,"EXPORTED_LINKS",len(bycity[city]),flush=True)
            if records: print("EVIDENCE_SAMPLE",city,summary(records[:2],1000),flush=True)
            if bycity[city]:print("LINK_SAMPLE",city,summary([{k:v for k,v in bycity[city][0].items() if k not in ("normalized_accepted_observation_payload","classifier_evidence_payload")}],1100),flush=True)
    print("PROBE_COMPLETE",flush=True)
if __name__=="__main__":main()
