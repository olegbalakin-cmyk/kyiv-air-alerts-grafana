#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg

CANONICALIZATION_VERSION = "alert-canonicalization-v1"
CONTRACT_DIR_ENV = "CANONICAL_PARENT_CONTRACT_DIR"
DB_BRANCH_ENV = "CANONICAL_PARENT_DB_BRANCH"
RUN_KIND = "live_parent_ordering_sync"


class ParentOrderingError(RuntimeError):
    code = "CANONICAL_PARENT_PERSISTENCE_FAILED"


class CanonicalParentIdentityMismatch(ParentOrderingError):
    code = "CANONICAL_PARENT_IDENTITY_MISMATCH"


class SeparateCanonicalIdentityBlocker(ParentOrderingError):
    code = "SEPARATE_CANONICAL_IDENTITY_BLOCKER"


class CanonicalParentPersistenceFailed(ParentOrderingError):
    code = "CANONICAL_PARENT_PERSISTENCE_FAILED"


def _as_utc(value: Any) -> datetime:
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value or "").strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        raise CanonicalParentIdentityMismatch(f"timezone-aware timestamp required: {value!r}")
    return dt.astimezone(timezone.utc)


def _load_contract():
    raw = str(os.environ.get(CONTRACT_DIR_ENV) or "").strip()
    if not raw:
        raise CanonicalParentPersistenceFailed(f"{CONTRACT_DIR_ENV} is required")
    contract_dir = Path(raw).resolve()
    if not contract_dir.is_dir():
        raise CanonicalParentPersistenceFailed(
            f"{CONTRACT_DIR_ENV} does not exist: {contract_dir}"
        )
    text = str(contract_dir)
    if text not in sys.path:
        sys.path.insert(0, text)
    try:
        import db_phase1_core
        import db_phase1_persistence
    except Exception as exc:
        raise CanonicalParentPersistenceFailed(
            f"existing canonical parent contract import failed: {type(exc).__name__}: {exc}"
        ) from exc
    if db_phase1_core.CANONICALIZATION_VERSION != CANONICALIZATION_VERSION:
        raise CanonicalParentPersistenceFailed(
            "canonical parent contract version mismatch: "
            f"{db_phase1_core.CANONICALIZATION_VERSION!r}"
        )
    return db_phase1_core, db_phase1_persistence


def ingestion_family(city_key: str) -> str:
    if city_key == "kyiv":
        return "Kyiv exact-city combined"
    if city_key == "sevastopol":
        return "Sevastopol verified exact-city pairs"
    if city_key in {"kharkiv", "zaporizhzhia"}:
        return "UkraineAlarm exact-hromada"
    return "UkraineAlarm raion-proxy"


def _candidate(episode: dict[str, Any]) -> dict[str, Any]:
    core, _ = _load_contract()
    city_key = str(episode.get("city_key") or "").strip()
    historical_episode_id = str(episode.get("episode_id") or "").strip()
    start_at = _as_utc(episode.get("alert_start"))
    end_at = _as_utc(episode.get("alert_end"))
    if not city_key or len(historical_episode_id) != 24:
        raise CanonicalParentIdentityMismatch(
            f"invalid live parent identity city={city_key!r} episode_id={historical_episode_id!r}"
        )
    expected = core.legacy_episode_id(city_key, start_at, end_at)
    if historical_episode_id != expected:
        raise CanonicalParentIdentityMismatch(
            "CANONICAL_PARENT_IDENTITY_MISMATCH: live episode_id is not the canonical "
            f"legacy_episode_id: {city_key}:{historical_episode_id} expected={expected}"
        )
    return {
        "legacy_episode_id": historical_episode_id,
        "city_key": city_key,
        "alert_type": "AIR",
        "start_at": start_at,
        "end_at": end_at,
        "episode_state": "closed",
        "canonicalization_version": CANONICALIZATION_VERSION,
    }


def _read_exact_and_conflicts(conn, candidate: dict[str, Any]) -> tuple[list[tuple], list[tuple]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT episode_uid, legacy_episode_id, city_key, start_at, end_at
            FROM public.alert_episodes
            WHERE legacy_episode_id = %s
              AND city_key = %s
              AND alert_type = 'AIR'
              AND episode_state = 'closed'
              AND canonicalization_version = %s
              AND start_at = %s
              AND end_at = %s
            """,
            (
                candidate["legacy_episode_id"],
                candidate["city_key"],
                CANONICALIZATION_VERSION,
                candidate["start_at"],
                candidate["end_at"],
            ),
        )
        exact = list(cur.fetchall())
        cur.execute(
            """
            SELECT episode_uid, legacy_episode_id, city_key, start_at, end_at
            FROM public.alert_episodes
            WHERE alert_type = 'AIR'
              AND episode_state = 'closed'
              AND canonicalization_version = %s
              AND (
                    legacy_episode_id = %s
                 OR (city_key = %s AND start_at = %s AND end_at = %s)
                 OR (
                      city_key = %s
                      AND start_at < %s
                      AND end_at > %s
                 )
              )
            ORDER BY start_at, end_at, episode_uid
            """,
            (
                CANONICALIZATION_VERSION,
                candidate["legacy_episode_id"],
                candidate["city_key"],
                candidate["start_at"],
                candidate["end_at"],
                candidate["city_key"],
                candidate["end_at"],
                candidate["start_at"],
            ),
        )
        conflicts = list(cur.fetchall())
    conn.rollback()
    return exact, conflicts


def _provenance(candidate: dict[str, Any]) -> dict[str, Any]:
    run_id = os.environ.get("GITHUB_RUN_ID")
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT")
    return {
        "run_kind": RUN_KIND,
        "workflow_repository": os.environ.get("GITHUB_REPOSITORY"),
        "workflow_name": os.environ.get("GITHUB_WORKFLOW"),
        "workflow_ref": os.environ.get("GITHUB_REF"),
        "workflow_sha": os.environ.get("GITHUB_SHA"),
        "input_repository": os.environ.get("GITHUB_REPOSITORY"),
        "input_ref": os.environ.get("GITHUB_REF_NAME"),
        "input_sha": os.environ.get("GITHUB_SHA"),
        "github_run_id": int(run_id) if run_id else None,
        "github_run_attempt": int(attempt) if attempt else None,
        "schema_version": "001_phase1_core",
        "canonicalization_version": CANONICALIZATION_VERSION,
        "parameters": {
            "ordering_gate": "before_authoritative_classifier",
            "city_key": candidate["city_key"],
            "historical_episode_id": candidate["legacy_episode_id"],
        },
    }


def ensure_canonical_parent(
    conn,
    episode: dict[str, Any],
    *,
    db_branch: str | None = None,
) -> dict[str, Any]:
    candidate = _candidate(episode)
    exact, conflicts = _read_exact_and_conflicts(conn, candidate)
    if len(exact) > 1:
        raise CanonicalParentIdentityMismatch(
            "CANONICAL_PARENT_IDENTITY_MISMATCH: multiple exact canonical parents"
        )
    if len(exact) == 1:
        return {
            "city": candidate["city_key"],
            "episode_id": candidate["legacy_episode_id"],
            "start_at": candidate["start_at"],
            "end_at": candidate["end_at"],
            "ingestion_family": ingestion_family(candidate["city_key"]),
            "parent_uid": str(exact[0][0]),
            "parent_newly_inserted": False,
            "parent_already_present": True,
            "exact_parent_readback_count": 1,
            "canonical_parent_existed_before_classification": True,
        }

    nonidentical = [
        row for row in conflicts
        if not (
            str(row[1]) == candidate["legacy_episode_id"]
            and str(row[2]) == candidate["city_key"]
            and _as_utc(row[3]) == candidate["start_at"]
            and _as_utc(row[4]) == candidate["end_at"]
        )
    ]
    if nonidentical:
        same_identity_collision = any(
            str(row[1]) == candidate["legacy_episode_id"]
            or (
                str(row[2]) == candidate["city_key"]
                and _as_utc(row[3]) == candidate["start_at"]
                and _as_utc(row[4]) == candidate["end_at"]
            )
            for row in nonidentical
        )
        blocker = (
            CanonicalParentIdentityMismatch
            if same_identity_collision
            else SeparateCanonicalIdentityBlocker
        )
        raise blocker(
            f"{blocker.code}: non-equivalent canonical alert_episodes row exists for "
            f"{candidate['city_key']}:{candidate['legacy_episode_id']}"
        )

    _, persistence = _load_contract()
    branch = str(db_branch or os.environ.get(DB_BRANCH_ENV) or "").strip()
    if not branch:
        raise CanonicalParentPersistenceFailed(f"{DB_BRANCH_ENV} is required")

    run_uuid = uuid.uuid4()
    started_at = datetime.now(timezone.utc)
    try:
        with conn.transaction():
            with conn.cursor() as cur:
                persistence.insert_ingestion_run(
                    cur,
                    run_id=run_uuid,
                    source_key=None,
                    city_key=candidate["city_key"],
                    db_branch=branch,
                    provenance=_provenance(candidate),
                    started_at=started_at,
                )
                parent_uid, inserted = persistence.persist_episode(
                    cur, candidate, run_id=run_uuid
                )
                finished_at = datetime.now(timezone.utc)
                stats = {
                    "episodes_inserted": int(bool(inserted)),
                    "episodes_existing": int(not inserted),
                    "episodes_updated": 0,
                    "source_observations_inserted": 0,
                    "checkpoint_changes": 0,
                    "canonical_episode_count": 1,
                    "ordering_gate": "before_authoritative_classifier",
                }
                persistence.finalize_ingestion_run(
                    cur,
                    run_id=run_uuid,
                    stats=stats,
                    committed_at=finished_at,
                    finished_at=finished_at,
                )
    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        if isinstance(exc, ParentOrderingError):
            raise
        raise CanonicalParentPersistenceFailed(
            "canonical parent persistence failed before classifier: "
            f"{type(exc).__name__}: {exc}"
        ) from exc

    exact_after, conflicts_after = _read_exact_and_conflicts(conn, candidate)
    if len(exact_after) != 1:
        raise CanonicalParentPersistenceFailed(
            "canonical parent exact read-back failed after durable parent transaction: "
            f"matches={len(exact_after)} conflicts={len(conflicts_after)}"
        )
    if str(exact_after[0][0]) != str(parent_uid):
        raise CanonicalParentIdentityMismatch(
            "CANONICAL_PARENT_IDENTITY_MISMATCH: read-back parent UID differs from persisted UID"
        )
    return {
        "city": candidate["city_key"],
        "episode_id": candidate["legacy_episode_id"],
        "start_at": candidate["start_at"],
        "end_at": candidate["end_at"],
        "ingestion_family": ingestion_family(candidate["city_key"]),
        "parent_uid": str(parent_uid),
        "parent_newly_inserted": bool(inserted),
        "parent_already_present": not bool(inserted),
        "exact_parent_readback_count": 1,
        "canonical_parent_existed_before_classification": True,
    }


def live_persistence_eligible(
    episode: dict[str, Any],
    *,
    cutoff: datetime,
) -> bool:
    """Restart-safe live admission based only on the closed alert lifecycle."""
    cutoff_utc = _as_utc(cutoff)
    end_raw = episode.get("alert_end")
    if not end_raw:
        return False
    try:
        end_at = _as_utc(end_raw)
    except (TypeError, ValueError):
        return False
    return end_at >= cutoff_utc


def select_post_cutoff_live_episodes(
    state: dict[str, Any],
    *,
    cutoff: datetime,
    max_episodes: int | None,
) -> tuple[list[dict[str, Any]], int]:
    cutoff_utc = _as_utc(cutoff)
    rows: list[tuple[datetime, datetime, str, str, dict[str, Any]]] = []
    seen: set[tuple[str, str]] = set()
    for city_key, cstate in (state.get("cities") or {}).items():
        for episode in cstate.get("episodes") or []:
            episode_id = str(episode.get("episode_id") or "")
            if not episode_id or not live_persistence_eligible(episode, cutoff=cutoff_utc):
                continue
            key = (str(city_key), episode_id)
            if key in seen:
                continue
            seen.add(key)
            row = dict(episode)
            row["city_key"] = str(city_key)
            end_at = _as_utc(row.get("alert_end"))
            start_at = _as_utc(row.get("alert_start"))
            rows.append((end_at, start_at, str(city_key), episode_id, row))
    rows.sort(key=lambda item: (item[0], item[1], item[2], item[3]))
    total = len(rows)
    if max_episodes is not None:
        rows = rows[:max_episodes]
    return [row[4] for row in rows], total


def durable_eligibility_restart_proof() -> dict[str, Any]:
    cutoff = _as_utc("2026-10-07T16:53:19Z")
    fixtures = [
        {
            "label": "pre_cutoff_known_before_restart",
            "city_key": "kharkiv",
            "episode_id": "000000000000000000000001",
            "alert_start": "2026-10-07T16:00:00Z",
            "alert_end": "2026-10-07T16:53:18Z",
            "live_first_seen_at": "2026-10-07T16:10:00Z",
            "expected": False,
        },
        {
            "label": "exact_boundary_first_seen_after_restart",
            "city_key": "dnipro",
            "episode_id": "000000000000000000000002",
            "alert_start": "2026-10-07T16:40:00Z",
            "alert_end": "2026-10-07T16:53:19Z",
            "live_first_seen_at": "2026-10-07T18:00:00Z",
            "expected": True,
        },
        {
            "label": "crosses_boundary_known_before_restart",
            "city_key": "poltava",
            "episode_id": "000000000000000000000003",
            "alert_start": "2026-10-07T16:40:00Z",
            "alert_end": "2026-10-07T16:54:00Z",
            "live_first_seen_at": "2026-10-07T16:45:00Z",
            "expected": True,
        },
        {
            "label": "post_cutoff_first_seen_after_restart",
            "city_key": "kyiv",
            "episode_id": "000000000000000000000004",
            "alert_start": "2026-10-07T17:00:00Z",
            "alert_end": "2026-10-07T17:30:00Z",
            "live_first_seen_at": "2026-10-07T18:30:00Z",
            "expected": True,
        },
    ]

    before = {
        row["episode_id"]: live_persistence_eligible(row, cutoff=cutoff)
        for row in fixtures
    }
    recreated = []
    for row in fixtures:
        copy = dict(row)
        copy.pop("live_first_seen_at", None)
        copy["live_first_seen_at"] = "2099-01-01T00:00:00Z"
        recreated.append(copy)
    after = {
        row["episode_id"]: live_persistence_eligible(row, cutoff=cutoff)
        for row in recreated
    }
    for row in fixtures:
        episode_id = row["episode_id"]
        assert before[episode_id] is row["expected"]
        assert after[episode_id] is row["expected"]
    changes = sum(before[key] != after[key] for key in before)
    assert changes == 0
    return {
        "predicate": "alert_end >= LIVE_PERSISTENCE_ACTIVATION_CUTOFF",
        "cutoff_utc": "2026-10-07T16:53:19Z",
        "inclusive": True,
        "fixtures": [
            {
                "label": row["label"],
                "episode_start": row["alert_start"],
                "episode_end": row["alert_end"],
                "runtime_first_seen": row.get("live_first_seen_at"),
                "expected_eligibility": row["expected"],
                "actual_eligibility": before[row["episode_id"]],
                "eligibility_after_recreated_state": after[row["episode_id"]],
            }
            for row in fixtures
        ],
        "eligibility_changes_after_restart": changes,
    }


def preclassification_parent_gate(
    state: dict[str, Any],
    *,
    cutoff: datetime | None,
    max_episodes: int | None,
    dsn: str | None = None,
    connection=None,
) -> dict[str, Any]:
    enabled = bool(connection is not None or dsn)
    result: dict[str, Any] = {
        "enabled": enabled,
        "ordering": "CANONICAL_PARENT_BEFORE_AUTHORITATIVE_CLASSIFIER",
        "eligible_post_cutoff_live_episodes": 0,
        "selected_live_episodes": 0,
        "deferred_by_canary_limit": 0,
        "parents_ready": 0,
        "parents_newly_inserted": 0,
        "parents_already_present": 0,
        "records": [],
    }
    if not enabled:
        result["reason"] = "ATTACK_EVENT_DATABASE_URL_NOT_CONFIGURED"
        return result
    if cutoff is None:
        raise CanonicalParentPersistenceFailed(
            "PRODUCTION_PERSISTENCE_CANARY_CUTOFF is required for live parent ordering writes"
        )
    if max_episodes is not None and max_episodes < 1:
        raise CanonicalParentPersistenceFailed(
            "ATTACK_EVENT_PERSISTENCE_CANARY_MAX_EPISODES must be positive"
        )

    episodes, total = select_post_cutoff_live_episodes(
        state, cutoff=cutoff, max_episodes=None
    )
    result["eligibility_predicate"] = "alert_end >= LIVE_PERSISTENCE_ACTIVATION_CUTOFF"
    result["eligibility_boundary_inclusive"] = True
    result["eligible_post_cutoff_live_episodes"] = total
    result["selected_live_episodes"] = 0
    result["deferred_by_canary_limit"] = 0
    result["parents_synced_live_episodes"] = 0
    result["separate_identity_blockers"] = []

    own = connection is None
    conn = connection or psycopg.connect(str(dsn), autocommit=False)
    try:
        for episode in episodes:
            if max_episodes is not None and result["selected_live_episodes"] >= max_episodes:
                break
            result["selected_live_episodes"] += 1
            try:
                record = ensure_canonical_parent(conn, episode)
            except SeparateCanonicalIdentityBlocker as exc:
                result["separate_identity_blockers"].append({
                    "city": str(episode.get("city_key") or ""),
                    "episode_id": str(episode.get("episode_id") or ""),
                    "code": exc.code,
                    "action": "FAIL_CLOSED_IDENTITY_NOT_REPAIRED",
                })
                continue
            result["records"].append(record)
            result["parents_ready"] += 1
            result["parents_newly_inserted"] += int(record["parent_newly_inserted"])
            result["parents_already_present"] += int(record["parent_already_present"])
        result["parents_synced_live_episodes"] = result["parents_ready"]
        result["deferred_by_canary_limit"] = max(
            0,
            total - result["selected_live_episodes"],
        )
        return result
    finally:
        if own:
            conn.close()
