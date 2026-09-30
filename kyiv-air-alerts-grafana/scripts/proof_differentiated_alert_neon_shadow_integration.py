#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import differentiated_alert_shadow_runtime as runtime

FIX = ROOT / "tests" / "fixtures" / "differentiated_alert_shadow"
OUT = Path(os.environ.get(
    "PROOF_RESULT_PATH",
    str(ROOT.parent / "research" / "differentiated_alert_neon_shadow_integration_runtime.json"),
))
DATABASE_URL = os.environ["DIFFERENTIATED_ALERT_SHADOW_DATABASE_URL"]
OBS_FIRST = "2026-09-30T20:00:00Z"
OBS_LATER = "2026-09-30T20:05:00Z"
OBS_PARTIAL = "2026-09-30T20:10:00Z"


def dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def base_env() -> dict[str, str]:
    return {
        runtime.FEATURE_FLAG: "1",
        runtime.BACKEND_ENV: "postgres",
        runtime.DATABASE_URL_ENV: DATABASE_URL,
        runtime.KYIV_INPUT_ENV: str(FIX / "kyiv_live_raw_2026-09-29_111347.json"),
        runtime.KYIV_INPUT_CLASS_ENV: "FIXTURE",
        runtime.UA_INPUT_ENV: str(FIX / "ukrainealarm_overlap_stored_raw_2026-09-14.json"),
        runtime.AIU_INPUT_ENV: str(FIX / "alerts_in_ua_stored_raw_2026-09-16.json"),
    }


def child_counts() -> dict[str, int]:
    with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM alert_state_snapshots")
            snapshots = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM alert_threat_observations")
            observations = cur.fetchone()[0]
    return {"snapshots": snapshots, "observations": observations}


def parent_state() -> dict:
    sql = """
    SELECT jsonb_build_object(
      'counts', jsonb_build_object(
        'ingestion_runs', (SELECT count(*) FROM ingestion_runs),
        'alert_episodes', (SELECT count(*) FROM alert_episodes),
        'alert_episode_sources', (SELECT count(*) FROM alert_episode_sources),
        'ingestion_checkpoints', (SELECT count(*) FROM ingestion_checkpoints),
        'max_checkpoint_seq', (SELECT max(checkpoint_seq) FROM ingestion_checkpoints)
      ),
      'fingerprints', jsonb_build_object(
        'ingestion_runs', (SELECT md5(coalesce(string_agg(to_jsonb(t)::text, '' ORDER BY run_id::text),'')) FROM ingestion_runs t),
        'alert_episodes', (SELECT md5(coalesce(string_agg(to_jsonb(t)::text, '' ORDER BY episode_uid::text),'')) FROM alert_episodes t),
        'alert_episode_sources', (SELECT md5(coalesce(string_agg(to_jsonb(t)::text, '' ORDER BY source_observation_id::text),'')) FROM alert_episode_sources t),
        'ingestion_checkpoints', (SELECT md5(coalesce(string_agg(to_jsonb(t)::text, '' ORDER BY checkpoint_id::text),'')) FROM ingestion_checkpoints t)
      )
    )
    """
    with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            return cur.fetchone()[0]


def bindings(observed_at: str) -> list[dict]:
    with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT source_key, target_city_key, binding_state, episode_uid::text
                FROM alert_state_snapshots
                WHERE observed_at = %s
                ORDER BY source_key
                """,
                (observed_at,),
            )
            rows = cur.fetchall()
    return [
        {
            "source": source,
            "target_city_key": city,
            "binding_state": state,
            "episode_uid": episode_uid,
        }
        for source, city, state, episode_uid in rows
    ]


def sqlite_regression() -> dict:
    with tempfile.TemporaryDirectory() as td:
        env = base_env()
        env[runtime.BACKEND_ENV] = "sqlite"
        env.pop(runtime.DATABASE_URL_ENV, None)
        env[runtime.DB_ENV] = str(Path(td) / "shadow.sqlite")
        first = runtime.run_shadow([], env=env, now=dt(OBS_FIRST))
        second = runtime.run_shadow([], env=env, now=dt(OBS_FIRST))
        return {
            "status": "PASS" if (
                first["status"] == "SUCCEEDED"
                and first["inserted_snapshots"] == 3
                and first["inserted_observations"] == 3
                and second["status"] == "SUCCEEDED"
                and second["inserted_snapshots"] == 0
                and second["inserted_observations"] == 0
                and second["store_counts"] == {"snapshots": 3, "observations": 3}
            ) else "FAIL",
            "first": {
                "status": first["status"],
                "inserted_snapshots": first["inserted_snapshots"],
                "inserted_observations": first["inserted_observations"],
            },
            "replay": {
                "status": second["status"],
                "inserted_snapshots": second["inserted_snapshots"],
                "inserted_observations": second["inserted_observations"],
                "store_counts": second["store_counts"],
            },
        }


def fresh_replay() -> int:
    out = runtime.run_shadow([], env=base_env(), now=dt(OBS_FIRST))
    print(json.dumps({
        "attempted": out["attempted"],
        "status": out["status"],
        "inserted_snapshots": out["inserted_snapshots"],
        "inserted_observations": out["inserted_observations"],
        "store_counts": out["store_counts"],
    }, sort_keys=True))
    return 0 if out["status"] == "SUCCEEDED" else 2


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--fresh-replay":
        return fresh_replay()

    result = {
        "status": "FAIL",
        "credentials_exposed": False,
        "branch_id": os.environ.get("CHILD_BRANCH_ID"),
        "branch_host": os.environ.get("CHILD_DB_HOST"),
    }

    parent_pre = parent_state()
    baseline = child_counts()
    result["baseline_child_counts"] = baseline
    result["parent_pre"] = parent_pre

    disabled = runtime.run_shadow(
        [],
        env={
            runtime.FEATURE_FLAG: "0",
            runtime.BACKEND_ENV: "postgres",
            runtime.DATABASE_URL_ENV: "postgresql://not-used.invalid/db",
        },
        now=dt(OBS_FIRST),
    )
    result["off"] = {
        "attempted": disabled["attempted"],
        "status": disabled["status"],
        "child_counts_after": child_counts(),
    }

    result["sqlite_regression"] = sqlite_regression()

    first = runtime.run_shadow([], env=base_env(), now=dt(OBS_FIRST))
    first_bindings = bindings(OBS_FIRST)
    result["postgres_first_on"] = {
        "attempted": first["attempted"],
        "status": first["status"],
        "inserted_snapshots": first["inserted_snapshots"],
        "inserted_observations": first["inserted_observations"],
        "store_counts": first["store_counts"],
        "bindings": first_bindings,
    }

    replay = runtime.run_shadow([], env=base_env(), now=dt(OBS_FIRST))
    result["exact_replay"] = {
        "attempted": replay["attempted"],
        "status": replay["status"],
        "inserted_snapshots": replay["inserted_snapshots"],
        "inserted_observations": replay["inserted_observations"],
        "store_counts": replay["store_counts"],
    }

    proc = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--fresh-replay"],
        cwd=str(ROOT),
        env=dict(os.environ),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    fresh = None
    if proc.stdout.strip():
        try:
            fresh = json.loads(proc.stdout.strip().splitlines()[-1])
        except json.JSONDecodeError:
            fresh = None
    result["fresh_process_replay"] = {
        "returncode": proc.returncode,
        "result": fresh,
    }

    later = runtime.run_shadow([], env=base_env(), now=dt(OBS_LATER))
    result["later_poll"] = {
        "attempted": later["attempted"],
        "status": later["status"],
        "inserted_snapshots": later["inserted_snapshots"],
        "inserted_observations": later["inserted_observations"],
        "store_counts": later["store_counts"],
    }

    bad_env = base_env()
    bad_env[runtime.DATABASE_URL_ENV] = (
        "postgresql://proof:proof@127.0.0.1:1/postgres?connect_timeout=1"
    )
    connection_failure = runtime.run_from_updater([], env=bad_env)
    result["connection_failure_fail_open"] = {
        "attempted": connection_failure.get("attempted"),
        "status": connection_failure.get("status"),
        "error_type": connection_failure.get("error_type"),
        "production_output_mutation": connection_failure.get("production_output_mutation"),
        "child_counts_after": child_counts(),
    }

    with tempfile.TemporaryDirectory() as td:
        malformed = Path(td) / "bad-kyiv.json"
        malformed.write_text("{not-json", encoding="utf-8")
        partial_env = base_env()
        partial_env[runtime.KYIV_INPUT_ENV] = str(malformed)
        partial = runtime.run_shadow([], env=partial_env, now=dt(OBS_PARTIAL))
    result["source_partial_failure"] = {
        "attempted": partial["attempted"],
        "status": partial["status"],
        "inserted_snapshots": partial["inserted_snapshots"],
        "inserted_observations": partial["inserted_observations"],
        "sources": {
            k: {
                "status": v.get("status"),
                "inserted_snapshots": v.get("inserted_snapshots"),
                "inserted_observations": v.get("inserted_observations"),
                "error_type": v.get("error_type"),
            }
            for k, v in partial["sources"].items()
        },
        "store_counts": partial["store_counts"],
    }

    parent_post = parent_state()
    final_counts = child_counts()
    result["parent_post"] = parent_post
    result["final_child_counts"] = final_counts

    expected_parent_counts = {
        "ingestion_runs": 1,
        "alert_episodes": 126,
        "alert_episode_sources": 140,
        "ingestion_checkpoints": 1,
        "max_checkpoint_seq": 1,
    }
    no_false_binding = (
        len(first_bindings) == 3
        and all(x["binding_state"] in {"UNBOUND", "AMBIGUOUS"} for x in first_bindings)
        and all(x["episode_uid"] is None for x in first_bindings)
    )
    fresh_ok = bool(
        proc.returncode == 0
        and fresh
        and fresh["status"] == "SUCCEEDED"
        and fresh["inserted_snapshots"] == 0
        and fresh["inserted_observations"] == 0
        and fresh["store_counts"] == {"snapshots": 8, "observations": 8}
    )
    source_results = result["source_partial_failure"]["sources"]
    partial_ok = (
        partial["status"] == "PARTIAL_FAILURE"
        and source_results["kyiv"]["status"] == "FAILED"
        and source_results["ukrainealarm"]["status"] == "SUCCEEDED"
        and source_results["alerts_in_ua"]["status"] == "SUCCEEDED"
        and partial["inserted_snapshots"] == 2
        and partial["inserted_observations"] == 3
    )

    gates = {
        "baseline_5_5": baseline == {"snapshots": 5, "observations": 5},
        "off_no_connection_no_write": (
            disabled["attempted"] is False
            and disabled["status"] == "DISABLED"
            and result["off"]["child_counts_after"] == baseline
        ),
        "sqlite_regression": result["sqlite_regression"]["status"] == "PASS",
        "postgres_first_on": (
            first["attempted"] is True
            and first["status"] == "SUCCEEDED"
            and first["inserted_snapshots"] == 3
            and first["inserted_observations"] == 3
            and first["store_counts"] == {"snapshots": 8, "observations": 8}
        ),
        "no_false_binding": no_false_binding,
        "exact_replay": (
            replay["attempted"] is True
            and replay["status"] == "SUCCEEDED"
            and replay["inserted_snapshots"] == 0
            and replay["inserted_observations"] == 0
            and replay["store_counts"] == {"snapshots": 8, "observations": 8}
        ),
        "fresh_process_replay": fresh_ok,
        "later_poll": (
            later["status"] == "SUCCEEDED"
            and later["inserted_snapshots"] == 3
            and later["inserted_observations"] == 3
            and later["store_counts"] == {"snapshots": 11, "observations": 11}
        ),
        "connection_failure_fail_open": (
            connection_failure.get("attempted") is True
            and connection_failure.get("status") == "FAILED"
            and connection_failure.get("production_output_mutation") is False
            and result["connection_failure_fail_open"]["child_counts_after"]
                == {"snapshots": 11, "observations": 11}
        ),
        "source_partial_failure": partial_ok,
        "parent_immutable": (
            parent_pre == parent_post
            and parent_post["counts"] == expected_parent_counts
        ),
        "final_child_counts": final_counts == {"snapshots": 13, "observations": 14},
    }
    result["gates"] = gates
    result["status"] = "PASS" if all(gates.values()) else "FAIL"

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": result["status"],
        "gates": gates,
        "final_child_counts": final_counts,
    }, sort_keys=True))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
