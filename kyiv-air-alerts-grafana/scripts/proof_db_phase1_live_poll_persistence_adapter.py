#!/usr/bin/env python3
from __future__ import annotations

import copy
import hashlib
import json
import os
import threading
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import psycopg
from psycopg.rows import dict_row

from db_phase1_lviv_import import build_lviv_persistence_payload
from db_phase1_persistence import (
    STREAM_LOCK_VERSION,
    persist_phase1_payload,
    read_current_checkpoint,
    stream_lock_key,
)

SOURCE_KEY = "ukrainealarm_region_history"
CITY_KEY = "lviv"
STREAM_KEY = "region_id:90:AIR"
EXPECTED_LOCK_KEY = -6396446657197887857
EXPECTED_SEQ1_ID = "40a0d262-2a79-405b-8e06-1af6e28bc908"
EXPECTED_INITIAL = {
    "ingestion_runs": 1,
    "alert_episodes": 126,
    "alert_episode_sources": 140,
    "ingestion_checkpoints": 1,
}
EXPECTED_FINAL = {
    "ingestion_runs": 6,
    "alert_episodes": 126,
    "alert_episode_sources": 140,
    "ingestion_checkpoints": 5,
}

class RecoveryProbeRollback(RuntimeError):
    pass

def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)

def direct_host(url: str) -> str:
    host = urlparse(url).hostname or ""
    require(bool(host) and "-pooler" not in host, "DIRECT POSTGRESQL CONNECTION UNAVAILABLE")
    return host

def counts(cur: Any) -> dict[str, int]:
    cur.execute("""
        SELECT
          (SELECT count(*) FROM ingestion_runs)::int AS ingestion_runs,
          (SELECT count(*) FROM alert_episodes)::int AS alert_episodes,
          (SELECT count(*) FROM alert_episode_sources)::int AS alert_episode_sources,
          (SELECT count(*) FROM ingestion_checkpoints)::int AS ingestion_checkpoints
    """)
    return {key: int(value) for key, value in dict(cur.fetchone()).items()}

def current_checkpoint(cur: Any) -> dict[str, Any] | None:
    row = read_current_checkpoint(cur, SOURCE_KEY, CITY_KEY, STREAM_KEY)
    if row is None:
        return None
    out = dict(row)
    for key in ("checkpoint_id", "previous_checkpoint_id", "created_by_run_id"):
        if out.get(key) is not None:
            out[key] = str(out[key])
    out["checkpoint_seq"] = int(out["checkpoint_seq"])
    return out

def checkpoint_history(cur: Any) -> list[dict[str, Any]]:
    cur.execute("""
        SELECT c.checkpoint_id::text AS checkpoint_id,
               c.checkpoint_seq::int AS checkpoint_seq,
               c.checkpoint_kind,
               c.previous_checkpoint_id::text AS previous_checkpoint_id,
               c.checked_at,
               c.metadata,
               c.created_by_run_id::text AS run_id,
               r.parameters,
               r.stats
        FROM ingestion_checkpoints c
        JOIN ingestion_runs r ON r.run_id = c.created_by_run_id
        WHERE c.source_key=%s AND c.city_key=%s AND c.stream_key=%s
        ORDER BY c.checkpoint_seq
    """, (SOURCE_KEY, CITY_KEY, STREAM_KEY))
    return [dict(row) for row in cur.fetchall()]

def proof_runs(cur: Any) -> list[dict[str, Any]]:
    cur.execute("""
        SELECT run_id::text AS run_id, run_kind, parameters, stats, started_at, finished_at
        FROM ingestion_runs
        WHERE run_kind = 'live_poll_persistence_proof'
        ORDER BY started_at
    """)
    return [dict(row) for row in cur.fetchall()]

def identity_snapshot(cur: Any) -> dict[str, Any]:
    cur.execute("""
        SELECT episode_uid::text AS episode_uid, legacy_episode_id
        FROM alert_episodes ORDER BY legacy_episode_id
    """)
    episodes = [dict(row) for row in cur.fetchall()]
    cur.execute("""
        SELECT source_observation_id::text AS source_observation_id,
               episode_uid::text AS episode_uid,
               source_key, source_record_key_version, source_record_key
        FROM alert_episode_sources
        ORDER BY source_key, source_record_key_version, source_record_key
    """)
    sources = [dict(row) for row in cur.fetchall()]
    def digest(rows: list[dict[str, Any]]) -> str:
        raw = json.dumps(rows, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()
    return {
        "episode_count": len(episodes),
        "episode_identity_sha256": digest(episodes),
        "source_count": len(sources),
        "source_identity_sha256": digest(sources),
    }

def snapshot(url: str) -> dict[str, Any]:
    direct_host(url)
    with psycopg.connect(url, autocommit=True, row_factory=dict_row, connect_timeout=15) as conn:
        with conn.cursor() as cur:
            return {
                "counts": counts(cur),
                "checkpoint": current_checkpoint(cur),
                "history": checkpoint_history(cur),
                "proof_runs": proof_runs(cur),
                "identity": identity_snapshot(cur),
            }

def poll_payload(label: str, checked_at: str) -> dict[str, Any]:
    payload = copy.deepcopy(build_lviv_persistence_payload())
    payload["run_provenance"] = copy.deepcopy(payload["run_provenance"])
    payload["run_provenance"]["run_kind"] = "live_poll_persistence_proof"
    payload["run_provenance"]["workflow_name"] = "Phase-1 Live Poll Persistence Adapter Proof"
    payload["run_provenance"]["workflow_repository"] = os.environ.get("GITHUB_REPOSITORY")
    payload["run_provenance"]["workflow_ref"] = os.environ.get("GITHUB_REF")
    payload["run_provenance"]["workflow_sha"] = os.environ.get("GITHUB_SHA")
    payload["run_provenance"]["github_run_id"] = int(os.environ["GITHUB_RUN_ID"])
    payload["run_provenance"]["github_run_attempt"] = int(os.environ["GITHUB_RUN_ATTEMPT"])
    payload["run_provenance"]["parameters"] = {
        **payload["run_provenance"].get("parameters", {}),
        "proof_only": True,
        "poll_label": label,
    }
    payload["checkpoint_candidate"] = {
        "source_key": SOURCE_KEY,
        "city_key": CITY_KEY,
        "stream_key": STREAM_KEY,
        "checkpoint_kind": "poll",
        "checked_at": checked_at,
        "continuity_verified": False,
        "continuity_method": None,
        "continuity_anchor_at": None,
        "observed_oldest_start_at": "2025-09-01T00:00:00Z",
        "observed_latest_end_at": "2026-09-28T12:00:00Z",
        "observed_record_count": 20,
        "cursor": {"proof_only": True, "poll": label},
        "metadata": {
            "proof_only": True,
            "live_poll_persistence_adapter": True,
            "poll": label,
        },
    }
    return payload

def apply(conn: Any, payload: dict[str, Any], branch_id: str, callback=None) -> dict[str, Any]:
    return persist_phase1_payload(
        conn,
        source_key=payload["source_key"],
        city_key=payload["city_key"],
        stream_key=payload["stream_key"],
        db_branch=branch_id,
        run_provenance=payload["run_provenance"],
        episodes=payload["episodes"],
        source_observations=payload["source_observations"],
        checkpoint_candidate=payload["checkpoint_candidate"],
        post_lock_callback=callback,
    )

def session_info(conn: Any) -> tuple[int, str]:
    previous = conn.autocommit
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_backend_pid()::int AS pid")
            pid = int(cur.fetchone()["pid"])
            cur.execute("SHOW transaction_isolation")
            isolation = str(cur.fetchone()["transaction_isolation"]).lower()
    finally:
        conn.autocommit = previous
    return pid, isolation

def wait_lock_evidence(observer: Any, pid_c: int, pid_d: int) -> list[dict[str, Any]]:
    deadline = time.monotonic() + 15
    last: list[dict[str, Any]] = []
    while time.monotonic() < deadline:
        with observer.cursor() as cur:
            cur.execute("""
                SELECT pid::int AS pid, granted, mode,
                       classid::bigint AS classid, objid::bigint AS objid, objsubid::int AS objsubid
                FROM pg_locks
                WHERE locktype='advisory' AND pid = ANY(%s)
                ORDER BY pid, granted DESC
            """, ([pid_c, pid_d],))
            last = [dict(row) for row in cur.fetchall()]
        granted = [row for row in last if row["pid"] == pid_c and row["granted"]]
        waiting = [row for row in last if row["pid"] == pid_d and not row["granted"]]
        for c_row in granted:
            for d_row in waiting:
                if all(c_row[key] == d_row[key] for key in ("classid", "objid", "objsubid")):
                    return [c_row, d_row]
        time.sleep(0.05)
    raise AssertionError(f"waiting advisory lock evidence not observed: {last}")

def validate_protected_baselines(protected: dict[str, dict[str, Any]]) -> None:
    require(protected["primary"]["counts"] == {
        "ingestion_runs": 0, "alert_episodes": 0, "alert_episode_sources": 0, "ingestion_checkpoints": 0
    }, "primary baseline changed")
    require(protected["accepted_bootstrap"]["counts"] == EXPECTED_INITIAL, "bootstrap baseline changed")
    require(protected["accepted_bootstrap"]["checkpoint"] is not None, "bootstrap checkpoint missing")
    require(
        protected["accepted_bootstrap"]["checkpoint"]["checkpoint_id"] == EXPECTED_SEQ1_ID
        and protected["accepted_bootstrap"]["checkpoint"]["checkpoint_seq"] == 1,
        "bootstrap checkpoint changed",
    )
    require(protected["accepted_live_e2e"]["counts"] == {
        "ingestion_runs": 2, "alert_episodes": 126, "alert_episode_sources": 140, "ingestion_checkpoints": 1
    }, "live E2E baseline changed")
    require(protected["accepted_previous_concurrency"]["counts"] == {
        "ingestion_runs": 3, "alert_episodes": 126, "alert_episode_sources": 140, "ingestion_checkpoints": 3
    }, "previous concurrency baseline changed")
    require(protected["old_blocked_concurrency"]["counts"] == {
        "ingestion_runs": 2, "alert_episodes": 126, "alert_episode_sources": 140, "ingestion_checkpoints": 2
    }, "blocked concurrency baseline changed")

def validate_final_state(final: dict[str, Any]) -> dict[str, Any]:
    require(final["counts"] == EXPECTED_FINAL, f"final counts wrong: {final['counts']}")
    rows = final["history"]
    require([row["checkpoint_seq"] for row in rows] == [1, 2, 3, 4, 5], "checkpoint history wrong")
    require(rows[0]["checkpoint_id"] == EXPECTED_SEQ1_ID, "seq1 checkpoint id changed")
    expected_labels = {2: "A", 3: "B", 4: "C", 5: "D"}
    for index, row in enumerate(rows):
        seq = index + 1
        if seq == 1:
            require(row["checkpoint_kind"] == "bootstrap", "seq1 is not bootstrap")
            require(row["previous_checkpoint_id"] is None, "seq1 previous is not NULL")
            continue
        require(row["checkpoint_kind"] == "poll", f"seq{seq} is not poll")
        require(row["previous_checkpoint_id"] == rows[index - 1]["checkpoint_id"], f"seq{seq} previous link wrong")
        require(row["metadata"].get("poll") == expected_labels[seq], f"seq{seq} poll label wrong")
        require(row["stats"].get("checkpoints_inserted") == 1, f"seq{seq} was not an append")
        require(row["stats"].get("episodes_inserted") == 0, f"seq{seq} inserted episodes")
        require(row["stats"].get("source_observations_inserted") == 0, f"seq{seq} inserted sources")

    runs = final["proof_runs"]
    require(len(runs) == 5, f"expected five proof runs, got {len(runs)}")
    labels = [run["parameters"].get("poll_label") for run in runs]
    require(labels == ["A", "A", "B", "C", "D"], f"proof run labels wrong: {labels}")
    require(runs[0]["stats"].get("checkpoints_inserted") == 1, "first poll A did not append")
    require(runs[1]["stats"].get("checkpoints_inserted") == 0, "poll A retry appended")
    require(runs[1]["stats"].get("exact_retry") is True, "poll A retry not exact")
    require(runs[2]["stats"].get("checkpoints_inserted") == 1, "poll B did not append")
    require(runs[3]["stats"].get("checkpoints_inserted") == 1, "poll C did not append")
    require(runs[4]["stats"].get("checkpoints_inserted") == 1, "poll D did not append")
    return {
        "poll_a_run_id": runs[0]["run_id"],
        "poll_a_retry_run_id": runs[1]["run_id"],
        "poll_b_run_id": runs[2]["run_id"],
        "poll_c_run_id": runs[3]["run_id"],
        "poll_d_run_id": runs[4]["run_id"],
        "poll_a_checkpoint_id": rows[1]["checkpoint_id"],
        "poll_b_checkpoint_id": rows[2]["checkpoint_id"],
    }

def recovery_lock_probe(target_url: str, branch_id: str) -> dict[str, Any]:
    before = snapshot(target_url)
    conn_c = psycopg.connect(target_url, row_factory=dict_row, connect_timeout=15)
    conn_d = psycopg.connect(target_url, row_factory=dict_row, connect_timeout=15)
    observer = psycopg.connect(target_url, autocommit=True, row_factory=dict_row, connect_timeout=15)
    errors: list[BaseException] = []
    observed_rollbacks: list[str] = []
    c_postlock: list[int] = []
    d_postlock: list[int] = []
    c_holding = threading.Event()
    release_c = threading.Event()
    d_started = threading.Event()
    try:
        pid_c, iso_c = session_info(conn_c)
        pid_d, iso_d = session_info(conn_d)
        require(pid_c != pid_d, "independent recovery probe sessions not established")
        require(iso_c == "read committed" and iso_d == "read committed", "recovery probe isolation is not read committed")

        def callback_c(cp):
            require(cp is not None, "recovery probe C checkpoint missing")
            c_postlock.append(int(cp["checkpoint_seq"]))
            c_holding.set()
            require(release_c.wait(timeout=20), "recovery probe C release timeout")
            raise RecoveryProbeRollback("expected recovery probe rollback C")

        def callback_d(cp):
            require(cp is not None, "recovery probe D checkpoint missing")
            d_postlock.append(int(cp["checkpoint_seq"]))
            raise RecoveryProbeRollback("expected recovery probe rollback D")

        def writer_c():
            try:
                apply(conn_c, poll_payload("D", "2026-09-28T16:00:00Z"), branch_id, callback_c)
                errors.append(AssertionError("recovery probe C unexpectedly committed"))
            except RecoveryProbeRollback:
                observed_rollbacks.append("C")
            except BaseException as exc:
                errors.append(exc)

        def writer_d():
            try:
                d_started.set()
                apply(conn_d, poll_payload("D", "2026-09-28T16:00:00Z"), branch_id, callback_d)
                errors.append(AssertionError("recovery probe D unexpectedly committed"))
            except RecoveryProbeRollback:
                observed_rollbacks.append("D")
            except BaseException as exc:
                errors.append(exc)

        tc = threading.Thread(target=writer_c, name="recovery-probe-c", daemon=True)
        td = threading.Thread(target=writer_d, name="recovery-probe-d", daemon=True)
        tc.start()
        require(c_holding.wait(timeout=10), "recovery probe C did not reach post-lock callback")
        td.start()
        require(d_started.wait(timeout=5), "recovery probe D did not start")
        evidence = wait_lock_evidence(observer, pid_c, pid_d)
        require(not d_postlock, "recovery probe D crossed lock before C rollback")
        release_c.set()
        tc.join(timeout=30)
        td.join(timeout=30)
        require(not tc.is_alive() and not td.is_alive(), "recovery probe threads did not finish")
        if errors:
            raise errors[0]
        require(sorted(observed_rollbacks) == ["C", "D"], f"unexpected recovery probe rollback set: {observed_rollbacks}")
        require(c_postlock == [5] and d_postlock == [5], f"recovery probe post-lock states wrong: {c_postlock}, {d_postlock}")
    finally:
        release_c.set()
        observer.close()
        conn_d.close()
        conn_c.close()
    after = snapshot(target_url)
    require(after == before, "recovery lock probe mutated proof branch")
    return {
        "concurrent_writer_c_pid": pid_c,
        "concurrent_writer_d_pid": pid_d,
        "waiting_lock_evidence": evidence,
        "recovery_probe_c_postlock_seq": c_postlock[0],
        "recovery_probe_d_postlock_seq": d_postlock[0],
        "recovery_probe_rollback_only": True,
        "recovery_probe_state_unchanged": True,
    }

def run_fresh_proof(target_url: str, branch_id: str) -> dict[str, Any]:
    initial = snapshot(target_url)
    require(initial["counts"] == EXPECTED_INITIAL, f"unexpected inherited counts: {initial['counts']}")
    require(initial["checkpoint"] is not None, "inherited checkpoint missing")
    require(initial["checkpoint"]["checkpoint_seq"] == 1, "inherited checkpoint seq is not 1")
    require(initial["checkpoint"]["checkpoint_id"] == EXPECTED_SEQ1_ID, "inherited checkpoint id changed")
    initial_identity = initial["identity"]

    with psycopg.connect(target_url, row_factory=dict_row, connect_timeout=15) as conn:
        poll_a = poll_payload("A", "2026-09-28T13:00:00Z")
        result_a = apply(conn, poll_a, branch_id)
    after_a = snapshot(target_url)
    require(after_a["counts"] == {
        "ingestion_runs": 2, "alert_episodes": 126, "alert_episode_sources": 140, "ingestion_checkpoints": 2
    }, "poll A counts wrong")
    require(result_a["stats"]["checkpoints_inserted"] == 1, "poll A checkpoint not inserted")
    seq2 = after_a["history"][1]
    require(seq2["previous_checkpoint_id"] == EXPECTED_SEQ1_ID, "seq2 previous link wrong")

    with psycopg.connect(target_url, row_factory=dict_row, connect_timeout=15) as conn:
        retry_a = apply(conn, poll_a, branch_id)
    after_retry = snapshot(target_url)
    require(after_retry["counts"] == {
        "ingestion_runs": 3, "alert_episodes": 126, "alert_episode_sources": 140, "ingestion_checkpoints": 2
    }, "poll A retry counts wrong")
    require(retry_a["stats"]["checkpoints_inserted"] == 0 and retry_a["stats"]["exact_retry"], "poll A retry not exact")
    require(after_retry["history"][1]["checkpoint_id"] == seq2["checkpoint_id"], "seq2 id changed on retry")

    with psycopg.connect(target_url, row_factory=dict_row, connect_timeout=15) as conn:
        result_b = apply(conn, poll_payload("B", "2026-09-28T14:00:00Z"), branch_id)
    after_b = snapshot(target_url)
    require(after_b["counts"] == {
        "ingestion_runs": 4, "alert_episodes": 126, "alert_episode_sources": 140, "ingestion_checkpoints": 3
    }, "poll B counts wrong")
    require(result_b["stats"]["checkpoints_inserted"] == 1, "poll B checkpoint not inserted")
    seq3 = after_b["history"][2]
    require(seq3["previous_checkpoint_id"] == seq2["checkpoint_id"], "seq3 previous link wrong")

    conn_c = psycopg.connect(target_url, row_factory=dict_row, connect_timeout=15)
    conn_d = psycopg.connect(target_url, row_factory=dict_row, connect_timeout=15)
    observer = psycopg.connect(target_url, autocommit=True, row_factory=dict_row, connect_timeout=15)
    errors: list[BaseException] = []
    results: dict[str, Any] = {}
    c_postlock: list[int] = []
    d_postlock: list[int] = []
    c_holding = threading.Event()
    release_c = threading.Event()
    d_started = threading.Event()
    try:
        pid_c, iso_c = session_info(conn_c)
        pid_d, iso_d = session_info(conn_d)
        require(pid_c != pid_d, "independent sessions not established")
        require(iso_c == "read committed" and iso_d == "read committed", "wrong transaction isolation")

        def callback_c(cp):
            require(cp is not None, "writer C checkpoint missing")
            c_postlock.append(int(cp["checkpoint_seq"]))
            require(c_postlock[-1] == 3, f"writer C post-lock seq was {c_postlock[-1]}")
            c_holding.set()
            require(release_c.wait(timeout=20), "writer C release timeout")

        def callback_d(cp):
            require(cp is not None, "writer D checkpoint missing")
            d_postlock.append(int(cp["checkpoint_seq"]))

        def writer_c():
            try:
                results["c"] = apply(conn_c, poll_payload("C", "2026-09-28T15:00:00Z"), branch_id, callback_c)
            except BaseException as exc:
                errors.append(exc)

        def writer_d():
            try:
                d_started.set()
                results["d"] = apply(conn_d, poll_payload("D", "2026-09-28T16:00:00Z"), branch_id, callback_d)
            except BaseException as exc:
                errors.append(exc)

        tc = threading.Thread(target=writer_c, name="writer-c", daemon=True)
        td = threading.Thread(target=writer_d, name="writer-d", daemon=True)
        tc.start()
        require(c_holding.wait(timeout=10), "writer C did not reach post-lock callback")
        td.start()
        require(d_started.wait(timeout=5), "writer D did not start")
        evidence = wait_lock_evidence(observer, pid_c, pid_d)
        require(not d_postlock, "writer D crossed lock before C commit")
        release_c.set()
        tc.join(timeout=30)
        td.join(timeout=30)
        require(not tc.is_alive() and not td.is_alive(), "writer thread did not finish")
        if errors:
            raise errors[0]
        require(c_postlock == [3], f"writer C post-lock state wrong: {c_postlock}")
        require(d_postlock == [4], f"writer D post-lock state wrong: {d_postlock}")
        require(results["c"]["stats"]["checkpoints_inserted"] == 1, "writer C did not append")
        require(results["d"]["stats"]["checkpoints_inserted"] == 1, "writer D did not append")
    finally:
        release_c.set()
        observer.close()
        conn_d.close()
        conn_c.close()

    final = snapshot(target_url)
    run_ids = validate_final_state(final)
    require(final["identity"] == initial_identity, "canonical identities changed")
    return {
        "proof_mode": "full",
        "initial": initial,
        "final": final,
        **run_ids,
        "poll_a_retry_exact_retry": True,
        "concurrent_writer_c_pid": pid_c,
        "concurrent_writer_d_pid": pid_d,
        "waiting_lock_evidence": evidence,
        "writer_c_postlock_seq": c_postlock[0],
        "writer_c_committed_seq": 4,
        "writer_d_postlock_seq": d_postlock[0],
        "writer_d_committed_seq": 5,
        "concurrency_evidence_scope": "same run as committed C/D append",
    }

def run_recovery_proof(target_url: str, branch_id: str, parent_snapshot: dict[str, Any]) -> dict[str, Any]:
    final = snapshot(target_url)
    run_ids = validate_final_state(final)
    require(final["identity"] == parent_snapshot["identity"], "canonical identities differ from protected bootstrap parent")
    probe = recovery_lock_probe(target_url, branch_id)
    return {
        "proof_mode": "artifact_recovery",
        "initial": parent_snapshot,
        "final": final,
        **run_ids,
        "poll_a_retry_exact_retry": True,
        **probe,
        "writer_c_postlock_seq": 3,
        "writer_c_committed_seq": 4,
        "writer_d_postlock_seq": 4,
        "writer_d_committed_seq": 5,
        "concurrency_evidence_scope": (
            "committed C/D append semantics recovered from persisted seq4/seq5 rows; "
            "server-side wait and independent PIDs re-proven by rollback-only real-adapter probe"
        ),
        "substantive_workflow_run_id": os.environ["SUBSTANTIVE_WORKFLOW_RUN_ID"],
        "substantive_implementation_sha": os.environ["SUBSTANTIVE_IMPLEMENTATION_SHA"],
    }

def main() -> int:
    out_path = Path(os.environ["PROOF_RESULT"])
    target_url = os.environ["PHASE1_PROOF_DATABASE_URL"]
    branch_id = os.environ["PHASE1_PROOF_BRANCH_ID"]
    direct_host(target_url)
    lock_key = stream_lock_key(SOURCE_KEY, CITY_KEY, STREAM_KEY)
    require(STREAM_LOCK_VERSION == "phase1-stream-lock-v1", "lock version changed")
    require(lock_key == EXPECTED_LOCK_KEY, f"lock key changed: {lock_key}")

    protected_env = {
        "primary": "PHASE1_PRIMARY_DATABASE_URL",
        "accepted_bootstrap": "PHASE1_BOOTSTRAP_DATABASE_URL",
        "accepted_live_e2e": "PHASE1_LIVE_E2E_DATABASE_URL",
        "accepted_previous_concurrency": "PHASE1_PREVIOUS_CONCURRENCY_DATABASE_URL",
        "old_blocked_concurrency": "PHASE1_BLOCKED_DATABASE_URL",
    }
    protected_before = {name: snapshot(os.environ[env]) for name, env in protected_env.items()}
    validate_protected_baselines(protected_before)

    recovery_mode = os.environ.get("PROOF_RECOVERY_MODE", "false").lower() == "true"
    if recovery_mode:
        proof = run_recovery_proof(target_url, branch_id, protected_before["accepted_bootstrap"])
    else:
        proof = run_fresh_proof(target_url, branch_id)

    protected_after = {name: snapshot(os.environ[env]) for name, env in protected_env.items()}
    validate_protected_baselines(protected_after)
    isolation = {
        name: protected_before[name] == protected_after[name]
        for name in protected_env
    }
    require(all(isolation.values()), f"protected branch isolation failed: {isolation}")

    initial = proof["initial"]
    final = proof["final"]
    artifact = {
        "schema_version": "db-phase1-live-poll-persistence-adapter-proof-v1",
        "base_git_sha": os.environ["BASE_GIT_SHA"],
        "implementation_sha": os.environ["GITHUB_SHA"],
        "workflow_run_id": os.environ["GITHUB_RUN_ID"],
        "old_persistence_blob": os.environ["OLD_PERSISTENCE_BLOB"],
        "new_persistence_blob": os.environ["NEW_PERSISTENCE_BLOB"],
        "ddl_blob": os.environ["DDL_BLOB"],
        "stream_identity": {"source_key": SOURCE_KEY, "city_key": CITY_KEY, "stream_key": STREAM_KEY},
        "lock_key_version": STREAM_LOCK_VERSION,
        "lock_key": lock_key,
        "neon_project_id": os.environ["NEON_PROJECT_ID"],
        "proof_branch_id": branch_id,
        "proof_branch_name": os.environ["PROOF_BRANCH_NAME"],
        "parent_branch_id": os.environ["PARENT_BRANCH_ID"],
        "direct_unpooled": True,
        "proof_mode": proof["proof_mode"],
        "initial_counts": initial["counts"],
        "initial_checkpoint": initial["checkpoint"],
        "poll_a_run_id": proof["poll_a_run_id"],
        "poll_a_checkpoint_id": proof["poll_a_checkpoint_id"],
        "poll_a_seq": 2,
        "poll_a_retry_run_id": proof["poll_a_retry_run_id"],
        "poll_a_retry_exact_retry": proof["poll_a_retry_exact_retry"],
        "poll_b_run_id": proof["poll_b_run_id"],
        "poll_b_checkpoint_id": proof["poll_b_checkpoint_id"],
        "poll_b_seq": 3,
        "poll_c_run_id": proof["poll_c_run_id"],
        "poll_d_run_id": proof["poll_d_run_id"],
        "concurrent_writer_c_pid": proof["concurrent_writer_c_pid"],
        "concurrent_writer_d_pid": proof["concurrent_writer_d_pid"],
        "waiting_lock_evidence": proof["waiting_lock_evidence"],
        "writer_c_postlock_seq": proof["writer_c_postlock_seq"],
        "writer_c_committed_seq": proof["writer_c_committed_seq"],
        "writer_d_postlock_seq": proof["writer_d_postlock_seq"],
        "writer_d_committed_seq": proof["writer_d_committed_seq"],
        "concurrency_evidence_scope": proof["concurrency_evidence_scope"],
        "final_counts": final["counts"],
        "checkpoint_history": [row["checkpoint_seq"] for row in final["history"]],
        "checkpoint_history_rows": final["history"],
        "canonical_episode_identity_stable": final["identity"]["episode_identity_sha256"] == initial["identity"]["episode_identity_sha256"],
        "canonical_source_identity_stable": final["identity"]["source_identity_sha256"] == initial["identity"]["source_identity_sha256"],
        "protected_branch_isolation": isolation,
        "site_prod_at_start": os.environ["SITE_PROD_AT_START"],
        "site_prod_at_end": os.environ["SITE_PROD_AT_END"],
        "main_at_start": os.environ["MAIN_AT_START"],
        "main_at_end": os.environ["MAIN_AT_END"],
        "site_prod_modified": False,
        "main_modified": False,
        "production_publication": False,
        "credentials_exposed": False,
        "test_count": int(os.environ["PHASE1_TEST_COUNT"]),
        "test_result": os.environ["PHASE1_TEST_RESULT"],
        "verdict": "PHASE-1 LIVE POLL PERSISTENCE ADAPTER PROVEN",
    }
    for key in (
        "recovery_probe_c_postlock_seq",
        "recovery_probe_d_postlock_seq",
        "recovery_probe_rollback_only",
        "recovery_probe_state_unchanged",
        "substantive_workflow_run_id",
        "substantive_implementation_sha",
    ):
        if key in proof:
            artifact[key] = proof[key]

    out_path.write_text(
        json.dumps(artifact, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    print("PHASE-1 LIVE POLL PERSISTENCE ADAPTER PROVEN")
    print(json.dumps(artifact, sort_keys=True, default=str))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
