#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SNAPSHOT_COMMIT = "efefa399e69eadd3d7fc8393ac1553cfde35f138"
SNAPSHOT_PATH = "research/attack_event_23city_persistence_snapshot_v2_2026-10-04.json"
SNAPSHOT_BLOB = "8a2f6bd33f879be9db978da59c12c34e61f6f843"
CLASSIFIER_COMMIT = "71cb6f6fbe856cc7b96759310fe9cc9c71cc0453"
CLASSIFIER_PATH = "kyiv-air-alerts-grafana/scripts/monitor_explosion_candidates.py"
CLASSIFIER_BLOB = "778469b74c2aa807d851cf2c2ee35cf4aa785589"
WORKER_PATH = "kyiv-air-alerts-grafana/scripts/run_historical_attack_event_backfill_batch.py"
WORKER_BLOB = "cb2791bd309abacf4c3aae8fee0d1a8f038220b2"
SOURCE_ADAPTER_PATH = "kyiv-air-alerts-grafana/scripts/historical_attack_event_sources.py"
SOURCE_ADAPTER_BLOB = "0ceb3ea480de9b401000ba9d8b0bb02b22d83c89"
METHODOLOGY_VERSION = "historical-attack-event-air-defense-action-v2"
NORMALIZATION_VERSION = "historical-attack-event-observation-v2"
CUTOFF = "2025-02-12"

KNOWN = {"STRICT_EVENT_POSITIVE","SENSITIVITY_EVENT_POSITIVE","NO_CONFIRMED_EVENT","NEEDS_REVIEW"}
EXPECTED_ALL = Counter({
    "STRICT_EVENT_POSITIVE":1017,
    "SENSITIVITY_EVENT_POSITIVE":63,
    "NO_CONFIRMED_EVENT":23530,
    "NEEDS_REVIEW":1795,
})
EXPECTED_KYIV = Counter({
    "STRICT_EVENT_POSITIVE":141,
    "SENSITIVITY_EVENT_POSITIVE":4,
    "NO_CONFIRMED_EVENT":2045,
    "NEEDS_REVIEW":266,
})
EXPECTED_COHORTS = (145,57,209)
UTC = timezone.utc

def run(*args: str) -> str:
    p = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    if p.returncode:
        raise RuntimeError("command failed: " + " ".join(args) + "\n" + p.stderr[-4000:])
    return p.stdout.strip()

def git_blob(commit: str, path: str) -> str:
    return run("git","rev-parse",f"{commit}:{path}")

def norm(v: Any) -> str:
    if v is None:
        return ""
    return re.sub(r"\s+"," ",str(v)).strip()

def low(v: Any) -> str:
    return norm(v).lower()

def scalar(v: Any) -> bool:
    return isinstance(v,(str,int,float,bool)) or v is None

def flatten(obj: Any, prefix: str = "") -> list[tuple[str,Any]]:
    out=[]
    if isinstance(obj,dict):
        for k,v in obj.items():
            p=f"{prefix}.{k}" if prefix else str(k)
            if scalar(v):
                out.append((p,v))
            elif isinstance(v,dict):
                out.extend(flatten(v,p))
            elif isinstance(v,list):
                if not v:
                    out.append((p,[]))
                else:
                    for i,x in enumerate(v):
                        q=f"{p}[{i}]"
                        if scalar(x):
                            out.append((q,x))
                        elif isinstance(x,(dict,list)):
                            out.extend(flatten(x,q))
    elif isinstance(obj,list):
        for i,x in enumerate(obj):
            q=f"{prefix}[{i}]"
            if scalar(x):
                out.append((q,x))
            elif isinstance(x,(dict,list)):
                out.extend(flatten(x,q))
    return out

def discover_arrays(obj: Any, prefix: str = "") -> list[tuple[str,list]]:
    found=[]
    if isinstance(obj,dict):
        for k,v in obj.items():
            p=f"{prefix}.{k}" if prefix else str(k)
            if isinstance(v,list):
                found.append((p,v))
            elif isinstance(v,dict):
                found.extend(discover_arrays(v,p))
    elif isinstance(obj,list):
        found.append((prefix,obj))
    return found

def path_leaf(p: str) -> str:
    return re.sub(r"\[\d+\]","",p).split(".")[-1].lower()

def table_hint(path: str) -> str:
    b=re.sub(r"\[\d+\]","",path.lower().split(".")[-1])
    if "classification" in b: return "classification"
    if "alert_episode" in b or b in ("alerts","alert_episodes"): return "alert_episode"
    if "observation" in b: return "observation"
    if "source_link" in b: return "source_link"
    if "source" in b: return "source"
    if "review" in b: return "review"
    if "provenance" in b: return "provenance"
    if "event" in b: return "event"
    return re.sub(r"s$","",b)

def id_pairs(record: dict, table_path: str) -> list[tuple[str,str]]:
    ans=[]
    hint=table_hint(table_path)
    for p,v in flatten(record):
        if v is None or isinstance(v,bool):
            continue
        leaf=path_leaf(p)
        canon=None
        if leaf.endswith("_id"):
            canon=leaf
        elif leaf=="id":
            parts=re.sub(r"\[\d+\]","",p).lower().split(".")
            parent=parts[-2] if len(parts)>=2 else hint
            if "classification" in parent: canon="classification_id"
            elif "alert_episode" in parent or parent=="alert": canon="alert_episode_id"
            elif "observation" in parent: canon="observation_id"
            elif "source_link" in parent: canon="source_link_id"
            elif "source" in parent: canon="source_id"
            elif "review" in parent: canon="review_id"
            elif "event" in parent: canon="event_id"
            else: canon=f"{hint}_id"
        if canon:
            sv=norm(v)
            if sv:
                ans.append((canon,sv))
    return ans

def has_truthy(v: Any) -> bool:
    if v is None or v is False:
        return False
    if isinstance(v,(list,dict)):
        return len(v)>0
    return low(v) not in ("","none","null","false","0","[]","{}","n/a","na")

def verdict_from_pairs(pairs: list[tuple[str,Any]]) -> str | None:
    vals=[norm(v) for _,v in pairs if norm(v) in KNOWN]
    return vals[0] if vals else None

def evidence_flags(pairs: list[tuple[str,Any]]) -> tuple[bool,bool,bool]:
    accepted=False
    source_links=False
    anyprov=False
    for p,v in pairs:
        if not has_truthy(v):
            continue
        pl=p.lower()
        if "accepted" in pl and ("evidence" in pl or "observation" in pl or "source" in pl):
            accepted=True
        if "source_link" in pl or "source_links" in pl:
            source_links=True
        if (
            ("accepted" in pl and ("evidence" in pl or "observation" in pl or "source" in pl))
            or "source_link" in pl
            or "observation_id" in pl
            or "evidence_payload" in pl
            or "evidence_excerpt" in pl
            or "evidence_text" in pl
            or "source_type" in pl
            or "source_family" in pl
            or "source_url" in pl
            or "originating_frozen_case" in pl
            or "campaign" in pl
        ):
            anyprov=True
    return accepted,source_links,anyprov

def parse_dt_any(v: Any):
    if not isinstance(v,str):
        return None
    s=v.strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s=s[:-1]+"+00:00"
        d=datetime.fromisoformat(s)
        if d.tzinfo is None:
            d=d.replace(tzinfo=UTC)
        return d.astimezone(UTC)
    except Exception:
        return None

def locate_classifications(data: Any) -> tuple[str,list[dict],str]:
    # Accepted semantic-path locator: identify one verdict field whose distribution
    # exactly matches the frozen 26,405-row authoritative classification corpus.
    candidates=[]
    for path,rows in discover_arrays(data):
        if len(rows)!=26405 or not rows or not isinstance(rows[0],dict):
            continue
        per_path={}
        for row in rows:
            rowvals=defaultdict(set)
            for fp,v in flatten(row):
                sv=norm(v)
                if sv in KNOWN:
                    sem=re.sub(r"\\[\\d+\\]","[]",fp)
                    rowvals[sem].add(sv)
            for sem,vals in rowvals.items():
                if len(vals)==1:
                    vv=next(iter(vals))
                    per_path.setdefault(sem,Counter())[vv]+=1
        for sem,counts in per_path.items():
            score=sum(min(counts[k],EXPECTED_ALL[k]) for k in EXPECTED_ALL)
            candidates.append((score,path,rows,counts,sem))
            if counts==EXPECTED_ALL:
                return path,rows,sem
    best=max(candidates,key=lambda x:x[0]) if candidates else None
    raise RuntimeError(f"authoritative classification table unresolved: {None if best is None else best[3]}")

def row_verdict(row: dict, verdict_sem: str) -> str | None:
    for p,v in flatten(row):
        if re.sub(r"\\[\\d+\\]","[]",p)==verdict_sem and norm(v) in KNOWN:
            return norm(v)
    return None

def row_city(row: dict) -> str:
    for k in ("city_key","city"):
        v=row.get(k)
        if isinstance(v,str):
            if low(v) in ("kyiv","київ","киев","м. київ","м. киев","city of kyiv","kyiv city"):
                return "kyiv"
            if v:
                return low(v)
    for p,v in flatten(row):
        if path_leaf(p) in ("city_key","city") and isinstance(v,str) and low(v) in ("kyiv","київ","киев","м. київ","м. киев","city of kyiv","kyiv city"):
            return "kyiv"
    return ""

def row_bounds(row: dict, pairs: list[tuple[str,Any]]) -> tuple[datetime|None,datetime|None]:
    starts=[]
    ends=[]
    for k in ("alert_start_utc_microseconds","alert_start_at","alert_start","start_at","alert_episode_start","start"):
        d=parse_dt_any(row.get(k))
        if d:
            starts.append((100,k,d))
    for k in ("alert_end_utc_microseconds","alert_end_at","alert_end","end_at","alert_episode_end","end"):
        d=parse_dt_any(row.get(k))
        if d:
            ends.append((100,k,d))
    for p,v in pairs:
        d=parse_dt_any(v)
        if not d:
            continue
        pl=p.lower()
        if "alert" in pl and any(t in pl for t in ("start","started","begin")):
            score=(30 if "classification." in pl else 0)+(20 if "alert_start" in pl else 0)
            starts.append((score,p,d))
        if "alert" in pl and any(t in pl for t in ("end","ended","finish")):
            score=(30 if "classification." in pl else 0)+(20 if "alert_end" in pl else 0)
            ends.append((score,p,d))
    starts.sort(key=lambda x:(x[0],-len(x[1])),reverse=True)
    ends.sort(key=lambda x:(x[0],-len(x[1])),reverse=True)
    return (starts[0][2] if starts else None, ends[0][2] if ends else None)

def build_index(arrays: list[tuple[str,list]]) -> tuple[dict,dict]:
    table_records={}
    idx=defaultdict(list)
    for tp,arr in arrays:
        if not arr or not isinstance(arr[0],dict):
            continue
        table_records[tp]=arr
        for i,r in enumerate(arr):
            if not isinstance(r,dict):
                continue
            for kv in id_pairs(r,tp):
                idx[kv].append((tp,i))
    return table_records,idx

def related_records(class_path: str, class_rows: list[dict], class_i: int, table_records: dict, idx: dict) -> list[tuple[str,int,dict]]:
    row=class_rows[class_i]
    seen={(class_path,class_i)}
    q=deque(id_pairs(row,class_path))
    known=set(q)
    rounds=0
    while q and rounds<3000 and len(seen)<500:
        kv=q.popleft()
        rounds+=1
        for tp,i in idx.get(kv,[]):
            key=(tp,i)
            if key in seen or tp==class_path:
                continue
            seen.add(key)
            rec=table_records[tp][i]
            for kv2 in id_pairs(rec,tp):
                if kv2 not in known:
                    known.add(kv2)
                    q.append(kv2)
    out=[(class_path,class_i,row)]
    for tp,i in sorted(seen):
        if tp==class_path and i==class_i:
            continue
        out.append((tp,i,table_records[tp][i]))
    return out

def context_pairs(records: list[tuple[str,int,dict]], class_path: str, class_i: int) -> list[tuple[str,Any]]:
    out=[]
    for tp,i,r in records:
        prefix="classification" if tp==class_path and i==class_i else f"related.{tp}[{i}]"
        out.extend((f"{prefix}.{p}",v) for p,v in flatten(r))
    return out

def walk_candidate_after(obj: Any, out: list[dict]) -> None:
    if isinstance(obj,dict):
        ca=obj.get("candidate_after")
        if isinstance(ca,dict):
            out.append(ca)
        elif isinstance(obj.get("candidate_before"),dict) and "candidate_after" not in obj:
            out.append(obj["candidate_before"])
        for v in obj.values():
            if isinstance(v,(dict,list)):
                walk_candidate_after(v,out)
    elif isinstance(obj,list):
        for v in obj:
            if isinstance(v,(dict,list)):
                walk_candidate_after(v,out)

def walk_observations(obj: Any, out: list[dict]) -> None:
    if isinstance(obj,dict):
        ev=obj.get("evidence_observations")
        if isinstance(ev,list):
            out.extend(x for x in ev if isinstance(x,dict))
        for k,v in obj.items():
            if k=="evidence_observations":
                continue
            if isinstance(v,(dict,list)):
                walk_observations(v,out)
    elif isinstance(obj,list):
        for v in obj:
            if isinstance(v,(dict,list)):
                walk_observations(v,out)

def evidence_text(d: dict) -> str:
    vals=[]
    for k in ("matched_text_excerpt","fulltext","full_text","article_text","source_text","evidence_text","excerpt","snippet","message_text","text","title"):
        v=d.get(k)
        if isinstance(v,str) and v.strip():
            vals.append(v.strip())
    seen=[]
    for x in vals:
        if x not in seen:
            seen.append(x)
    return "\n".join(seen)

def candidate_from_raw(raw: dict) -> dict | None:
    text=evidence_text(raw)
    title=raw.get("title") if isinstance(raw.get("title"),str) else ""
    snippet=raw.get("snippet") if isinstance(raw.get("snippet"),str) else ""
    matched=raw.get("matched_text_excerpt") if isinstance(raw.get("matched_text_excerpt"),str) else ""
    excerpt=raw.get("excerpt") if isinstance(raw.get("excerpt"),str) else ""
    if not snippet and excerpt:
        snippet=excerpt
    if not snippet and text:
        snippet=text
    if not title and text:
        title=text[:240]
    published=raw.get("published_at") or raw.get("source_timestamp") or raw.get("publication_time") or raw.get("message_timestamp")
    url=raw.get("url") or raw.get("resolved_url") or raw.get("source_url") or ""
    source=raw.get("source")
    if not source:
        channel=raw.get("telegram_channel")
        source=(f"Telegram / {channel}" if channel else raw.get("source_family") or raw.get("source_type") or "stored_evidence")
    publisher=raw.get("publisher") or raw.get("source_family") or ""
    basis=raw.get("discovery_basis")
    if not basis:
        st=low(raw.get("source_type") or "")
        basis="publisher_fulltext" if ("publisher" in st and "full" in st) else "stored_evidence_replay"
    cand={
        "source":source,
        "title":title,
        "url":url,
        "resolved_url":raw.get("resolved_url") or url,
        "publisher":publisher,
        "publisher_url":raw.get("publisher_url") or "",
        "published_at":published,
        "snippet":snippet,
        "matched_text_excerpt":matched or (text if basis=="publisher_fulltext" else ""),
        "discovery_basis":basis,
        "candidate_id":raw.get("candidate_id") or raw.get("observation_id") or "",
        "city_key":"kyiv",
    }
    if isinstance(raw.get("review_provenance"),dict):
        cand["review_provenance"]=copy.deepcopy(raw["review_provenance"])
    if not (text or published or url or cand.get("review_provenance")):
        return None
    return cand

def candidate_key(c: dict) -> str:
    raw="|".join([
        norm(c.get("candidate_id")), norm(c.get("url")), norm(c.get("published_at")),
        norm(c.get("title")), norm(c.get("snippet")), norm(c.get("matched_text_excerpt"))
    ])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def extract_candidates(records: list[tuple[str,int,dict]], class_path: str, class_i: int) -> tuple[list[dict],str]:
    primary=records[0][2]
    native=[]
    walk_candidate_after(primary,native)
    source="classification_native_replay"
    raw=native
    if not raw:
        native=[]
        for _,_,r in records[1:]:
            walk_candidate_after(r,native)
        raw=native
        source="related_native_replay"
    if not raw:
        obs=[]
        for _,_,r in records:
            walk_observations(r,obs)
        raw=obs
        source="stored_evidence_observation_reconstruction"
    out=[]
    seen=set()
    for r in raw:
        c=candidate_from_raw(r)
        if not c:
            continue
        k=candidate_key(c)
        if k in seen:
            continue
        seen.add(k)
        out.append(c)
    return out,source

def gate_vector(decision: dict) -> dict:
    ce=decision.get("candidate_evidence") or {}
    return {
        "attack_event": bool((decision.get("strict_explosion_evidence") or {}).get("present")),
        "exact_city": bool((decision.get("exact_city_classification_evidence") or {}).get("present")),
        "air_context": bool((decision.get("air_military_context") or {}).get("present")),
        "same_attack": bool((decision.get("same_attack_context") or {}).get("present")),
        "temporal_binding": bool((decision.get("temporal_binding") or {}).get("present")) or bool((decision.get("single_episode_day_inference") or {}).get("present")),
        "candidate_attack_event": bool((ce.get("strict_explosion") or {}).get("present")),
        "candidate_exact_city": bool((ce.get("exact_city") or {}).get("present")),
        "candidate_air_context": bool((ce.get("air_military_context") or {}).get("present")),
        "candidate_same_attack": bool((ce.get("same_attack_context") or {}).get("present")),
        "candidate_temporal_binding": bool((ce.get("temporal_binding") or {}).get("present")) or bool((ce.get("single_episode_day_inference") or {}).get("present")),
    }

GATE_ORDER=[
    ("attack_event","attack-event semantics"),
    ("exact_city","exact-city semantics"),
    ("air_context","air context"),
    ("same_attack","same-attack relation"),
    ("temporal_binding","temporal binding"),
]

def decision_first_failure(decision: dict) -> str:
    codes=set(str(x) for x in (decision.get("reason_codes") or []))
    for k,label in GATE_ORDER:
        if not gate_vector(decision)[k]:
            if k=="temporal_binding" and any("AMBIGUOUS" in c or "MULTI_EPISODE" in c for c in codes):
                return "alert ambiguity"
            return label
    if decision.get("proposed_outcome")=="rejected":
        return "attack-event semantics"
    return "other actual gate"

def promotion_enabler(decision: dict) -> str:
    g=gate_vector(decision)
    for k,label in GATE_ORDER:
        ck="candidate_"+k
        if g.get(k) and not g.get(ck):
            return label
    return "all non-review evidence gates already pass"

def best_decision(decisions: list[dict]) -> dict | None:
    if not decisions:
        return None
    def score(d):
        g=gate_vector(d)
        passed=sum(1 for k,_ in GATE_ORDER if g[k])
        out=d.get("proposed_outcome")
        rank={"approved_strict":4,"approved_sensitivity":3,"needs_review":2,"rejected":1}.get(out,0)
        return (rank,passed)
    return max(decisions,key=score)

def semantic_summary(rows: list[dict]) -> dict:
    keys=["attack_event","exact_city","air_context","same_attack","temporal_binding","source_evidence_complete"]
    return {
        k: {
            "supported":sum(1 for r in rows if r["semantic_support"].get(k)),
            "total":len(rows),
        } for k in keys
    }

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--snapshot",required=True)
    ap.add_argument("--stack",required=True)
    ap.add_argument("--summary",required=True)
    ap.add_argument("--ledger",required=True)
    ap.add_argument("--run-id",required=True)
    args=ap.parse_args()
    summary_path=Path(args.summary)
    ledger_path=Path(args.ledger)

    base_summary={
        "schema_version":1,
        "kind":"kyiv_411_episode_classification_continuity_replay",
        "actions_run_id":int(args.run_id),
        "authoritative_classifier":{
            "commit":CLASSIFIER_COMMIT,
            "classifier_path":CLASSIFIER_PATH,
            "classifier_blob":CLASSIFIER_BLOB,
            "worker_path":WORKER_PATH,
            "worker_blob":WORKER_BLOB,
            "source_adapter_path":SOURCE_ADAPTER_PATH,
            "source_adapter_blob":SOURCE_ADAPTER_BLOB,
            "methodology_version":METHODOLOGY_VERSION,
            "normalization_version":NORMALIZATION_VERSION,
        },
        "frozen_snapshot":{"commit":SNAPSHOT_COMMIT,"path":SNAPSHOT_PATH,"blob":SNAPSHOT_BLOB},
        "mutation_confirmation":{
            "classifier_mutations":0,"parser_mutations":0,"temporal_representation_mutations":0,
            "alert_grouping_mutations":0,"source_evidence_mutations":0,"review_provenance_mutations":0,
            "historical_state_mutations":0,"queue_mutations":0,"persistence_mutations":0,
            "neon_db_queries":0,"neon_db_writes":0,"deployments":0,
        }
    }

    try:
        if git_blob(SNAPSHOT_COMMIT,SNAPSHOT_PATH)!=SNAPSHOT_BLOB:
            raise RuntimeError("SNAPSHOT_BLOB_MISMATCH")
        if git_blob(CLASSIFIER_COMMIT,CLASSIFIER_PATH)!=CLASSIFIER_BLOB:
            raise RuntimeError("CLASSIFIER_BLOB_MISMATCH")
        if git_blob(CLASSIFIER_COMMIT,WORKER_PATH)!=WORKER_BLOB:
            raise RuntimeError("WORKER_BLOB_MISMATCH")
        if git_blob(CLASSIFIER_COMMIT,SOURCE_ADAPTER_PATH)!=SOURCE_ADAPTER_BLOB:
            raise RuntimeError("SOURCE_ADAPTER_BLOB_MISMATCH")

        stack=Path(args.stack)
        sys.path.insert(0,str(stack/"kyiv-air-alerts-grafana"/"scripts"))
        spec=importlib.util.spec_from_file_location("authoritative_monitor",stack/CLASSIFIER_PATH)
        monitor=importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(monitor)

        data=json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
        class_path,class_rows,verdict_sem=locate_classifications(data)
        verdict_counts=Counter(row_verdict(row,verdict_sem) for row in class_rows)
        verdict_counts.pop(None,None)
        if verdict_counts!=EXPECTED_ALL:
            raise RuntimeError(f"AUTHORITATIVE_TOTAL_MISMATCH:{dict(verdict_counts)}")

        kyiv_idx=[i for i,r in enumerate(class_rows) if row_city(r)=="kyiv"]
        if len(kyiv_idx)!=2456:
            raise RuntimeError(f"KYIV_EPISODE_COUNT_MISMATCH:{len(kyiv_idx)}")

        arrays=discover_arrays(data)
        table_records,idx=build_index(arrays)
        # Ensure the selected classification table is available for relation traversal.
        table_records[class_path]=class_rows
        for i,r in enumerate(class_rows):
            for kv in id_pairs(r,class_path):
                if (class_path,i) not in idx[kv]:
                    idx[kv].append((class_path,i))

        contexts={}
        for i in kyiv_idx:
            recs=related_records(class_path,class_rows,i,table_records,idx)
            pairs=context_pairs(recs,class_path,i)
            contexts[i]=(recs,pairs)

        observed_kyiv=Counter(row_verdict(class_rows[i],verdict_sem) for i in kyiv_idx)
        if observed_kyiv!=EXPECTED_KYIV:
            raise RuntimeError(f"KYIV_VERDICT_COUNT_MISMATCH:{dict(observed_kyiv)}")

        # Rebuild the full logical Kyiv alert universe strictly from alert boundaries.
        episodes=[]
        episode_for_idx={}
        for i in kyiv_idx:
            st,en=row_bounds(class_rows[i],contexts[i][1])
            if not st or not en:
                raise RuntimeError(f"KYIV_ALERT_BOUNDARY_MISSING:{i}")
            ep=monitor.make_episode("kyiv",st,en,source="frozen_authoritative_snapshot")
            episodes.append(ep)
            episode_for_idx[i]=ep
        episodes.sort(key=lambda x:(x["alert_start"],x["alert_end"],x["episode_id"]))
        if len({e["episode_id"] for e in episodes})!=2456:
            raise RuntimeError("KYIV_LOGICAL_EPISODE_ID_COLLISION")

        # Cohort identity selection only; accepted verdicts are not placed in classifier inputs.
        positive_idx=[]
        hold_idx=[]
        post_idx=[]
        labels={}
        for i in kyiv_idx:
            pairs=contexts[i][1]
            v=row_verdict(class_rows[i],verdict_sem)
            st,_=row_bounds(class_rows[i],pairs)
            date=st.date().isoformat() if st else None
            _,_,evidence=evidence_flags(pairs)
            if v in ("STRICT_EVENT_POSITIVE","SENSITIVITY_EVENT_POSITIVE"):
                positive_idx.append(i)
                labels[i]=v
            elif v=="NEEDS_REVIEW" and evidence and date and date<=CUTOFF:
                hold_idx.append(i)
                labels[i]=v
            elif v=="NEEDS_REVIEW" and evidence and date and date>CUTOFF:
                post_idx.append(i)
                labels[i]=v
        if (len(positive_idx),len(hold_idx),len(post_idx))!=EXPECTED_COHORTS:
            raise RuntimeError(f"COHORT_COUNT_MISMATCH:{len(positive_idx)},{len(hold_idx)},{len(post_idx)}")

        target_idx=positive_idx+hold_idx+post_idx
        blind_inputs=[]
        for i in target_idx:
            recs,pairs=contexts[i]
            cands,input_source=extract_candidates(recs,class_path,i)
            ep=episode_for_idx[i]
            # Explicit blind input object excludes historical verdict/cohort fields.
            blind_inputs.append({
                "classification_row_index":i,
                "episode":copy.deepcopy(ep),
                "candidates":cands,
                "input_source":input_source,
            })

        replay={}
        led=[]
        for item in blind_inputs:
            i=item["classification_row_index"]
            ep=item["episode"]
            eid=ep["episode_id"]
            decisions=[]
            for cand in item["candidates"]:
                # Recompute matching from alert boundaries. No stored classifier outcome is used.
                matching=monitor.match_candidate_to_episodes(cand,episodes)
                d=monitor.classify_candidate(cand,"kyiv",episodes,matching)
                decisions.append(d)
            strict=[d for d in decisions if d.get("proposed_outcome")=="approved_strict" and d.get("proposed_matched_episode_id")==eid]
            sens=[d for d in decisions if d.get("proposed_outcome")=="approved_sensitivity" and d.get("proposed_matched_episode_id")==eid]
            review=[d for d in decisions if d.get("proposed_outcome")=="needs_review"]
            if strict:
                state="STRICT_EVENT_POSITIVE"
                winning=best_decision(strict)
            elif sens:
                state="SENSITIVITY_EVENT_POSITIVE"
                winning=best_decision(sens)
            elif review or not decisions:
                state="NEEDS_REVIEW"
                winning=best_decision(review or decisions)
            else:
                state="NO_CONFIRMED_EVENT"
                winning=best_decision(decisions)

            if not decisions:
                first_failure="missing evidence payload"
                semantic={
                    "attack_event":False,"exact_city":False,"air_context":False,"same_attack":False,
                    "temporal_binding":False,"source_evidence_complete":False
                }
                candidate_semantic={k:False for k in ("attack_event","exact_city","air_context","same_attack","temporal_binding")}
                reason_codes=[]
            else:
                bd=winning or best_decision(decisions)
                g=gate_vector(bd)
                first_failure=None if state in ("STRICT_EVENT_POSITIVE","SENSITIVITY_EVENT_POSITIVE") else decision_first_failure(bd)
                semantic={
                    "attack_event":any(gate_vector(d)["attack_event"] for d in decisions),
                    "exact_city":any(gate_vector(d)["exact_city"] for d in decisions),
                    "air_context":any(gate_vector(d)["air_context"] for d in decisions),
                    "same_attack":any(gate_vector(d)["same_attack"] for d in decisions),
                    "temporal_binding":any(gate_vector(d)["temporal_binding"] for d in decisions),
                    "source_evidence_complete":any(bool(evidence_text(c)) for c in item["candidates"]),
                }
                candidate_semantic={
                    "attack_event":any(gate_vector(d)["candidate_attack_event"] for d in decisions),
                    "exact_city":any(gate_vector(d)["candidate_exact_city"] for d in decisions),
                    "air_context":any(gate_vector(d)["candidate_air_context"] for d in decisions),
                    "same_attack":any(gate_vector(d)["candidate_same_attack"] for d in decisions),
                    "temporal_binding":any(gate_vector(d)["candidate_temporal_binding"] for d in decisions),
                }
                reason_codes=sorted({str(c) for d in decisions for c in (d.get("reason_codes") or [])})

            replay[i]=state
            led.append({
                "classification_row_index":i,
                "episode_id":eid,
                "alert_start":ep["alert_start"],
                "alert_end":ep["alert_end"],
                "candidate_count":len(item["candidates"]),
                "input_source":item["input_source"],
                "replay_state":state,
                "first_failure_gate":first_failure,
                "semantic_support":semantic,
                "candidate_only_semantic_support":candidate_semantic,
                "reason_codes":reason_codes,
                "promotion_enabler":None,
            })

        # Scoring starts here: accepted historical labels are introduced only after replay exists.
        ledger_by_idx={r["classification_row_index"]:r for r in led}
        hist_pos=[ledger_by_idx[i] for i in positive_idx]
        hist_hold=[ledger_by_idx[i] for i in hold_idx]
        post=[ledger_by_idx[i] for i in post_idx]

        pos_output=Counter(r["replay_state"] for r in hist_pos)
        hold_output=Counter(r["replay_state"] for r in hist_hold)
        post_output=Counter(r["replay_state"] for r in post)

        strict_expected=[i for i in positive_idx if labels[i]=="STRICT_EVENT_POSITIVE"]
        sens_expected=[i for i in positive_idx if labels[i]=="SENSITIVITY_EVENT_POSITIVE"]
        strict_reproduced=sum(replay[i]=="STRICT_EVENT_POSITIVE" for i in strict_expected)
        sens_reproduced=sum(replay[i]=="SENSITIVITY_EVENT_POSITIVE" for i in sens_expected)
        any_positive_reproduced=sum(replay[i] in ("STRICT_EVENT_POSITIVE","SENSITIVITY_EVENT_POSITIVE") for i in positive_idx)

        pos_miss_tax=Counter()
        for i in positive_idx:
            if replay[i] not in ("STRICT_EVENT_POSITIVE","SENSITIVITY_EVENT_POSITIVE"):
                pos_miss_tax[ledger_by_idx[i]["first_failure_gate"] or "other actual gate"]+=1

        promo_tax=Counter()
        for i in hold_idx:
            if replay[i] in ("STRICT_EVENT_POSITIVE","SENSITIVITY_EVENT_POSITIVE"):
                r=ledger_by_idx[i]
                # Re-run compactly to identify the first gate supplied by review provenance, if any.
                item=next(x for x in blind_inputs if x["classification_row_index"]==i)
                eid=item["episode"]["episode_id"]
                winners=[]
                for cand in item["candidates"]:
                    m=monitor.match_candidate_to_episodes(cand,episodes)
                    d=monitor.classify_candidate(cand,"kyiv",episodes,m)
                    if d.get("proposed_outcome") in ("approved_strict","approved_sensitivity") and d.get("proposed_matched_episode_id")==eid:
                        winners.append(d)
                w=best_decision(winners)
                gate=promotion_enabler(w) if w else "other actual gate"
                r["promotion_enabler"]=gate
                promo_tax[gate]+=1

        raw_strict=post_output["STRICT_EVENT_POSITIVE"]
        raw_sens=post_output["SENSITIVITY_EVENT_POSITIVE"]
        raw_pos=raw_strict+raw_sens
        hold_strict=hold_output["STRICT_EVENT_POSITIVE"]
        hold_sens=hold_output["SENSITIVITY_EVENT_POSITIVE"]
        strict_safe=(hold_strict==0)
        sens_safe=(hold_sens==0)
        safe_pos=(raw_strict if strict_safe else 0)+(raw_sens if sens_safe else 0)

        exact_positive_behavior=(strict_reproduced==141 and sens_reproduced==4)
        unsupported_promotions=hold_strict+hold_sens
        if exact_positive_behavior and unsupported_promotions==0:
            verdict="KYIV CLASSIFICATION CONTINUITY = PROVEN"
        elif any_positive_reproduced>0:
            verdict="KYIV CLASSIFICATION CONTINUITY = PARTIAL"
        else:
            verdict="KYIV CLASSIFICATION CONTINUITY = FAILED"

        if unsupported_promotions:
            dominant=("unsupported historical hold promotions: "+promo_tax.most_common(1)[0][0]) if promo_tax else "unsupported historical hold promotions"
        elif pos_miss_tax:
            dominant=pos_miss_tax.most_common(1)[0][0]
        else:
            dominant="none"

        summary={
            **base_summary,
            "verdict":verdict,
            "episodes_replayed":411,
            "historical":{
                "accepted_positives_total":145,
                "positive_outputs":{
                    "STRICT_EVENT_POSITIVE":pos_output["STRICT_EVENT_POSITIVE"],
                    "SENSITIVITY_EVENT_POSITIVE":pos_output["SENSITIVITY_EVENT_POSITIVE"],
                    "NEEDS_REVIEW":pos_output["NEEDS_REVIEW"],
                    "NO_CONFIRMED_EVENT":pos_output["NO_CONFIRMED_EVENT"],
                },
                "any_positive_reproduced":any_positive_reproduced,
                "strict_expected_reproduced":strict_reproduced,
                "strict_expected_total":141,
                "sensitivity_expected_reproduced":sens_reproduced,
                "sensitivity_expected_total":4,
                "holds_total":57,
                "hold_outputs":{
                    "NEEDS_REVIEW":hold_output["NEEDS_REVIEW"],
                    "NO_CONFIRMED_EVENT":hold_output["NO_CONFIRMED_EVENT"],
                    "STRICT_EVENT_POSITIVE":hold_strict,
                    "SENSITIVITY_EVENT_POSITIVE":hold_sens,
                },
                "holds_preserved":hold_output["NEEDS_REVIEW"]+hold_output["NO_CONFIRMED_EVENT"],
                "unsupported_hold_promotions":unsupported_promotions,
                "positive_miss_first_gate":dict(pos_miss_tax.most_common()),
                "hold_promotion_first_gate":dict(promo_tax.most_common()),
            },
            "post_cutoff":{
                "total":209,
                "STRICT_EVENT_POSITIVE":raw_strict,
                "SENSITIVITY_EVENT_POSITIVE":raw_sens,
                "NEEDS_REVIEW":post_output["NEEDS_REVIEW"],
                "NO_CONFIRMED_EVENT":post_output["NO_CONFIRMED_EVENT"],
                "raw_positives":raw_pos,
                "safe_path_validation":{
                    "STRICT":{"historical_hold_promotions":hold_strict,"safe_for_transfer":strict_safe},
                    "SENSITIVITY":{"historical_hold_promotions":hold_sens,"safe_for_transfer":sens_safe},
                },
                "safe_positives":safe_pos,
            },
            "current_kyiv_confirmed_positives":145,
            "counterfactual_kyiv_confirmed_positives_safe_only":145+safe_pos,
            "semantic_comparison":{
                "HISTORICAL_ACCEPTED_POSITIVE":semantic_summary(hist_pos),
                "HISTORICAL_REVIEW_HOLD":semantic_summary(hist_hold),
                "POST_CUTOFF_EVIDENCE_BACKED":semantic_summary(post),
            },
            "candidate_input_sources":dict(Counter(r["input_source"] for r in led)),
            "episodes_with_zero_reconstructed_candidates":sum(r["candidate_count"]==0 for r in led),
            "dominant_blocker":dominant,
            "historical_positive_behavior_contract":{
                "rule":"all 141 historical STRICT controls remain STRICT, all 4 historical SENSITIVITY controls remain SENSITIVITY, and no historical hold is promoted",
                "passes":exact_positive_behavior and unsupported_promotions==0,
            },
        }

        # Add scoring labels only in the detailed ledger artifact, after blind replay has completed.
        cohort_by_idx={**{i:"HISTORICAL_ACCEPTED_POSITIVE" for i in positive_idx},
                       **{i:"HISTORICAL_REVIEW_HOLD" for i in hold_idx},
                       **{i:"POST_CUTOFF_EVIDENCE_BACKED" for i in post_idx}}
        for r in led:
            i=r["classification_row_index"]
            r["scoring_cohort"]=cohort_by_idx[i]
            r["historical_label_for_scoring"]=labels[i]
        ledger={
            "schema_version":1,
            "kind":"kyiv_411_episode_classification_continuity_replay_ledger",
            "blind_replay_completed_before_scoring_labels_attached":True,
            "authoritative_classifier":base_summary["authoritative_classifier"],
            "episodes":led,
        }

        summary_path.write_text(json.dumps(summary,ensure_ascii=False,indent=2,sort_keys=False)+"\n",encoding="utf-8")
        ledger_path.write_text(json.dumps(ledger,ensure_ascii=False,indent=2,sort_keys=False)+"\n",encoding="utf-8")
        print(json.dumps(summary,ensure_ascii=False,sort_keys=True))
        return 0
    except Exception as exc:
        blocked={
            **base_summary,
            "verdict":"KYIV CLASSIFICATION CONTINUITY = BLOCKED",
            "episodes_replayed":0,
            "blocker":f"{type(exc).__name__}: {exc}",
        }
        summary_path.parent.mkdir(parents=True,exist_ok=True)
        summary_path.write_text(json.dumps(blocked,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print(json.dumps(blocked,ensure_ascii=False,sort_keys=True))
        return 2

if __name__=="__main__":
    raise SystemExit(main())
