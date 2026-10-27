#!/usr/bin/env python3
"""Fail-closed bound-dataset check for isolated C2 release staging.
Never queries Neon; verifies the exact committed parent rows using local PostgreSQL.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

from db_phase1_core import canonical_json
from multicity_canonical_postgres import classify_candidates


def verify(conn, payload_path, dashboard_path, receipt_path):
    payload = json.loads(Path(payload_path).read_text())
    dashboard = json.loads(Path(dashboard_path).read_text())
    receipt = json.loads(Path(receipt_path).read_text())
    keys = dashboard["multicity_meta"]["production_city_keys"]
    if len(keys) != 23 or len(set(keys)) != 23 or set(payload["cities"]) != set(keys):
        raise ValueError("23-city keys/payload mismatch")
    rows = []
    for key in keys:
        block = payload["cities"][key]
        if block["episode_count"] != len(block["episodes"]):
            raise ValueError("episode_count mismatch")
        if any(r["city_key"] != key for r in block["episodes"]):
            raise ValueError("episode city mismatch")
        rows.extend(block["episodes"])
    digest = hashlib.sha256(canonical_json({
        "canonicalization_version": payload["canonicalization_version"],
        "production_city_keys": keys, "episodes": rows,
    }).encode()).hexdigest()
    if (receipt.get("status") != "succeeded"
        or receipt.get("canonical_episode_count") != len(rows)
        or receipt.get("corpus_sha256") != digest):
        raise ValueError("canonical receipt does not match actual payload")
    with conn.cursor() as cur:
        cur.execute("""SELECT episode_uid, legacy_episode_id, city_key, alert_type,
                       start_at, end_at, episode_state, canonicalization_version
                       FROM alert_episodes""")
        cols = ("episode_uid", "legacy_episode_id", "city_key", "alert_type",
                "start_at", "end_at", "episode_state", "canonicalization_version")
        db_rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    matches = classify_candidates(rows, db_rows)
    if any(matches[k] for k in (
            "missing_to_insert", "semantic_conflict", "duplicate_candidate_legacy_id",
            "duplicate_candidate_interval")) or matches["exact_existing"] != len(rows):
        raise ValueError("committed canonical database rows diverge from payload")
    return {"status": "pass", "canonical_rows": len(rows), "corpus_sha256": digest}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--payload", required=True)
    p.add_argument("--dashboard", required=True)
    p.add_argument("--receipt", required=True)
    args = p.parse_args()
    import os
    from urllib.parse import urlparse
    dsn = os.environ["C2_TEST_DATABASE_URL"]
    uri = urlparse(dsn)
    if uri.hostname != "127.0.0.1" or uri.path != "/c2_test":
        raise SystemExit("refusing any non-isolated database")
    import psycopg
    with psycopg.connect(dsn) as conn:
        print(json.dumps(verify(conn, args.payload, args.dashboard, args.receipt)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
