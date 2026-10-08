#!/usr/bin/env python3
from __future__ import annotations
import base64,gzip,hashlib,importlib,json,shutil,subprocess,sys,tempfile,types
from collections import Counter,defaultdict
from pathlib import Path

MAT=Path("research/attack_event_execution_unit_a_materialized_inputs_2026-10-07.json")
CONT_REF="48099cd6d93c2b911e331e79b5141dd482d242a8"
CONT_PATH="research/attack_event_classification_continuity_audit_2026-10-06.json"
PINNED="71cb6f6fbe856cc7b96759310fe9cc9c71cc0453"
EXPECTED=1713

def git(*args):
    return subprocess.check_output(["git",*args])

mat=json.loads(MAT.read_text(encoding="utf-8"))
corpus=json.loads(gzip.decompress(base64.b64decode(mat["corpus"]["payload_base64"])))
targets=list(corpus["episodes"])
assert len(targets)==EXPECTED
cont=json.loads(git("show",f"{CONT_REF}:{CONT_PATH}"))
main_commit=str(cont["audited_main_commit"])

for p in ("/tmp/a3_main","/tmp/a3_pinned"):
    shutil.rmtree(p,ignore_errors=True)
subprocess.check_call(["git","worktree","add","--detach","/tmp/a3_main",main_commit],stdout=subprocess.DEVNULL)
subprocess.check_call(["git","worktree","add","--detach","/tmp/a3_pinned",PINNED],stdout=subprocess.DEVNULL)
scripts=Path("/tmp/a3_pinned/kyiv-air-alerts-grafana/scripts")
sys.path.insert(0,str(scripts))
bs4=types.ModuleType("bs4")
bs4.BeautifulSoup=lambda *a,**k: (_ for _ in ()).throw(RuntimeError("DISCOVERY_FORBIDDEN"))
sys.modules["bs4"]=bs4
monitor=importlib.import_module("monitor_explosion_candidates")
replay=importlib.import_module("replay_explosion_history")

by_city=defaultdict(list)
for t in targets:
    by_city[str(t["classifier_episode_input"]["city_key"])].append(t)

source_cache={}
context_hashes={}
result=[]
reasons=Counter()
main_root=Path("/tmp/a3_main/kyiv-air-alerts-grafana")

def exact_in(eps,ci):
    for ep in eps:
        if (str(ep.get("episode_id") or "")==str(ci.get("episode_id") or "")
            and ep.get("alert_start")==ci.get("alert_start")
            and ep.get("alert_end")==ci.get("alert_end")):
            return True
    return False

for city in sorted(by_city):
    ts=by_city[city]
    if city not in {"kyiv","sevastopol"}:
        try:
            eps,sources=replay.load_historical_episodes(main_root,city,monitor)
            payload=[{"episode_id":str(e.get("episode_id") or ""),"alert_start":e.get("alert_start"),"alert_end":e.get("alert_end")} for e in eps]
            h=hashlib.sha256((json.dumps(payload,sort_keys=True,separators=(",",":"))+"\n").encode()).hexdigest()
            context_hashes[f"{city}:audited_main"]={"sha256":h,"episode_count":len(eps),"sources":sources}
            for t in ts:
                ok=exact_in(eps,t["classifier_episode_input"])
                result.append((t["alert_episode_uid"],city,ok,"audited_main",main_commit,None if ok else "TARGET_NOT_IN_PINNED_MAIN_CONTEXT"))
                if not ok: reasons["TARGET_NOT_IN_PINNED_MAIN_CONTEXT"]+=1
        except Exception as exc:
            for t in ts:
                result.append((t["alert_episode_uid"],city,False,"audited_main",main_commit,f"{type(exc).__name__}:{str(exc)[:160]}"))
                reasons[f"{city}:MAIN_LOADER_ERROR"]+=1
        continue

    data_path="kyiv-air-alerts-grafana/data/alerts_combined.json" if city=="kyiv" else "kyiv-air-alerts-grafana/data/sevastopol_events.json"
    loader=monitor.load_kyiv_alert_episodes if city=="kyiv" else monitor.load_sevastopol_alert_episodes
    for t in ts:
        prov=t.get("evidence_provenance") or {}
        qid=prov.get("collection_queue_identity") or {}
        commit=str(qid.get("commit") or "")
        if not commit:
            result.append((t["alert_episode_uid"],city,False,"queue_snapshot","", "QUEUE_COMMIT_MISSING"))
            reasons[f"{city}:QUEUE_COMMIT_MISSING"]+=1
            continue
        key=(commit,data_path)
        if key not in source_cache:
            try:
                raw=git("show",f"{commit}:{data_path}")
                tmp=Path(tempfile.gettempdir())/f"a3_{city}_{commit}.json"
                tmp.write_bytes(raw)
                eps=loader(tmp)
                payload=[{"episode_id":str(e.get("episode_id") or ""),"alert_start":e.get("alert_start"),"alert_end":e.get("alert_end")} for e in eps]
                h=hashlib.sha256((json.dumps(payload,sort_keys=True,separators=(",",":"))+"\n").encode()).hexdigest()
                source_cache[key]=(eps,None,h)
                context_hashes[f"{city}:{commit}"]={"sha256":h,"episode_count":len(eps),"git_blob":git("rev-parse",f"{commit}:{data_path}").decode().strip()}
            except Exception as exc:
                source_cache[key]=(None,f"{type(exc).__name__}:{str(exc)[:180]}",None)
        eps,err,h=source_cache[key]
        if err:
            result.append((t["alert_episode_uid"],city,False,"queue_snapshot",commit,err))
            reasons[f"{city}:QUEUE_CONTEXT_ERROR"]+=1
        else:
            ok=exact_in(eps,t["classifier_episode_input"])
            result.append((t["alert_episode_uid"],city,ok,"queue_snapshot",commit,None if ok else "TARGET_NOT_IN_QUEUE_CONTEXT"))
            if not ok: reasons[f"{city}:TARGET_NOT_IN_QUEUE_CONTEXT"]+=1

bad=[r for r in result if not r[2]]
by_city_summary={}
for city in sorted(by_city):
    rr=[r for r in result if r[1]==city]
    by_city_summary[city]={"targets":len(rr),"exact":sum(1 for r in rr if r[2]),"blocked":sum(1 for r in rr if not r[2])}

out={
 "target_episodes":len(targets),
 "target_cities":len(by_city),
 "exact_context_targets":len(result)-len(bad),
 "blocked_targets":len(bad),
 "by_city":by_city_summary,
 "blocker_reason_distribution":dict(sorted(reasons.items())),
 "smallest_blocker":({"alert_episode_uid":bad[0][0],"city":bad[0][1],"source_mode":bad[0][3],"source_commit":bad[0][4],"reason":bad[0][5]} if bad else None),
 "context_hash_count":len(context_hashes),
 "context_hashes":context_hashes,
 "external_evidence_requests":0,
 "discovery_executions":0,
}
print("A3_CONTEXT_PROOF "+json.dumps(out,ensure_ascii=False,sort_keys=True))
print("A3_CONTEXT_PROOF="+("PASS" if not bad and len(result)==EXPECTED else "BLOCKED"))
