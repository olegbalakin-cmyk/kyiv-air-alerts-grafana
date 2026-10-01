#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

UTC = timezone.utc
ACCEPTED_FROZEN_SHA = "8e9f3660039de4e0490db25229fe1760f5926b6b73490c8a325b9abc7555971b"
ACCEPTED_FROZEN_COUNT = 27866
ACCEPTED_REPAIRED_LVIV = {
    "575f370c-6e99-4623-8219-f8fbdfd6c978": {
        "legacy_episode_id": "7dd411c2a2587efc740a1a66",
        "start_at": "2026-09-12T22:00:05.398348Z",
        "end_at": "2026-09-12T22:14:27Z",
    },
    "c90e7b05-1982-461f-945f-53d8130c627b": {
        "legacy_episode_id": "c2cd9a96768756d84c250735",
        "start_at": "2026-09-13T02:32:14Z",
        "end_at": "2026-09-13T06:11:11.976953Z",
    },
    "451c8a2c-248a-41e5-b49e-31af3f44631f": {
        "legacy_episode_id": "94ce779cf047984e881bfdd5",
        "start_at": "2026-09-15T16:44:13Z",
        "end_at": "2026-09-15T17:09:02Z",
    },
}
ACCEPTED_SUPERSESSIONS = {
    "cherkasy": {
        "frozen": {
            "legacy_episode_id": "bf257aa6eec95163da3d6e83",
            "start_at": "2026-09-30T07:41:55.394018Z",
            "end_at": "2026-09-30T08:45:08.294769Z",
        },
        "current": {
            "legacy_episode_id": "afcef7b230c5de2744537b72",
            "start_at": "2026-09-30T02:02:42.067496Z",
            "end_at": "2026-09-30T18:03:04.653473Z",
        },
    },
    "poltava": {
        "frozen": {
            "legacy_episode_id": "edcd6d1baa0ae94f6c61260c",
            "start_at": "2026-09-30T13:45:54.742331Z",
            "end_at": "2026-09-30T15:30:23.570835Z",
        },
        "current": {
            "legacy_episode_id": "391a673766d8d512d54fcf52",
            "start_at": "2026-09-30T11:33:40.554164Z",
            "end_at": "2026-09-30T19:23:26.328094Z",
        },
    },
}


def parse_utc(value: Any) -> datetime:
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        raise AssertionError(f"naive timestamp: {value!r}")
    return dt.astimezone(UTC)


def same_time(a: Any, b: Any) -> bool:
    return parse_utc(a) == parse_utc(b)


def full_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row["city_key"],
        row["alert_type"],
        parse_utc(row["start_at"]),
        parse_utc(row["end_at"]),
        row["episode_state"],
        row["legacy_episode_id"],
        row["canonicalization_version"],
    )


def interval_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row["city_key"],
        row["alert_type"],
        parse_utc(row["start_at"]),
        parse_utc(row["end_at"]),
    )


def fingerprint(rows: list[dict[str, Any]]) -> str:
    payload = "\n".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
        for row in rows
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def fetch_json_rows(cursor: Any, table: str, where: str = "TRUE", order_by: str = "1") -> list[dict[str, Any]]:
    if table not in {"alert_episodes", "alert_episode_sources", "ingestion_checkpoints"}:
        raise ValueError(table)
    cursor.execute(
        f"SELECT to_jsonb(t) FROM (SELECT * FROM {table} WHERE {where} ORDER BY {order_by}) AS t"
    )
    return [row[0] for row in cursor.fetchall()]


def snapshot(connection: Any) -> dict[str, Any]:
    c = connection.cursor()
    try:
        c.execute("""SELECT
          (SELECT count(*) FROM ingestion_runs),
          (SELECT count(*) FROM alert_episodes),
          (SELECT count(*) FROM alert_episode_sources),
          (SELECT count(*) FROM ingestion_checkpoints),
          (SELECT max(checkpoint_seq) FROM ingestion_checkpoints),
          (SELECT count(*) FROM alert_episode_sources WHERE source_key='alerts_in_ua'),
          (SELECT count(*) FROM alert_episodes WHERE city_key <> 'lviv'),
          to_regclass('public.alert_state_snapshots')::text,
          to_regclass('public.alert_threat_observations')::text,
          to_regclass('public.attack_events')::text
        """)
        row = c.fetchone()
        lviv = fetch_json_rows(c, "alert_episodes", "city_key='lviv'", "episode_uid")
        sources = fetch_json_rows(c, "alert_episode_sources", "TRUE", "source_observation_id")
        checkpoints = fetch_json_rows(c, "ingestion_checkpoints", "TRUE", "checkpoint_id")
        return {
            "ingestion_runs": int(row[0]),
            "alert_episodes": int(row[1]),
            "alert_episode_sources": int(row[2]),
            "ingestion_checkpoints": int(row[3]),
            "max_checkpoint_seq": int(row[4]) if row[4] is not None else None,
            "alerts_in_ua_sources": int(row[5]),
            "non_lviv_episodes": int(row[6]),
            "alert_state_snapshots_table": row[7],
            "alert_threat_observations_table": row[8],
            "attack_events_table": row[9],
            "lviv_parent_fingerprint_sha256": fingerprint(lviv),
            "source_fingerprint_sha256": fingerprint(sources),
            "checkpoint_fingerprint_sha256": fingerprint(checkpoints),
            "lviv_rows": lviv,
        }
    finally:
        c.close()


def verify_accepted_lviv(pre: dict[str, Any]) -> None:
    assert pre["alert_episodes"] == 126, pre
    assert pre["non_lviv_episodes"] == 0, pre
    assert pre["alert_episode_sources"] == 143, pre
    assert pre["alerts_in_ua_sources"] == 3, pre
    assert pre["ingestion_checkpoints"] == 18, pre
    assert pre["max_checkpoint_seq"] == 18, pre
    assert pre["alert_state_snapshots_table"] is None, pre
    assert pre["alert_threat_observations_table"] is None, pre
    assert pre["attack_events_table"] is None, pre
    by_uid = {str(x["episode_uid"]): x for x in pre["lviv_rows"]}
    assert len(by_uid) == 126
    for uid, expected in ACCEPTED_REPAIRED_LVIV.items():
        row = by_uid[uid]
        assert row["legacy_episode_id"] == expected["legacy_episode_id"], (uid, row)
        assert same_time(row["start_at"], expected["start_at"]), (uid, row)
        assert same_time(row["end_at"], expected["end_at"]), (uid, row)


def validate_corpora(current: dict[str, Any], frozen: dict[str, Any]) -> dict[str, Any]:
    assert frozen["corpus_sha256"] == ACCEPTED_FROZEN_SHA
    assert frozen["total_episode_count"] == ACCEPTED_FROZEN_COUNT
    assert frozen["city_count"] == 23
    assert frozen["open_episode_count"] == 0
    assert frozen["boundary_proven"] is True
    assert not frozen["boundary_errors"]

    assert current["city_count"] == 23
    assert current["open_episode_count"] == 0
    assert current["boundary_proven"] is True
    assert not current["boundary_errors"]
    assert all(v["daily28_parity"] for v in current["per_city"].values())

    cur_rows = current["episodes"]
    old_rows = frozen["episodes"]
    cur_full = {full_key(x) for x in cur_rows}
    old_full = {full_key(x) for x in old_rows}
    assert len(cur_full) == len(cur_rows)
    assert len(old_full) == len(old_rows)

    cur_legacy = [x["legacy_episode_id"] for x in cur_rows]
    cur_intervals = [interval_key(x) for x in cur_rows]
    duplicate_legacy = len(cur_legacy) - len(set(cur_legacy))
    duplicate_interval = len(cur_intervals) - len(set(cur_intervals))
    assert duplicate_legacy == 0
    assert duplicate_interval == 0

    accepted_old_ids = {
        spec["frozen"]["legacy_episode_id"] for spec in ACCEPTED_SUPERSESSIONS.values()
    }
    old_by_legacy = {x["legacy_episode_id"]: x for x in old_rows}
    cur_by_legacy = {x["legacy_episode_id"]: x for x in cur_rows}
    cur_by_interval = {interval_key(x): x for x in cur_rows}

    frozen_missing = [x for x in old_rows if full_key(x) not in cur_full]
    unexpected_missing = [
        x for x in frozen_missing if x["legacy_episode_id"] not in accepted_old_ids
    ]
    assert not unexpected_missing, unexpected_missing
    assert len(frozen_missing) == 2, frozen_missing

    unexpected_boundary_changed = []
    unexpected_legacy_id_changed = []
    for legacy, old in old_by_legacy.items():
        if legacy in accepted_old_ids:
            continue
        cur = cur_by_legacy.get(legacy)
        if cur is None or full_key(cur) != full_key(old):
            unexpected_boundary_changed.append({"old": old, "current": cur})
        same_interval = cur_by_interval.get(interval_key(old))
        if same_interval is not None and same_interval["legacy_episode_id"] != legacy:
            unexpected_legacy_id_changed.append(
                {"old": old, "current": same_interval}
            )
    assert not unexpected_boundary_changed, unexpected_boundary_changed
    assert not unexpected_legacy_id_changed, unexpected_legacy_id_changed

    accepted = []
    for city, spec in ACCEPTED_SUPERSESSIONS.items():
        old = old_by_legacy[spec["frozen"]["legacy_episode_id"]]
        assert old["city_key"] == city
        assert same_time(old["start_at"], spec["frozen"]["start_at"])
        assert same_time(old["end_at"], spec["frozen"]["end_at"])
        assert spec["frozen"]["legacy_episode_id"] not in cur_by_legacy

        new = cur_by_legacy[spec["current"]["legacy_episode_id"]]
        assert new["city_key"] == city
        assert same_time(new["start_at"], spec["current"]["start_at"])
        assert same_time(new["end_at"], spec["current"]["end_at"])
        accepted.append({"city_key": city, "frozen": old, "current": new})

    return {
        "historical_continuity": {
            "frozen_total": len(old_rows),
            "frozen_exact_retained": len(old_rows) - len(frozen_missing),
            "accepted_supersession_count": len(accepted),
            "accepted_supersessions": accepted,
            "unexpected_frozen_missing": len(unexpected_missing),
            "unexpected_frozen_boundary_changed": len(unexpected_boundary_changed),
            "unexpected_frozen_legacy_id_changed": len(unexpected_legacy_id_changed),
        },
        "current_corpus": {
            "city_count": current["city_count"],
            "episode_count": current["total_episode_count"],
            "corpus_sha256": current["corpus_sha256"],
            "open_episode_count": current["open_episode_count"],
            "boundary_error_count": len(current["boundary_errors"]),
            "duplicate_legacy_ids": duplicate_legacy,
            "duplicate_exact_intervals": duplicate_interval,
            "production_parity": "PASS",
            "per_city_counts": {
                key: value["episode_count"] for key, value in current["per_city"].items()
            },
        },
    }


def connect(url: str) -> Any:
    import psycopg
    return psycopg.connect(url)


def query_db_parity(connection: Any, episodes: list[dict[str, Any]]) -> dict[str, Any]:
    c = connection.cursor()
    try:
        c.execute("""SELECT episode_uid::text, legacy_episode_id, city_key, alert_type,
                            start_at, end_at, episode_state, canonicalization_version
                     FROM alert_episodes""")
        db_rows = c.fetchall()
    finally:
        c.close()

    cand_by_legacy = {x["legacy_episode_id"]: x for x in episodes}
    db_by_legacy = {str(x[1]): x for x in db_rows}
    missing = sorted(set(cand_by_legacy) - set(db_by_legacy))
    extra = sorted(set(db_by_legacy) - set(cand_by_legacy))
    boundary = []
    legacy = []
    city = []
    state = []
    version = []

    db_by_interval = {
        (str(x[2]), str(x[3]), parse_utc(x[4]), parse_utc(x[5])): str(x[1])
        for x in db_rows
    }
    for legacy_id, row in cand_by_legacy.items():
        db = db_by_legacy.get(legacy_id)
        if db is None:
            continue
        if not same_time(db[4], row["start_at"]) or not same_time(db[5], row["end_at"]):
            boundary.append(legacy_id)
        if str(db[2]) != row["city_key"]:
            city.append(legacy_id)
        if str(db[6]) != row["episode_state"]:
            state.append(legacy_id)
        if str(db[7]) != row["canonicalization_version"]:
            version.append(legacy_id)
        marker = interval_key(row)
        other = db_by_interval.get(marker)
        if other is not None and other != legacy_id:
            legacy.append({"candidate": legacy_id, "db": other})

    return {
        "db_total": len(db_rows),
        "db_city_count": len(set(str(x[2]) for x in db_rows)),
        "missing": len(missing),
        "extra": len(extra),
        "boundary_mismatches": len(boundary),
        "legacy_id_mismatches": len(legacy),
        "city_mismatches": len(city),
        "state_mismatches": len(state),
        "canonicalization_version_mismatches": len(version),
    }


def provenance(args: argparse.Namespace, current: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_kind": "multicity_canonical_bootstrap",
        "workflow_repository": os.environ.get("GITHUB_REPOSITORY"),
        "workflow_name": os.environ.get("GITHUB_WORKFLOW"),
        "workflow_ref": os.environ.get("GITHUB_REF"),
        "workflow_sha": os.environ.get("GITHUB_SHA"),
        "input_repository": "olegbalakin-cmyk/kyiv-air-alerts-grafana",
        "input_ref": "site-prod",
        "input_sha": args.enablement_base,
        "github_run_id": int(os.environ["GITHUB_RUN_ID"]) if os.environ.get("GITHUB_RUN_ID") else None,
        "github_run_attempt": int(os.environ["GITHUB_RUN_ATTEMPT"]) if os.environ.get("GITHUB_RUN_ATTEMPT") else None,
        "canonicalization_version": current["canonicalization_version"],
        "parameters": {
            "production_city_count": current["city_count"],
            "canonical_episode_count": current["total_episode_count"],
            "corpus_sha256": current["corpus_sha256"],
            "source_provenance_coverage": "partial",
            "pinned_vadimkin_ref": args.current_vadimkin_ref,
            "pinned_vadimkin_blob": args.current_vadimkin_blob,
        },
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=("bootstrap", "replay"), required=True)
    p.add_argument("--current-boundary", required=True)
    p.add_argument("--frozen-boundary")
    p.add_argument("--runtime-scripts", required=True)
    p.add_argument("--db-url", required=True)
    p.add_argument("--db-branch", required=True)
    p.add_argument("--enablement-base", required=True)
    p.add_argument("--current-vadimkin-ref", required=True)
    p.add_argument("--current-vadimkin-blob", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()

    sys.path.insert(0, str(Path(args.runtime_scripts).resolve()))
    import multicity_canonical_postgres as mcp

    current = json.loads(Path(args.current_boundary).read_text(encoding="utf-8"))
    connection = connect(args.db_url)
    try:
        if args.mode == "replay":
            pre = snapshot(connection)
            result = mcp.persist_canonical_episodes(
                connection,
                current["episodes"],
                provenance=provenance(args, current),
                db_branch=args.db_branch,
            )
            post = snapshot(connection)
            parity = query_db_parity(connection, current["episodes"])
            assert result["status"] == "already_persisted", result
            assert result["writes"] == 0, result
            assert result["episodes_inserted"] == 0, result
            assert result["episodes_updated"] == 0, result
            assert result["checkpoint_changes"] == 0, result
            assert pre == post, "fresh-process replay changed DB state"
            assert all(parity[k] == 0 for k in (
                "missing", "extra", "boundary_mismatches", "legacy_id_mismatches",
                "city_mismatches", "state_mismatches", "canonicalization_version_mismatches"
            )), parity
            out = {
                "mode": "fresh_process_replay",
                "status": result["status"],
                "writes": result["writes"],
                "episodes_inserted": result["episodes_inserted"],
                "episodes_updated": result["episodes_updated"],
                "checkpoint_changes": result["checkpoint_changes"],
                "new_ingestion_run": result.get("run_id") is not None,
                "state_unchanged": True,
                "db_parity": parity,
            }
        else:
            if not args.frozen_boundary:
                raise SystemExit("--frozen-boundary is required in bootstrap mode")
            frozen = json.loads(Path(args.frozen_boundary).read_text(encoding="utf-8"))
            gates = validate_corpora(current, frozen)
            pre = snapshot(connection)
            verify_accepted_lviv(pre)

            classification = mcp.preflight(connection, current["episodes"])
            exact_cities = sorted({
                row["city_key"] for row in classification["exact_existing_rows"]
            })
            expected_missing = current["total_episode_count"] - 126
            assert classification["existing_db_count"] == 126, classification
            assert classification["exact_existing"] == 126, classification
            assert exact_cities == ["lviv"], exact_cities
            assert classification["missing_to_insert"] == expected_missing, classification
            for key in (
                "conflicting_legacy_id", "conflicting_exact_interval", "semantic_conflict",
                "duplicate_candidate_legacy_id", "duplicate_candidate_interval"
            ):
                assert classification[key] == 0, (key, classification[key])

            result = mcp.persist_canonical_episodes(
                connection,
                current["episodes"],
                provenance=provenance(args, current),
                db_branch=args.db_branch,
            )
            assert result["status"] == "persisted", result
            assert result["episodes_inserted"] == expected_missing, result
            assert result["episodes_existing"] == 126, result
            assert result["episodes_updated"] == 0, result
            assert result["checkpoint_changes"] == 0, result

            post = snapshot(connection)
            parity = query_db_parity(connection, current["episodes"])
            assert post["alert_episodes"] == current["total_episode_count"], post
            assert post["ingestion_checkpoints"] == 18 and post["max_checkpoint_seq"] == 18, post
            assert post["alert_episode_sources"] == 143 and post["alerts_in_ua_sources"] == 3, post
            assert post["lviv_parent_fingerprint_sha256"] == pre["lviv_parent_fingerprint_sha256"]
            assert post["source_fingerprint_sha256"] == pre["source_fingerprint_sha256"]
            assert post["checkpoint_fingerprint_sha256"] == pre["checkpoint_fingerprint_sha256"]
            assert post["alert_state_snapshots_table"] is None
            assert post["alert_threat_observations_table"] is None
            assert post["attack_events_table"] is None
            assert all(parity[k] == 0 for k in (
                "missing", "extra", "boundary_mismatches", "legacy_id_mismatches",
                "city_mismatches", "state_mismatches", "canonicalization_version_mismatches"
            )), parity

            exact_retry = mcp.persist_canonical_episodes(
                connection,
                current["episodes"],
                provenance=provenance(args, current),
                db_branch=args.db_branch,
            )
            assert exact_retry["status"] == "already_persisted", exact_retry
            assert exact_retry["writes"] == 0 and exact_retry["run_id"] is None, exact_retry
            retry_post = snapshot(connection)
            assert retry_post == post, "same-process exact replay changed DB state"

            out = {
                "mode": "bootstrap",
                **gates,
                "enablement_base_site_prod_sha": args.enablement_base,
                "pinned_vadimkin_ref": args.current_vadimkin_ref,
                "pinned_vadimkin_blob": args.current_vadimkin_blob,
                "legacy_checkpoint_frozen_baseline": {
                    "count": 18,
                    "max_seq": 18,
                    "accepted_fingerprint_md5": "2e7548caf59ce199c1c7bd1877780676",
                },
                "accepted_repaired_lviv_fingerprints_md5": {
                    "parents": "f2d4823d986afb4908b49e98125d6263",
                    "sources": "9f6c011d2dcdc962335f54a4cd595f99",
                },
                "pre_state": {k: v for k, v in pre.items() if k != "lviv_rows"},
                "preflight": {
                    "existing_db_count": classification["existing_db_count"],
                    "exact_existing": classification["exact_existing"],
                    "exact_existing_city_keys": exact_cities,
                    "missing_to_insert": classification["missing_to_insert"],
                    "semantic_conflicts": classification["semantic_conflict"],
                    "legacy_id_conflicts": classification["conflicting_legacy_id"],
                    "exact_interval_conflicts": classification["conflicting_exact_interval"],
                    "duplicate_candidate_legacy_ids": classification["duplicate_candidate_legacy_id"],
                    "duplicate_candidate_intervals": classification["duplicate_candidate_interval"],
                },
                "bootstrap": {
                    "status": result["status"],
                    "ingestion_run_id": result["run_id"],
                    "run_kind": "multicity_canonical_bootstrap",
                    "episodes_inserted": result["episodes_inserted"],
                    "episodes_existing": result["episodes_existing"],
                    "episodes_updated": result["episodes_updated"],
                    "checkpoint_changes": result["checkpoint_changes"],
                    "writes": result["writes"],
                },
                "post_state": {k: v for k, v in post.items() if k != "lviv_rows"},
                "db_parity": parity,
                "exact_replay": {
                    "status": exact_retry["status"],
                    "writes": exact_retry["writes"],
                    "episodes_inserted": exact_retry["episodes_inserted"],
                    "episodes_updated": exact_retry["episodes_updated"],
                    "checkpoint_changes": exact_retry["checkpoint_changes"],
                    "new_ingestion_run": exact_retry["run_id"] is not None,
                },
                "lviv_episode_uid_values_preserved": True,
                "lviv_parent_fingerprint_unchanged": True,
                "source_observation_rows_unchanged": True,
                "checkpoint_fingerprint_unchanged": True,
                "source_provenance_coverage": "partial",
                "differentiated_production_shadow_enabled": False,
                "attack_events_in_neon": False,
            }

        Path(args.output).write_text(
            json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
    finally:
        connection.close()


if __name__ == "__main__":
    main()
