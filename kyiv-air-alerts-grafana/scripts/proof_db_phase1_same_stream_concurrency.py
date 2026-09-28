#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import psycopg
from psycopg.rows import dict_row

from db_phase1_persistence import (
    SCHEMA_VERSION,
    STREAM_LOCK_VERSION,
    acquire_stream_lock,
    finalize_ingestion_run,
    insert_ingestion_run,
    read_current_checkpoint,
    stream_lock_key,
)

SOURCE_KEY = "ukrainealarm_region_history"
CITY_KEY = "lviv"
STREAM_KEY = "region_id:90:AIR"
EXPECTED_LOCK_KEY = -6396446657197887857
EXPECTED_ACCEPTED_CHECKPOINT_ID = "40a0d262-2a79-405b-8e06-1af6e28bc908"
CANONICALIZATION_VERSION = "alert-canonicalization-v1"
ASSEMBLY_PROFILE = "lviv-historical-v1"

EXPECTED_INITIAL_COUNTS = {
    "ingestion_runs": 1,
    "alert_episodes": 126,
    "alert_episode_sources": 140,
    "ingestion_checkpoints": 1,
}
EXPECTED_A_ONLY_COUNTS = {
    "ingestion_runs": 2,
    "alert_episodes": 126,
    "alert_episode_sources": 140,
    "ingestion_checkpoints": 2,
}
EXPECTED_FINAL_COUNTS = {
    "ingestion_runs": 3,
    "alert_episodes": 126,
    "alert_episode_sources": 140,
    "ingestion_checkpoints": 3,
}

EVENTS: list[dict[str, Any]] = []
EVENT_LOCK = threading.Lock()
ORDERING_GATE = threading.Lock()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def mark(name: str, **details: Any) -> dict[str, Any]:
    entry = {
        "event": name,
        "monotonic_ns": time.monotonic_ns(),
        "utc": utc_now().isoformat(),
        **details,
    }
    with EVENT_LOCK:
        EVENTS.append(entry)
    rendered = " ".join(f"{k}={v}" for k, v in details.items())
    print(f"PROOF_EVENT {name}" + (f" {rendered}" if rendered else ""), flush=True)
    return entry


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def direct_hostname(database_url: str) -> str:
    host = urlparse(database_url).hostname or ""
    if not host or "-pooler" in host:
        raise RuntimeError("DIRECT POSTGRESQL CONNECTION UNAVAILABLE")
    return host


def scalar_int(value: Any) -> int:
    return int(value) if value is not None else 0


def counts(cursor: Any) -> dict[str, int]:
    cursor.execute(
        """
        SELECT
          (SELECT count(*) FROM ingestion_runs)::int AS ingestion_runs,
          (SELECT count(*) FROM alert_episodes)::int AS alert_episodes,
          (SELECT count(*) FROM alert_episode_sources)::int AS alert_episode_sources,
          (SELECT count(*) FROM ingestion_checkpoints)::int AS ingestion_checkpoints
        """
    )
    row = dict(cursor.fetchone())
    return {key: scalar_int(value) for key, value in row.items()}


def current_checkpoint(cursor: Any) -> dict[str, Any] | None:
    row = read_current_checkpoint(cursor, SOURCE_KEY, CITY_KEY, STREAM_KEY)
    if row is None:
        return None
    out = dict(row)
    if out.get("checkpoint_id") is not None:
        out["checkpoint_id"] = str(out["checkpoint_id"])
    if out.get("previous_checkpoint_id") is not None:
        out["previous_checkpoint_id"] = str(out["previous_checkpoint_id"])
    if out.get("checkpoint_seq") is not None:
        out["checkpoint_seq"] = int(out["checkpoint_seq"])
    return out


def checkpoint_history(cursor: Any) -> list[int]:
    cursor.execute(
        """
        SELECT checkpoint_seq
        FROM ingestion_checkpoints
        WHERE source_key = %s AND city_key = %s AND stream_key = %s
        ORDER BY checkpoint_seq
        """,
        (SOURCE_KEY, CITY_KEY, STREAM_KEY),
    )
    return [int(row["checkpoint_seq"]) for row in cursor.fetchall()]


def _hash_rows(rows: list[dict[str, Any]]) -> str:
    payload = json.dumps(rows, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def canonical_identity_snapshot(cursor: Any) -> dict[str, Any]:
    cursor.execute(
        """
        SELECT episode_uid::text AS episode_uid, legacy_episode_id
        FROM alert_episodes
        ORDER BY episode_uid
        """
    )
    episodes = [dict(row) for row in cursor.fetchall()]
    cursor.execute(
        """
        SELECT source_observation_id::text AS source_observation_id,
               episode_uid::text AS episode_uid,
               source_key, source_record_key_version, source_record_key
        FROM alert_episode_sources
        ORDER BY source_observation_id
        """
    )
    sources = [dict(row) for row in cursor.fetchall()]
    return {
        "episode_count": len(episodes),
        "episode_identity_sha256": _hash_rows(episodes),
        "source_count": len(sources),
        "source_identity_sha256": _hash_rows(sources),
    }


def snapshot_url(database_url: str) -> dict[str, Any]:
    with psycopg.connect(database_url, autocommit=True, row_factory=dict_row, connect_timeout=15) as conn:
        with conn.cursor() as cur:
            return {
                "counts": counts(cur),
                "checkpoint": current_checkpoint(cur),
                "checkpoint_history": checkpoint_history(cur),
            }


def run_provenance(writer: str) -> dict[str, Any]:
    run_id_text = os.environ.get("GITHUB_RUN_ID")
    attempt_text = os.environ.get("GITHUB_RUN_ATTEMPT")
    return {
        "run_kind": "same_stream_concurrency_proof",
        "schema_version": SCHEMA_VERSION,
        "canonicalization_version": CANONICALIZATION_VERSION,
        "parameters": {
            "assembly_profile": ASSEMBLY_PROFILE,
            "proof_only": True,
            "writer": writer,
            "no_alert": True,
        },
        "workflow_repository": os.environ.get("GITHUB_REPOSITORY"),
        "workflow_name": "Phase-1 Same-Stream Concurrency Proof",
        "workflow_ref": os.environ.get("GITHUB_REF"),
        "workflow_sha": os.environ.get("GITHUB_SHA"),
        "input_repository": os.environ.get("GITHUB_REPOSITORY"),
        "input_ref": os.environ.get("GITHUB_REF"),
        "input_sha": os.environ.get("GITHUB_SHA"),
        "github_run_id": int(run_id_text) if run_id_text else None,
        "github_run_attempt": int(attempt_text) if attempt_text else None,
    }


def insert_successor_checkpoint(
    cursor: Any,
    *,
    previous_checkpoint: dict[str, Any],
    run_id: uuid.UUID,
    writer: str,
) -> tuple[str, int]:
    next_seq = int(previous_checkpoint["checkpoint_seq"]) + 1
    cursor.execute(
        """/* PHASE1:PROOF_SUCCESSOR_CHECKPOINT_INSERT */
        INSERT INTO ingestion_checkpoints (
            source_key, city_key, stream_key, checkpoint_seq, checkpoint_kind,
            previous_checkpoint_id, checked_at, continuity_verified, continuity_method,
            continuity_anchor_at, observed_oldest_start_at, observed_latest_end_at,
            observed_record_count, cursor, metadata, created_by_run_id
        ) VALUES (
            %s, %s, %s, %s, 'poll',
            %s, %s, FALSE, NULL,
            NULL, NULL, NULL,
            0, %s::jsonb, %s::jsonb, %s
        )
        RETURNING checkpoint_id::text AS checkpoint_id
        """,
        (
            SOURCE_KEY,
            CITY_KEY,
            STREAM_KEY,
            next_seq,
            previous_checkpoint["checkpoint_id"],
            utc_now(),
            json.dumps({"proof_seq": next_seq, "writer": writer}, sort_keys=True),
            json.dumps(
                {
                    "proof_only": True,
                    "same_stream_concurrency": True,
                    "no_alert": True,
                    "writer": writer,
                },
                sort_keys=True,
            ),
            run_id,
        ),
    )
    row = dict(cursor.fetchone())
    return str(row["checkpoint_id"]), next_seq


def session_info(conn: Any) -> dict[str, Any]:
    previous_autocommit = conn.autocommit
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_backend_pid()::int AS pid")
            pid = int(cur.fetchone()["pid"])
            cur.execute("SHOW transaction_isolation")
            isolation = str(cur.fetchone()["transaction_isolation"]).lower()
    finally:
        conn.autocommit = previous_autocommit
    return {"pid": pid, "transaction_isolation": isolation}


def waiting_lock_evidence(observer: Any, pid_a: int, pid_b: int, acquired_event: threading.Event) -> list[dict[str, Any]]:
    deadline = time.monotonic() + 12.0
    last_rows: list[dict[str, Any]] = []
    while time.monotonic() < deadline:
        with observer.cursor() as cur:
            cur.execute(
                """
                SELECT pid::int AS pid, granted, mode,
                       classid::bigint AS classid, objid::bigint AS objid, objsubid::int AS objsubid
                FROM pg_locks
                WHERE locktype = 'advisory' AND pid = ANY(%s)
                ORDER BY pid, granted DESC
                """,
                ([pid_a, pid_b],),
            )
            last_rows = [dict(row) for row in cur.fetchall()]
        a_granted = [row for row in last_rows if row["pid"] == pid_a and row["granted"]]
        b_waiting = [row for row in last_rows if row["pid"] == pid_b and not row["granted"]]
        for a_row in a_granted:
            for b_row in b_waiting:
                same_key = all(
                    a_row[field] == b_row[field]
                    for field in ("classid", "objid", "objsubid")
                )
                if same_key:
                    require(not acquired_event.is_set(), "Writer B acquired the lock before Writer A committed")
                    return [a_row, b_row]
        require(not acquired_event.is_set(), "Writer B crossed the blocking lock boundary before Writer A committed")
        time.sleep(0.05)
    raise AssertionError(f"server-side waiting advisory lock evidence not observed: {last_rows}")


def verify_event_order() -> list[str]:
    required = [
        "A_LOCK_ACQUIRED",
        "B_BLOCKING_LOCK_STARTED",
        "A_COMMIT",
        "B_LOCK_ACQUIRED",
        "B_POSTLOCK_REREAD",
        "B_COMMIT",
    ]
    by_name = {event["event"]: event for event in EVENTS if event["event"] in required}
    require(set(by_name) == set(required), f"missing required ordering events: {set(required) - set(by_name)}")
    values = [int(by_name[name]["monotonic_ns"]) for name in required]
    require(values == sorted(values) and len(set(values)) == len(values), "required event order is not strictly monotonic")
    return required


def main() -> int:
    result_path = Path(os.environ["PHASE1_CONCURRENCY_RESULT"])
    target_url = os.environ["PHASE1_CONCURRENCY_DATABASE_URL"]
    branch_id = os.environ["PHASE1_CONCURRENCY_BRANCH_ID"]
    direct_hostname(target_url)

    lock_key = stream_lock_key(SOURCE_KEY, CITY_KEY, STREAM_KEY)
    require(STREAM_LOCK_VERSION == "phase1-stream-lock-v1", "unexpected production stream lock version")
    require(lock_key == EXPECTED_LOCK_KEY, f"unexpected production stream lock key: {lock_key}")

    result: dict[str, Any] = {
        "schema_version": "db-phase1-same-stream-concurrency-proof-v1",
        "verdict": "PHASE-1 SAME-STREAM CONCURRENCY BLOCKED",
        "git": {
            "base_sha": os.environ.get("PHASE1_PROOF_BASE_SHA"),
            "proof_workflow_sha": os.environ.get("GITHUB_SHA"),
            "workflow_run_id": os.environ.get("GITHUB_RUN_ID"),
            "ddl_blob": os.environ.get("PHASE1_DDL_BLOB"),
            "persistence_blob": os.environ.get("PHASE1_PERSISTENCE_BLOB"),
            "importer_blob": os.environ.get("PHASE1_IMPORTER_BLOB"),
        },
        "neon": {
            "project_id": os.environ.get("NEON_PROJECT_ID"),
            "branch_id": branch_id,
            "branch_name": os.environ.get("E2E_BRANCH_NAME"),
            "parent_branch_id": os.environ.get("E2E_PARENT_BRANCH_ID"),
            "direct_unpooled_connection": True,
        },
        "stream_identity": {"source": SOURCE_KEY, "city": CITY_KEY, "stream": STREAM_KEY},
        "lock_key_version": STREAM_LOCK_VERSION,
        "lock_key": lock_key,
        "credentials_exposed": False,
        "writer_a_committed": False,
        "writer_b_committed": False,
        "events": EVENTS,
    }

    protected_envs = {
        "primary": "PHASE1_PRIMARY_DATABASE_URL",
        "accepted_bootstrap": "PHASE1_ACCEPTED_DATABASE_URL",
        "accepted_live_e2e": "PHASE1_LIVE_E2E_DATABASE_URL",
        "old_blocked_concurrency": "PHASE1_BLOCKED_DATABASE_URL",
    }

    conn_a = conn_b = observer = None
    b_thread: threading.Thread | None = None
    b_blocking_started = threading.Event()
    b_lock_acquired = threading.Event()
    b_allow_postlock = threading.Event()
    b_abort = threading.Event()
    b_done = threading.Event()
    b_error: list[BaseException] = []
    writer_a_run_id: str | None = None
    writer_b_run_id: str | None = None
    a_committed = False
    b_committed = False

    try:
        protected_before = {name: snapshot_url(os.environ[env]) for name, env in protected_envs.items()}
        result["protected_before"] = protected_before

        require(protected_before["primary"]["counts"] == {
            "ingestion_runs": 0, "alert_episodes": 0, "alert_episode_sources": 0, "ingestion_checkpoints": 0
        }, f"primary baseline changed: {protected_before['primary']}")
        require(protected_before["accepted_bootstrap"]["counts"] == EXPECTED_INITIAL_COUNTS,
                f"accepted bootstrap baseline changed: {protected_before['accepted_bootstrap']}")
        accepted_cp = protected_before["accepted_bootstrap"]["checkpoint"]
        require(accepted_cp is not None and accepted_cp["checkpoint_id"] == EXPECTED_ACCEPTED_CHECKPOINT_ID and accepted_cp["checkpoint_seq"] == 1,
                f"accepted bootstrap checkpoint changed: {accepted_cp}")
        require(protected_before["old_blocked_concurrency"]["counts"] == {
            "ingestion_runs": 2, "alert_episodes": 126, "alert_episode_sources": 140, "ingestion_checkpoints": 2
        }, f"old blocked branch changed: {protected_before['old_blocked_concurrency']}")

        conn_a = psycopg.connect(target_url, row_factory=dict_row, connect_timeout=15)
        conn_b = psycopg.connect(target_url, row_factory=dict_row, connect_timeout=15)
        observer = psycopg.connect(target_url, autocommit=True, row_factory=dict_row, connect_timeout=15)

        info_a = session_info(conn_a)
        info_b = session_info(conn_b)
        result["writer_a_backend_pid"] = info_a["pid"]
        result["writer_b_backend_pid"] = info_b["pid"]
        result["transaction_isolation_a"] = info_a["transaction_isolation"]
        result["transaction_isolation_b"] = info_b["transaction_isolation"]
        require(info_a["pid"] != info_b["pid"], "TWO INDEPENDENT POSTGRESQL SESSIONS NOT ESTABLISHED")
        require(info_a["transaction_isolation"] == "read committed", f"Writer A isolation is {info_a['transaction_isolation']}")
        require(info_b["transaction_isolation"] == "read committed", f"Writer B isolation is {info_b['transaction_isolation']}")

        with observer.cursor() as cur:
            initial_counts = counts(cur)
            initial_cp = current_checkpoint(cur)
            initial_identity = canonical_identity_snapshot(cur)
        result["initial_counts"] = initial_counts
        result["initial_checkpoint"] = initial_cp
        result["initial_canonical_identity"] = initial_identity
        require(initial_counts == EXPECTED_INITIAL_COUNTS, f"unexpected inherited counts: {initial_counts}")
        require(initial_cp is not None and initial_cp["checkpoint_id"] == EXPECTED_ACCEPTED_CHECKPOINT_ID and initial_cp["checkpoint_seq"] == 1,
                f"unexpected inherited checkpoint: {initial_cp}")

        with conn_a.cursor() as cur_a:
            cur_a.execute("BEGIN")
            acquired_key = acquire_stream_lock(cur_a, SOURCE_KEY, CITY_KEY, STREAM_KEY)
            require(acquired_key == lock_key, "Writer A acquired a different lock key")
            mark("A_LOCK_ACQUIRED", pid=info_a["pid"])
            a_cp = current_checkpoint(cur_a)
            require(a_cp is not None and a_cp["checkpoint_seq"] == 1, f"Writer A post-lock checkpoint was {a_cp}")
            result["writer_a_postlock_checkpoint_seq"] = 1
            mark("A_POSTLOCK_REREAD", checkpoint_seq=1)

            run_a_uuid = uuid.uuid4()
            writer_a_run_id = str(run_a_uuid)
            result["writer_a_run_id"] = writer_a_run_id
            started = utc_now()
            insert_ingestion_run(
                cur_a,
                run_id=run_a_uuid,
                source_key=SOURCE_KEY,
                city_key=CITY_KEY,
                db_branch=branch_id,
                provenance=run_provenance("A"),
                started_at=started,
            )
            checkpoint_a_id, checkpoint_a_seq = insert_successor_checkpoint(
                cur_a, previous_checkpoint=a_cp, run_id=run_a_uuid, writer="A"
            )
            require(checkpoint_a_seq == 2, f"Writer A successor checkpoint seq was {checkpoint_a_seq}")
            finalize_ingestion_run(
                cur_a,
                run_id=run_a_uuid,
                stats={"proof_only": True, "writer": "A", "checkpoint_seq": checkpoint_a_seq, "no_alert": True},
                committed_at=utc_now(),
                finished_at=utc_now(),
            )
            result["writer_a_prepared_checkpoint_id"] = checkpoint_a_id
            result["writer_a_committed_seq"] = checkpoint_a_seq
            mark("A_WRITES_PREPARED", checkpoint_seq=checkpoint_a_seq)

        with conn_b.cursor() as cur_b:
            cur_b.execute("BEGIN")
            b_pre = current_checkpoint(cur_b)
            require(b_pre is not None and b_pre["checkpoint_seq"] == 1, f"Writer B pre-lock checkpoint was {b_pre}")
            result["writer_b_prelock_checkpoint_seq"] = 1
            mark("B_PRELOCK_REREAD", checkpoint_seq=1)
            cur_b.execute("SELECT pg_try_advisory_xact_lock(%s) AS acquired", (lock_key,))
            try_result = bool(cur_b.fetchone()["acquired"])
            result["writer_b_try_lock_while_a_holds"] = try_result
            mark("B_TRY_LOCK", acquired=try_result)
            require(try_result is False, "Writer B unexpectedly acquired pg_try_advisory_xact_lock while A held it")

        def writer_b() -> None:
            nonlocal writer_b_run_id, b_committed
            try:
                with conn_b.cursor() as cur:
                    mark("B_BLOCKING_LOCK_STARTED", pid=info_b["pid"])
                    b_blocking_started.set()
                    acquired = acquire_stream_lock(cur, SOURCE_KEY, CITY_KEY, STREAM_KEY)
                    require(acquired == lock_key, "Writer B acquired a different lock key")
                    with ORDERING_GATE:
                        mark("B_LOCK_ACQUIRED", pid=info_b["pid"])
                        b_lock_acquired.set()
                    if b_abort.is_set():
                        conn_b.rollback()
                        mark("B_ABORTED_AFTER_LOCK")
                        return
                    if not b_allow_postlock.wait(timeout=20):
                        raise AssertionError("Writer B post-lock gate timed out")
                    if b_abort.is_set():
                        conn_b.rollback()
                        mark("B_ABORTED_BEFORE_POSTLOCK_REREAD")
                        return
                    b_post = current_checkpoint(cur)
                    require(b_post is not None and b_post["checkpoint_seq"] == 2, f"Writer B post-lock checkpoint was {b_post}")
                    result["writer_b_postlock_checkpoint_seq"] = 2
                    mark("B_POSTLOCK_REREAD", checkpoint_seq=2)

                    run_b_uuid = uuid.uuid4()
                    writer_b_run_id = str(run_b_uuid)
                    result["writer_b_run_id"] = writer_b_run_id
                    insert_ingestion_run(
                        cur,
                        run_id=run_b_uuid,
                        source_key=SOURCE_KEY,
                        city_key=CITY_KEY,
                        db_branch=branch_id,
                        provenance=run_provenance("B"),
                        started_at=utc_now(),
                    )
                    checkpoint_b_id, checkpoint_b_seq = insert_successor_checkpoint(
                        cur, previous_checkpoint=b_post, run_id=run_b_uuid, writer="B"
                    )
                    require(checkpoint_b_seq == 3, f"Writer B successor checkpoint seq was {checkpoint_b_seq}")
                    finalize_ingestion_run(
                        cur,
                        run_id=run_b_uuid,
                        stats={"proof_only": True, "writer": "B", "checkpoint_seq": checkpoint_b_seq, "no_alert": True},
                        committed_at=utc_now(),
                        finished_at=utc_now(),
                    )
                    result["writer_b_prepared_checkpoint_id"] = checkpoint_b_id
                    result["writer_b_committed_seq"] = checkpoint_b_seq
                    conn_b.commit()
                    b_committed = True
                    result["writer_b_committed"] = True
                    mark("B_COMMIT", checkpoint_seq=checkpoint_b_seq)
            except BaseException as exc:
                b_error.append(exc)
                try:
                    if not b_committed:
                        conn_b.rollback()
                except Exception:
                    pass
            finally:
                b_done.set()

        b_thread = threading.Thread(target=writer_b, name="writer-b", daemon=True)
        b_thread.start()
        require(b_blocking_started.wait(timeout=5), "Writer B did not enter blocking lock call")
        require(not b_lock_acquired.is_set(), "Writer B lock acquired event was already set before waiting evidence")

        evidence = waiting_lock_evidence(observer, info_a["pid"], info_b["pid"], b_lock_acquired)
        result["server_side_waiting_evidence"] = evidence
        result["writer_b_lock_acquired_event_while_a_holds"] = b_lock_acquired.is_set()
        require(result["writer_b_lock_acquired_event_while_a_holds"] is False,
                "Writer B crossed lock boundary before Writer A commit")
        mark("B_WAITING_CONFIRMED")

        with ORDERING_GATE:
            conn_a.commit()
            a_committed = True
            result["writer_a_committed"] = True
            mark("A_COMMIT", checkpoint_seq=2)

        require(b_lock_acquired.wait(timeout=10), "Writer B did not acquire lock after Writer A commit")
        if b_error:
            raise b_error[0]

        with observer.cursor() as cur:
            a_only_counts = counts(cur)
            a_only_cp = current_checkpoint(cur)
        result["after_a_commit_counts"] = a_only_counts
        result["after_a_commit_checkpoint"] = a_only_cp
        require(a_only_counts == EXPECTED_A_ONLY_COUNTS, f"unexpected state after Writer A commit: {a_only_counts}")
        require(a_only_cp is not None and a_only_cp["checkpoint_seq"] == 2,
                f"unexpected current checkpoint after Writer A commit: {a_only_cp}")

        b_allow_postlock.set()
        require(b_done.wait(timeout=20), "Writer B did not finish")
        if b_thread is not None:
            b_thread.join(timeout=1)
        if b_error:
            raise b_error[0]
        require(b_committed, "Writer B did not commit")

        with observer.cursor() as cur:
            final_counts = counts(cur)
            final_cp = current_checkpoint(cur)
            history = checkpoint_history(cur)
            final_identity = canonical_identity_snapshot(cur)
        result["final_counts"] = final_counts
        result["final_checkpoint"] = final_cp
        result["checkpoint_history"] = history
        result["final_canonical_identity"] = final_identity
        result["canonical_identity_stability"] = final_identity == initial_identity
        require(final_counts == EXPECTED_FINAL_COUNTS, f"unexpected final counts: {final_counts}")
        require(final_cp is not None and final_cp["checkpoint_seq"] == 3,
                f"unexpected final checkpoint: {final_cp}")
        require(history == [1, 2, 3], f"unexpected checkpoint history: {history}")
        require(final_identity == initial_identity, "canonical episode/source identities changed")
        require(result["writer_b_prelock_checkpoint_seq"] == 1 and result["writer_b_postlock_checkpoint_seq"] == 2,
                "Writer B did not demonstrate stale-prelock then fresh-postlock checkpoint state")

        protected_after = {name: snapshot_url(os.environ[env]) for name, env in protected_envs.items()}
        result["protected_after"] = protected_after
        result["isolation_checks"] = {
            name: {
                "before": protected_before[name],
                "after": protected_after[name],
                "unchanged": protected_before[name] == protected_after[name],
            }
            for name in protected_envs
        }
        require(all(item["unchanged"] for item in result["isolation_checks"].values()),
                f"protected branch changed: {result['isolation_checks']}")
        require(protected_after["primary"]["counts"] == {
            "ingestion_runs": 0, "alert_episodes": 0, "alert_episode_sources": 0, "ingestion_checkpoints": 0
        }, "primary isolation failed")
        require(protected_after["accepted_bootstrap"]["counts"] == EXPECTED_INITIAL_COUNTS,
                "accepted bootstrap isolation failed")
        accepted_after_cp = protected_after["accepted_bootstrap"]["checkpoint"]
        require(accepted_after_cp is not None and accepted_after_cp["checkpoint_id"] == EXPECTED_ACCEPTED_CHECKPOINT_ID and accepted_after_cp["checkpoint_seq"] == 1,
                "accepted bootstrap checkpoint isolation failed")
        require(protected_after["old_blocked_concurrency"]["counts"] == {
            "ingestion_runs": 2, "alert_episodes": 126, "alert_episode_sources": 140, "ingestion_checkpoints": 2
        }, "old blocked concurrency branch isolation failed")

        required_order = verify_event_order()
        result["event_ordering"] = {
            "required_order": required_order,
            "events": list(EVENTS),
            "strictly_monotonic": True,
        }
        result["verdict"] = "PHASE-1 SAME-STREAM CONCURRENCY PROVEN"
        result["writer_a_committed"] = a_committed
        result["writer_b_committed"] = b_committed
        result["events"] = list(EVENTS)
        result_path.write_text(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
        print("PHASE-1 SAME-STREAM CONCURRENCY PROVEN")
        print("PROOF_RESULT_JSON=" + json.dumps(result, sort_keys=True, separators=(",", ":"), default=str), flush=True)
        return 0

    except BaseException as exc:
        b_abort.set()
        if not a_committed and conn_a is not None:
            try:
                conn_a.rollback()
            except Exception:
                pass
        b_allow_postlock.set()
        if b_thread is not None and b_thread.is_alive():
            b_done.wait(timeout=10)
            b_thread.join(timeout=1)
        if not b_committed and conn_b is not None:
            try:
                conn_b.rollback()
            except Exception:
                pass

        result["writer_a_committed"] = a_committed
        result["writer_b_committed"] = b_committed
        result["writer_a_run_id"] = writer_a_run_id
        result["writer_b_run_id"] = writer_b_run_id
        result["failing_step"] = EVENTS[-1]["event"] if EVENTS else "preflight"
        result["failure_type"] = type(exc).__name__
        result["failure_message"] = str(exc) if isinstance(exc, AssertionError) else type(exc).__name__
        result["events"] = list(EVENTS)
        try:
            if observer is not None:
                with observer.cursor() as cur:
                    result["observed_final_counts"] = counts(cur)
                    result["observed_final_checkpoint"] = current_checkpoint(cur)
                    result["observed_checkpoint_history"] = checkpoint_history(cur)
        except Exception as snap_exc:
            result["target_failure_snapshot_error_type"] = type(snap_exc).__name__
        try:
            result["protected_after"] = {
                name: snapshot_url(os.environ[env]) for name, env in protected_envs.items()
            }
            if "protected_before" in result:
                result["isolation_checks"] = {
                    name: {
                        "before": result["protected_before"][name],
                        "after": result["protected_after"][name],
                        "unchanged": result["protected_before"][name] == result["protected_after"][name],
                    }
                    for name in protected_envs
                }
        except Exception as isolation_exc:
            result["parent_isolation_snapshot_error_type"] = type(isolation_exc).__name__
        result_path.write_text(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
        print("PHASE-1 SAME-STREAM CONCURRENCY BLOCKED")
        print("PROOF_RESULT_JSON=" + json.dumps(result, sort_keys=True, separators=(",", ":"), default=str), flush=True)
        raise
    finally:
        for conn in (observer, conn_b, conn_a):
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass


if __name__ == "__main__":
    raise SystemExit(main())
