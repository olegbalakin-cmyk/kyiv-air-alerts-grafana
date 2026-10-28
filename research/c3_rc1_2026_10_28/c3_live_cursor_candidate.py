# RECONSTRUCTED C3-RC1 (2026-10-28). Based on independently accepted PG16 proof source b1036d43ebd9b2df15eb58fce2192f67eb30ee68.
# The earlier five C3 local-file bytes were unavailable. This is NOT their byte-identical recovery.
#!/usr/bin/env python3
"""Durable live canonical obligations and bounded, DB-reconciled work selection.

The WIP monitor-state file is an obligation journal, NOT canonical commit authority.
A database current-tip query is repeated on every run before capacity is charged.
No discovery/check schedule or classifier semantics are changed here.
"""
from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any

SCHEMA_VERSION = 1
RETRY_DELAY = timedelta(minutes=15)
LIVE_ORIGIN_KIND = "shared_live_attack_event_canonical_persistence_v1"


class CanonicalQueueError(RuntimeError):
    pass


def instant(value: Any) -> datetime:
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    else:
        raise CanonicalQueueError("canonical queue requires an aware instant")
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise CanonicalQueueError("canonical queue cannot accept naive timestamps")
    return dt.astimezone(timezone.utc)


def precise(value: Any) -> str:
    return instant(value).isoformat(timespec="microseconds").replace("+00:00", "Z")


def identity(episode: dict[str, Any], city_key: str | None = None) -> tuple[str, str, str, str]:
    city = str(city_key or episode.get("city_key") or "").strip()
    episode_id = str(episode.get("episode_id") or "").strip()
    if not city or len(episode_id) != 24 or any(c not in "0123456789abcdef" for c in episode_id):
        raise CanonicalQueueError("missing/invalid canonical live city and episode ID")
    start = precise(episode.get("alert_start"))
    end = precise(episode.get("alert_end"))
    if instant(end) <= instant(start):
        raise CanonicalQueueError("invalid canonical live interval")
    return city, episode_id, start, end


def identity_key(values: tuple[str, str, str, str]) -> str:
    value = json.dumps(list(values), ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def store(state: dict[str, Any]) -> dict[str, Any]:
    work = state.setdefault("canonical_work", {"schema_version": SCHEMA_VERSION, "entries": {}})
    if not isinstance(work, dict) or work.get("schema_version") != SCHEMA_VERSION:
        raise CanonicalQueueError("unrecognized durable canonical work schema")
    if not isinstance(work.get("entries"), dict):
        raise CanonicalQueueError("invalid durable canonical work entries")
    return work["entries"]


def register_city(state: dict[str, Any], city_key: str, episodes: list[dict[str, Any]], cutoff: datetime) -> int:
    """Register before the per-city WIP retention truncation, preserving exact identity."""
    cutoff = instant(cutoff)
    entries = store(state)
    added = 0
    for episode in episodes:
        if not episode.get("alert_end") or instant(episode["alert_end"]) < cutoff:
            continue
        values = identity(episode, city_key)
        key = identity_key(values)
        if key not in entries:
            entries[key] = {
                "city_key": values[0],
                "episode_id": values[1],
                "alert_start": values[2],
                "alert_end": values[3],
                "status": "pending",
                "attempts": 0,
                "next_retry_at": None,
                "expected_current_tip": None,
                "last_committed_key": None,
                "quarantine_reason": None,
                "coverage_checks": {},
                "evidence_snapshots": {},
            }
            added += 1
        else:
            saved = entries[key]
            if tuple(saved.get(field) for field in ("city_key", "episode_id", "alert_start", "alert_end")) != values:
                raise CanonicalQueueError("durable identity-key collision")
        # Previously checked legacy work does not acquire a fictitious coverage
        # certificate. New observations are certified only after source checks.
        checks = entries[key].setdefault("coverage_checks", {})
        entries[key].setdefault("evidence_snapshots", {})
        for check in episode.get("checks") or []:
            label = str(check.get("label") or "")
            if not label:
                continue
            due = precise(check["due_at"])
            if label not in checks:
                checks[label] = {
                    "due_at": due,
                    "status": "legacy_unverified" if check.get("checked_at") else "pending",
                    "completed_at": None,
                    "reason": "LEGACY_CHECK_WITHOUT_SOURCE_COVERAGE" if check.get("checked_at") else None,
                }
            elif checks[label]["due_at"] != due:
                raise CanonicalQueueError("FOLLOWUP_SCHEDULE_IDENTITY_DRIFT")
        if episode.get("identity_superseded_by_episode_id"):
            entries[key]["status"] = "quarantined"
            entries[key]["quarantine_reason"] = "SUPERSEDED_LOGICAL_IDENTITY"
    return added


def register_state(state: dict[str, Any], cutoff: datetime, city_keys: set[str] | None = None) -> int:
    count = 0
    for city, cstate in sorted((state.get("cities") or {}).items()):
        if city_keys is not None and city not in city_keys:
            continue
        count += register_city(state, city, cstate.get("episodes") or [], cutoff)
    return count


def episode_from_entry(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "city_key": entry["city_key"],
        "episode_id": entry["episode_id"],
        "alert_start": entry["alert_start"],
        "alert_end": entry["alert_end"],
    }


def read_current_tips(conn, cutoff: datetime) -> dict[str, dict[str, Any]]:
    """Read *committed* current tips by exact four-part identity.

    Unrelated historical and pre-cutoff rows cannot match a registered obligation.
    Multiple current tips fail closed. No writes, advisory locks or transactions.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT c.city_key, c.historical_episode_id,
                   c.alert_start_at, c.alert_end_at,
                   c.classification_uid, c.classification_key,
                   c.origin_provenance, p.episode_uid
            FROM public.attack_event_classifications c
            LEFT JOIN public.alert_episodes p
              ON p.legacy_episode_id = c.historical_episode_id
             AND p.city_key = c.city_key
             AND p.start_at = c.alert_start_at AND p.end_at = c.alert_end_at
             AND p.alert_type = 'AIR' AND p.episode_state = 'closed'
             AND p.canonicalization_version = 'alert-canonicalization-v1'
            WHERE c.alert_end_at >= %s
              AND NOT EXISTS (
                  SELECT 1 FROM public.attack_event_classifications n
                  WHERE n.supersedes_classification_uid = c.classification_uid
              )
            ORDER BY c.alert_end_at, c.city_key, c.historical_episode_id
            """,
            (instant(cutoff),),
        )
        rows = cur.fetchall()
    output: dict[str, dict[str, Any]] = {}
    for city, episode_id, start, end, uid, key, origin, parent_uid in rows:
        i = (str(city), str(episode_id), precise(start), precise(end))
        digest = identity_key(i)
        if digest in output:
            raise CanonicalQueueError("MULTIPLE_CURRENT_CLASSIFICATION_TIPS:" + digest)
        output[digest] = {
            "classification_uid": str(uid),
            "classification_key": str(key),
            "origin_kind": str((origin or {}).get("kind") or "") if isinstance(origin, dict) else "",
            "exact_parent": parent_uid is not None,
        }
    return output



def relevant_evidence(entry: dict[str, Any], candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Recover durable source observations; the current review queue wins for updated reviews.

    A source disappearing from the mutable queue cannot turn an earlier positive
    or review hold into a spurious negative.
    """
    from attack_event_canonical_persistence import _episode_refs
    city, episode_id = entry["city_key"], entry["episode_id"]
    retained = entry.get("evidence_snapshots") or {}
    if not isinstance(retained, dict):
        raise CanonicalQueueError("EVIDENCE_SNAPSHOT_CORRUPT")
    merged = {key: copy.deepcopy(value) for key, value in retained.items()}
    for row in candidates:
        if not isinstance(row, dict) or str(row.get("city_key") or "") != city:
            continue
        if episode_id not in _episode_refs(row):
            continue
        cid = str(row.get("candidate_id") or "")
        if not cid:
            raise CanonicalQueueError("EPISODE_EVIDENCE_MISSING_CANDIDATE_ID")
        merged[cid] = row
    for cid, row in merged.items():
        if str(row.get("candidate_id")) != cid or str(row.get("city_key")) != city or episode_id not in _episode_refs(row):
            raise CanonicalQueueError("DURABLE_EPISODE_EVIDENCE_IDENTITY_MISMATCH")
    return [merged[key] for key in sorted(merged)]


def record_coverage(
    state: dict[str, Any],
    due: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]],
    coverage_by_city: dict[str, bool],
    candidates: list[dict[str, Any]],
    checked_at: datetime,
) -> dict[str, int]:
    """Certify each executed follow-up only after the approved discovery path finishes.

    Missing source coverage stays pending; the monitor must not set checked_at
    on those checks, allowing the unchanged discovery strategy to retry.
    """
    complete = failed = 0
    entries = store(state)
    for city, city_due in sorted(due.items()):
        for episode, check in city_due:
            key = identity_key(identity(episode, city))
            entry = entries.get(key)
            if entry is None:
                raise CanonicalQueueError("UNREGISTERED_FOLLOWUP_OBLIGATION")
            label = str(check.get("label") or "")
            cert = entry.get("coverage_checks", {}).get(label)
            if cert is None:
                raise CanonicalQueueError("MISSING_FOLLOWUP_COVERAGE_SCHEDULE")
            if not coverage_by_city.get(city):
                cert["status"] = "pending"
                cert["reason"] = "SOURCE_COVERAGE_INCOMPLETE_RETRY_DUE_CHECK"
                check["checked_at"] = None
                failed += 1
                continue
            for row in relevant_evidence(entry, candidates):
                entry["evidence_snapshots"][row["candidate_id"]] = copy.deepcopy(row)
            cert["status"] = "complete"
            cert["reason"] = None
            cert["completed_at"] = precise(checked_at)
            check["checked_at"] = precise(checked_at)
            complete += 1
    return {"checks_complete": complete, "checks_retryable": failed}


def evidence_gate(entry: dict[str, Any], now: datetime) -> tuple[bool, str | None]:
    checks = entry.get("coverage_checks") or {}
    if not isinstance(checks, dict) or not checks:
        return False, "NO_DURABLE_FOLLOWUP_COVERAGE_CONTRACT"
    eligible = [check for check in checks.values() if instant(check["due_at"]) <= instant(now)]
    if not eligible:
        return False, "NO_FOLLOWUP_CHECK_DUE_YET"
    for check in eligible:
        if check.get("status") != "complete":
            return False, str(check.get("reason") or "FOLLOWUP_EVIDENCE_NOT_COMPLETE")
    return True, None

def desired_classification_key(
    entry: dict[str, Any],
    candidates: list[dict[str, Any]],
) -> str:
    """Pure fingerprint projection of ALREADY reviewed/automatically classified evidence.

    Only called for an existing canonical tip with a proven exact parent.
    This does not invoke the authoritative source classifier or write a verdict.
    """
    from attack_event_canonical_persistence import build_episode_classification
    origin = {
        "ref": "OFFLINE_FINGERPRINT_ONLY",
        "commit": "0" * 40,
        "monitor_blob": "0" * 40,
        "run_id": None,
        "origin_provenance": {"kind": "FINGERPRINT_ONLY"},
        "origin_provenance_sha256": "0" * 64,
    }
    return str(build_episode_classification(episode_from_entry(entry), candidates, origin=origin)["classification_key"])


def reconcile_and_select(
    state: dict[str, Any],
    *,
    tips: dict[str, dict[str, Any]],
    candidates: list[dict[str, Any]],
    cutoff: datetime,
    max_episodes: int | None,
    now: datetime,
) -> dict[str, Any]:
    """Oldest unmet obligation first, with deterministic tie-breaks.

    It does not consume the canary slot for identical committed work or for a
    quarantined item. Old pending work has priority over newly arrived work.
    """
    cutoff, now = instant(cutoff), instant(now)
    if max_episodes is not None and max_episodes < 1:
        raise CanonicalQueueError("maximum episode batch must be positive")
    entries = store(state)
    total = 0
    pending: list[tuple[tuple[str, str, str, str], str, dict[str, Any], dict[str, Any] | None]] = []
    committed = quarantined = retry_waiting = blocked_evidence = 0
    for digest, entry in entries.items():
        i = identity(episode_from_entry(entry))
        if identity_key(i) != digest:
            raise CanonicalQueueError("durable queue record identity mismatch")
        if instant(i[3]) < cutoff:
            continue
        total += 1
        tip = tips.get(digest)
        if entry.get("status") == "quarantined":
            quarantined += 1
            continue
        if tip and not tip.get("exact_parent"):
            entry["status"] = "quarantined"
            entry["quarantine_reason"] = "CURRENT_TIP_PARENT_NOT_EXACT"
            quarantined += 1
            continue

        covered, reason = evidence_gate(entry, now)
        if not covered:
            # A committed tip is authoritative even if old WIP discovery metadata
            # is incomplete. Never fabricate a revision from missing candidates.
            if tip:
                entry["status"] = "committed"
                entry["last_committed_key"] = tip["classification_key"]
                entry["next_retry_at"] = None
                committed += 1
            else:
                entry["status"] = "blocked_evidence"
                entry["last_error"] = reason
                blocked_evidence += 1
            continue

        try:
            source_rows = relevant_evidence(entry, candidates)
            wanted_key = desired_classification_key(entry, source_rows)
        except (CanonicalQueueError, ValueError, KeyError) as exc:
            entry["status"] = "blocked_evidence"
            entry["last_error"] = f"EVIDENCE_RECONSTRUCTION_FAILED:{type(exc).__name__}:{exc}"[:350]
            blocked_evidence += 1
            continue
        if tip and wanted_key == tip["classification_key"]:
            entry["status"] = "committed"
            entry["last_committed_key"] = wanted_key
            entry["next_retry_at"] = None
            entry["last_error"] = None
            committed += 1
            continue
        if tip and tip.get("origin_kind") != LIVE_ORIGIN_KIND:
            entry["status"] = "quarantined"
            entry["quarantine_reason"] = "NONLIVE_ORIGIN_REVISION_FORBIDDEN"
            quarantined += 1
            continue
        if entry.get("status") == "committed" and tip is None:
            entry["last_committed_key"] = None
        entry["status"] = "pending"
        entry["expected_current_tip"] = tip["classification_uid"] if tip else None
        entry["expected_current_key"] = tip["classification_key"] if tip else None
        next_retry = entry.get("next_retry_at")
        if next_retry and instant(next_retry) > now:
            retry_waiting += 1
            continue
        pending.append((i, digest, entry, tip))
    pending.sort(key=lambda row: (row[0][3], row[0][2], row[0][0], row[0][1]))
    selected_rows = pending[:max_episodes] if max_episodes is not None else pending
    return {
        "total_registered": total,
        "db_committed_current": committed,
        "quarantined": quarantined,
        "retry_waiting": retry_waiting,
        "blocked_evidence": blocked_evidence,
        "ready_pending": len(pending),
        "selected": [
            {
                "work_id": digest,
                "episode": episode_from_entry(entry),
                "expected_current_tip": tip["classification_uid"] if tip else None,
                "expected_current_key": tip["classification_key"] if tip else None,
                "work_kind": "revision" if tip else "initial",
                "coverage_complete": True,
            }
            for _, digest, entry, tip in selected_rows
        ],
    }


def quarantine(state: dict[str, Any], work_id: str, reason: str) -> None:
    entry = store(state)[work_id]
    entry["status"] = "quarantined"
    entry["quarantine_reason"] = str(reason)


def retry(state: dict[str, Any], work_id: str, at: datetime, reason: str) -> None:
    entry = store(state)[work_id]
    entry["status"] = "retryable_failure"
    entry["attempts"] = int(entry.get("attempts") or 0) + 1
    entry["next_retry_at"] = precise(instant(at) + RETRY_DELAY)
    entry["last_error"] = str(reason)[:350]


def committed_readback(state: dict[str, Any], work_id: str, expected_key: str, actual_key: str) -> None:
    if expected_key != actual_key:
        raise CanonicalQueueError("POST_COMMIT_READBACK_KEY_MISMATCH")
    entry = store(state)[work_id]
    entry["status"] = "committed"
    entry["last_committed_key"] = actual_key
    entry["expected_current_key"] = actual_key
    entry["next_retry_at"] = None
    entry["last_error"] = None
