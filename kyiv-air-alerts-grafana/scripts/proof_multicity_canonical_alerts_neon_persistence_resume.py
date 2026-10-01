#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

import psycopg
from psycopg.rows import dict_row

from db_phase1_core import CANONICALIZATION_VERSION, canonical_json, legacy_timestamp
from db_phase1_persistence import (
    EpisodeConflict,
    acquire_stream_lock,
    finalize_ingestion_run,
    insert_ingestion_run,
    persist_episode,
)

EXPECTED_SITE_PROD_SHA = "928a566b7a8dc7916c93810eaafe319da3b28ee4"
EXPECTED_VADIMKIN_SHA = "58ee75bc20113181b9ddf8029d4cbf3a62d8cd10"
EXPECTED_CORPUS_SHA256 = "8e9f3660039de4e0490db25229fe1760f5926b6b73490c8a325b9abc7555971b"
EXPECTED_CITY_COUNT = 23
EXPECTED_EPISODE_COUNT = 27866
EXPECTED_LVIV_COUNT = 126
CHILD_BRANCH_ID = "br-icy-forest-b5mfyezq"
SOURCE_KEY = "production_canonical_boundary"
CITY_KEY = "multicity"
STREAM_KEY = f"frozen-site-prod:{EXPECTED_SITE_PROD_SHA}:{EXPECTED_CORPUS_SHA256}"
BASELINE_COUNTS = {
    "ingestion_runs": 2,
    "alert_episodes": 126,
    "alert_episode_sources": 143,
    "ingestion_checkpoints": 1,
    "max_checkpoint_seq": 1,
    "alert_state_snapshots": 13,
    "alert_threat_observations": 14,
    "alerts_in_ua_sources": 3,
    "lviv_episodes": 126,
}
BASELINE_FINGERPRINTS = {
    "lviv_alert_episodes": "aff237177559be3b5ca8f4ca0ed00d79",
    "alert_episode_sources": "54294429cf09acc8c2a1a3ad304a53c3",
    "ingestion_checkpoints": "2a982250b3dc8e3b11e96dc859e83acb",
    "alert_state_snapshots": "f1b361222d3b9428bd74519f873a9ce3",
    "alert_threat_observations": "7ca8f9930c8b645c733b35797aad96f6",
}
REPAIRED = {
    "575f370c-6e99-4623-8219-f8fbdfd6c978": {
        "legacy_episode_id": "7dd411c2a2587efc740a1a66",
        "start_at": "2026-09-12T22:00:05.398348Z",
        "end_at": "2026-09-12T22:14:27Z",
        "sources": {
            "alerts_in_ua": (False, True, "980d8771eb46bca4bc542aa98c987795f254e01ce4fc59d25b1e4cd0fb55c7e0"),
            "ukrainealarm_region_history": (True, False, "6438e15f3ba3fc00edafa8bbfe1e00059376367cde5940f8c982129173aae0b4"),
        },
    },
    "c90e7b05-1982-461f-945f-53d8130c627b": {
        "legacy_episode_id": "c2cd9a96768756d84c250735",
        "start_at": "2026-09-13T02:32:14Z",
        "end_at": "2026-09-13T06:11:11.976953Z",
        "sources": {
            "alerts_in_ua": (True, False, "828e721a803eb19280ff3b20182314e3196dba48516a780fd050639136354664"),
            "ukrainealarm_region_history": (False, True, "2efa73724264110d0fd59d3a48d99ea50b0bc26e9aa97be4074095c6c85b374c"),
        },
    },
    "451c8a2c-248a-41e5-b49e-31af3f44631f": {
        "legacy_episode_id": "94ce779cf047984e881bfdd5",
        "start_at": "2026-09-15T16:44:13Z",
        "end_at": "2026-09-15T17:09:02Z",
        "sources": {
            "alerts_in_ua": (True, True, "9c827b4b944729c82daafc29b42acd7146752920e6871a6ff39962e18b785b91"),
            "ukrainealarm_region_history": (False, False, "14c2dd485537e53228dfb52e8f199bce18a58bf150c9ec5e1992b6311ef9f3c6"),
        },
    },
}

class ProofBlocked(RuntimeError):
    pass

class ForcedRollback(RuntimeError):
    pass

def require(condition: bool, message: str) -> None:
    if not condition:
        raise ProofBlocked(message)

def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)

def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))

def load_corpus(path: Path) -> dict[str, Any]:
    payload = load_json(path)
    require(payload.get("boundary_proven") is True, "accepted canonical artifact boundary_proven != true")
    require(payload.get("production_frozen_site_prod_sha") == EXPECTED_SITE_PROD_SHA, "frozen site-prod SHA drift")
    require(payload.get("vadimkin_frozen_sha") == EXPECTED_VADIMKIN_SHA, "frozen Vadimkin SHA drift")
    require(payload.get("canonicalization_version") == CANONICALIZATION_VERSION, "canonicalization version drift")
    require(payload.get("city_count") == EXPECTED_CITY_COUNT, "canonical city count drift")
    require(payload.get("total_episode_count") == EXPECTED_EPISODE_COUNT, "canonical episode count drift")
    require(payload.get("open_episode_count") == 0, "canonical artifact unexpectedly contains open episodes")
    require(len(payload.get("boundary_errors", [])) == 0, "canonical artifact contains boundary errors")
    episodes = payload.get("episodes") or []
    city_keys = payload.get("production_city_keys") or []
    serial = {
        "canonicalization_version": CANONICALIZATION_VERSION,
        "production_city_keys": city_keys,
        "episodes": episodes,
    }
    digest = hashlib.sha256(canonical_json(serial).encode("utf-8")).hexdigest()
    require(digest == EXPECTED_CORPUS_SHA256, f"canonical corpus hash drift: {digest}")
    require(payload.get("corpus_sha256") == EXPECTED_CORPUS_SHA256, "artifact-declared corpus hash drift")
    require(len(city_keys) == EXPECTED_CITY_COUNT and len(set(city_keys)) == EXPECTED_CITY_COUNT, "city key boundary drift")
    require(len(episodes) == EXPECTED_EPISODE_COUNT, "episode payload length drift")
    return payload

def connect() -> psycopg.Connection:
    url = os.environ.get("CHILD_DATABASE_URL")
    require(bool(url), "CHILD_DATABASE_URL is not set")
    return psycopg.connect(url, autocommit=False, row_factory=dict_row)

def scalar(cur: Any, sql: str, params: tuple[Any, ...] = ()) -> Any:
    cur.execute(sql, params)
    row = cur.fetchone()
    if row is None:
        raise ProofBlocked("scalar query returned no row")
    return next(iter(row.values())) if isinstance(row, dict) else row[0]

def table_md5(cur: Any, table: str, where_sql: str = "", params: tuple[Any, ...] = ()) -> str:
    allowed = {
        "alert_episodes",
        "alert_episode_sources",
        "ingestion_runs",
        "ingestion_checkpoints",
        "alert_state_snapshots",
        "alert_threat_observations",
    }
    require(table in allowed, f"unsafe fingerprint table {table}")
    sql = f"SELECT md5(coalesce(string_agg(to_jsonb(t)::text,E'\\n' ORDER BY to_jsonb(t)::text),'')) AS md5 FROM {table} t {where_sql}"
    return str(scalar(cur, sql, params))

def counts(cur: Any) -> dict[str, int | None]:
    return {
        "ingestion_runs": int(scalar(cur, "SELECT count(*) FROM ingestion_runs")),
        "alert_episodes": int(scalar(cur, "SELECT count(*) FROM alert_episodes")),
        "alert_episode_sources": int(scalar(cur, "SELECT count(*) FROM alert_episode_sources")),
        "ingestion_checkpoints": int(scalar(cur, "SELECT count(*) FROM ingestion_checkpoints")),
        "max_checkpoint_seq": scalar(cur, "SELECT max(checkpoint_seq) FROM ingestion_checkpoints"),
        "alert_state_snapshots": int(scalar(cur, "SELECT count(*) FROM alert_state_snapshots")),
        "alert_threat_observations": int(scalar(cur, "SELECT count(*) FROM alert_threat_observations")),
        "alerts_in_ua_sources": int(scalar(cur, "SELECT count(*) FROM alert_episode_sources WHERE source_key='alerts_in_ua'")),
        "lviv_episodes": int(scalar(cur, "SELECT count(*) FROM alert_episodes WHERE city_key='lviv'")),
    }

def fingerprints(cur: Any) -> dict[str, str]:
    return {
        "lviv_alert_episodes": table_md5(cur, "alert_episodes", "WHERE city_key='lviv'"),
        "alert_episodes_all": table_md5(cur, "alert_episodes"),
        "alert_episode_sources": table_md5(cur, "alert_episode_sources"),
        "ingestion_runs": table_md5(cur, "ingestion_runs"),
        "ingestion_checkpoints": table_md5(cur, "ingestion_checkpoints"),
        "alert_state_snapshots": table_md5(cur, "alert_state_snapshots"),
        "alert_threat_observations": table_md5(cur, "alert_threat_observations"),
    }

def lviv_uid_map(cur: Any) -> dict[str, str]:
    cur.execute("SELECT legacy_episode_id, episode_uid::text AS episode_uid FROM alert_episodes WHERE city_key='lviv' ORDER BY legacy_episode_id")
    return {str(r["legacy_episode_id"]): str(r["episode_uid"]) for r in cur.fetchall()}

def state(cur: Any) -> dict[str, Any]:
    return {"counts": counts(cur), "fingerprints_md5": fingerprints(cur), "lviv_uid_map": lviv_uid_map(cur)}

def semantic_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "alert_type": str(row["alert_type"]),
        "canonicalization_version": str(row["canonicalization_version"]),
        "city_key": str(row["city_key"]),
        "end_at": None if row["end_at"] is None else legacy_timestamp(row["end_at"]),
        "episode_state": str(row["episode_state"]),
        "legacy_episode_id": str(row["legacy_episode_id"]),
        "start_at": legacy_timestamp(row["start_at"]),
    }

def db_semantic_rows(cur: Any) -> list[dict[str, Any]]:
    cur.execute("""
        SELECT legacy_episode_id, city_key, alert_type, start_at, end_at,
               episode_state, canonicalization_version
        FROM alert_episodes
        ORDER BY city_key, start_at, end_at, legacy_episode_id
    """)
    return [semantic_row(dict(r)) for r in cur.fetchall()]

def group_rows(rows: Iterable[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["city_key"])].append(row)
    for city in grouped:
        grouped[city].sort(key=lambda r: (r["start_at"], r["end_at"] or "", r["legacy_episode_id"]))
    return dict(grouped)

def parity(cur: Any, corpus: dict[str, Any], cities: list[str] | None = None) -> dict[str, Any]:
    expected_grouped = group_rows(corpus["episodes"])
    actual_grouped = group_rows(db_semantic_rows(cur))
    city_keys = cities or list(corpus["production_city_keys"])
    per_city: dict[str, Any] = {}
    missing_total = extra_total = mismatched_rows = id_mismatches = boundary_mismatches = exact_total = 0
    for city in city_keys:
        expected = expected_grouped.get(city, [])
        actual = actual_grouped.get(city, [])
        exp_by_id = {r["legacy_episode_id"]: r for r in expected}
        act_by_id = {r["legacy_episode_id"]: r for r in actual}
        missing_ids = sorted(set(exp_by_id) - set(act_by_id))
        extra_ids = sorted(set(act_by_id) - set(exp_by_id))
        shared = sorted(set(exp_by_id) & set(act_by_id))
        mismatches = []
        for legacy_id in shared:
            e, a = exp_by_id[legacy_id], act_by_id[legacy_id]
            fields = [f for f in ("start_at", "end_at", "alert_type", "episode_state", "canonicalization_version", "city_key") if e.get(f) != a.get(f)]
            if fields:
                mismatches.append({"legacy_episode_id": legacy_id, "fields": fields, "expected": e, "actual": a})
                if "start_at" in fields or "end_at" in fields:
                    boundary_mismatches += 1
            else:
                exact_total += 1
        missing_total += len(missing_ids)
        extra_total += len(extra_ids)
        id_mismatches += len(missing_ids) + len(extra_ids)
        mismatched_rows += len(mismatches)
        per_city[city] = {
            "expected": len(expected),
            "actual": len(actual),
            "exact": len(shared) - len(mismatches),
            "missing": len(missing_ids),
            "extra": len(extra_ids),
            "semantic_mismatches": len(mismatches),
            "first_mismatches": mismatches[:3],
        }
    result: dict[str, Any] = {
        "city_count": len(city_keys),
        "exact_total": exact_total,
        "missing": missing_total,
        "extra": extra_total,
        "id_mismatches": id_mismatches,
        "boundary_mismatches": boundary_mismatches,
        "semantic_mismatches": mismatched_rows,
        "per_city": per_city,
    }
    if cities is None:
        ordered: list[dict[str, Any]] = []
        for city in corpus["production_city_keys"]:
            ordered.extend(actual_grouped.get(city, []))
        serial = {
            "canonicalization_version": CANONICALIZATION_VERSION,
            "production_city_keys": list(corpus["production_city_keys"]),
            "episodes": ordered,
        }
        result["db_corpus_sha256"] = hashlib.sha256(canonical_json(serial).encode("utf-8")).hexdigest()
    return result

def repaired_rows(cur: Any) -> dict[str, Any]:
    uids = list(REPAIRED)
    cur.execute("""
        SELECT episode_uid::text AS episode_uid, legacy_episode_id, start_at, end_at
        FROM alert_episodes
        WHERE episode_uid = ANY(%s::uuid[])
        ORDER BY episode_uid
    """, (uids,))
    parents = {str(r["episode_uid"]): dict(r) for r in cur.fetchall()}
    out: dict[str, Any] = {}
    for uid, expected in REPAIRED.items():
        row = parents.get(uid)
        require(row is not None, f"repaired Lviv episode missing: {uid}")
        require(str(row["legacy_episode_id"]) == expected["legacy_episode_id"], f"repaired legacy id drift: {uid}")
        require(legacy_timestamp(row["start_at"]) == expected["start_at"], f"repaired start drift: {uid}")
        require(legacy_timestamp(row["end_at"]) == expected["end_at"], f"repaired end drift: {uid}")
        cur.execute("""
            SELECT source_key, source_record_key, binding_state, canonicalization_role,
                   contributes_start_boundary, contributes_end_boundary
            FROM alert_episode_sources
            WHERE episode_uid=%s::uuid
            ORDER BY source_key, source_record_key
        """, (uid,))
        sources = [dict(r) for r in cur.fetchall()]
        source_map = {str(r["source_key"]): r for r in sources}
        for source_key, (start_flag, end_flag, record_key) in expected["sources"].items():
            s = source_map.get(source_key)
            require(s is not None, f"repaired source missing {uid} {source_key}")
            require(str(s["source_record_key"]) == record_key, f"repaired source key drift {uid} {source_key}")
            require(str(s["binding_state"]) == "bound", f"repaired binding drift {uid} {source_key}")
            require(str(s["canonicalization_role"]) == "canonical_input", f"repaired role drift {uid} {source_key}")
            require(bool(s["contributes_start_boundary"]) is start_flag, f"repaired start contributor drift {uid} {source_key}")
            require(bool(s["contributes_end_boundary"]) is end_flag, f"repaired end contributor drift {uid} {source_key}")
        out[uid] = {
            "legacy_episode_id": str(row["legacy_episode_id"]),
            "start_at": legacy_timestamp(row["start_at"]),
            "end_at": legacy_timestamp(row["end_at"]),
            "sources": [{
                "source_key": str(s["source_key"]),
                "source_record_key": str(s["source_record_key"]),
                "binding_state": str(s["binding_state"]),
                "canonicalization_role": str(s["canonicalization_role"]),
                "contributes_start_boundary": bool(s["contributes_start_boundary"]),
                "contributes_end_boundary": bool(s["contributes_end_boundary"]),
            } for s in sources],
        }
    return out

def run_provenance(phase: str) -> dict[str, Any]:
    return {
        "run_kind": "historical_multicity_parent_import",
        "workflow_repository": os.environ.get("GITHUB_REPOSITORY"),
        "workflow_name": os.environ.get("GITHUB_WORKFLOW"),
        "workflow_ref": os.environ.get("GITHUB_REF"),
        "workflow_sha": os.environ.get("GITHUB_SHA"),
        "input_repository": os.environ.get("GITHUB_REPOSITORY"),
        "input_ref": EXPECTED_SITE_PROD_SHA,
        "input_sha": EXPECTED_SITE_PROD_SHA,
        "github_run_id": int(os.environ.get("GITHUB_RUN_ID", "0")) or None,
        "github_run_attempt": int(os.environ.get("GITHUB_RUN_ATTEMPT", "0")) or None,
        "canonicalization_version": CANONICALIZATION_VERSION,
        "parameters": {
            "proof_only": True,
            "phase": phase,
            "accepted_corpus_sha256": EXPECTED_CORPUS_SHA256,
            "accepted_boundary_artifact_run_id": 36816630480,
            "source_provenance_coverage": "partial",
            "source_observations_fabricated": False,
            "checkpoint_persisted": False,
        },
    }

def run_parent_import(conn: psycopg.Connection, episodes: list[dict[str, Any]], *, phase: str, force_rollback_after_insert: bool = False) -> dict[str, Any]:
    run_id = uuid.uuid4()
    inserted = existing = 0
    cur = conn.cursor()
    try:
        cur.execute("BEGIN")
        acquire_stream_lock(cur, SOURCE_KEY, CITY_KEY, STREAM_KEY)
        insert_ingestion_run(
            cur,
            run_id=run_id,
            source_key=SOURCE_KEY,
            city_key=CITY_KEY,
            db_branch=CHILD_BRANCH_ID,
            provenance=run_provenance(phase),
            started_at=datetime.now(timezone.utc),
        )
        for episode in episodes:
            _, was_inserted = persist_episode(cur, episode, run_id=run_id)
            if was_inserted:
                inserted += 1
                if force_rollback_after_insert:
                    raise ForcedRollback("deterministic forced rollback after first new parent insert")
            else:
                existing += 1
        stats = {
            "episodes_inserted": inserted,
            "episodes_existing": existing,
            "source_observations_inserted": 0,
            "source_observations_existing": 0,
            "source_observations_last_seen_updated": 0,
            "checkpoints_inserted": 0,
            "exact_retry": inserted == 0,
        }
        now = datetime.now(timezone.utc)
        finalize_ingestion_run(cur, run_id=run_id, stats=stats, committed_at=now, finished_at=datetime.now(timezone.utc))
        conn.commit()
        return {"run_id": str(run_id), "stats": stats, "rolled_back": False}
    except ForcedRollback as exc:
        conn.rollback()
        return {
            "run_id": str(run_id),
            "stats_before_rollback": {"episodes_inserted": inserted, "episodes_existing": existing},
            "rolled_back": True,
            "injected_failure": str(exc),
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()

def run_conflict_attempt(conn: psycopg.Connection, candidate: dict[str, Any]) -> dict[str, Any]:
    run_id = uuid.uuid4()
    cur = conn.cursor()
    try:
        cur.execute("BEGIN")
        acquire_stream_lock(cur, SOURCE_KEY, CITY_KEY, STREAM_KEY)
        insert_ingestion_run(
            cur,
            run_id=run_id,
            source_key=SOURCE_KEY,
            city_key=CITY_KEY,
            db_branch=CHILD_BRANCH_ID,
            provenance=run_provenance("semantic_conflict_rejection"),
            started_at=datetime.now(timezone.utc),
        )
        persist_episode(cur, candidate, run_id=run_id)
        raise ProofBlocked("semantic conflict candidate was not rejected")
    except EpisodeConflict as exc:
        conn.rollback()
        return {"run_id": str(run_id), "rejected": True, "exception": str(exc)}
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()

def assert_baseline(pre: dict[str, Any]) -> None:
    require(pre["counts"] == BASELINE_COUNTS, f"Gate A baseline count drift: {pre['counts']}")
    for key, expected in BASELINE_FINGERPRINTS.items():
        require(pre["fingerprints_md5"].get(key) == expected, f"Gate A fingerprint drift {key}: {pre['fingerprints_md5'].get(key)}")
    require(len(pre["lviv_uid_map"]) == EXPECTED_LVIV_COUNT, "Gate A Lviv UID inventory drift")

def assert_invariants_against_pre(pre: dict[str, Any], post: dict[str, Any], *, compare_ingestion_runs: bool) -> None:
    for key in ("alert_episode_sources", "ingestion_checkpoints", "alert_state_snapshots", "alert_threat_observations"):
        require(post["fingerprints_md5"][key] == pre["fingerprints_md5"][key], f"invariant fingerprint changed: {key}")
    require(post["fingerprints_md5"]["lviv_alert_episodes"] == pre["fingerprints_md5"]["lviv_alert_episodes"], "Lviv physical rows changed")
    require(post["lviv_uid_map"] == pre["lviv_uid_map"], "existing Lviv episode_uid identity changed")
    if compare_ingestion_runs:
        require(post["fingerprints_md5"]["ingestion_runs"] == pre["fingerprints_md5"]["ingestion_runs"], "ingestion_runs changed across rollback")

def primary(corpus: dict[str, Any], result_path: Path) -> None:
    conn = connect()
    try:
        cur = conn.cursor()
        pre = state(cur)
        assert_baseline(pre)
        repaired_before = repaired_rows(cur)
        lviv = parity(cur, corpus, ["lviv"])
        require(lviv["per_city"]["lviv"]["expected"] == EXPECTED_LVIV_COUNT, "Gate B production Lviv count drift")
        require(lviv["per_city"]["lviv"]["actual"] == EXPECTED_LVIV_COUNT, "Gate B DB Lviv count drift")
        require(lviv["per_city"]["lviv"]["exact"] == EXPECTED_LVIV_COUNT, f"Gate B compatibility not 126/126: {lviv}")
        require(lviv["missing"] == 0 and lviv["extra"] == 0 and lviv["semantic_mismatches"] == 0, f"Gate B mismatches: {lviv}")
        conn.rollback()
        cur.close()

        rollback_attempt = run_parent_import(conn, corpus["episodes"], phase="forced_rollback", force_rollback_after_insert=True)
        require(rollback_attempt["rolled_back"] is True, "Gate C forced rollback did not occur")
        require(rollback_attempt["stats_before_rollback"]["episodes_inserted"] >= 1, "Gate C failure injected before any new parent insert")
        cur = conn.cursor()
        post_rollback = state(cur)
        require(post_rollback["counts"] == pre["counts"], f"Gate C count residue: {post_rollback['counts']}")
        assert_invariants_against_pre(pre, post_rollback, compare_ingestion_runs=True)
        require(post_rollback["fingerprints_md5"]["alert_episodes_all"] == pre["fingerprints_md5"]["alert_episodes_all"], "Gate C parent episode residue")
        require(int(scalar(cur, "SELECT count(*) FROM alert_episodes WHERE city_key <> 'lviv'")) == 0, "Gate C non-Lviv residue != 0")
        conn.rollback()
        cur.close()

        successful_import = run_parent_import(conn, corpus["episodes"], phase="successful_full_23_city_import")
        require(successful_import["stats"]["episodes_inserted"] == EXPECTED_EPISODE_COUNT - EXPECTED_LVIV_COUNT, f"Gate D inserted count drift: {successful_import}")
        require(successful_import["stats"]["episodes_existing"] == EXPECTED_LVIV_COUNT, f"Gate D existing count drift: {successful_import}")
        require(successful_import["stats"]["checkpoints_inserted"] == 0, "Gate D checkpoint write occurred")
        require(successful_import["stats"]["source_observations_inserted"] == 0, "Gate D source provenance fabricated")

        cur = conn.cursor()
        post_import = state(cur)
        require(post_import["counts"]["alert_episodes"] == EXPECTED_EPISODE_COUNT, f"Gate D total parent count drift: {post_import['counts']}")
        require(post_import["counts"]["alert_episode_sources"] == BASELINE_COUNTS["alert_episode_sources"], "Gate D source rows changed")
        require(post_import["counts"]["ingestion_checkpoints"] == 1 and post_import["counts"]["max_checkpoint_seq"] == 1, "Gate D checkpoint changed")
        require(post_import["counts"]["alert_state_snapshots"] == 13 and post_import["counts"]["alert_threat_observations"] == 14, "Gate D differentiated child count changed")
        assert_invariants_against_pre(pre, post_import, compare_ingestion_runs=False)
        full_parity = parity(cur, corpus)
        require(full_parity["exact_total"] == EXPECTED_EPISODE_COUNT, f"Gate E exact parity not 27866/27866: {full_parity['exact_total']}")
        require(full_parity["missing"] == 0 and full_parity["extra"] == 0 and full_parity["id_mismatches"] == 0 and full_parity["boundary_mismatches"] == 0 and full_parity["semantic_mismatches"] == 0, f"Gate E mismatches: {full_parity}")
        require(full_parity["db_corpus_sha256"] == EXPECTED_CORPUS_SHA256, f"Gate E DB corpus hash mismatch: {full_parity['db_corpus_sha256']}")
        repaired_after_import = repaired_rows(cur)
        require(repaired_after_import == repaired_before, "Gate F repaired Lviv rows/source flags changed")
        parent_fp_after_import = post_import["fingerprints_md5"]["alert_episodes_all"]
        conn.rollback()
        cur.close()

        exact_retry = run_parent_import(conn, corpus["episodes"], phase="exact_retry")
        require(exact_retry["stats"]["episodes_inserted"] == 0, f"Gate G exact retry inserted parents: {exact_retry}")
        require(exact_retry["stats"]["episodes_existing"] == EXPECTED_EPISODE_COUNT, f"Gate G exact retry existing count drift: {exact_retry}")
        require(exact_retry["stats"]["exact_retry"] is True, "Gate G exact retry flag false")
        require(exact_retry["stats"]["checkpoints_inserted"] == 0, "Gate G checkpoint advanced")
        cur = conn.cursor()
        post_retry = state(cur)
        require(post_retry["fingerprints_md5"]["alert_episodes_all"] == parent_fp_after_import, "Gate G canonical parent physical state changed")
        assert_invariants_against_pre(pre, post_retry, compare_ingestion_runs=False)
        retry_parity = parity(cur, corpus)
        require(retry_parity["exact_total"] == EXPECTED_EPISODE_COUNT and retry_parity["db_corpus_sha256"] == EXPECTED_CORPUS_SHA256, "Gate G parity failed")
        conn.rollback()
        cur.close()

        result = {
            "proof_kind": "multicity_canonical_alerts_neon_persistence_proof_continuation_runtime",
            "status": "primary_passed",
            "verdict": None,
            "predecessor_artifact": "research/multicity_canonical_alerts_neon_persistence_proof_2026-09-30.json",
            "predecessor_blocked_head": "8b6dff2bcf813b13f09bf5efd6078f393e76c494",
            "continuation_base_head": "299bb5dd2101facae9f70dc7c885851575505212",
            "git_proof_branch": "multicity-canonical-alerts-neon-persistence-proof-resume-2026-10-01",
            "github_proof_run_id": int(os.environ.get("GITHUB_RUN_ID", "0")) or None,
            "github_run_attempt": int(os.environ.get("GITHUB_RUN_ATTEMPT", "0")) or None,
            "workflow_sha": os.environ.get("GITHUB_SHA"),
            "neon": {"project_id": "green-cake-44216048", "disposable_branch_id": CHILD_BRANCH_ID},
            "frozen_corpus": {
                "production_frozen_site_prod_sha": EXPECTED_SITE_PROD_SHA,
                "vadimkin_frozen_sha": EXPECTED_VADIMKIN_SHA,
                "canonicalization_version": CANONICALIZATION_VERSION,
                "city_count": EXPECTED_CITY_COUNT,
                "total_episode_count": EXPECTED_EPISODE_COUNT,
                "corpus_sha256": EXPECTED_CORPUS_SHA256,
                "accepted_boundary_artifact_run_id": 36816630480,
                "accepted_boundary_artifact_id": 11141228922,
                "reused_without_rebuild": True,
                "source_provenance_coverage": "partial",
            },
            "gate_a_fresh_pre_state": pre,
            "gate_b_lviv_compatibility": {
                "result": "PASS",
                "production_lviv_episodes": EXPECTED_LVIV_COUNT,
                "neon_lviv_episodes": EXPECTED_LVIV_COUNT,
                "exact_compatible": EXPECTED_LVIV_COUNT,
                "mismatch_count": 0,
                "repaired_rows": repaired_before,
            },
            "gate_c_atomic_rollback": {"result": "PASS", "residue": 0, "attempt": rollback_attempt, "post_rollback_state": post_rollback},
            "gate_d_successful_full_import": {"result": "PASS", "import": successful_import, "post_import_state": post_import},
            "gate_e_per_city_exact_db_parity": {"result": "PASS", **full_parity},
            "gate_f_lviv_identity_preservation": {
                "result": "PASS",
                "episode_uid_map_pre": pre["lviv_uid_map"],
                "episode_uid_map_post": post_import["lviv_uid_map"],
                "repaired_rows_post": repaired_after_import,
            },
            "gate_g_exact_replay": {"result": "PASS", "retry": exact_retry, "post_retry_state": post_retry, "parity": retry_parity},
            "gate_h_fresh_process_replay": {"result": "NOT_RUN_YET"},
            "gate_i_conflict_rejection": {"result": "NOT_RUN_YET"},
            "gate_j_child_immutability": {"result": "NOT_FINALIZED_YET"},
            "gate_k_checkpoint_invariance": {"result": "NOT_FINALIZED_YET"},
            "safety": {
                "main_mutated": False,
                "site_prod_mutated": False,
                "production_default_neon_mutated": False,
                "permanent_shadow_mutated": False,
                "db_cutover": False,
                "deploy": False,
                "attack_events_imported": False,
                "differentiated_child_semantics_changed": False,
                "source_provenance_fabricated": False,
            },
        }
        write_json(result_path, result)
        print(json.dumps({
            "phase": "primary",
            "gate_a": "PASS",
            "gate_b": "PASS 126/126",
            "gate_c": "PASS residue=0",
            "gate_d": successful_import["stats"],
            "gate_e": f"PASS {full_parity['exact_total']}/{EXPECTED_EPISODE_COUNT}",
            "gate_f": "PASS",
            "gate_g": exact_retry["stats"],
        }, indent=2, sort_keys=True))
    finally:
        conn.close()

def fresh_replay(corpus: dict[str, Any], result_path: Path) -> None:
    result = load_json(result_path)
    require(result.get("status") == "primary_passed", "fresh replay requires primary_passed runtime state")
    conn = connect()
    try:
        cur = conn.cursor()
        before = state(cur)
        require(before["counts"]["alert_episodes"] == EXPECTED_EPISODE_COUNT, "Gate H pre-state parent count drift")
        for key in ("alert_episode_sources", "ingestion_checkpoints", "alert_state_snapshots", "alert_threat_observations"):
            require(before["fingerprints_md5"][key] == BASELINE_FINGERPRINTS[key], f"Gate H pre-state fingerprint drift: {key}")
        conn.rollback()
        cur.close()

        replay = run_parent_import(conn, corpus["episodes"], phase="fresh_process_replay")
        require(replay["stats"]["episodes_inserted"] == 0, f"Gate H fresh replay inserted parents: {replay}")
        require(replay["stats"]["episodes_existing"] == EXPECTED_EPISODE_COUNT, f"Gate H existing count drift: {replay}")
        require(replay["stats"]["exact_retry"] is True, "Gate H exact retry flag false")
        require(replay["stats"]["checkpoints_inserted"] == 0, "Gate H checkpoint advanced")
        cur = conn.cursor()
        after = state(cur)
        require(after["fingerprints_md5"]["alert_episodes_all"] == before["fingerprints_md5"]["alert_episodes_all"], "Gate H canonical parent physical state changed")
        for key in ("lviv_alert_episodes", "alert_episode_sources", "ingestion_checkpoints", "alert_state_snapshots", "alert_threat_observations"):
            require(after["fingerprints_md5"][key] == before["fingerprints_md5"][key], f"Gate H invariant changed: {key}")
        require(after["lviv_uid_map"] == before["lviv_uid_map"], "Gate H Lviv identity changed")
        p = parity(cur, corpus)
        require(p["exact_total"] == EXPECTED_EPISODE_COUNT and p["missing"] == 0 and p["extra"] == 0 and p["semantic_mismatches"] == 0, "Gate H exact DB parity failed")
        require(p["db_corpus_sha256"] == EXPECTED_CORPUS_SHA256, "Gate H DB corpus hash failed")
        conn.rollback()
        cur.close()
        result["gate_h_fresh_process_replay"] = {
            "result": "PASS",
            "replay": replay,
            "pre_state": before,
            "post_state": after,
            "parity": p,
            "new_process": True,
            "new_connection": True,
        }
        result["status"] = "fresh_replay_passed"
        write_json(result_path, result)
        print(json.dumps({"phase": "fresh_replay", "gate_h": "PASS", "stats": replay["stats"]}, indent=2, sort_keys=True))
    finally:
        conn.close()

def finalize(corpus: dict[str, Any], result_path: Path) -> None:
    result = load_json(result_path)
    require(result.get("status") == "fresh_replay_passed", "finalize requires fresh_replay_passed runtime state")
    conn = connect()
    try:
        cur = conn.cursor()
        before = state(cur)
        before_parity = parity(cur, corpus)
        require(before_parity["exact_total"] == EXPECTED_EPISODE_COUNT and before_parity["db_corpus_sha256"] == EXPECTED_CORPUS_SHA256, "Gate I pre-conflict parity drift")
        conn.rollback()
        cur.close()

        conflict = copy.deepcopy(corpus["episodes"][0])
        original_end = datetime.fromisoformat(str(conflict["end_at"]).replace("Z", "+00:00"))
        conflict["end_at"] = legacy_timestamp(original_end + timedelta(seconds=1))
        conflict_attempt = run_conflict_attempt(conn, conflict)
        require(conflict_attempt["rejected"] is True, "Gate I conflict not rejected")

        cur = conn.cursor()
        after = state(cur)
        require(after["counts"] == before["counts"], f"Gate I rollback count residue: before={before['counts']} after={after['counts']}")
        for key in ("alert_episodes_all", "lviv_alert_episodes", "alert_episode_sources", "ingestion_runs", "ingestion_checkpoints", "alert_state_snapshots", "alert_threat_observations"):
            require(after["fingerprints_md5"][key] == before["fingerprints_md5"][key], f"Gate I residue fingerprint changed: {key}")
        require(after["lviv_uid_map"] == before["lviv_uid_map"], "Gate I Lviv identity changed")
        final_parity = parity(cur, corpus)
        require(final_parity["city_count"] == EXPECTED_CITY_COUNT, "final city count drift")
        require(final_parity["exact_total"] == EXPECTED_EPISODE_COUNT, "final exact parity drift")
        require(final_parity["missing"] == 0 and final_parity["extra"] == 0 and final_parity["id_mismatches"] == 0 and final_parity["boundary_mismatches"] == 0 and final_parity["semantic_mismatches"] == 0, f"final parity mismatches: {final_parity}")
        require(final_parity["db_corpus_sha256"] == EXPECTED_CORPUS_SHA256, "final DB corpus hash drift")
        repaired_final = repaired_rows(cur)
        pre = result["gate_a_fresh_pre_state"]
        require(after["fingerprints_md5"]["lviv_alert_episodes"] == pre["fingerprints_md5"]["lviv_alert_episodes"], "Gate F/J Lviv rows changed")
        require(after["lviv_uid_map"] == pre["lviv_uid_map"], "Gate F existing Lviv identity not preserved")
        require(after["fingerprints_md5"]["alert_episode_sources"] == pre["fingerprints_md5"]["alert_episode_sources"], "Gate J source rows changed")
        require(after["fingerprints_md5"]["alert_state_snapshots"] == pre["fingerprints_md5"]["alert_state_snapshots"], "Gate J snapshot fingerprint changed")
        require(after["fingerprints_md5"]["alert_threat_observations"] == pre["fingerprints_md5"]["alert_threat_observations"], "Gate J threat fingerprint changed")
        require(after["counts"]["alert_state_snapshots"] == 13 and after["counts"]["alert_threat_observations"] == 14, "Gate J differentiated child counts changed")
        require(after["fingerprints_md5"]["ingestion_checkpoints"] == pre["fingerprints_md5"]["ingestion_checkpoints"], "Gate K checkpoint fingerprint changed")
        require(after["counts"]["ingestion_checkpoints"] == 1 and after["counts"]["max_checkpoint_seq"] == 1, "Gate K checkpoint count/seq changed")
        require(after["counts"]["alert_episode_sources"] == 143 and after["counts"]["alerts_in_ua_sources"] == 3, "final source counts changed")
        require(after["counts"]["alert_episodes"] == EXPECTED_EPISODE_COUNT, "final parent episode count changed")
        conn.rollback()
        cur.close()

        result["gate_i_conflict_rejection"] = {"result": "PASS", "attempt": conflict_attempt, "residue": 0, "pre_state": before, "post_state": after}
        result["gate_j_child_immutability"] = {
            "result": "PASS",
            "alert_state_snapshots_count_pre": pre["counts"]["alert_state_snapshots"],
            "alert_state_snapshots_count_post": after["counts"]["alert_state_snapshots"],
            "alert_state_snapshots_md5_pre": pre["fingerprints_md5"]["alert_state_snapshots"],
            "alert_state_snapshots_md5_post": after["fingerprints_md5"]["alert_state_snapshots"],
            "alert_threat_observations_count_pre": pre["counts"]["alert_threat_observations"],
            "alert_threat_observations_count_post": after["counts"]["alert_threat_observations"],
            "alert_threat_observations_md5_pre": pre["fingerprints_md5"]["alert_threat_observations"],
            "alert_threat_observations_md5_post": after["fingerprints_md5"]["alert_threat_observations"],
        }
        result["gate_k_checkpoint_invariance"] = {
            "result": "PASS",
            "count_pre": pre["counts"]["ingestion_checkpoints"],
            "count_post": after["counts"]["ingestion_checkpoints"],
            "max_checkpoint_seq_pre": pre["counts"]["max_checkpoint_seq"],
            "max_checkpoint_seq_post": after["counts"]["max_checkpoint_seq"],
            "fingerprint_pre": pre["fingerprints_md5"]["ingestion_checkpoints"],
            "fingerprint_post": after["fingerprints_md5"]["ingestion_checkpoints"],
        }
        result["final_neon_state"] = after
        result["final_per_city_parity"] = final_parity
        result["final_repaired_lviv_rows"] = repaired_final
        result["status"] = "proven"
        result["verdict"] = "MULTICITY CANONICAL ALERTS NEON PERSISTENCE PROVEN"
        write_json(result_path, result)
        print(json.dumps({
            "phase": "finalize",
            "gate_i": "PASS residue=0",
            "gate_j": "PASS",
            "gate_k": "PASS",
            "verdict": result["verdict"],
            "final_counts": after["counts"],
            "exact_parity": final_parity["exact_total"],
            "db_corpus_sha256": final_parity["db_corpus_sha256"],
        }, indent=2, sort_keys=True))
    finally:
        conn.close()

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", required=True, choices=("primary", "fresh-replay", "finalize"))
    parser.add_argument("--corpus", required=True)
    parser.add_argument("--result", required=True)
    args = parser.parse_args()
    corpus = load_corpus(Path(args.corpus))
    result_path = Path(args.result)
    if args.phase == "primary":
        primary(corpus, result_path)
    elif args.phase == "fresh-replay":
        fresh_replay(corpus, result_path)
    else:
        finalize(corpus, result_path)

if __name__ == "__main__":
    main()
