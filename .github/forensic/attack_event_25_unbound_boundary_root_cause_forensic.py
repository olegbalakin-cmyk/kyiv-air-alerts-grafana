from __future__ import annotations

import hashlib
import io
import json
import os
import re
import subprocess
import sys
import urllib.request
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import psycopg

REPO = "olegbalakin-cmyk/kyiv-air-alerts-grafana"
EXPECTED_BRANCH_ID = "br-bold-mode-b5rub8pq"
PRED_RUN = 37285225186
PRED_JOB = 111682419864
PRED_ARTIFACT = 11334350472
PRED_ARTIFACT_NAME = "attack-event-25-unbound-parent-forensic"
PRED_HEAD = "fafe467f99ad256e36d33f79e73d1517ba12db6b"

SNAPSHOT_COMMIT = "efefa399e69eadd3d7fc8393ac1553cfde35f138"
SNAPSHOT_PATH = "research/attack_event_23city_persistence_snapshot_v2_2026-10-04.json"
SNAPSHOT_SHA256 = "09458bcf0a019fa2939eb9dfa484da46cd8fa2be077343c5ba6d595c93d71788"

BINDING_COMMIT = "e213f445f08bfc119b234c9460b66bd3efe75d36"
BINDING_PATH = "research/attack_event_23city_parent_binding_map_v1_2026-10-05.json"
BINDING_SHA256 = "b0ecd5ce980d76cf5ffce65f80ee1d5bd43c0d1b1438afb85424ae95aaef1241"

EXPECTED_PARENT_SHA = "882802f162334c336bc5015e1ef12b9e0d36b338c12f4939700fc69419387146"
EXPECTED_TARGETS = 25
CANONICAL_VERSION = "alert-canonicalization-v1"

OUTDIR = Path(os.environ.get("RUNNER_TEMP", "/tmp")) / "attack-event-25-unbound-boundary-root-cause-forensic"
OUTDIR.mkdir(parents=True, exist_ok=True)
FULL_PATH = OUTDIR / "attack_event_25_unbound_boundary_root_cause_forensic.json"
SUMMARY_PATH = OUTDIR / "summary.json"
INPUT_DIR = OUTDIR / "inputs"
INPUT_DIR.mkdir(parents=True, exist_ok=True)

PROVEN_CATEGORIES = {
    "TIMESTAMP_PRECISION_NORMALIZATION_DIFFERENCE",
    "HISTORICAL_BOUNDARY_NORMALIZATION_DIFFERENCE",
    "CANONICAL_BOUNDARY_POLICY_DIFFERENCE",
    "SOURCE_SET_DIFFERENCE",
    "LATE_OR_UPDATED_SOURCE_OBSERVATION",
    "CANONICAL_SPLIT_PROVEN",
    "CANONICAL_MERGE_PROVEN",
    "LEGACY_IMPORT_BOUNDARY_DIFFERENCE",
    "SOURCE_RECORD_CORRECTION",
    "OTHER_PROVEN_CAUSE",
}
HYPOTHESES = {
    "PRECISION_DIFFERENCE_SUSPECTED",
    "BOUNDARY_POLICY_DIFFERENCE_SUSPECTED",
    "SOURCE_SET_DIFFERENCE_SUSPECTED",
    "SPLIT_MERGE_SUSPECTED",
    "LEGACY_IMPORT_DIFFERENCE_SUSPECTED",
    "UNKNOWN",
}

class GateError(RuntimeError):
    def __init__(self, gate, affected_count=None, provenance_source=None, detail=None):
        super().__init__(gate)
        self.gate = gate
        self.affected_count = affected_count
        self.provenance_source = provenance_source
        self.detail = detail

def fail(gate, affected_count=None, provenance_source=None, detail=None):
    raise GateError(gate, affected_count, provenance_source, detail)

def run(cmd, *, check=True, text=True):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=text)
    if check and p.returncode != 0:
        raise RuntimeError(f"command failed: {cmd[0]} rc={p.returncode} stderr={p.stderr[:400] if text else ''}")
    return p

def write_json(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")), encoding="utf-8")

def canonical_json_bytes(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")

def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()

def safe(v):
    if isinstance(v, datetime):
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
        return v.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(v, (bytes, bytearray, memoryview)):
        return bytes(v).hex()
    return v

def gh_json(url):
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        fail("GITHUB_TOKEN_MISSING", EXPECTED_TARGETS, "GitHub Actions")
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "25-unbound-boundary-root-cause-forensic",
    })
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))

def validate_artifact():
    meta = gh_json(f"https://api.github.com/repos/{REPO}/actions/artifacts/{PRED_ARTIFACT}")
    wr = meta.get("workflow_run") or {}
    if (int(meta.get("id") or 0) != PRED_ARTIFACT or meta.get("name") != PRED_ARTIFACT_NAME
        or bool(meta.get("expired")) or int(wr.get("id") or 0) != PRED_RUN or wr.get("head_sha") != PRED_HEAD):
        fail("PREDECESSOR_ARTIFACT_IDENTITY_MISMATCH", EXPECTED_TARGETS, "predecessor Actions artifact",
             {"actual_name": meta.get("name"), "run_id": wr.get("id"), "head_sha": wr.get("head_sha"), "expired": meta.get("expired")})

def download_artifact():
    token = os.environ["GITHUB_TOKEN"]
    zpath = INPUT_DIR / "predecessor.zip"
    cmd = [
        "curl","-fsSL",
        "-H","Accept: application/vnd.github+json",
        "-H",f"Authorization: Bearer {token}",
        "-H","X-GitHub-Api-Version: 2022-11-28",
        f"https://api.github.com/repos/{REPO}/actions/artifacts/{PRED_ARTIFACT}/zip",
        "-o",str(zpath)
    ]
    p = run(cmd, check=False)
    if p.returncode:
        fail("PREDECESSOR_ARTIFACT_DOWNLOAD_FAILED", EXPECTED_TARGETS, "predecessor Actions artifact")
    root = INPUT_DIR / "predecessor"
    root.mkdir(exist_ok=True)
    with zipfile.ZipFile(zpath) as zf:
        zf.extractall(root)
    fp = root / "attack_event_25_unbound_parent_forensic.json"
    sp = root / "summary.json"
    if not fp.is_file() or not sp.is_file():
        fail("PREDECESSOR_ARTIFACT_CONTENT_MISSING", EXPECTED_TARGETS, "predecessor Actions artifact")
    return json.loads(fp.read_text(encoding="utf-8")), json.loads(sp.read_text(encoding="utf-8"))

def git_show_bytes(commit, path):
    p = subprocess.run(["git","show",f"{commit}:{path}"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode:
        fail("FROZEN_REPOSITORY_ARTIFACT_UNAVAILABLE", EXPECTED_TARGETS, f"{commit}:{path}")
    return p.stdout

def recursive_find_records(obj, target_keys, out):
    if isinstance(obj, dict):
        ck = obj.get("classification_key")
        if ck is not None and str(ck) in target_keys:
            out.setdefault(str(ck), []).append(obj)
        for v in obj.values():
            recursive_find_records(v, target_keys, out)
    elif isinstance(obj, list):
        for v in obj:
            recursive_find_records(v, target_keys, out)

def collect_values(obj, key_re, limit=200):
    vals = []
    def walk(x):
        if len(vals) >= limit:
            return
        if isinstance(x, dict):
            for k,v in x.items():
                if key_re.search(str(k)):
                    if isinstance(v, (str,int,float,bool)) or v is None:
                        vals.append((str(k), safe(v)))
                    elif isinstance(v, list):
                        for z in v[:50]:
                            if isinstance(z, (str,int,float,bool)):
                                vals.append((str(k), safe(z)))
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(obj)
    return vals[:limit]

def extract_source_ids(obj):
    pairs = collect_values(obj, re.compile(r"(?i)(source.*id|observation_id|alert_id|native.*id|source_url)$"), 300)
    ids = set()
    for k,v in pairs:
        if v is None:
            continue
        s = str(v).strip()
        if s and len(s) <= 500:
            ids.add(s)
    return sorted(ids)

def extract_timestamp_values(obj):
    pairs = collect_values(obj, re.compile(r"(?i)(start|end|time|timestamp|created|updated|ingest|observed)"), 400)
    return pairs

def find_origin_path(needles):
    candidates = []
    for needle in needles:
        if not needle:
            continue
        p = run(["git","grep","-l","-F",str(needle),"--","research","kyiv-air-alerts-grafana"], check=False)
        if p.returncode not in (0,1):
            continue
        for line in p.stdout.splitlines():
            if line and line not in candidates:
                candidates.append(line)
                if len(candidates) >= 20:
                    return candidates
    return candidates

def earliest_commit_blob(path):
    p = run(["git","log","--all","--reverse","--format=%H","--",path], check=False)
    commits = [x.strip() for x in p.stdout.splitlines() if x.strip()]
    if not commits:
        return None, None
    for c in commits:
        b = run(["git","rev-parse",f"{c}:{path}"], check=False)
        if b.returncode == 0:
            return c, b.stdout.strip()
    return None, None

def lineage_by_pickaxe(term):
    p = run(["git","log","--all","--reverse",f"-S{term}","--format=%H"], check=False)
    commits = [x.strip() for x in p.stdout.splitlines() if x.strip()]
    if not commits:
        return {"term": term, "commit": None, "paths": [], "blobs": {}}
    c = commits[0]
    n = run(["git","show","--pretty=format:","--name-only",c], check=False)
    paths = [x.strip() for x in n.stdout.splitlines() if x.strip()]
    blobs = {}
    for path in paths[:30]:
        b = run(["git","rev-parse",f"{c}:{path}"], check=False)
        if b.returncode == 0:
            blobs[path] = b.stdout.strip()
    return {"term": term, "commit": c, "paths": paths[:30], "blobs": blobs}

def best_snapshot_record(candidates, pred):
    if not candidates:
        return None
    hist = str(pred.get("historical_episode_id") or "")
    for c in candidates:
        if str(c.get("historical_episode_id") or "") == hist:
            return c
    return candidates[0]

def source_row_ids(row):
    ids=set()
    for k,v in row.items():
        lk=k.lower()
        if v is None:
            continue
        if ("source" in lk and "id" in lk) or lk in {"alert_id","observation_id","native_id","source_url"}:
            ids.add(str(v))
    return ids

def row_boundary_matches(row, start_s, end_s):
    hits=[]
    for k,v in row.items():
        lk=k.lower()
        if v is None:
            continue
        sv=str(safe(v))
        if "start" in lk and start_s and sv.startswith(start_s[:19]):
            hits.append(("start",k,sv))
        if "end" in lk and end_s and sv.startswith(end_s[:19]):
            hits.append(("end",k,sv))
    return hits

def hypothesis_for(rec, hist_ids, canon_ids, canonical_text):
    sd=rec.get("exact_deltas",{}).get("start_seconds")
    ed=rec.get("exact_deltas",{}).get("end_seconds")
    vals=[abs(float(x)) for x in (sd,ed) if x is not None]
    small=bool(vals) and max(vals) <= 60
    large=bool(vals) and max(vals) > 1800
    mech=rec.get("predecessor_mechanical_category","")
    flags=set(rec.get("predecessor_secondary_flags") or [])
    if small:
        return "PRECISION_DIFFERENCE_SUSPECTED"
    if hist_ids and canon_ids and set(hist_ids) != set(canon_ids):
        return "SOURCE_SET_DIFFERENCE_SUSPECTED"
    if large and ("SPLIT" in mech or "MERGE" in mech or any("SPLIT" in x or "MERGE" in x for x in flags)):
        return "SPLIT_MERGE_SUSPECTED"
    if re.search(r"(?i)\b(legacy|import)\b", canonical_text):
        return "LEGACY_IMPORT_DIFFERENCE_SUSPECTED"
    if mech in {"PARTIAL_INTERVAL_OVERLAP","CANONICAL_INTERVAL_CONTAINS_HISTORICAL","HISTORICAL_INTERVAL_CONTAINS_CANONICAL",
                "EXACT_START_ONLY_END_DRIFT","EXACT_END_ONLY_START_DRIFT"}:
        return "BOUNDARY_POLICY_DIFFERENCE_SUSPECTED"
    return "UNKNOWN"

def classify_proven(rec, hist_ids, source_rows, canonical_text, hist_complete, canon_complete):
    canon_ids=set()
    boundary_hits=[]
    rep=(rec.get("diagnostic_canonical_candidates") or [{}])[0] if rec.get("diagnostic_canonical_candidates") else {}
    cs=rep.get("start_at")
    ce=rep.get("end_at")
    for row in source_rows:
        canon_ids |= source_row_ids(row)
        boundary_hits.extend(row_boundary_matches(row, cs, ce))
    # Strict: different persisted source sets + a canonical source row mechanically contributes
    # one mismatched canonical boundary + both provenance sides complete.
    if hist_complete and canon_complete and hist_ids and canon_ids and set(hist_ids) != canon_ids and boundary_hits:
        return "SOURCE_SET_DIFFERENCE", {
            "historical_only_source_observations": sorted(set(hist_ids)-canon_ids),
            "canonical_only_source_observations": sorted(canon_ids-set(hist_ids)),
            "canonical_boundary_source_matches": boundary_hits[:20],
        }
    # Strict legacy/import proof only when the persisted source provenance itself says legacy/import,
    # the row carries a canonical boundary value, and both sides are provenance-complete.
    if hist_complete and canon_complete and re.search(r"(?i)\b(legacy|import)\b", canonical_text) and boundary_hits:
        return "LEGACY_IMPORT_BOUNDARY_DIFFERENCE", {
            "legacy_import_markers": sorted(set(re.findall(r"(?i)\b(?:legacy|import)\w*", canonical_text)))[:20],
            "canonical_boundary_source_matches": boundary_hits[:20],
        }
    return None, None

conn=None
cur=None
parent_sha_match="NO"
parent_sha=None
records_out=[]
db_prov_rows=[]

try:
    validate_artifact()
    pred_doc, pred_summary = download_artifact()
    pred_records = pred_doc.get("records")
    if not isinstance(pred_records,list) or len(pred_records) != EXPECTED_TARGETS:
        fail("PREDECESSOR_TARGET_SET_INVALID", len(pred_records) if isinstance(pred_records,list) else 0, "predecessor forensic artifact")
    if any(r.get("accepted_binding_state") != "UNBOUND" or r.get("binding_changed") not in (False,0) for r in pred_records):
        fail("PREDECESSOR_BINDING_STATE_INVALID", EXPECTED_TARGETS, "predecessor forensic artifact")
    target_keys={str(r.get("classification_key")) for r in pred_records}
    if len(target_keys) != EXPECTED_TARGETS:
        fail("PREDECESSOR_CLASSIFICATION_KEY_UNIQUENESS_FAILURE", EXPECTED_TARGETS, "predecessor forensic artifact")

    snap_bytes=git_show_bytes(SNAPSHOT_COMMIT,SNAPSHOT_PATH)
    if sha256_bytes(snap_bytes) != SNAPSHOT_SHA256:
        fail("FROZEN_23CITY_SNAPSHOT_SHA_MISMATCH", EXPECTED_TARGETS, SNAPSHOT_PATH)
    snapshot=json.loads(snap_bytes)
    found={}
    recursive_find_records(snapshot,target_keys,found)
    snapshot_records={}
    for pr in pred_records:
        ck=str(pr["classification_key"])
        sr=best_snapshot_record(found.get(ck,[]),pr)
        if sr is None:
            fail("TARGET_CLASSIFICATION_NOT_FOUND_IN_FROZEN_SNAPSHOT",1,SNAPSHOT_PATH,{"classification_key":ck})
        snapshot_records[ck]=sr

    bind_bytes=git_show_bytes(BINDING_COMMIT,BINDING_PATH)
    if sha256_bytes(bind_bytes) != BINDING_SHA256:
        fail("FROZEN_PARENT_BINDING_MAP_SHA_MISMATCH", EXPECTED_TARGETS, BINDING_PATH)
    binding=json.loads(bind_bytes)
    bound_found={}
    recursive_find_records(binding,target_keys,bound_found)
    for ck in sorted(target_keys):
        candidates=bound_found.get(ck,[])
        if not candidates or not any(str(x.get("binding_state"))=="UNBOUND" for x in candidates):
            fail("FROZEN_BINDING_STATE_NOT_UNBOUND",1,BINDING_PATH,{"classification_key":ck})

    hist_lineage=lineage_by_pickaxe("historical-attack-event-observation-v2")
    canon_lineage=lineage_by_pickaxe(CANONICAL_VERSION)
    canon_sources_lineage=lineage_by_pickaxe("alert_episode_sources")

    db_url=os.environ.get("PHASE1_PROD_SHADOW_DATABASE_URL","")
    branch_id=os.environ.get("PHASE1_PROD_SHADOW_BRANCH_ID","")
    if not db_url:
        fail("PHASE1_PROD_SHADOW_DATABASE_URL_MISSING",EXPECTED_TARGETS,"Neon connection config")
    if branch_id != EXPECTED_BRANCH_ID:
        fail("PERMANENT_NEON_BRANCH_ID_MISMATCH",EXPECTED_TARGETS,"Neon branch guard",{"actual":branch_id})

    conn=psycopg.connect(db_url,autocommit=True,connect_timeout=30,options="-c default_transaction_read_only=on")
    cur=conn.cursor()
    cur.execute("BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
    cur.execute("SET LOCAL default_transaction_read_only=on")
    cur.execute("SELECT current_setting('transaction_read_only'),current_setting('default_transaction_read_only')")
    if tuple(cur.fetchone()) != ("on","on"):
        fail("READ_ONLY_TRANSACTION_NOT_ENFORCED",EXPECTED_TARGETS,"Neon transaction")

    def select(sql,params=()):
        if not sql.lstrip().upper().startswith(("SELECT","WITH")):
            fail("NON_READ_ONLY_SQL_ATTEMPT",EXPECTED_TARGETS,"SQL guard")
        cur.execute(sql,params)
        return cur.fetchall()

    all_cities=sorted({str(v) for k,v in collect_values(binding,re.compile(r"^city_key$"),100000) if v})\n    if len(all_cities) != 23:\n        fail("PARENT_CORPUS_CITY_SCOPE_MISMATCH",EXPECTED_TARGETS,BINDING_PATH,{"city_count":len(all_cities)})
    parent_rows=select(
        "SELECT episode_uid::text,city_key::text,alert_type::text,episode_state::text,canonicalization_version::text,start_at,end_at "
        "FROM public.alert_episodes WHERE city_key=ANY(%s) ORDER BY city_key,start_at,end_at,episode_uid",
        (all_cities,)
    )
    norm=[]
    for uid,city,atype,state,cv,st,en in parent_rows:
        def ts(x):
            return None if x is None else x.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        norm.append([str(uid),str(city),None if atype is None else str(atype),None if state is None else str(state),
                     None if cv is None else str(cv),ts(st),ts(en)])
    norm.sort(key=lambda row:tuple("" if v is None else str(v) for v in row))
    parent_sha=hashlib.sha256(json.dumps(norm,ensure_ascii=False,separators=(",",":")).encode("utf-8")).hexdigest()
    if parent_sha != EXPECTED_PARENT_SHA:
        fail("UNBOUND_ROOT_CAUSE_PARENT_CORPUS_DRIFT",EXPECTED_TARGETS,"public.alert_episodes")
    parent_sha_match="YES"

    # Discover the persisted canonical provenance schema without assuming optional columns.
    source_table_exists=bool(select(
        "SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='alert_episode_sources'"
    ))
    source_cols=[]
    source_rows_by_uid=defaultdict(list)
    if source_table_exists:
        source_cols=[r[0] for r in select(
            "SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name='alert_episode_sources' ORDER BY ordinal_position"
        )]
        if "episode_uid" in source_cols:
            all_uids=sorted({
                str(c.get("episode_uid"))
                for pr in pred_records for c in (pr.get("diagnostic_candidates") or [])
                if isinstance(c,dict) and c.get("episode_uid")
            })
            if all_uids:
                qcols=",".join('"' + c.replace('"','""') + '"' for c in source_cols)
                rows=select(f"SELECT {qcols} FROM public.alert_episode_sources WHERE episode_uid::text=ANY(%s) ORDER BY episode_uid::text",(all_uids,))
                for row in rows:
                    obj={source_cols[i]:safe(row[i]) for i in range(len(source_cols))}
                    source_rows_by_uid[str(obj.get("episode_uid"))].append(obj)
                    db_prov_rows.append({"table":"public.alert_episode_sources","row":obj})

    # Bounded canonical episode rows actually used by this forensic.
    candidate_uids=sorted({
        str(c.get("episode_uid"))
        for pr in pred_records for c in (pr.get("diagnostic_candidates") or [])
        if isinstance(c,dict) and c.get("episode_uid")
    })
    episode_rows={}
    if candidate_uids:
        rows=select(
            "SELECT episode_uid::text,city_key::text,alert_type::text,episode_state::text,canonicalization_version::text,start_at,end_at "
            "FROM public.alert_episodes WHERE episode_uid::text=ANY(%s) ORDER BY episode_uid::text",(candidate_uids,)
        )
        for row in rows:
            obj={"episode_uid":str(row[0]),"city_key":str(row[1]),"alert_type":safe(row[2]),"episode_state":safe(row[3]),
                 "canonicalization_version":safe(row[4]),"start_at":safe(row[5]),"end_at":safe(row[6])}
            episode_rows[obj["episode_uid"]]=obj
            db_prov_rows.append({"table":"public.alert_episodes","row":obj})

    for pr in sorted(pred_records,key=lambda x:str(x.get("classification_key"))):
        ck=str(pr["classification_key"])
        sr=snapshot_records[ck]
        diag=[c for c in (pr.get("diagnostic_candidates") or []) if isinstance(c,dict)]
        hist_start=pr.get("historical_start")
        hist_end=pr.get("historical_end")
        hist_id=str(pr.get("historical_episode_id"))
        hist_source_ids=extract_source_ids(sr)
        hist_ts=extract_timestamp_values(sr)

        origin_paths=find_origin_path([hist_id,ck])
        origin_path=origin_paths[0] if origin_paths else None
        hist_commit,hist_blob=(earliest_commit_blob(origin_path) if origin_path else (None,None))
        hist_summary={
            "frozen_snapshot_commit":SNAPSHOT_COMMIT,
            "frozen_snapshot_path":SNAPSHOT_PATH,
            "snapshot_record_found":True,
            "origin_repository":REPO,
            "origin_path":origin_path,
            "origin_commit":hist_commit,
            "origin_blob":hist_blob,
            "candidate_origin_paths":origin_paths[:10],
            "source_identity_values":hist_source_ids[:100],
            "timestamp_provenance_values":hist_ts[:100],
            "historical_lineage":hist_lineage,
        }
        hist_complete=bool(origin_path and hist_commit and hist_blob and hist_source_ids)

        candidate_summaries=[]
        all_source_rows=[]
        canon_ids=set()
        for c in diag:
            uid=str(c.get("episode_uid"))
            src=source_rows_by_uid.get(uid,[])
            all_source_rows.extend(src)
            for row in src:
                canon_ids |= source_row_ids(row)
            candidate_summaries.append({
                "episode_uid":uid,
                "candidate_start":c.get("start_at"),
                "candidate_end":c.get("end_at"),
                "persisted_episode_row":episode_rows.get(uid),
                "source_rows":src,
            })
        canonical_text=json.dumps(candidate_summaries,ensure_ascii=False,sort_keys=True,default=str)
        canon_complete=bool(diag and all(str(c.get("episode_uid")) in episode_rows for c in diag[:1])
                            and source_table_exists and all_source_rows
                            and (canon_lineage.get("commit") or canon_sources_lineage.get("commit")))
        canon_summary={
            "source_table_available":source_table_exists,
            "source_table_columns":source_cols,
            "candidate_count":len(diag),
            "candidates":candidate_summaries,
            "canonicalization_lineage":canon_lineage,
            "episode_sources_lineage":canon_sources_lineage,
            "canonical_source_identity_values":sorted(canon_ids)[:100],
        }

        rep=diag[0] if diag else {}
        exact_deltas={
            "start_seconds":rep.get("start_delta_seconds"),
            "end_seconds":rep.get("end_delta_seconds"),
        }
        base_record={
            "classification_key":ck,
            "city_key":pr.get("city_key"),
            "historical_episode_id":hist_id,
            "historical_start":hist_start,
            "historical_end":hist_end,
            "diagnostic_canonical_episode_uids":[c.get("episode_uid") for c in diag],
            "diagnostic_canonical_candidates":diag,
            "canonical_start":rep.get("start_at"),
            "canonical_end":rep.get("end_at"),
            "exact_deltas":exact_deltas,
            "predecessor_mechanical_category":pr.get("primary_forensic_category"),
            "predecessor_secondary_flags":pr.get("secondary_flags") or [],
            "historical_provenance_summary":hist_summary,
            "canonical_provenance_summary":canon_summary,
            "historical_producer_commit":hist_commit or hist_lineage.get("commit"),
            "historical_producer_blob":hist_blob or next(iter(hist_lineage.get("blobs",{}).values()),None),
            "canonical_producer_commit":canon_lineage.get("commit") or canon_sources_lineage.get("commit"),
            "canonical_producer_blob":next(iter(canon_lineage.get("blobs",{}).values()),None) or next(iter(canon_sources_lineage.get("blobs",{}).values()),None),
            "historical_boundary_provenance_complete":hist_complete,
            "canonical_boundary_provenance_complete":canon_complete,
            "binding_state":"UNBOUND",
            "binding_changed":False,
        }
        cat,evidence=classify_proven(base_record,hist_source_ids,all_source_rows,canonical_text,hist_complete,canon_complete)
        if cat:
            base_record["root_cause_status"]="PROVEN"
            base_record["proven_root_cause_category"]=cat
            base_record["proof_evidence_references"]=[
                {"type":"frozen_snapshot","commit":SNAPSHOT_COMMIT,"path":SNAPSHOT_PATH},
                {"type":"historical_origin","commit":hist_commit,"path":origin_path,"blob":hist_blob},
                {"type":"canonical_db_rows","episode_uids":base_record["diagnostic_canonical_episode_uids"]},
                {"type":"canonical_code_lineage","commit":base_record["canonical_producer_commit"],"blob":base_record["canonical_producer_blob"]},
                {"type":"mechanism", "detail":evidence},
            ]
            base_record["best_supported_hypothesis"]=None
        else:
            base_record["root_cause_status"]="NOT_PROVEN"
            base_record["proven_root_cause_category"]=None
            base_record["proof_evidence_references"]=[
                {"type":"frozen_snapshot","commit":SNAPSHOT_COMMIT,"path":SNAPSHOT_PATH},
                {"type":"historical_origin","commit":hist_commit,"path":origin_path,"blob":hist_blob},
                {"type":"canonical_db_rows","episode_uids":base_record["diagnostic_canonical_episode_uids"]},
            ]
            base_record["best_supported_hypothesis"]=hypothesis_for(base_record,hist_source_ids,sorted(canon_ids),canonical_text)
        records_out.append(base_record)

    if len(records_out) != EXPECTED_TARGETS or len({r["classification_key"] for r in records_out}) != EXPECTED_TARGETS:
        fail("FORENSIC_OUTPUT_TARGET_COUNT_INVALID",len(records_out),"forensic output")
    if any(r["binding_state"]!="UNBOUND" or r["binding_changed"] for r in records_out):
        fail("BINDING_MUTATION_DETECTED",EXPECTED_TARGETS,"forensic output")
    if any(r["root_cause_status"] not in {"PROVEN","NOT_PROVEN"} for r in records_out):
        fail("ROOT_CAUSE_STATUS_MISSING",EXPECTED_TARGETS,"forensic output")
    if any(r["root_cause_status"]=="PROVEN" and r["proven_root_cause_category"] not in PROVEN_CATEGORIES for r in records_out):
        fail("PROVEN_CATEGORY_INVALID",EXPECTED_TARGETS,"forensic output")
    if any(r["root_cause_status"]=="NOT_PROVEN" and r["best_supported_hypothesis"] not in HYPOTHESES for r in records_out):
        fail("UNRESOLVED_HYPOTHESIS_INVALID",EXPECTED_TARGETS,"forensic output")

    proven=[r for r in records_out if r["root_cause_status"]=="PROVEN"]
    unresolved=[r for r in records_out if r["root_cause_status"]=="NOT_PROVEN"]
    by_cat=dict(sorted(Counter(r["proven_root_cause_category"] for r in proven).items()))
    by_hyp=dict(sorted(Counter(r["best_supported_hypothesis"] for r in unresolved).items()))
    by_city=dict(sorted(Counter(r["city_key"] for r in records_out).items()))

    sub60=[]
    gt30=[]
    for r in records_out:
        vals=[abs(float(x)) for x in r["exact_deltas"].values() if x is not None]
        if vals and max(vals)<=60:
            sub60.append(r)
        if vals and max(vals)>1800:
            gt30.append(r)
    sub60_proven=sum(r["root_cause_status"]=="PROVEN" and r["proven_root_cause_category"] in {
        "TIMESTAMP_PRECISION_NORMALIZATION_DIFFERENCE","HISTORICAL_BOUNDARY_NORMALIZATION_DIFFERENCE"
    } for r in sub60)
    gt30_causes=dict(sorted(Counter(r["proven_root_cause_category"] for r in gt30 if r["root_cause_status"]=="PROVEN").items()))

    groups=defaultdict(list)
    for r in proven:
        key=(r["proven_root_cause_category"],r.get("historical_producer_blob"),r.get("canonical_producer_blob"))
        groups[key].append(r["classification_key"])
    shared_groups=[
        {"root_cause_category":k[0],"historical_producer_blob":k[1],"canonical_producer_blob":k[2],
         "count":len(v),"classification_keys":v}
        for k,v in groups.items() if len(v)>=2
    ]

    db_prov_sha=sha256_bytes(canonical_json_bytes(db_prov_rows))
    reps=[]
    for r in records_out:
        if len(reps)>=5: break
        if r["root_cause_status"]=="PROVEN":
            reps.append({
                "classification_key":r["classification_key"],"city_key":r["city_key"],
                "status":"PROVEN","category":r["proven_root_cause_category"],
                "start_delta_seconds":r["exact_deltas"]["start_seconds"],
                "end_delta_seconds":r["exact_deltas"]["end_seconds"],
            })
    if len(reps)<5:
        for r in records_out:
            if len(reps)>=5: break
            if any(x["classification_key"]==r["classification_key"] for x in reps): continue
            reps.append({
                "classification_key":r["classification_key"],"city_key":r["city_key"],
                "status":r["root_cause_status"],"hypothesis":r["best_supported_hypothesis"],
                "start_delta_seconds":r["exact_deltas"]["start_seconds"],
                "end_delta_seconds":r["exact_deltas"]["end_seconds"],
            })

    summary={
        "verdict":"ATTACK-EVENT 25 UNBOUND BOUNDARY ROOT-CAUSE FORENSIC COMPLETED",
        "proof_branch":os.environ.get("GITHUB_REF_NAME"),
        "targets":EXPECTED_TARGETS,
        "proven_root_causes_count":len(proven),
        "unresolved_count":len(unresolved),
        "count_by_proven_root_cause_category":by_cat,
        "count_by_best_supported_hypothesis":by_hyp,
        "count_by_city":by_city,
        "count_with_complete_historical_provenance":sum(r["historical_boundary_provenance_complete"] for r in records_out),
        "count_with_complete_canonical_provenance":sum(r["canonical_boundary_provenance_complete"] for r in records_out),
        "sub_60_second_mismatch_count":len(sub60),
        "sub_60_second_proven_precision_or_normalization_count":sub60_proven,
        "gt_30_minute_mismatch_count":len(gt30),
        "gt_30_minute_proven_causes":gt30_causes,
        "shared_proven_mechanism_groups":shared_groups,
        "representative_cases":reps,
        "parent_corpus_sha256":parent_sha,
        "parent_corpus_sha_match":"YES",
        "forensic_db_provenance_sha256":db_prov_sha,
        "predecessor_run_id":PRED_RUN,
        "predecessor_job_id":PRED_JOB,
        "predecessor_artifact_id":PRED_ARTIFACT,
        "db_writes":0,
        "neon_mutations":0,
        "binding_changes":0,
    }
    full={
        "schema_version":1,
        "kind":"attack_event_25_unbound_boundary_root_cause_forensic",
        "frozen_inputs":{
            "predecessor":{"run_id":PRED_RUN,"job_id":PRED_JOB,"artifact_id":PRED_ARTIFACT,"artifact_name":PRED_ARTIFACT_NAME,"head_sha":PRED_HEAD},
            "snapshot":{"commit":SNAPSHOT_COMMIT,"path":SNAPSHOT_PATH,"sha256":SNAPSHOT_SHA256},
            "parent_binding_map":{"commit":BINDING_COMMIT,"path":BINDING_PATH,"sha256":BINDING_SHA256},
        },
        "summary":summary,
        "records":records_out,
        "db_provenance_rows":db_prov_rows,
    }
    write_json(FULL_PATH,full)
    write_json(SUMMARY_PATH,summary)
    print("ROOT_CAUSE_SUMMARY="+json.dumps(summary,ensure_ascii=False,sort_keys=True,separators=(",",":")))

except GateError as exc:
    blocked={
        "verdict":"ATTACK-EVENT 25 UNBOUND BOUNDARY ROOT-CAUSE FORENSIC BLOCKED",
        "first_failing_gate":exc.gate,
        "affected_count":exc.affected_count,
        "parent_corpus_sha_match":parent_sha_match,
        "provenance_source_that_failed":exc.provenance_source,
        "db_writes":0,
        "neon_mutations":0,
        "binding_changes":0,
        "safe_continuation_point":"Resume only the 25-case read-only provenance forensic from the failing provenance gate; repair nothing.",
    }
    if exc.detail is not None:
        blocked["detail"]=exc.detail
    write_json(SUMMARY_PATH,blocked)
    write_json(FULL_PATH,{"schema_version":1,"kind":"attack_event_25_unbound_boundary_root_cause_forensic",
                          "verdict":blocked["verdict"],"records":records_out,"blocked":blocked})
    print("ROOT_CAUSE_SUMMARY="+json.dumps(blocked,ensure_ascii=False,sort_keys=True,separators=(",",":")))
    sys.exit(1)
except Exception as exc:
    msg=str(exc)
    secret=os.environ.get("PHASE1_PROD_SHADOW_DATABASE_URL","")
    if secret:
        msg=msg.replace(secret,"<redacted>")
    blocked={
        "verdict":"ATTACK-EVENT 25 UNBOUND BOUNDARY ROOT-CAUSE FORENSIC BLOCKED",
        "first_failing_gate":"EXECUTION_HARNESS_FAILURE",
        "affected_count":EXPECTED_TARGETS,
        "parent_corpus_sha_match":parent_sha_match,
        "provenance_source_that_failed":"execution harness",
        "detail":{"error_type":type(exc).__name__,"error":msg[:1000]},
        "db_writes":0,"neon_mutations":0,"binding_changes":0,
        "safe_continuation_point":"Resume only the forensic execution harness; repair no production or binding state.",
    }
    write_json(SUMMARY_PATH,blocked)
    write_json(FULL_PATH,{"schema_version":1,"kind":"attack_event_25_unbound_boundary_root_cause_forensic",
                          "verdict":blocked["verdict"],"records":records_out,"blocked":blocked})
    print("ROOT_CAUSE_SUMMARY="+json.dumps(blocked,ensure_ascii=False,sort_keys=True,separators=(",",":")))
    sys.exit(1)
finally:
    if cur is not None:
        try: cur.execute("ROLLBACK")
        except Exception: pass
    if conn is not None:
        try: conn.close()
        except Exception: pass
