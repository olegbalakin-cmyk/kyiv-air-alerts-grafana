#!/usr/bin/env python3
"""Durable live canonical obligations and bounded, DB-reconciled work selection.

The WIP monitor-state file is an obligation journal, NOT canonical commit authority.
A database current-tip query is repeated on every run before capacity is charged.
No discovery/check schedule or classifier semantics are changed here.
"""
from __future__ import annotations

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
            }
            added += 1
        else:
            saved = entries[key]
            if tuple(saved.get(field) for field in ("city_key", "episode_id", "alert_start", "alert_end")) != values:
                raise CanonicalQueueError("durable identity-key collision")
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
    committed = quarantined = retry_waiting = 0
    for digest, entry in entries.items():
        i = identity(episode_from_entry(entry))
        if identity_key(i) != digest:
            raise CanonicalQueueError("durable queue record identity mismatch")
        if instant(i[3]) < cutoff:
            continue
        total += 1
        tip = tips.get(digest)
        if tip:
            if not tip.get("exact_parent"):
                entry["status"] = "quarantined"
                entry["quarantine_reason"] = "CURRENT_TIP_PARENT_NOT_EXACT"
            elif entry.get("status") != "quarantined":
                key = desired_classification_key(entry, candidates)
                if key == tip.get("classification_key"):
                    entry["status"] = "committed"
                    entry["last_committed_key"] = key
                    entry["next_retry_at"] = None
                elif tip.get("origin_kind") != LIVE_ORIGIN_KIND:
                    entry["status"] = "quarantined"
                    entry["quarantine_reason"] = "NONLIVE_ORIGIN_REVISION_FORBIDDEN"
                else:
                    entry["status"] = "pending"
                    entry["expected_current_tip"] = tip["classification_uid"]
                    entry["expected_current_key"] = tip["classification_key"]
        elif entry.get("status") == "committed":
            # A WIP flag can NEVER overrule missing database commitment.
            entry["status"] = "pending"
            entry["last_committed_key"] = None
        if entry.get("status") == "quarantined":
            quarantined += 1
            continue
        if entry.get("status") == "committed":
            committed += 1
            continue
        next_retry = entry.get("next_retry_at")
        if next_retry and instant(next_retry) > now:
            retry_waiting += 1
            continue
        if tip is None:
            entry["expected_current_tip"] = None
            entry["expected_current_key"] = None
        pending.append((i, digest, entry, tip))
    pending.sort(key=lambda row: (row[0][3], row[0][2], row[0][0], row[0][1]))
    selected_rows = pending[:max_episodes] if max_episodes is not None else pending
    return {
        "total_registered": total,
        "db_committed_current": committed,
        "quarantined": quarantined,
        "retry_waiting": retry_waiting,
        "ready_pending": len(pending),
        "selected": [
            {
                "work_id": digest,
                "episode": episode_from_entry(entry),
                "expected_current_tip": tip["classification_uid"] if tip else None,
                "expected_current_key": tip["classification_key"] if tip else None,
                "work_kind": "revision" if tip else "initial",
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
