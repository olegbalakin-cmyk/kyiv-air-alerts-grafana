#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

REPO = "olegbalakin-cmyk/kyiv-air-alerts-grafana"
AUDIT_BRANCH = "attack-event-partitioned-classification-recovery-audit-2026-10-06"
FROZEN_COMMIT = "48099cd6d93c2b911e331e79b5141dd482d242a8"
CONTINUITY_PATH = "research/attack_event_classification_continuity_audit_2026-10-06.json"
CONTINUITY_BLOB = "57240aa3569b342f317f077b026928c2de21cfc8"
CONTINUITY_SHA256 = "6bf02b2686f3f37de31965ebda786969cdcc83a80a27cf2a452f3de31158932c"
CONTINUITY_VERDICT = "ATTACK-EVENT POST-CUTOFF CLASSIFICATION COVERAGE = RECOVERY REQUIRED"
HISTORICAL_HEAD = "71cb6f6fbe856cc7b96759310fe9cc9c71cc0453"
HISTORICAL_BRANCH = "historical-attack-event-backfill-2026-09-27"
HISTORICAL_WORKER = "kyiv-air-alerts-grafana/scripts/run_historical_attack_event_backfill_batch.py"
HISTORICAL_WORKER_BLOB = "cb2791bd309abacf4c3aae8fee0d1a8f038220b2"
CLASSIFIER = "kyiv-air-alerts-grafana/scripts/monitor_explosion_candidates.py"
CLASSIFIER_BLOB = "778469b74c2aa807d851cf2c2ee35cf4aa785589"
HISTORICAL_LAUNCH = "research/historical_attack_event_backfill_campaign_launch_2026-09-27.json"
HISTORICAL_STATUS = "research/historical_attack_event_backfill_status.json"
LIVE_BRANCH = "multicity-wip-2026-09-16"
LIVE_STATE = "kyiv-air-alerts-grafana/data/explosion_candidate_monitor_state.json"
LIVE_QUEUE = "kyiv-air-alerts-grafana/data/explosion_review_queue.json"
LIVE_LAST_RUN = "kyiv-air-alerts-grafana/data/explosion_candidate_monitor_last_run.json"
LIVE_BASELINE = "kyiv-air-alerts-grafana/data/explosion_audited_baseline.json"
METHODOLOGY = "historical-attack-event-air-defense-action-v2"
NORMALIZATION = "historical-attack-event-observation-v2"
EXPECTED_COUNTS = {
    "CLASSIFIER_INPUT_READY": 0,
    "EVIDENCE_AVAILABLE_BUT_PIPELINE_NOT_MATERIALIZED": 1737,
    "EVIDENCE_PIPELINE_COVERAGE_MISSING": 328,
    "INPUT_IDENTITY_OR_BINDING_BLOCKED": 35,
    "NOT_APPLICABLE_OR_OTHER_PROVEN_REASON": 0,
    "UNCATEGORIZED": 0,
}
EXPECTED_TOTAL = 2100
UTC = timezone.utc
KYIV_TZ = ZoneInfo("Europe/Kyiv")
TERMINAL_HISTORICAL = {
    "STRICT_EVENT_POSITIVE", "SENSITIVITY_EVENT_POSITIVE",
    "NO_CONFIRMED_EVENT", "NEEDS_REVIEW",
}
CANDIDATE_REQUIRED = ("candidate_id", "city_key", "source", "url", "title")
CANDIDATE_OPTIONAL = (
    "publisher", "publisher_url", "published_at", "snippet",
    "discovery_basis", "resolved_url", "matched_text_excerpt", "review_provenance",
)
PARENT_UID_KEYS = (
    "alert_episode_uid", "canonical_parent_uid", "parent_alert_episode_uid",
    "canonical_alert_episode_uid",
)


class Blocked(RuntimeError):
    def __init__(self, gate: str, phase: str, cohort: str, count: int, detail: str,
                 reconciled: int = 0):
        super().__init__(detail)
        self.gate = gate
        self.phase = phase
        self.cohort = cohort
        self.count = int(count)
        self.detail = detail
        self.reconciled = int(reconciled)


def run(*args: str) -> str:
    p = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if p.returncode:
        raise RuntimeError(f"command failed: {' '.join(args)}\n{p.stderr[-4000:]}")
    return p.stdout


def git(*args: str) -> str:
    return run("git", *args).strip()


def git_show(ref: str, path: str) -> bytes:
    p = subprocess.run(["git", "show", f"{ref}:{path}"], stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, check=False)
    if p.returncode:
        raise RuntimeError(
            f"git show failed {ref}:{path}: "
            + p.stderr.decode("utf-8", "replace")[-2000:]
        )
    return p.stdout


def json_show(ref: str, path: str) -> Any:
    return json.loads(git_show(ref, path).decode("utf-8"))


def json_show_optional(ref: str, path: str) -> Any | None:
    try:
        return json_show(ref, path)
    except Exception:
        return None


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def artifact_identity(ref: str, path: str) -> dict:
    raw = git_show(ref, path)
    return {
        "commit": ref,
        "path": path,
        "blob": git("rev-parse", f"{ref}:{path}"),
        "sha256": sha256_bytes(raw),
    }


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


def key_for(city: str, start: datetime, end: datetime) -> tuple[str, datetime, datetime]:
    return (str(city), start, end)


def parent_key(row: dict) -> tuple[str, datetime, datetime]:
    city = str(row.get("city_key") or "")
    start = parse_dt(row.get("start_at"))
    end = parse_dt(row.get("end_at"))
    if not city or not start or not end:
        raise Blocked("PARENT_IDENTITY_INVALID", "PHASE_1", "frozen_universe", 1,
                      f"Invalid canonical parent row: {row}")
    return key_for(city, start, end)


def live_key(city: str, ep: dict) -> tuple[str, datetime, datetime] | None:
    start = parse_dt(ep.get("alert_start") or ep.get("start_at") or ep.get("start"))
    end = parse_dt(ep.get("alert_end") or ep.get("end_at") or ep.get("end"))
    if not start or not end:
        return None
    return key_for(str(city), start, end)


def live_episode_id(city: str, start: datetime, end: datetime) -> str:
    raw = f"{city}|{iso(start)}|{iso(end)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def get_72h_check(ep: dict, end: datetime) -> dict | None:
    target = end + timedelta(hours=72)
    for check in ep.get("checks") or []:
        if not isinstance(check, dict):
            continue
        label = str(check.get("label") or "").casefold()
        due = parse_dt(check.get("due_at"))
        if label == "72h" or (due and abs((due - target).total_seconds()) <= 300):
            return check
    return None


def report_collection_status(report: dict | None, city: str) -> tuple[bool, list[str]]:
    reasons = []
    if not isinstance(report, dict):
        return False, ["MATCHING_LIVE_RUN_REPORT_MISSING"]
    searches = report.get("searches") or {}
    city_search = searches.get(city)
    if not isinstance(city_search, dict):
        reasons.append("CITY_EVIDENCE_SEARCH_RECORD_MISSING")
    else:
        if city_search.get("google_error"):
            reasons.append("GOOGLE_NEWS_COLLECTION_ERROR")
    telegram = report.get("telegram") or {}
    if not isinstance(telegram, dict) or not telegram:
        reasons.append("TELEGRAM_COLLECTION_STATUS_MISSING")
    else:
        for source_key, row in telegram.items():
            if isinstance(row, dict) and row.get("last_error"):
                reasons.append(f"TELEGRAM_COLLECTION_ERROR:{source_key}")
    return not reasons, sorted(set(reasons))


def relevant_queue_rows(queue: list[dict], episode_id: str,
                        checked_at: datetime | None) -> list[dict]:
    by_candidate: dict[str, dict] = {}
    for row in queue:
        if not isinstance(row, dict):
            continue
        matched = str(row.get("matched_episode_id") or "")
        triggers = {str(x) for x in row.get("trigger_episode_ids") or [] if str(x)}
        if episode_id not in triggers and matched != episode_id:
            continue
        discovered = parse_dt(row.get("first_discovered_at"))
        if checked_at and discovered and discovered > checked_at:
            continue
        cid = str(row.get("candidate_id") or "")
        if not cid:
            cid = hashlib.sha256(
                json.dumps(row, ensure_ascii=False, sort_keys=True).encode("utf-8")
            ).hexdigest()[:24]
        by_candidate[cid] = row
    return [by_candidate[k] for k in sorted(by_candidate)]


def project_candidate(row: dict, city: str) -> tuple[dict | None, list[str]]:
    missing = []
    for field in CANDIDATE_REQUIRED:
        value = row.get(field)
        if field == "city_key":
            if str(value or "") != city:
                missing.append(field)
        elif value is None or (isinstance(value, str) and not value.strip()):
            missing.append(field)
    if missing:
        return None, sorted(set(missing))
    out = {field: row.get(field) for field in CANDIDATE_REQUIRED}
    for field in CANDIDATE_OPTIONAL:
        if field in row:
            out[field] = row.get(field)
    return out, []


def input_projection(rows: list[dict], city: str) -> tuple[list[dict], list[str]]:
    out = []
    missing = set()
    for row in rows:
        projected, absent = project_candidate(row, city)
        missing.update(absent)
        if projected is not None:
            out.append(projected)
    return out, sorted(missing)


def build_live_indexes(state: dict) -> tuple[dict, dict]:
    exact: dict[tuple[str, datetime, datetime], list[dict]] = defaultdict(list)
    by_city: dict[str, list[tuple[datetime, datetime, dict]]] = defaultdict(list)
    for city, city_state in (state.get("cities") or {}).items():
        for ep in (city_state or {}).get("episodes") or []:
            if not isinstance(ep, dict):
                continue
            key = live_key(str(city), ep)
            if not key:
                continue
            _, start, end = key
            exact[key].append(ep)
            by_city[str(city)].append((start, end, ep))
    for city in by_city:
        by_city[city].sort(key=lambda x: (x[0], x[1], str(x[2].get("episode_id") or "")))
    return exact, by_city


def git_history(ref: str, path: str) -> list[str]:
    text = git("log", "--format=%H", ref, "--", path)
    return [line.strip() for line in text.splitlines() if line.strip()]


def run_report_index(live_commit: str) -> tuple[dict[str, dict], list[dict]]:
    by_started = {}
    identities = []
    for commit in git_history(live_commit, LIVE_LAST_RUN):
        report = json_show_optional(commit, LIVE_LAST_RUN)
        if not isinstance(report, dict):
            continue
        started = parse_dt(report.get("started_at"))
        if not started:
            continue
        started_key = iso(started)
        identity = {
            "commit": commit,
            "path": LIVE_LAST_RUN,
            "blob": git("rev-parse", f"{commit}:{LIVE_LAST_RUN}"),
        }
        by_started.setdefault(started_key, {"report": report, "identity": identity})
        identities.append(identity)
    return by_started, identities


def find_historical_exact_states(live_commit: str,
                                 targets: dict[tuple[str, datetime, datetime], str]) -> dict:
    found = {}
    remaining = set(targets)
    if not remaining:
        return found
    for commit in git_history(live_commit, LIVE_STATE):
        if not remaining:
            break
        state = json_show_optional(commit, LIVE_STATE)
        if not isinstance(state, dict):
            continue
        for city, city_state in (state.get("cities") or {}).items():
            if not any(k[0] == str(city) for k in remaining):
                continue
            for ep in (city_state or {}).get("episodes") or []:
                if not isinstance(ep, dict):
                    continue
                key = live_key(str(city), ep)
                if key in remaining:
                    found[key] = {
                        "commit": commit,
                        "episode": ep,
                        "state_blob": git("rev-parse", f"{commit}:{LIVE_STATE}"),
                    }
                    remaining.remove(key)
                    if not remaining:
                        break
    return found


def queue_at_commit(commit: str, cache: dict[str, list[dict]]) -> list[dict]:
    if commit in cache:
        return cache[commit]
    doc = json_show_optional(commit, LIVE_QUEUE)
    cache[commit] = doc if isinstance(doc, list) else []
    return cache[commit]


def temporal_position_map(doc: dict, parent_uids: set[str]) -> tuple[dict[str, str], dict]:
    mapping = {}
    for segment in doc.get("temporal_gap_segments") or []:
        raw = str(segment.get("temporal_position") or "")
        if raw in {"INTERNAL_HISTORICAL_COVERAGE_HOLE", "LEADING_HISTORICAL_COVERAGE_HOLE"}:
            label = "HISTORICAL_CLASSIFICATION_COVERAGE_HOLE"
        elif raw == "TRAILING_AFTER_CITY_CLASSIFICATION_FRONTIER":
            label = "TRAILING_AFTER_CITY_CLASSIFICATION_FRONTIER"
        else:
            raise Blocked("TEMPORAL_POSITION_UNRESOLVED", "PHASE_5", "temporal_position",
                          len(segment.get("uncovered_parent_uids") or []),
                          f"Unsupported temporal position: {raw}", len(mapping))
        for uid in segment.get("uncovered_parent_uids") or []:
            uid = str(uid)
            if uid in mapping:
                raise Blocked("TEMPORAL_UID_DUPLICATE", "PHASE_5", "temporal_position",
                              1, uid, len(mapping))
            mapping[uid] = label
    if set(mapping) != parent_uids:
        raise Blocked("TEMPORAL_UID_RECONCILIATION_MISMATCH", "PHASE_5",
                      "temporal_position", len(parent_uids ^ set(mapping)),
                      "Temporal segments do not exactly cover the frozen UID universe.",
                      len(parent_uids & set(mapping)))
    counts = Counter(mapping.values())
    if counts["HISTORICAL_CLASSIFICATION_COVERAGE_HOLE"] != 26 or        counts["TRAILING_AFTER_CITY_CLASSIFICATION_FRONTIER"] != 2074:
        raise Blocked("TEMPORAL_POSITION_COUNT_DRIFT", "PHASE_5", "temporal_position",
                      sum(counts.values()), f"Observed={dict(counts)}", len(mapping))
    return mapping, dict(counts)


def cross_tab(uid_to_group: dict[str, str], temporal: dict[str, str]) -> dict:
    out: dict[str, Counter] = defaultdict(Counter)
    for uid, group in uid_to_group.items():
        out[group][temporal[uid]] += 1
    return {
        group: {
            "HISTORICAL_CLASSIFICATION_COVERAGE_HOLE": int(counts["HISTORICAL_CLASSIFICATION_COVERAGE_HOLE"]),
            "TRAILING_AFTER_CITY_CLASSIFICATION_FRONTIER": int(counts["TRAILING_AFTER_CITY_CLASSIFICATION_FRONTIER"]),
            "total": int(sum(counts.values())),
        }
        for group, counts in sorted(out.items())
    }


def group_rows(rows: list[dict], key: str) -> list[dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[str(row[key])].append(row)
    out = []
    for name, members in sorted(grouped.items()):
        out.append({
            "name": name,
            "count": len(members),
            "episode_uids": sorted(str(x["alert_episode_uid"]) for x in members),
        })
    return out


def historical_batch_probe(city: str, start: datetime, end: datetime,
                           launch: dict, status: dict) -> dict | None:
    universe = (launch.get("frozen_city_universe") or {}).get(city) or {}
    ids = set(str(x) for x in universe.get("ordered_episode_ids") or [])
    expected_id = live_episode_id(city, start, end)
    if expected_id not in ids:
        return None
    city_status = (status.get("cities") or {}).get(city) or {}
    state = (city_status.get("episode_states") or {}).get(expected_id)
    if not isinstance(state, dict):
        return {
            "episode_id": expected_id,
            "in_frozen_universe": True,
            "status_record": None,
            "recovery_action": "UNRESOLVED",
        }
    batch_no = int(state.get("batch") or 0)
    batch_path = (
        f"research/historical_attack_event_backfill/historical-attack-events-v2-2026-09-27/"
        f"{city}/batch_{batch_no:06d}.json"
        if batch_no > 0 else None
    )
    batch_exists = bool(batch_path and json_show_optional(HISTORICAL_HEAD, batch_path) is not None)
    state_name = str(state.get("state") or "")
    if state_name in TERMINAL_HISTORICAL and batch_exists:
        action = "REPLAY_EXISTING_INTERNAL_COLLECTION"
    elif state_name == "SOURCE_FETCH_RETRY_REQUIRED":
        action = "NEW_EXTERNAL_EVIDENCE_FETCH_REQUIRED"
    else:
        action = "UNRESOLVED"
    return {
        "episode_id": expected_id,
        "in_frozen_universe": True,
        "status_record": state,
        "batch_path": batch_path,
        "batch_exists": batch_exists,
        "recovery_action": action,
    }


def source_identity_list(live_commit: str) -> list[dict]:
    rows = [
        artifact_identity(live_commit, LIVE_STATE),
        artifact_identity(live_commit, LIVE_QUEUE),
        artifact_identity(live_commit, LIVE_LAST_RUN),
        artifact_identity(live_commit, LIVE_BASELINE),
        artifact_identity(HISTORICAL_HEAD, HISTORICAL_LAUNCH),
        artifact_identity(HISTORICAL_HEAD, HISTORICAL_STATUS),
        artifact_identity(HISTORICAL_HEAD, HISTORICAL_WORKER),
        artifact_identity(HISTORICAL_HEAD, CLASSIFIER),
    ]
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--summary", required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--job-id", required=False)
    args = ap.parse_args()
    out_path = Path(args.out)
    summary_path = Path(args.summary)

    # PHASE 1: exact frozen continuity artifact reconciliation.
    observed_blob = git("rev-parse", f"{FROZEN_COMMIT}:{CONTINUITY_PATH}")
    if observed_blob != CONTINUITY_BLOB:
        raise Blocked("FROZEN_CONTINUITY_BLOB_MISMATCH", "PHASE_1", "frozen_universe",
                      EXPECTED_TOTAL, f"{observed_blob} != {CONTINUITY_BLOB}")
    raw = git_show(FROZEN_COMMIT, CONTINUITY_PATH)
    observed_sha = sha256_bytes(raw)
    if observed_sha != CONTINUITY_SHA256:
        raise Blocked("FROZEN_CONTINUITY_SHA256_MISMATCH", "PHASE_1", "frozen_universe",
                      EXPECTED_TOTAL, f"{observed_sha} != {CONTINUITY_SHA256}")
    doc = json.loads(raw.decode("utf-8"))
    if doc.get("verdict") != CONTINUITY_VERDICT:
        raise Blocked("FROZEN_CONTINUITY_VERDICT_MISMATCH", "PHASE_1", "frozen_universe",
                      EXPECTED_TOTAL, str(doc.get("verdict")))

    readiness = list(doc.get("per_episode_readiness") or [])
    parents = list(doc.get("uncovered_parent_identities") or [])
    if len(readiness) != EXPECTED_TOTAL or len(parents) != EXPECTED_TOTAL:
        raise Blocked("FROZEN_UNIVERSE_COUNT_MISMATCH", "PHASE_1", "frozen_universe",
                      max(len(readiness), len(parents)),
                      f"readiness={len(readiness)} parents={len(parents)}")
    parent_by_uid = {}
    parent_key_by_uid = {}
    for parent in parents:
        uid = str(parent.get("alert_episode_uid") or "")
        if not uid or uid in parent_by_uid:
            raise Blocked("PARENT_UID_MISSING_OR_DUPLICATE", "PHASE_1", "frozen_universe",
                          1, uid or "<missing>", len(parent_by_uid))
        parent_by_uid[uid] = parent
        parent_key_by_uid[uid] = parent_key(parent)

    readiness_by_uid = {}
    observed_counts = Counter()
    for row in readiness:
        uid = str(row.get("alert_episode_uid") or "")
        category = str(row.get("category") or "")
        if not uid or uid in readiness_by_uid:
            raise Blocked("READINESS_UID_MISSING_OR_DUPLICATE", "PHASE_1",
                          "frozen_universe", 1, uid or "<missing>", len(readiness_by_uid))
        if category not in EXPECTED_COUNTS:
            raise Blocked("READINESS_CATEGORY_UNEXPECTED", "PHASE_1", "frozen_universe",
                          1, category, len(readiness_by_uid))
        readiness_by_uid[uid] = row
        observed_counts[category] += 1
    if set(parent_by_uid) != set(readiness_by_uid):
        raise Blocked("PARENT_READINESS_UID_MISMATCH", "PHASE_1", "frozen_universe",
                      len(set(parent_by_uid) ^ set(readiness_by_uid)),
                      "Parent and readiness UID sets differ.",
                      len(set(parent_by_uid) & set(readiness_by_uid)))
    for category, expected in EXPECTED_COUNTS.items():
        if int(observed_counts[category]) != expected:
            raise Blocked("READINESS_PARTITION_COUNT_DRIFT", "PHASE_1", category,
                          int(observed_counts[category]),
                          f"expected={expected}", EXPECTED_TOTAL)
    universe_uids = sorted(parent_by_uid)
    universe_hash = hashlib.sha256(("\n".join(universe_uids) + "\n").encode("utf-8")).hexdigest()
    temporal_map, temporal_counts = temporal_position_map(doc, set(universe_uids))

    # Frozen code identities: validation only, no classifier invocation.
    if git("rev-parse", f"{HISTORICAL_HEAD}:{HISTORICAL_WORKER}") != HISTORICAL_WORKER_BLOB:
        raise Blocked("HISTORICAL_NORMALIZATION_IMPLEMENTATION_DRIFT", "PHASE_2",
                      "materialization", 1737, HISTORICAL_WORKER)
    if git("rev-parse", f"{HISTORICAL_HEAD}:{CLASSIFIER}") != CLASSIFIER_BLOB:
        raise Blocked("FROZEN_CLASSIFIER_BLOB_DRIFT", "PHASE_2",
                      "materialization", 1737, CLASSIFIER)

    live_commit = str(
        (((doc.get("existing_evidence_coverage_by_source_family") or {})
          .get("live_monitor") or {}).get("commit") or "")
    )
    if not live_commit:
        raise Blocked("PINNED_LIVE_COMMIT_MISSING", "PHASE_1", "evidence_authority",
                      EXPECTED_TOTAL, "Frozen continuity artifact has no live monitor commit.",
                      EXPECTED_TOTAL)
    live_state = json_show(live_commit, LIVE_STATE)
    live_queue = json_show(live_commit, LIVE_QUEUE)
    live_last = json_show(live_commit, LIVE_LAST_RUN)
    live_baseline = json_show(live_commit, LIVE_BASELINE)
    if not isinstance(live_queue, list):
        raise Blocked("PINNED_LIVE_QUEUE_SCHEMA_INVALID", "PHASE_1", "evidence_authority",
                      EXPECTED_TOTAL, "Live review queue is not a list.", EXPECTED_TOTAL)
    live_cutoff = parse_dt(live_last.get("followup_cutoff_at") or live_last.get("finished_at"))
    if not live_cutoff:
        raise Blocked("PINNED_LIVE_CUTOFF_MISSING", "PHASE_1", "evidence_authority",
                      EXPECTED_TOTAL, "No frozen live cutoff.", EXPECTED_TOTAL)
    exact_index, city_index = build_live_indexes(live_state)
    reports_by_started, _report_identities = run_report_index(live_commit)
    queue_cache: dict[str, list[dict]] = {}

    # PHASE 2: materialization cohort.
    materialization_rows = []
    materialization_safe_uids = set()
    materialization_blocked_uids = set()
    materialization_uid_to_subtype = {}
    unit_b_reason = {}
    unit_c_reason = {}
    for uid in universe_uids:
        r = readiness_by_uid[uid]
        if r.get("category") != "EVIDENCE_AVAILABLE_BUT_PIPELINE_NOT_MATERIALIZED":
            continue
        city, start, end = parent_key_by_uid[uid]
        exact_eps = exact_index.get((city, start, end), [])
        row = {
            "alert_episode_uid": uid,
            "city_key": city,
            "start_at": iso(start),
            "end_at": iso(end),
            "external_evidence_required": "NO",
            "normalization_semantics_change_required": "NO",
            "identity_ambiguity": "NO",
            "candidate_input_count": 0,
            "missing_input_fields": [],
        }
        if len(exact_eps) != 1:
            subtype = "MULTIPLE_EXISTING_REPRESENTATIONS_REQUIRE_BINDING_DECISION"
            row.update({
                "subtype": subtype,
                "identity_ambiguity": "YES",
                "deterministic_episode_mapping": "NO",
                "recovery_action": "IDENTITY_FORENSIC_REQUIRED",
                "live_exact_representation_count": len(exact_eps),
            })
            materialization_blocked_uids.add(uid)
            unit_c_reason[uid] = subtype
            materialization_uid_to_subtype[uid] = subtype
            materialization_rows.append(row)
            continue
        ep = exact_eps[0]
        eid = str(ep.get("episode_id") or "")
        check72 = get_72h_check(ep, end)
        checked_at = parse_dt((check72 or {}).get("checked_at"))
        report_entry = reports_by_started.get(iso(checked_at)) if checked_at else None
        report = (report_entry or {}).get("report")
        collection_complete, collection_blockers = report_collection_status(report, city)
        run_commit = str(((report_entry or {}).get("identity") or {}).get("commit") or "")
        run_queue = queue_at_commit(run_commit, queue_cache) if run_commit else []
        qrows = relevant_queue_rows(run_queue, eid, checked_at)
        projected, missing_fields = input_projection(qrows, city)
        row.update({
            "live_monitor_episode_id": eid or None,
            "followup_72h_due_at": (check72 or {}).get("due_at"),
            "followup_72h_checked_at": (check72 or {}).get("checked_at"),
            "collection_run_identity": (report_entry or {}).get("identity"),
            "collection_queue_identity": (
                {
                    "commit": run_commit,
                    "path": LIVE_QUEUE,
                    "blob": git("rev-parse", f"{run_commit}:{LIVE_QUEUE}"),
                }
                if run_commit else None
            ),
            "collection_complete": collection_complete,
            "collection_blockers": collection_blockers,
            "candidate_input_count": len(projected),
            "missing_input_fields": missing_fields,
            "deterministic_episode_mapping": "YES",
            "expected_output_representation": "FROZEN_LIVE_CANDIDATE_INPUT_BUNDLE",
            "external_requests_required_to_materialize": False,
        })
        if not checked_at or not collection_complete or missing_fields:
            subtype = "EXISTING_EVIDENCE_INCOMPLETE_FOR_FROZEN_NORMALIZATION"
            row["subtype"] = subtype
            row["external_evidence_required"] = "YES"
            row["recovery_action"] = "RUN_EXISTING_EVIDENCE_COLLECTOR"
            materialization_blocked_uids.add(uid)
            unit_b_reason[uid] = subtype
        elif projected:
            subtype = "LIVE_MONITOR_COMPLETE_NORMALIZATION_MISSING"
            row["subtype"] = subtype
            row["recovery_action"] = "SAFE_EXISTING_EVIDENCE_MATERIALIZATION"
            materialization_safe_uids.add(uid)
        else:
            subtype = "NORMALIZABLE_FROM_EXISTING_ACCEPTED_RECORDS"
            row["subtype"] = subtype
            row["recovery_action"] = "SAFE_EXISTING_EVIDENCE_MATERIALIZATION"
            row["accepted_empty_candidate_set"] = True
            materialization_safe_uids.add(uid)
        materialization_uid_to_subtype[uid] = subtype
        materialization_rows.append(row)

    if len(materialization_rows) != 1737:
        raise Blocked("MATERIALIZATION_COHORT_RECONCILIATION_MISMATCH", "PHASE_2",
                      "materialization", len(materialization_rows),
                      "Expected exactly 1,737 rows.", EXPECTED_TOTAL)

    # PHASE 3: exact evidence-coverage-missing reasons. Search prior accepted live
    # state history only for exact canonical identities; never near-match bind.
    missing_uids = [
        uid for uid in universe_uids
        if readiness_by_uid[uid].get("category") == "EVIDENCE_PIPELINE_COVERAGE_MISSING"
    ]
    no_current_targets = {
        parent_key_by_uid[uid]: uid
        for uid in missing_uids
        if len(exact_index.get(parent_key_by_uid[uid], [])) == 0
    }
    historical_exact = find_historical_exact_states(live_commit, no_current_targets)
    historical_launch = json_show(HISTORICAL_HEAD, HISTORICAL_LAUNCH)
    historical_status = json_show(HISTORICAL_HEAD, HISTORICAL_STATUS)
    evidence_rows = []
    evidence_uid_to_reason = {}
    evidence_action_counts = Counter()

    baseline_cities = live_baseline.get("cities") or {}
    for uid in missing_uids:
        city, start, end = parent_key_by_uid[uid]
        exact_eps = exact_index.get((city, start, end), [])
        reason = None
        action = None
        ext = "NO"
        detail = {}
        if len(exact_eps) > 1:
            reason = "MULTIPLE_EXACT_LIVE_REPRESENTATIONS"
            action = "PIPELINE_REPAIR_REQUIRED"
            ext = "NO"
        elif len(exact_eps) == 1:
            ep = exact_eps[0]
            check72 = get_72h_check(ep, end)
            horizon = end + timedelta(hours=72)
            checked_at = parse_dt((check72 or {}).get("checked_at"))
            if live_cutoff < horizon:
                reason = "ACCEPTED_72H_EVIDENCE_HORIZON_NOT_ELAPSED_AT_FROZEN_LIVE_CUTOFF"
                action = "WAIT_ONLY"
                ext = "NO"
            elif check72 is None or not checked_at:
                reason = "72H_FOLLOWUP_DUE_BUT_NOT_MATERIALIZED"
                action = "RUN_EXISTING_EVIDENCE_COLLECTOR"
                ext = "YES"
            else:
                report_entry = reports_by_started.get(iso(checked_at))
                complete, blockers = report_collection_status(
                    (report_entry or {}).get("report"), city
                )
                if complete:
                    reason = "72H_FOLLOWUP_COMPLETE_BUT_CONTINUITY_EVIDENCE_COVERAGE_FLAGGED_MISSING"
                    action = "REPLAY_EXISTING_INTERNAL_COLLECTION"
                    ext = "NO"
                else:
                    reason = "72H_FOLLOWUP_MATERIALIZED_WITH_SOURCE_COLLECTION_GAP"
                    action = "RUN_EXISTING_EVIDENCE_COLLECTOR"
                    ext = "YES"
                    detail["collection_blockers"] = blockers
        else:
            hist = historical_exact.get((city, start, end))
            if hist:
                ep = hist["episode"]
                check72 = get_72h_check(ep, end)
                checked_at = parse_dt((check72 or {}).get("checked_at"))
                report_entry = reports_by_started.get(iso(checked_at)) if checked_at else None
                complete, blockers = report_collection_status(
                    (report_entry or {}).get("report"), city
                )
                if checked_at and complete:
                    run_commit = str(((report_entry or {}).get("identity") or {}).get("commit") or "")
                    hqueue = queue_at_commit(run_commit, queue_cache) if run_commit else []
                    qrows = relevant_queue_rows(hqueue, str(ep.get("episode_id") or ""), checked_at)
                    projected, missing_fields = input_projection(qrows, city)
                    if not missing_fields:
                        reason = "CURRENT_LIVE_IDENTITY_ABSENT_BUT_HISTORICAL_INTERNAL_COLLECTION_AVAILABLE"
                        action = "REPLAY_EXISTING_INTERNAL_COLLECTION"
                        ext = "NO"
                        detail["historical_candidate_input_count"] = len(projected)
                        detail["historical_state_commit"] = hist["commit"]
                        detail["collection_run_identity"] = (report_entry or {}).get("identity")
                    else:
                        reason = "HISTORICAL_INTERNAL_COLLECTION_INPUT_INCOMPLETE"
                        action = "RUN_EXISTING_EVIDENCE_COLLECTOR"
                        ext = "YES"
                        detail["missing_input_fields"] = missing_fields
                else:
                    reason = "HISTORICAL_LIVE_EPISODE_FOUND_BUT_72H_COLLECTION_INCOMPLETE"
                    action = "RUN_EXISTING_EVIDENCE_COLLECTOR"
                    ext = "YES"
                    detail["collection_blockers"] = blockers
            else:
                batch = historical_batch_probe(city, start, end, historical_launch, historical_status)
                if batch and batch["recovery_action"] == "REPLAY_EXISTING_INTERNAL_COLLECTION":
                    reason = "HISTORICAL_BATCH_INTERNAL_COLLECTION_AVAILABLE"
                    action = "REPLAY_EXISTING_INTERNAL_COLLECTION"
                    ext = "NO"
                    detail["historical_batch"] = batch
                elif batch and batch["recovery_action"] == "NEW_EXTERNAL_EVIDENCE_FETCH_REQUIRED":
                    reason = "HISTORICAL_BATCH_SOURCE_FETCH_RETRY_REQUIRED"
                    action = "NEW_EXTERNAL_EVIDENCE_FETCH_REQUIRED"
                    ext = "YES"
                    detail["historical_batch"] = batch
                elif batch:
                    reason = "HISTORICAL_BATCH_UNIVERSE_PRESENT_BUT_RECOVERY_PATH_UNRESOLVED"
                    action = "UNRESOLVED"
                    ext = "NO"
                    detail["historical_batch"] = batch
                else:
                    cstate = (live_state.get("cities") or {}).get(city) or {}
                    baseline_end = str(
                        cstate.get("baseline_coverage_end")
                        or (baseline_cities.get(city) or {}).get("coverage_end")
                        or ""
                    )
                    local_day = start.astimezone(KYIV_TZ).date().isoformat()
                    latest_api_end = parse_dt(cstate.get("latest_api_alert_end"))
                    if baseline_end and local_day <= baseline_end:
                        reason = "LIVE_MONITOR_BASELINE_EXCLUDED_EPISODE"
                        action = "PIPELINE_REPAIR_REQUIRED"
                        ext = "YES"
                    elif latest_api_end and end > latest_api_end:
                        reason = "LIVE_COLLECTION_STOPPED_BEFORE_EPISODE"
                        action = "PIPELINE_REPAIR_REQUIRED"
                        ext = "YES"
                    else:
                        reason = "CITY_ALERT_SOURCE_COLLECTION_GAP"
                        action = "PIPELINE_REPAIR_REQUIRED"
                        ext = "YES"
                    detail.update({
                        "baseline_coverage_end": baseline_end or None,
                        "canonical_parent_local_date": local_day,
                        "latest_api_alert_end": iso(latest_api_end),
                        "last_poll_error": cstate.get("last_poll_error"),
                        "historical_batch_universe_excluded": True,
                    })
        evidence_uid_to_reason[uid] = reason
        evidence_action_counts[action] += 1
        evidence_rows.append({
            "alert_episode_uid": uid,
            "city_key": city,
            "start_at": iso(start),
            "end_at": iso(end),
            "reason_group": reason,
            "recovery_action": action,
            "external_evidence_required": ext,
            **detail,
        })
        if action == "UNRESOLVED":
            unit_b_reason.pop(uid, None)

    if len(evidence_rows) != 328:
        raise Blocked("EVIDENCE_MISSING_COHORT_RECONCILIATION_MISMATCH", "PHASE_3",
                      "evidence_missing", len(evidence_rows),
                      "Expected exactly 328 rows.", EXPECTED_TOTAL)

    # PHASE 4: forensic only; near matches are diagnostics and never accepted bindings.
    binding_rows = []
    binding_uid_to_shape = {}
    binding_group_stats: dict[str, dict] = {}
    auto_resolvable = set()
    auto_not_allowed = set()
    for uid in universe_uids:
        if readiness_by_uid[uid].get("category") != "INPUT_IDENTITY_OR_BINDING_BLOCKED":
            continue
        city, start, end = parent_key_by_uid[uid]
        near = []
        for cstart, cend, ep in city_index.get(city, []):
            sd = (cstart - start).total_seconds()
            ed = (cend - end).total_seconds()
            if abs(sd) <= 90 and abs(ed) <= 90 and (sd != 0 or ed != 0):
                near.append((cstart, cend, ep, sd, ed))
        if not near:
            shape = "OTHER_PROVEN_SHAPE"
        elif len(near) > 1:
            shape = "MULTIPLE_NEAR_CANDIDATES"
        else:
            _, _, _, sd, ed = near[0]
            if sd != 0 and ed == 0:
                shape = "EXACT_CITY_START_DRIFT_ONLY"
            elif sd == 0 and ed != 0:
                shape = "EXACT_CITY_END_DRIFT_ONLY"
            elif sd != 0 and ed != 0:
                shape = "EXACT_CITY_BOTH_BOUNDARY_DRIFT"
            else:
                shape = "OVERLAP_BUT_NO_EXACT_INTERVAL"

        explicit_parent_links = []
        for _, _, ep, _, _ in near:
            for field in PARENT_UID_KEYS:
                if str(ep.get(field) or "") == uid:
                    explicit_parent_links.append({
                        "episode_id": ep.get("episode_id"),
                        "field": field,
                    })
        exact_derivable_metadata = bool(explicit_parent_links)
        contract_change_required = bool(near)
        current_exact_contract_resolvable = False
        if current_exact_contract_resolvable:
            auto_resolvable.add(uid)
        else:
            auto_not_allowed.add(uid)
            unit_c_reason[uid] = "AUTOMATIC_BINDING_NOT_ALLOWED"
        overlaps = 0
        candidates = []
        for cstart, cend, ep, sd, ed in near:
            overlap = max(start, cstart) <= min(end, cend)
            overlaps += int(overlap)
            candidates.append({
                "episode_id": ep.get("episode_id"),
                "start_at": iso(cstart),
                "end_at": iso(cend),
                "start_delta_seconds": sd,
                "end_delta_seconds": ed,
                "overlaps_canonical_interval": overlap,
                "explicit_parent_identity_links": [
                    x for x in explicit_parent_links
                    if x.get("episode_id") == ep.get("episode_id")
                ],
            })
        binding_rows.append({
            "alert_episode_uid": uid,
            "city_key": city,
            "canonical_start_at": iso(start),
            "canonical_end_at": iso(end),
            "mismatch_shape": shape,
            "candidate_evidence_episode_count": len(near),
            "near_candidates": candidates[:10],
            "overlap_but_no_exact_interval_count": overlaps,
            "exact_deterministic_mapping_from_immutable_metadata": exact_derivable_metadata,
            "current_exact_parent_binding_contract_resolvable": current_exact_contract_resolvable,
            "resolving_requires_parent_binding_contract_change": contract_change_required,
            "automatic_binding_status": (
                "AUTOMATICALLY_RESOLVABLE_UNDER_CURRENT_EXACT_CONTRACT"
                if current_exact_contract_resolvable else "AUTOMATIC_BINDING_NOT_ALLOWED"
            ),
        })
        binding_uid_to_shape[uid] = shape
        stat = binding_group_stats.setdefault(shape, {
            "count": 0, "candidate_evidence_episode_count": 0,
            "max_absolute_start_delta_seconds": 0.0,
            "max_absolute_end_delta_seconds": 0.0,
            "episode_uids": [],
            "exact_deterministic_mapping_from_immutable_metadata_count": 0,
            "automatic_binding_not_allowed_count": 0,
        })
        stat["count"] += 1
        stat["candidate_evidence_episode_count"] += len(near)
        stat["episode_uids"].append(uid)
        stat["max_absolute_start_delta_seconds"] = max(
            stat["max_absolute_start_delta_seconds"],
            max([abs(x[3]) for x in near] or [0.0]),
        )
        stat["max_absolute_end_delta_seconds"] = max(
            stat["max_absolute_end_delta_seconds"],
            max([abs(x[4]) for x in near] or [0.0]),
        )
        stat["exact_deterministic_mapping_from_immutable_metadata_count"] += int(exact_derivable_metadata)
        stat["automatic_binding_not_allowed_count"] += int(not current_exact_contract_resolvable)

    if len(binding_rows) != 35:
        raise Blocked("BINDING_COHORT_RECONCILIATION_MISMATCH", "PHASE_4",
                      "identity_binding", len(binding_rows),
                      "Expected exactly 35 rows.", EXPECTED_TOTAL)

    # PHASE 6: bounded execution units. No classification-ready rows exist.
    unit_a = set(materialization_safe_uids)
    unit_b = set(materialization_blocked_uids) - set(unit_c_reason)
    unit_b.update(missing_uids)
    unit_c = set(unit_c_reason)
    unit_c.update(auto_not_allowed)
    # An evidence row explicitly unresolved cannot be safely assigned to B.
    unresolved_evidence = {
        row["alert_episode_uid"] for row in evidence_rows
        if row["recovery_action"] == "UNRESOLVED"
    }
    unit_b -= unresolved_evidence
    unit_d = set(unresolved_evidence)

    # If a binding row ever becomes exactly resolvable under the unchanged contract,
    # it would still need evidence readiness for later routing. Current accepted cohort
    # has none; guard rather than silently guess.
    if auto_resolvable:
        unit_d.update(auto_resolvable)
        unit_c -= auto_resolvable

    assigned = unit_a | unit_b | unit_c | unit_d
    overlaps = (
        (unit_a & unit_b) | (unit_a & unit_c) | (unit_a & unit_d)
        | (unit_b & unit_c) | (unit_b & unit_d) | (unit_c & unit_d)
    )
    if overlaps or assigned != set(universe_uids):
        raise Blocked("EXECUTION_UNIT_PARTITION_MISMATCH", "PHASE_6",
                      "execution_units", len(assigned),
                      f"overlaps={len(overlaps)} missing={len(set(universe_uids)-assigned)}",
                      len(assigned))

    readiness_group = {
        uid: str(readiness_by_uid[uid].get("category") or "") for uid in universe_uids
    }
    execution_group = {}
    for uid in unit_a:
        execution_group[uid] = "EXECUTION_UNIT_A_SAFE_EXISTING_EVIDENCE_MATERIALIZATION"
    for uid in unit_b:
        execution_group[uid] = "EXECUTION_UNIT_B_EVIDENCE_COLLECTION_RECOVERY"
    for uid in unit_c:
        execution_group[uid] = "EXECUTION_UNIT_C_IDENTITY_FORENSIC_MANUAL_CONTRACT_DECISION"
    for uid in unit_d:
        execution_group[uid] = "EXECUTION_UNIT_D_UNRESOLVED"

    materialization_subtypes = group_rows(materialization_rows, "subtype")
    evidence_reason_groups = group_rows(evidence_rows, "reason_group")
    for group in evidence_reason_groups:
        members = [
            row for row in evidence_rows if row["reason_group"] == group["name"]
        ]
        actions = Counter(str(x["recovery_action"]) for x in members)
        ext = Counter(str(x["external_evidence_required"]) for x in members)
        group["recovery_actions"] = dict(sorted(actions.items()))
        group["external_evidence_requirement"] = dict(sorted(ext.items()))

    binding_groups = []
    for shape, stat in sorted(binding_group_stats.items()):
        binding_groups.append({"name": shape, **stat})

    materialization_safe_count = len(materialization_safe_uids)
    materialization_blocked_count = 1737 - materialization_safe_count
    evidence_replayable_count = sum(
        1 for row in evidence_rows
        if row["recovery_action"] == "REPLAY_EXISTING_INTERNAL_COLLECTION"
    )
    external_evidence_required_count = sum(
        1 for row in evidence_rows
        if row["external_evidence_required"] == "YES"
    )
    wait_only_count = sum(
        1 for row in evidence_rows if row["recovery_action"] == "WAIT_ONLY"
    )
    other_evidence_blocker_count = 328 - (
        evidence_replayable_count + external_evidence_required_count + wait_only_count
    )

    source_ids = source_identity_list(live_commit)
    frozen_identity = {
        "commit": FROZEN_COMMIT,
        "path": CONTINUITY_PATH,
        "blob": CONTINUITY_BLOB,
        "sha256": CONTINUITY_SHA256,
    }

    unresolved_count = len(unit_d)
    verdict = (
        "ATTACK-EVENT PARTITIONED CLASSIFICATION RECOVERY AUDIT = PLANNED"
        if unresolved_count == 0
        else "ATTACK-EVENT PARTITIONED CLASSIFICATION RECOVERY AUDIT = BLOCKED"
    )

    if unit_a:
        first_task = "EXECUTION UNIT A — SAFE EXISTING-EVIDENCE MATERIALIZATION"
    elif unit_b:
        first_task = "EXECUTION UNIT B — EVIDENCE COLLECTION / RECOVERY"
    elif unit_c:
        first_task = "EXECUTION UNIT C — IDENTITY FORENSIC / MANUAL CONTRACT DECISION"
    else:
        first_task = "NO SAFE RECOVERY TASK"

    artifact = {
        "schema_version": 1,
        "kind": "attack_event_partitioned_classification_recovery_audit",
        "verdict": verdict,
        "audit_branch": AUDIT_BRANCH,
        "actions_run_id": int(args.run_id),
        "frozen_continuity_artifact_identity": frozen_identity,
        "frozen_universe": EXPECTED_TOTAL,
        "episode_uid_universe_sha256": universe_hash,
        "readiness_partition_reconciliation": {
            "expected": EXPECTED_COUNTS,
            "observed": {k: int(observed_counts[k]) for k in EXPECTED_COUNTS},
            "uids_unique": True,
            "parent_readiness_uid_sets_equal": True,
            "universe_reconciled": "YES",
        },
        "governing_semantics": {
            "classifier_methodology": METHODOLOGY,
            "normalization_version": NORMALIZATION,
            "classification_identity": "v2",
            "parent_binding": "exact canonical city/start/end only",
            "absence_of_evidence_is_not_no_confirmed_event": True,
            "all_2100_remain_unclassified": True,
        },
        "normalization_forensic": {
            "historical_observation_builder": {
                "ref": HISTORICAL_HEAD,
                "path": HISTORICAL_WORKER,
                "blob": HISTORICAL_WORKER_BLOB,
                "normalization_version": NORMALIZATION,
                "reusable_as_preclassification_materializer": False,
                "reason": "classify_row invokes the frozen classifier while building historical observation-v2; invoking it would violate this audit's no-classification boundary",
            },
            "frozen_classifier_input_projection": {
                "ref": HISTORICAL_HEAD,
                "path": CLASSIFIER,
                "blob": CLASSIFIER_BLOB,
                "representation": "FROZEN_LIVE_CANDIDATE_INPUT_BUNDLE",
                "required_input_fields": list(CANDIDATE_REQUIRED),
                "optional_input_fields": list(CANDIDATE_OPTIONAL),
                "projection_rule": "copy only persisted pre-classification candidate fields from the accepted live review queue; do not copy status/classification outputs",
                "normalization_semantics_change_required": "NO",
                "external_requests_required": "NO for materialization-safe rows",
            },
        },
        "source_artifact_identities": source_ids,
        "pinned_live_monitor_commit": live_commit,
        "materialization_cohort": {
            "count": 1737,
            "safe_count": materialization_safe_count,
            "blocked_count": materialization_blocked_count,
            "subtypes": materialization_subtypes,
            "rows": materialization_rows,
        },
        "evidence_missing_cohort": {
            "count": 328,
            "reason_groups": evidence_reason_groups,
            "rows": evidence_rows,
            "replayable_existing_internal_collection_count": evidence_replayable_count,
            "external_evidence_required_count": external_evidence_required_count,
            "wait_only_count": wait_only_count,
            "other_evidence_blocker_count": other_evidence_blocker_count,
        },
        "identity_binding_cohort": {
            "count": 35,
            "mismatch_groups": binding_groups,
            "rows": binding_rows,
            "automatically_resolvable_under_current_exact_contract_count": len(auto_resolvable),
            "automatic_binding_not_allowed_count": len(auto_not_allowed),
        },
        "temporal_position_cross_tab": {
            "totals": temporal_counts,
            "readiness_partition": cross_tab(readiness_group, temporal_map),
            "execution_unit": cross_tab(execution_group, temporal_map),
            "historical_hole_mechanism_counts": {
                group: values["HISTORICAL_CLASSIFICATION_COVERAGE_HOLE"]
                for group, values in cross_tab(execution_group, temporal_map).items()
            },
        },
        "execution_units": {
            "A_SAFE_EXISTING_EVIDENCE_MATERIALIZATION": {
                "count": len(unit_a),
                "episode_uids": sorted(unit_a),
                "external_evidence_required": "NO",
                "classifier_semantics_change_required": "NO",
                "normalization_semantics_change_required": "NO",
                "identity_ambiguity": "NO",
            },
            "B_EVIDENCE_COLLECTION_RECOVERY": {
                "count": len(unit_b),
                "episode_uids": sorted(unit_b),
                "contains_replay_existing_internal_collection": any(
                    row["alert_episode_uid"] in unit_b
                    and row["recovery_action"] == "REPLAY_EXISTING_INTERNAL_COLLECTION"
                    for row in evidence_rows
                ),
                "contains_new_external_requests": any(
                    row["alert_episode_uid"] in unit_b
                    and row["external_evidence_required"] == "YES"
                    for row in evidence_rows
                ) or any(
                    uid in unit_b for uid in materialization_blocked_uids
                ),
                "contains_wait_only": any(
                    row["alert_episode_uid"] in unit_b
                    and row["recovery_action"] == "WAIT_ONLY"
                    for row in evidence_rows
                ),
            },
            "C_IDENTITY_FORENSIC_MANUAL_CONTRACT_DECISION": {
                "count": len(unit_c),
                "episode_uids": sorted(unit_c),
                "automatic_classification_allowed": False,
            },
            "D_UNRESOLVED": {
                "count": len(unit_d),
                "episode_uids": sorted(unit_d),
            },
        },
        "recommended_first_recovery_task": first_task,
        "db_writes": 0,
        "neon_queries": 0,
        "production_mutation": "NO",
        "credentials_exposed": False,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )

    if unresolved_count:
        first_uid = sorted(unit_d)[0]
        summary = {
            "verdict": verdict,
            "first_failing_gate": "DETERMINISTIC_RECOVERY_UNIT_UNRESOLVED",
            "phase": "PHASE_6",
            "affected_cohort": "EXECUTION_UNIT_D",
            "affected_count": unresolved_count,
            "exact_unresolved_authority_or_representation": (
                "At least one frozen episode cannot be assigned to A/B/C without "
                "inventing a recovery authority; first UID=" + first_uid
            ),
            "reconciled_identities_count": EXPECTED_TOTAL,
            "db_writes": 0,
            "production_mutation": "NO",
            "safe_continuation_point": (
                "Resolve the explicit UNIT D authority gap only; do not classify, "
                "normalize, bind by tolerance, or collect evidence until that authority exists."
            ),
        }
        summary_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        return 2

    summary = {
        "verdict": verdict,
        "audit_branch": AUDIT_BRANCH,
        "actions_run_id": int(args.run_id),
        "frozen_universe": EXPECTED_TOTAL,
        "universe_reconciled": "YES",
        "materialization_cohort": 1737,
        "materialization_safe_count": materialization_safe_count,
        "materialization_blocked_count": materialization_blocked_count,
        "evidence_missing_cohort": 328,
        "evidence_replayable_count": evidence_replayable_count,
        "external_evidence_required_count": external_evidence_required_count,
        "wait_only_count": wait_only_count,
        "other_evidence_blocker_count": other_evidence_blocker_count,
        "identity_binding_cohort": 35,
        "automatically_resolvable_under_current_exact_contract_count": len(auto_resolvable),
        "automatic_binding_not_allowed_count": len(auto_not_allowed),
        "unresolved_count": 0,
        "execution_unit_A_count": len(unit_a),
        "execution_unit_B_count": len(unit_b),
        "execution_unit_C_count": len(unit_c),
        "execution_unit_D_count": len(unit_d),
        "recommended_FIRST_recovery_task": first_task,
        "db_writes": 0,
        "production_mutation": "NO",
    }
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Blocked as exc:
        payload = {
            "verdict": "ATTACK-EVENT PARTITIONED CLASSIFICATION RECOVERY AUDIT = BLOCKED",
            "first_failing_gate": exc.gate,
            "phase": exc.phase,
            "affected_cohort": exc.cohort,
            "affected_count": exc.count,
            "exact_unresolved_authority_or_representation": exc.detail,
            "reconciled_identities_count": exc.reconciled,
            "db_writes": 0,
            "production_mutation": "NO",
            "safe_continuation_point": (
                f"Resolve {exc.gate} within the read-only recovery audit; do not "
                "repair data, fetch evidence, normalize inputs, bind by tolerance, or classify episodes."
            ),
        }
        fallback = os.environ.get("RECOVERY_SUMMARY_FALLBACK")
        if fallback:
            Path(fallback).write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        raise SystemExit(2)
