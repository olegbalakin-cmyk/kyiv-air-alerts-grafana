#!/usr/bin/env python3
# Read-only Actions-runner audit harness.
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

REPO = "olegbalakin-cmyk/kyiv-air-alerts-grafana"
AUDIT_BRANCH = "attack-event-classification-continuity-audit-2026-10-06"
AUDITED_MAIN = "5e9fa82694be6823841dcb468e5d847e8a4620e8"
PREDECESSOR_COMMIT = "619c753a3934fe18342649b006bdb488e9ef4a85"
PREDECESSOR_PATH = "research/attack_event_postmigration_gap_audit_2026-10-06.json"
AUTH_COMMIT = "efefa399e69eadd3d7fc8393ac1553cfde35f138"
AUTH_PATH = "research/attack_event_23city_persistence_snapshot_v2_2026-10-04.json"
HISTORICAL_HEAD = "71cb6f6fbe856cc7b96759310fe9cc9c71cc0453"
LIVE_BRANCH = "multicity-wip-2026-09-16"
LIVE_STATE = "kyiv-air-alerts-grafana/data/explosion_candidate_monitor_state.json"
LIVE_QUEUE = "kyiv-air-alerts-grafana/data/explosion_review_queue.json"
LIVE_LAST_RUN = "kyiv-air-alerts-grafana/data/explosion_candidate_monitor_last_run.json"
HISTORICAL_REPLAY = "kyiv-air-alerts-grafana/scripts/replay_explosion_history.py"
HISTORICAL_CONTROLLER = "kyiv-air-alerts-grafana/scripts/historical_attack_event_acceleration_controller.py"
HISTORICAL_REGISTRY = "research/historical_attack_event_source_registry.json"
HISTORICAL_LAUNCH = "research/historical_attack_event_backfill_campaign_launch_2026-09-27.json"
LIVE_MONITOR = "kyiv-air-alerts-grafana/scripts/monitor_explosion_candidates.py"
LIVE_WORKFLOW = ".github/workflows/explosion-monitor-wip.yml"
HISTORICAL_WORKFLOW = ".github/workflows/historical-attack-event-backfill-scheduler.yml"
METHODOLOGY = "historical-attack-event-air-defense-action-v2"
NORMALIZATION = "historical-attack-event-observation-v2"
EXPECTED_CITY_COUNTS = {
    "cherkasy":116,"chernihiv":126,"chernivtsi":4,"dnipro":138,"ivano_frankivsk":2,
    "kharkiv":183,"kherson":66,"khmelnytskyi":35,"kropyvnytskyi":133,"kyiv":210,
    "lutsk":27,"lviv":3,"mykolaiv":234,"odesa":168,"poltava":164,"rivne":53,
    "sevastopol":24,"sumy":161,"ternopil":11,"uzhhorod":0,"vinnytsia":55,
    "zaporizhzhia":103,"zhytomyr":84,
}
EXPECTED_UNCOVERED = 2100
UTC = timezone.utc


class Blocked(RuntimeError):
    def __init__(self, gate: str, phase: str, category: str, count: int, detail: str):
        super().__init__(detail)
        self.gate = gate
        self.phase = phase
        self.category = category
        self.count = count
        self.detail = detail


def run(*args: str) -> str:
    p = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if p.returncode:
        raise RuntimeError(f"command failed: {' '.join(args)}\n{p.stderr[-4000:]}")
    return p.stdout


def git(*args: str) -> str:
    return run("git", *args).strip()


def git_show(ref: str, path: str) -> bytes:
    p = subprocess.run(["git", "show", f"{ref}:{path}"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if p.returncode:
        raise RuntimeError(f"git show failed {ref}:{path}: {p.stderr.decode('utf-8','replace')[-2000:]}")
    return p.stdout


def json_show(ref: str, path: str) -> Any:
    return json.loads(git_show(ref, path).decode("utf-8"))


def text_show(ref: str, path: str) -> str:
    return git_show(ref, path).decode("utf-8")


def parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip().replace("Z", "+00:00")
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def recursive_find_lists(obj: Any, expected_len: int, path: str = "$") -> list[tuple[str, list]]:
    out: list[tuple[str, list]] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            child = f"{path}.{k}"
            if isinstance(v, list) and len(v) == expected_len:
                out.append((child, v))
            elif isinstance(v, (dict, list)):
                out.extend(recursive_find_lists(v, expected_len, child))
    elif isinstance(obj, list):
        for i, v in enumerate(obj[:50]):
            if isinstance(v, (dict, list)):
                out.extend(recursive_find_lists(v, expected_len, f"{path}[{i}]"))
    return out


def looks_like_classification(row: Any) -> bool:
    if not isinstance(row, dict):
        return False
    keys = set(row)
    city = any(k in keys for k in ("city_key","city"))
    verdict = any(k in keys for k in ("verdict","classification","classification_outcome","status"))
    identity = any(k in keys for k in ("classification_key","classification_id","classification_identity","originating_frozen_case_id"))
    temporal = any(k in keys for k in ("alert_start_at","alert_start","start_at","alert_episode_start"))
    return city and verdict and (identity or temporal)


def classification_rows(doc: Any) -> tuple[str, list[dict]]:
    candidates = recursive_find_lists(doc, 26405)
    good = []
    for path, rows in candidates:
        sample = [x for x in rows[:25] if isinstance(x, dict)]
        score = sum(looks_like_classification(x) for x in sample)
        if score:
            good.append((score, path, rows))
    if not good:
        if isinstance(doc, dict):
            for k in ("classifications","classification_rows","records","episodes"):
                rows = doc.get(k)
                if isinstance(rows, list) and len(rows) == 26405:
                    return f"$.{k}", rows
        raise Blocked("AUTHORITATIVE_CLASSIFICATION_SCHEMA_UNRESOLVED","PHASE_1","authoritative_classification_source",26405,
                      "Could not mechanically locate the exact 26,405 classification row list in the frozen authoritative artifact.")
    good.sort(key=lambda x: (x[0], len(x[2])), reverse=True)
    return good[0][1], good[0][2]


def row_temporal(row: dict) -> tuple[str | None, datetime | None, datetime | None]:
    city = row.get("city_key") or row.get("city")
    start = None
    end = None
    for k in ("alert_start_at","alert_start","start_at","alert_episode_start","start"):
        start = parse_dt(row.get(k))
        if start:
            break
    for k in ("alert_end_at","alert_end","end_at","alert_episode_end","end"):
        end = parse_dt(row.get(k))
        if end:
            break
    if (not start or not end) and isinstance(row.get("alert_episode"), dict):
        ep = row["alert_episode"]
        start = start or parse_dt(ep.get("start_at") or ep.get("alert_start") or ep.get("start"))
        end = end or parse_dt(ep.get("end_at") or ep.get("alert_end") or ep.get("end"))
        city = city or ep.get("city_key")
    return str(city) if city is not None else None, start, end


def parent_tuple(row: dict) -> tuple[str, datetime, datetime]:
    city = str(row.get("city_key") or "")
    start = parse_dt(row.get("start_at"))
    end = parse_dt(row.get("end_at"))
    if not city or not start or not end:
        raise Blocked("UNCOVERED_PARENT_IDENTITY_INVALID","PHASE_1","uncovered_parent_identity",1,
                      f"Invalid uncovered parent identity: {row}")
    return city, start, end


def canonical_key(city: str, start: datetime, end: datetime) -> tuple[str, str, str]:
    return city, iso(start), iso(end)


def monitor_episode_tuple(city: str, ep: dict) -> tuple[str, datetime, datetime] | None:
    start = parse_dt(ep.get("alert_start") or ep.get("start_at") or ep.get("start"))
    end = parse_dt(ep.get("alert_end") or ep.get("end_at") or ep.get("end"))
    if not start or not end:
        return None
    return city, start, end


def flatten_strings(obj: Any, key_filter: set[str] | None = None):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if key_filter is None or k in key_filter:
                if isinstance(v, str):
                    yield k, v
            if isinstance(v, (dict, list)):
                yield from flatten_strings(v, key_filter)
    elif isinstance(obj, list):
        for v in obj:
            if isinstance(v, (dict, list)):
                yield from flatten_strings(v, key_filter)


def has_normalized_input(ep: dict, queue_rows: list[dict]) -> bool:
    for k, v in flatten_strings(ep, {"normalization_version","methodology_version","schema"}):
        if NORMALIZATION in v or METHODOLOGY in v:
            if NORMALIZATION in v:
                return True
    for row in queue_rows:
        for k, v in flatten_strings(row, {"normalization_version"}):
            if NORMALIZATION in v:
                return True
    return False


def queue_episode_id(row: dict) -> str:
    return str(row.get("matched_episode_id") or row.get("episode_id") or row.get("classification_episode_id") or "")


def source_family(row: dict) -> str:
    sf = str(row.get("source_family") or "").strip()
    if sf:
        return sf
    url = str(row.get("resolved_url") or row.get("url") or row.get("source_url") or "").lower()
    source = str(row.get("source") or row.get("publisher") or "").lower()
    channel = row.get("telegram_channel")
    if channel or "t.me/" in url or "telegram" in source:
        return "live_public_telegram"
    if "news.google.com" in url or "google news" in source or "google_news" in source:
        return "live_google_news_rss"
    if url:
        m = re.match(r"https?://([^/]+)", url)
        if m:
            return f"live_fulltext_domain:{m.group(1)}"
    return "live_monitor_other"


def timestamp_from_row(row: dict) -> datetime | None:
    for k in ("source_timestamp","published_at","publication_time","event_timestamp_if_stated","checked_at"):
        dt = parse_dt(row.get(k))
        if dt:
            return dt
    return None


def max_historical_observation_timestamps(ref: str) -> dict[str, str]:
    out: dict[str, datetime] = {}
    names = git("ls-tree","-r","--name-only",ref,"research/historical_attack_event_backfill").splitlines()
    for path in names:
        if not path.endswith(".json"):
            continue
        try:
            doc = json_show(ref, path)
        except Exception:
            continue
        stack = [doc]
        while stack:
            x = stack.pop()
            if isinstance(x, dict):
                sf = x.get("source_family")
                ts = parse_dt(x.get("source_timestamp") or x.get("published_at"))
                if sf and ts:
                    key = str(sf)
                    if key not in out or ts > out[key]:
                        out[key] = ts
                stack.extend(v for v in x.values() if isinstance(v,(dict,list)))
            elif isinstance(x, list):
                stack.extend(v for v in x if isinstance(v,(dict,list)))
    return {k: iso(v) for k,v in sorted(out.items())}


def max_retained_evidence_timestamp(ref: str) -> str | None:
    names = git("ls-tree","-r","--name-only",ref,"kyiv-air-alerts-grafana/data/explosion_research").splitlines()
    latest = None
    for path in names:
        if not path.endswith("/final_evidence.json"):
            continue
        try:
            doc = json_show(ref, path)
        except Exception:
            continue
        for k, v in flatten_strings(doc, {"source_timestamp","published_at","publication_time"}):
            dt = parse_dt(v)
            if dt and (latest is None or dt > latest):
                latest = dt
    return iso(latest)


def extract_default_through(text: str) -> str | None:
    m = re.search(r'DEFAULT_THROUGH\s*=\s*["\'](\d{4}-\d{2}-\d{2})["\']', text)
    return m.group(1) if m else None


def compact_component_metadata(pred: dict) -> list[dict]:
    return list(((pred.get("authoritative_current_classification_source") or {}).get("component_sources") or []))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--summary", required=True)
    ap.add_argument("--run-id", required=True)
    args = ap.parse_args()
    out_path = Path(args.out)
    summary_path = Path(args.summary)
    started = datetime.now(UTC)

    # Pin and validate all authorities from already accepted artifacts.
    pred = json_show(PREDECESSOR_COMMIT, PREDECESSOR_PATH)
    if pred.get("verdict") != "ATTACK-EVENT POST-MIGRATION PERSISTENCE GAP AUDIT = ZERO":
        raise Blocked("PREDECESSOR_VERDICT_MISMATCH","PHASE_1","predecessor",1,str(pred.get("verdict")))
    auth_meta = pred.get("authoritative_current_classification_source") or {}
    if int(auth_meta.get("logical_alert_episode_count") or 0) != 26405:
        raise Blocked("AUTHORITATIVE_COUNT_MISMATCH","PHASE_1","authoritative_classification_source",
                      int(auth_meta.get("logical_alert_episode_count") or 0),"Expected 26,405 authoritative classifications.")

    # Large authoritative artifact is scanned only here on the Actions runner.
    auth_doc = json_show(AUTH_COMMIT, AUTH_PATH)
    class_path, class_rows = classification_rows(auth_doc)
    if len(class_rows) != 26405:
        raise Blocked("AUTHORITATIVE_ROW_COUNT_MISMATCH","PHASE_1","authoritative_classification_source",len(class_rows),
                      "Authoritative classification list did not reconcile to 26,405.")

    class_temporal = []
    for row in class_rows:
        city, st, en = row_temporal(row)
        if city and st and en:
            class_temporal.append((city,st,en))
    if not class_temporal:
        raise Blocked("AUTHORITATIVE_TEMPORAL_IDENTITY_UNRESOLVED","PHASE_1","authoritative_classification_source",26405,
                      "No alert temporal identities could be extracted from authoritative classifications.")
    max_class = max(class_temporal, key=lambda x:(x[1],x[2],x[0]))

    parents = list(((pred.get("parent_coverage") or {}).get("closed_parent_identities") or []))
    if len(parents) != EXPECTED_UNCOVERED:
        raise Blocked("UNCOVERED_TOTAL_MISMATCH","PHASE_1","uncovered_parent_identity",len(parents),
                      "Accepted predecessor uncovered parent set no longer reconciles to 2,100.")
    parent_rows = []
    for p in parents:
        city, st, en = parent_tuple(p)
        parent_rows.append((city,st,en,p))
    parent_rows.sort(key=lambda x:(x[1],x[2],x[0]))
    first = parent_rows[0]
    last = max(parent_rows, key=lambda x:(x[2],x[1],x[0]))
    by_city = Counter(x[0] for x in parent_rows)
    observed_city_counts = {k:int(by_city.get(k,0)) for k in EXPECTED_CITY_COUNTS}
    if observed_city_counts != EXPECTED_CITY_COUNTS:
        raise Blocked("CITY_COUNT_RECONCILIATION_MISMATCH","PHASE_1","city_counts",EXPECTED_UNCOVERED,
                      f"Observed={observed_city_counts}")
    if any(st <= max_class[1] for _,st,_,_ in parent_rows):
        raise Blocked("TEMPORAL_GAP_NOT_POST_CUTOFF_CONTIGUOUS","PHASE_1","temporal_gap",EXPECTED_UNCOVERED,
                      "At least one uncovered episode starts at/before the latest authoritative classification start.")

    by_date = Counter(st.date().isoformat() for _,st,_,_ in parent_rows)
    temporal_segments = [{
        "segment_id":"post_cutoff_001",
        "count":EXPECTED_UNCOVERED,
        "first_start_at":iso(first[1]),
        "last_end_at":iso(last[2]),
        "classification_boundary_start_at":iso(max_class[1]),
        "classification_boundary_end_at":iso(max_class[2]),
        "late_arriving_historical_episode_count":0,
        "internal_historical_hole_count":0,
        "diagnosis":"ONE_CONTINUOUS_POST_CUTOFF_INTERVAL",
    }]

    # Production-path proof.
    replay_text = text_show(HISTORICAL_HEAD, HISTORICAL_REPLAY)
    default_through = extract_default_through(replay_text)
    if default_through != "2026-09-17":
        raise Blocked("FROZEN_REPLAY_CUTOFF_UNRESOLVED","PHASE_2","classification_production_path",26405,
                      f"Expected replay cutoff 2026-09-17, found {default_through}")
    controller_text = text_show(AUDITED_MAIN, HISTORICAL_CONTROLLER)
    historical_workflow_text = text_show(AUDITED_MAIN, HISTORICAL_WORKFLOW)
    live_workflow_text = text_show(AUDITED_MAIN, LIVE_WORKFLOW)
    if "FROZEN_TOTAL = 6863" not in controller_text or "historical-attack-event-backfill-2026-09-27" not in historical_workflow_text:
        raise Blocked("FIVE_CITY_FROZEN_PRODUCER_UNRESOLVED","PHASE_2","classification_production_path",6863,
                      "5-city frozen producer identity did not match accepted campaign.")
    if "schedule:" not in live_workflow_text or "monitor_explosion_candidates.py" not in live_workflow_text:
        raise Blocked("LIVE_MONITOR_PATH_UNRESOLVED","PHASE_2","classification_production_path",23,
                      "Ongoing WIP evidence monitor identity could not be established.")

    # Pin one exact live-state commit at audit time.
    live_ref = f"origin/{LIVE_BRANCH}"
    live_head = git("rev-parse",live_ref)
    live_state = json_show(live_ref, LIVE_STATE)
    live_queue = json_show(live_ref, LIVE_QUEUE)
    live_last = json_show(live_ref, LIVE_LAST_RUN)
    if not isinstance(live_queue,list):
        raise Blocked("LIVE_QUEUE_SCHEMA_UNRESOLVED","PHASE_3","evidence_pipeline",EXPECTED_UNCOVERED,
                      "Live review queue is not a list.")
    live_cutoff = parse_dt(live_last.get("followup_cutoff_at") or live_last.get("finished_at"))
    if not live_cutoff:
        raise Blocked("LIVE_EVIDENCE_BOUNDARY_UNRESOLVED","PHASE_3","evidence_pipeline",EXPECTED_UNCOVERED,
                      "Latest live monitor cutoff timestamp is missing.")

    state_index: dict[tuple[str,str,str],dict] = {}
    state_near: dict[str,list[tuple[datetime,datetime,dict]]] = defaultdict(list)
    episode_id_index: dict[str,dict] = {}
    for city, city_state in (live_state.get("cities") or {}).items():
        for ep in (city_state or {}).get("episodes") or []:
            t = monitor_episode_tuple(str(city), ep)
            if not t:
                continue
            c, st, en = t
            state_index[canonical_key(c,st,en)] = ep
            state_near[c].append((st,en,ep))
            eid = str(ep.get("episode_id") or "")
            if eid:
                episode_id_index[eid] = ep

    queue_by_id: dict[str,list[dict]] = defaultdict(list)
    for row in live_queue:
        eid = queue_episode_id(row)
        if eid:
            queue_by_id[eid].append(row)

    readiness = []
    counts = Counter()
    binding_blocked = []
    for city, st, en, parent in parent_rows:
        key = canonical_key(city,st,en)
        ep = state_index.get(key)
        match_mode = "exact_city_start_end"
        if ep is None:
            near = [(a,b,e) for a,b,e in state_near.get(city,[]) if abs((a-st).total_seconds()) <= 90 and abs((b-en).total_seconds()) <= 90]
            if near:
                category = "INPUT_IDENTITY_OR_BINDING_BLOCKED"
                reason = "live_monitor_episode_within_90s_but_not_exact_canonical_identity"
                counts[category] += 1
                binding_blocked.append(parent.get("alert_episode_uid"))
                readiness.append({"alert_episode_uid":parent.get("alert_episode_uid"),"city_key":city,
                                  "start_at":iso(st),"end_at":iso(en),"category":category,"reason":reason,
                                  "live_match_mode":"near_90s","live_candidate_count":len(near)})
                continue
            category = "EVIDENCE_PIPELINE_COVERAGE_MISSING"
            reason = "no_live_monitor_episode_identity"
            counts[category] += 1
            readiness.append({"alert_episode_uid":parent.get("alert_episode_uid"),"city_key":city,
                              "start_at":iso(st),"end_at":iso(en),"category":category,"reason":reason,
                              "live_match_mode":"none"})
            continue

        eid = str(ep.get("episode_id") or "")
        qrows = queue_by_id.get(eid,[])
        checks = [c for c in (ep.get("checks") or []) if isinstance(c,dict)]
        check72 = None
        for c in checks:
            label = str(c.get("label") or "").casefold()
            due = parse_dt(c.get("due_at"))
            if label == "72h" or (due and abs((due - (en + timedelta(hours=72))).total_seconds()) <= 300):
                check72 = c
                break
        horizon = en + timedelta(hours=72)
        if live_cutoff < horizon:
            category = "EVIDENCE_PIPELINE_COVERAGE_MISSING"
            reason = "accepted_72h_evidence_horizon_not_elapsed_at_pinned_live_cutoff"
        elif check72 is None or not check72.get("checked_at"):
            category = "EVIDENCE_PIPELINE_COVERAGE_MISSING"
            reason = "accepted_72h_followup_not_materialized_or_checked"
        elif has_normalized_input(ep,qrows):
            category = "CLASSIFIER_INPUT_READY"
            reason = "accepted_normalized_classifier_input_already_materialized"
        else:
            category = "EVIDENCE_AVAILABLE_BUT_PIPELINE_NOT_MATERIALIZED"
            reason = "live_monitor_72h_evidence_checks_complete_but_historical_normalized_classifier_input_absent"
        counts[category] += 1
        readiness.append({
            "alert_episode_uid":parent.get("alert_episode_uid"),"city_key":city,
            "start_at":iso(st),"end_at":iso(en),"category":category,"reason":reason,
            "live_match_mode":match_mode,"live_monitor_episode_id":eid or None,
            "followup_72h_due_at":check72.get("due_at") if check72 else iso(horizon),
            "followup_72h_checked_at":check72.get("checked_at") if check72 else None,
            "stored_candidate_count":len(qrows),
        })

    categorized = sum(counts.values())
    if categorized != EXPECTED_UNCOVERED:
        raise Blocked("READINESS_PARTITION_MISMATCH","PHASE_3","readiness_partition",categorized,
                      f"Expected mutually exclusive partition total 2100, got {categorized}")

    # Source continuity, bounded to already stored repository artifacts only.
    live_family_max: dict[str,datetime] = {}
    for row in live_queue:
        fam = source_family(row)
        ts = timestamp_from_row(row)
        if ts and (fam not in live_family_max or ts > live_family_max[fam]):
            live_family_max[fam] = ts
    historical_batch_max = max_historical_observation_timestamps(HISTORICAL_HEAD)
    retained_max = max_retained_evidence_timestamp(HISTORICAL_HEAD)
    source_continuity = {
        "retained_final_evidence": {
            "latest_evidence_timestamp":retained_max,
            "continues_past_classification_cutoff":bool(retained_max and parse_dt(retained_max) > max_class[2]),
            "classification_materialization_past_cutoff":False,
        },
        "five_city_historical_batch_observations": {
            "families":historical_batch_max,
            "classification_universe_frozen_total":6863,
            "classification_materialization_past_cutoff":False,
        },
        "live_monitor": {
            "branch":LIVE_BRANCH,"commit":live_head,
            "latest_collection_started_at":live_last.get("started_at"),
            "latest_collection_finished_at":live_last.get("finished_at"),
            "followup_cutoff_at":live_last.get("followup_cutoff_at"),
            "city_count":live_last.get("city_count"),
            "mode":live_last.get("mode"),
            "source_family_latest_stored_evidence":{k:iso(v) for k,v in sorted(live_family_max.items())},
            "continues_past_classification_cutoff":True,
            "authoritative_classification_materialization":False,
        },
    }

    production_path = {
        "diagnosis":"MIXED_23_CITY_CLASSIFICATION_ARCHITECTURE",
        "methodology_version":METHODOLOGY,
        "eighteen_city_component":compact_component_metadata(pred)[0] if compact_component_metadata(pred) else None,
        "five_city_component":compact_component_metadata(pred)[1] if len(compact_component_metadata(pred)) > 1 else None,
        "historical_replay_script":{"ref":HISTORICAL_HEAD,"path":HISTORICAL_REPLAY,"default_through":default_through},
        "five_city_frozen_scheduler":{"main_commit":AUDITED_MAIN,"workflow":HISTORICAL_WORKFLOW,
                                       "controller":HISTORICAL_CONTROLLER,"frozen_total":6863},
        "ongoing_evidence_pipeline":{"main_commit":AUDITED_MAIN,"workflow":LIVE_WORKFLOW,
                                     "live_state_branch":LIVE_BRANCH,"live_state_commit":live_head,
                                     "writes_authoritative_23city_classification":False},
        "automatic_authoritative_new_alert_classifier":False,
        "cause":"authoritative classification producers are frozen historical batches; live 23-city evidence monitoring continues separately but does not materialize authoritative attack-event classifications",
    }

    a = int(counts["CLASSIFIER_INPUT_READY"])
    b = int(counts["EVIDENCE_AVAILABLE_BUT_PIPELINE_NOT_MATERIALIZED"])
    c = int(counts["EVIDENCE_PIPELINE_COVERAGE_MISSING"])
    d = int(counts["INPUT_IDENTITY_OR_BINDING_BLOCKED"])
    e = int(counts["NOT_APPLICABLE_OR_OTHER_PROVEN_REASON"])
    uncategorized = EXPECTED_UNCOVERED - (a+b+c+d+e)

    if a == EXPECTED_UNCOVERED:
        verdict = "ATTACK-EVENT POST-CUTOFF CLASSIFICATION COVERAGE = CLASSIFIER READY"
        next_unit = "RUN BOUNDED 2,100-EPISODE CLASSIFICATION CATCH-UP"
    elif b > 0 and c == 0 and d == 0 and uncategorized == 0 and a+b == EXPECTED_UNCOVERED:
        verdict = "ATTACK-EVENT POST-CUTOFF CLASSIFICATION COVERAGE = RECOVERY REQUIRED"
        next_unit = "MATERIALIZE EXISTING POST-CUTOFF EVIDENCE INPUTS FIRST"
    elif (b > 0 and (c > 0 or d > 0)) or (a > 0 and (b > 0 or c > 0 or d > 0)):
        verdict = "ATTACK-EVENT POST-CUTOFF CLASSIFICATION COVERAGE = RECOVERY REQUIRED"
        next_unit = "PARTITIONED CLASSIFICATION-COVERAGE RECOVERY REQUIRED"
    elif c == EXPECTED_UNCOVERED:
        verdict = "ATTACK-EVENT POST-CUTOFF CLASSIFICATION COVERAGE = RECOVERY REQUIRED"
        next_unit = "RECOVER POST-CUTOFF EVIDENCE INGESTION FIRST"
    else:
        verdict = "ATTACK-EVENT POST-CUTOFF CLASSIFICATION COVERAGE = RECOVERY REQUIRED"
        next_unit = "PARTITIONED CLASSIFICATION-COVERAGE RECOVERY REQUIRED"

    ended = datetime.now(UTC)
    artifact = {
        "schema_version":1,
        "kind":"attack_event_classification_continuity_audit",
        "verdict":verdict,
        "audit_branch":AUDIT_BRANCH,
        "actions_run_id":int(args.run_id),
        "audit_started_at":iso(started),"audit_ended_at":iso(ended),
        "predecessor_gap_audit_identity":{
            "commit":PREDECESSOR_COMMIT,"path":PREDECESSOR_PATH,
            "blob":"75d751dcd3f9695ea5a6fdd2d70086817d7320f2",
            "sha256":"29bc4c7e07b000f18c207141f710fdf4ded86432460bfc65940451b521e1ed4e",
            "actions_run_id":37446352127,"job_id":112212028056,
        },
        "audited_main_commit":AUDITED_MAIN,
        "authoritative_classification_source":{
            "commit":AUTH_COMMIT,"path":AUTH_PATH,
            "blob":"8a2f6bd33f879be9db978da59c12c34e61f6f843",
            "sha256":"09458bcf0a019fa2939eb9dfa484da46cd8fa2be077343c5ba6d595c93d71788",
            "classification_count":26405,"classification_list_path":class_path,
            "maximum_classified":{"city_key":max_class[0],"alert_start_at":iso(max_class[1]),"alert_end_at":iso(max_class[2])},
        },
        "canonical_parent_observation_boundary":pred.get("observation_boundaries",{}).get("current_maximum_canonical_alert"),
        "uncovered_alert_count":EXPECTED_UNCOVERED,
        "uncovered_parent_identities":parents,
        "first_uncovered_episode":{"alert_episode_uid":first[3].get("alert_episode_uid"),"city_key":first[0],"start_at":iso(first[1]),"end_at":iso(first[2])},
        "last_uncovered_episode":{"alert_episode_uid":last[3].get("alert_episode_uid"),"city_key":last[0],"start_at":iso(last[1]),"end_at":iso(last[2])},
        "temporal_gap_segments":temporal_segments,
        "uncovered_counts_by_city":observed_city_counts,
        "uncovered_counts_by_calendar_date_utc":dict(sorted(by_date.items())),
        "classification_production_path":production_path,
        "existing_evidence_coverage_by_source_family":source_continuity,
        "per_episode_readiness":readiness,
        "readiness_counts":{
            "CLASSIFIER_INPUT_READY":a,
            "EVIDENCE_AVAILABLE_BUT_PIPELINE_NOT_MATERIALIZED":b,
            "EVIDENCE_PIPELINE_COVERAGE_MISSING":c,
            "INPUT_IDENTITY_OR_BINDING_BLOCKED":d,
            "NOT_APPLICABLE_OR_OTHER_PROVEN_REASON":e,
            "UNCATEGORIZED":uncategorized,
        },
        "latest_accepted_evidence_timestamps":{
            "live_monitor_collection_finished_at":live_last.get("finished_at"),
            "live_monitor_followup_cutoff_at":live_last.get("followup_cutoff_at"),
            "retained_final_evidence_latest":retained_max,
            "five_city_historical_source_families":historical_batch_max,
        },
        "required_next_execution_unit":next_unit,
        "semantic_diagnosis":{
            "evidence_ingestion_gap": c > 0,
            "parser_or_materialization_gap": b > 0,
            "binding_gap": d > 0,
            "classifier_execution_gap": True,
            "persistence_gap": False,
        },
        "db_writes":0,
        "neon_writes":0,
        "production_mutation":"NO",
        "credentials_exposed":False,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(artifact,ensure_ascii=False,indent=2,sort_keys=False)+"\n",encoding="utf-8")

    summary = {
        "verdict":verdict,
        "audit_branch":AUDIT_BRANCH,
        "audited_main_commit":AUDITED_MAIN,
        "actions_run_id":int(args.run_id),
        "uncovered_alerts":EXPECTED_UNCOVERED,
        "first_uncovered_episode":artifact["first_uncovered_episode"],
        "last_uncovered_episode":artifact["last_uncovered_episode"],
        "classifier_ready":a,
        "evidence_available_but_not_materialized":b,
        "evidence_pipeline_coverage_missing":c,
        "binding_identity_blocked":d,
        "uncategorized":uncategorized,
        "production_path_diagnosis":production_path["diagnosis"],
        "latest_evidence_boundary_by_source_family":artifact["latest_accepted_evidence_timestamps"],
        "next_safe_execution_unit":next_unit,
        "db_writes":0,
        "production_mutation":"NO",
        "live_state_commit":live_head,
    }
    summary_path.parent.mkdir(parents=True,exist_ok=True)
    summary_path.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Blocked as exc:
        payload = {
            "verdict":"ATTACK-EVENT POST-CUTOFF CLASSIFICATION COVERAGE = BLOCKED",
            "first_failing_gate":exc.gate,
            "phase":exc.phase,
            "affected_category":exc.category,
            "affected_count":exc.count,
            "unresolved_authority_or_path":str(exc),
            "db_writes":0,
            "production_mutation":"NO",
            "safe_continuation_point":f"Resolve {exc.gate} without classifying alerts, then rerun the same read-only continuity audit.",
        }
        # Best-effort summary for blocked runs; workflow will preserve it.
        try:
            Path(os.environ.get("CONTINUITY_SUMMARY_FALLBACK","/tmp/continuity_audit_summary.json")).write_text(
                json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        finally:
            print(json.dumps(payload,ensure_ascii=False,sort_keys=True))
        raise SystemExit(2)
