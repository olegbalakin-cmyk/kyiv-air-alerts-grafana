#!/usr/bin/env python3
from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import differentiated_alert_postgres as pg
import proof_differentiated_alert_shadow_ingestion as shadow

FIX = ROOT / "tests" / "fixtures" / "differentiated_alert_shadow"
OUT = Path(os.environ.get("PROOF_RESULT_PATH", str(ROOT.parent / "research" / "differentiated_alert_postgres_child_persistence_runtime.json")))
FROZEN_OBSERVED_AT = "2026-09-29T09:13:47Z"
CHILD_URL = os.environ["CHILD_DATABASE_URL"]


def load_json(name: str):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def iso(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return str(value)


def load_parent_episode_view():
    with psycopg.connect(CHILD_URL, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT episode_uid, legacy_episode_id, city_key, alert_type, start_at, end_at
                FROM alert_episodes
                ORDER BY start_at, episode_uid
                """
            )
            rows = cur.fetchall()
    episodes = []
    for episode_uid, legacy_episode_id, city_key, alert_type, start_at, end_at in rows:
        episodes.append({
            "episode_uid": str(episode_uid),
            "episode_id": legacy_episode_id,
            "legacy_episode_id": legacy_episode_id,
            "city_key": city_key,
            "alert_type": alert_type,
            "start_at": iso(start_at),
            "end_at": iso(end_at),
        })
    return episodes


def frozen_real_records(observed_at: str = FROZEN_OBSERVED_AT):
    parents = load_parent_episode_view()
    kyiv = shadow.canonicalize_kyiv(
        load_json("kyiv_live_raw_2026-09-29_111347.json"),
        observed_at=observed_at,
        target_city_key="kyiv",
        raw_object_path="$LIVE_RAW",
    )
    ua_payload = load_json("ukrainealarm_overlap_stored_raw_2026-09-14.json")
    ua = shadow.canonicalize_ukrainealarm(
        ua_payload,
        observed_at=observed_at,
        target_city_key="zaporizhzhia",
        region_id=str(ua_payload.get("regionId") or "147"),
        raw_object_path="$STORED_RAW",
    )
    aiu = shadow.canonicalize_alerts_in_ua(
        load_json("alerts_in_ua_stored_raw_2026-09-16.json"),
        observed_at=observed_at,
        target_city_key="donetsk",
        raw_object_path="$STORED_RAW",
    )
    return [shadow.bind(r, parents) for r in (kyiv, ua, aiu)]


def child_counts():
    with psycopg.connect(CHILD_URL, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM alert_state_snapshots")
            snapshots = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM alert_threat_observations")
            observations = cur.fetchone()[0]
    return {"snapshots": snapshots, "observations": observations}


def persist(records):
    with psycopg.connect(CHILD_URL) as conn:
        return pg.persist_records(conn, records)


def fresh_replay_mode():
    records = frozen_real_records()
    stats = persist(records)
    print(json.dumps({"stats": stats, "counts": child_counts()}, sort_keys=True))
    return 0


def expect_reject(name, sql, params, expected_constraint=None):
    try:
        with psycopg.connect(CHILD_URL, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
    except Exception as exc:
        diag = getattr(exc, "diag", None)
        constraint = getattr(diag, "constraint_name", None) if diag is not None else None
        ok = expected_constraint is None or constraint == expected_constraint
        return {
            "name": name,
            "rejected": True,
            "error_type": type(exc).__name__,
            "constraint": constraint,
            "expected_constraint": expected_constraint,
            "pass": ok,
        }
    return {
        "name": name,
        "rejected": False,
        "error_type": None,
        "constraint": None,
        "expected_constraint": expected_constraint,
        "pass": False,
    }


def synthetic_bound_case(parent):
    marker = "PROOF_SYNTHETIC_BOUNDING_CASE"
    raw_hash = hashlib.sha256(marker.encode()).hexdigest()
    snapshot_key = hashlib.sha256((marker + "|snapshot").encode()).hexdigest()
    record = {
        "snapshot": {
            "snapshot_key_version": "differentiated-snapshot-v1",
            "snapshot_key": snapshot_key,
            "episode_uid": parent["episode_uid"],
            "binding_state": "BOUND",
            "source": marker,
            "source_alert_id": "synthetic-bound-1",
            "target_city_key": parent["city_key"],
            "alert_type": parent["alert_type"],
            "source_geography": {"scope": "CITY", "type_raw": "proof", "id_raw": "lviv"},
            "observed_at": parent["start_at"],
            "source_state_at": parent["start_at"],
            "source_active": True,
            "source_alert_level_raw": None,
            "source_state_raw": "proof",
            "raw_payload_hash": raw_hash,
            "raw_object_path": "$PROOF_SYNTHETIC_BOUNDING_CASE",
        },
        "threat_observations": [],
    }
    stats = persist([record])
    with psycopg.connect(CHILD_URL, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT binding_state, episode_uid::text, target_city_key, source_key FROM alert_state_snapshots WHERE snapshot_key=%s",
                (snapshot_key,),
            )
            row = cur.fetchone()
    return {
        "stats": stats,
        "snapshot_key": snapshot_key,
        "expected_episode_uid": parent["episode_uid"],
        "row": None if row is None else {
            "binding_state": row[0], "episode_uid": row[1], "target_city_key": row[2], "source_key": row[3]
        },
        "pass": bool(row and row[0] == "BOUND" and row[1] == parent["episode_uid"]),
    }


def raw_preservation(records):
    checks = []
    with psycopg.connect(CHILD_URL, autocommit=True) as conn:
        with conn.cursor() as cur:
            for record in records:
                s = record["snapshot"]
                cur.execute(
                    "SELECT provenance::text, raw_sha256, source_key, binding_state, episode_uid FROM alert_state_snapshots WHERE snapshot_key=%s",
                    (s["snapshot_key"],),
                )
                row = cur.fetchone()
                if row is None:
                    checks.append({"snapshot_key": s["snapshot_key"], "pass": False, "reason": "missing"})
                    continue
                prov = json.loads(row[0])
                exact_snapshot = prov.get("snapshot") == record["snapshot"]
                exact_threats = prov.get("threat_observations") == record["threat_observations"]
                raw_hash = row[1] == s["raw_payload_hash"]
                no_false_parent = row[3] in ("AMBIGUOUS", "UNBOUND") and row[4] is None
                checks.append({
                    "source": s["source"],
                    "snapshot_key": s["snapshot_key"],
                    "provenance_snapshot_exact": exact_snapshot,
                    "provenance_threats_exact": exact_threats,
                    "raw_sha256_exact": raw_hash,
                    "binding_state": row[3],
                    "episode_uid_is_null": row[4] is None,
                    "pass": exact_snapshot and exact_threats and raw_hash and no_false_parent,
                })
    return {"records": checks, "pass": all(x["pass"] for x in checks)}


def rollback_case(base_observed: str):
    later = (datetime.fromisoformat(base_observed.replace("Z", "+00:00")) + timedelta(minutes=10)).isoformat().replace("+00:00", "Z")
    parents = load_parent_episode_view()
    record = shadow.canonicalize_alerts_in_ua(
        load_json("alerts_in_ua_stored_raw_2026-09-16.json"),
        observed_at=later,
        target_city_key="donetsk",
        raw_object_path="$STORED_RAW",
    )
    record = shadow.bind(record, parents)
    before = child_counts()
    failed = False
    error_type = None
    try:
        with psycopg.connect(CHILD_URL) as conn:
            def boom(_record, _uid):
                raise RuntimeError("PROOF_FORCED_FAILURE_AFTER_SNAPSHOT")
            pg.persist_record(conn, record, after_snapshot_hook=boom)
    except Exception as exc:
        failed = True
        error_type = type(exc).__name__
    after = child_counts()
    with psycopg.connect(CHILD_URL, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM alert_state_snapshots WHERE snapshot_key=%s", (record["snapshot"]["snapshot_key"],))
            residue_snapshot = cur.fetchone()[0]
            keys = [x["observation_key"] for x in record["threat_observations"]]
            if keys:
                cur.execute("SELECT count(*) FROM alert_threat_observations WHERE threat_observation_key = ANY(%s)", (keys,))
                residue_obs = cur.fetchone()[0]
            else:
                residue_obs = 0
    return {
        "failure_injected": True,
        "failed": failed,
        "error_type": error_type,
        "before_counts": before,
        "after_counts": after,
        "snapshot_residue": residue_snapshot,
        "observation_residue": residue_obs,
        "pass": failed and before == after and residue_snapshot == 0 and residue_obs == 0,
    }


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--fresh-replay":
        return fresh_replay_mode()

    result = {
        "status": "FAIL",
        "credentials_exposed": False,
        "child_branch_id": os.environ.get("CHILD_BRANCH_ID"),
        "child_host": os.environ.get("CHILD_DB_HOST"),
        "adapter_blob": "3cd9c9c5fc0676550aeb1cfa117894e1fc91e85f",
        "schema_candidate_blob": "3580847807c449df12b3d4a9ea062d69a8f6ec01",
    }
    initial_counts = child_counts()
    records = frozen_real_records()
    result["initial_child_counts"] = initial_counts
    result["real_fixture_pre_binding"] = [
        {
            "source": r["snapshot"]["source"],
            "target_city_key": r["snapshot"]["target_city_key"],
            "binding_state": r["snapshot"]["binding_state"],
            "episode_id": r["snapshot"].get("episode_id"),
            "snapshot_key": r["snapshot"]["snapshot_key"],
            "threat_count": len(r["threat_observations"]),
        }
        for r in records
    ]
    no_false_binding = all(
        r["snapshot"]["binding_state"] in ("UNBOUND", "AMBIGUOUS")
        and r["snapshot"].get("episode_id") is None
        for r in records
    )
    result["no_false_binding"] = no_false_binding

    first = persist(records)
    second = persist(records)
    result["real_fixture_first_run"] = first
    result["exact_replay_second_run"] = second

    proc = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--fresh-replay"],
        cwd=str(ROOT), env=dict(os.environ), text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
    )
    fresh = None
    if proc.returncode == 0 and proc.stdout.strip():
        fresh = json.loads(proc.stdout.strip().splitlines()[-1])
    result["fresh_process_replay"] = {"returncode": proc.returncode, "result": fresh}

    parents = load_parent_episode_view()
    parent = parents[0]
    synthetic = synthetic_bound_case(parent)
    result["synthetic_bound_case"] = synthetic

    existing_uid = parent["episode_uid"]
    base_snapshot_sql = """
      INSERT INTO alert_state_snapshots (
        snapshot_key_version,snapshot_key,episode_uid,binding_state,source_key,alert_type,
        target_city_key,source_geo_scope,observed_at,raw_sha256,provenance
      ) VALUES (%s,%s,%s,%s,%s,'AIR','lviv','CITY',%s,%s,'{}'::jsonb)
    """
    now = FROZEN_OBSERVED_AT
    def key(label):
        return hashlib.sha256(("constraint|" + label).encode()).hexdigest()
    invalid_parent = str(uuid.uuid4())
    rejects = []
    rejects.append(expect_reject(
        "BOUND_plus_null_episode", base_snapshot_sql,
        ("differentiated-snapshot-v1", key("bound-null"), None, "BOUND", "constraint-proof", now, key("raw1")),
        "alert_state_snapshots_binding_check"))
    rejects.append(expect_reject(
        "UNBOUND_plus_nonnull_episode", base_snapshot_sql,
        ("differentiated-snapshot-v1", key("unbound-nonnull"), existing_uid, "UNBOUND", "constraint-proof", now, key("raw2")),
        "alert_state_snapshots_binding_check"))
    rejects.append(expect_reject(
        "AMBIGUOUS_plus_nonnull_episode", base_snapshot_sql,
        ("differentiated-snapshot-v1", key("ambiguous-nonnull"), existing_uid, "AMBIGUOUS", "constraint-proof", now, key("raw3")),
        "alert_state_snapshots_binding_check"))
    rejects.append(expect_reject(
        "nonexistent_parent_fk", base_snapshot_sql,
        ("differentiated-snapshot-v1", key("missing-parent"), invalid_parent, "BOUND", "constraint-proof", now, key("raw4")),
        "alert_state_snapshots_episode_uid_fkey"))

    missing_snapshot = str(uuid.uuid4())
    threat_sql = """
      INSERT INTO alert_threat_observations (
        snapshot_uid,threat_observation_key_version,threat_observation_key,component_identity_basis,
        source_started_at,source_ended_at
      ) VALUES (%s,'differentiated-threat-observation-v1',%s,'SNAPSHOT_ONLY',%s,%s)
    """
    rejects.append(expect_reject(
        "nonexistent_snapshot_fk", threat_sql,
        (missing_snapshot, key("missing-snapshot"), None, None),
        "alert_threat_observations_snapshot_uid_fkey"))

    with psycopg.connect(CHILD_URL, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT snapshot_uid::text FROM alert_state_snapshots WHERE snapshot_key=%s", (records[0]["snapshot"]["snapshot_key"],))
            valid_snapshot_uid = cur.fetchone()[0]
    rejects.append(expect_reject(
        "source_ended_before_started", threat_sql,
        (valid_snapshot_uid, key("bad-end"), "2026-09-30T10:00:00Z", "2026-09-30T09:00:00Z"),
        "alert_threat_observations_end_after_start_check"))
    result["constraint_rejections"] = {"cases": rejects, "pass": all(x["pass"] for x in rejects)}

    later_observed = (datetime.fromisoformat(FROZEN_OBSERVED_AT.replace("Z", "+00:00")) + timedelta(minutes=5)).isoformat().replace("+00:00", "Z")
    ua_payload = load_json("ukrainealarm_overlap_stored_raw_2026-09-14.json")
    later_record = shadow.canonicalize_ukrainealarm(
        ua_payload, observed_at=later_observed, target_city_key="zaporizhzhia",
        region_id=str(ua_payload.get("regionId") or "147"), raw_object_path="$STORED_RAW")
    later_record = shadow.bind(later_record, parents)
    later_stats = persist([later_record])
    result["later_legitimate_poll"] = {
        "observed_at": later_observed,
        "binding_state": later_record["snapshot"]["binding_state"],
        "episode_id": later_record["snapshot"].get("episode_id"),
        "stats": later_stats,
        "pass": later_stats["inserted_snapshots"] == 1 and later_stats["inserted_observations"] == len(later_record["threat_observations"]),
    }

    result["rollback_proof"] = rollback_case(FROZEN_OBSERVED_AT)
    result["raw_value_preservation"] = raw_preservation(records)
    result["final_child_counts"] = child_counts()

    exact_second_ok = (
        second["inserted_snapshots"] == 0 and second["inserted_observations"] == 0
        and second["existing_snapshots"] == len(records)
        and second["existing_observations"] == sum(len(r["threat_observations"]) for r in records)
    )
    fresh_ok = bool(
        fresh and fresh["stats"]["inserted_snapshots"] == 0
        and fresh["stats"]["inserted_observations"] == 0
    )
    first_ok = (
        first["inserted_snapshots"] == len(records)
        and first["inserted_observations"] == sum(len(r["threat_observations"]) for r in records)
    )
    gates = {
        "initial_child_empty": initial_counts == {"snapshots": 0, "observations": 0},
        "real_fixture_persistence": first_ok,
        "no_false_binding": no_false_binding,
        "synthetic_bound": synthetic["pass"],
        "constraints": result["constraint_rejections"]["pass"],
        "exact_replay": exact_second_ok,
        "fresh_process_replay": fresh_ok,
        "later_poll": result["later_legitimate_poll"]["pass"],
        "rollback": result["rollback_proof"]["pass"],
        "raw_preservation": result["raw_value_preservation"]["pass"],
    }
    result["gates"] = gates
    result["status"] = "PASS" if all(gates.values()) else "FAIL"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "gates": gates, "final_child_counts": result["final_child_counts"]}, sort_keys=True))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
