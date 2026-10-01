#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

UTC = timezone.utc


def parse_utc(value: Any) -> datetime:
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        raise AssertionError(f"naive timestamp: {value!r}")
    return dt.astimezone(UTC)


def interval_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row["city_key"],
        row["alert_type"],
        parse_utc(row["start_at"]),
        parse_utc(row["end_at"]),
    )


def checkpoint_fingerprint(connection: Any) -> str:
    c=connection.cursor()
    try:
        c.execute("SELECT to_jsonb(t) FROM (SELECT * FROM ingestion_checkpoints ORDER BY checkpoint_id) AS t")
        rows=[r[0] for r in c.fetchall()]
    finally:
        c.close()
    serial="\n".join(json.dumps(x,sort_keys=True,separators=(",",":"),default=str) for x in rows)
    return hashlib.sha256(serial.encode()).hexdigest()


def parity(connection: Any, episodes: list[dict[str, Any]]) -> dict[str, Any]:
    c=connection.cursor()
    try:
        c.execute("""SELECT episode_uid::text, legacy_episode_id, city_key, alert_type,
                            start_at, end_at, episode_state, canonicalization_version,
                            created_by_run_id::text, updated_by_run_id::text
                     FROM alert_episodes""")
        rows=c.fetchall()
    finally:
        c.close()
    candidate={x["legacy_episode_id"]:x for x in episodes}
    db={str(x[1]):x for x in rows}
    db_intervals={(str(x[2]),str(x[3]),parse_utc(x[4]),parse_utc(x[5])):str(x[1]) for x in rows}
    missing=set(candidate)-set(db)
    extra=set(db)-set(candidate)
    boundary=[]; legacy=[]; city=[]; state=[]; version=[]
    for legacy_id,row in candidate.items():
        x=db.get(legacy_id)
        if x is None: continue
        if parse_utc(x[4])!=parse_utc(row["start_at"]) or parse_utc(x[5])!=parse_utc(row["end_at"]):
            boundary.append(legacy_id)
        if str(x[2])!=row["city_key"]: city.append(legacy_id)
        if str(x[6])!=row["episode_state"]: state.append(legacy_id)
        if str(x[7])!=row["canonicalization_version"]: version.append(legacy_id)
        other=db_intervals.get(interval_key(row))
        if other is not None and other!=legacy_id:
            legacy.append((legacy_id,other))
    return {
        "db_total":len(rows),
        "db_city_count":len(set(str(x[2]) for x in rows)),
        "missing":len(missing),"extra":len(extra),
        "boundary_mismatches":len(boundary),
        "legacy_id_mismatches":len(legacy),
        "city_mismatches":len(city),
        "state_mismatches":len(state),
        "canonicalization_version_mismatches":len(version),
    }


def main() -> None:
    p=argparse.ArgumentParser()
    p.add_argument("--boundary",required=True)
    p.add_argument("--diagnostic",required=True)
    p.add_argument("--db-url",required=True)
    p.add_argument("--expected-run-id",type=int,required=True)
    p.add_argument("--expected-checkpoint-fingerprint",required=True)
    p.add_argument("--output",required=True)
    args=p.parse_args()

    boundary=json.loads(Path(args.boundary).read_text(encoding="utf-8"))
    diagnostic=json.loads(Path(args.diagnostic).read_text(encoding="utf-8"))

    assert boundary["boundary_proven"] is True and not boundary["boundary_errors"]
    assert boundary["city_count"]==23 and boundary["open_episode_count"]==0
    assert all(v["daily28_parity"] for v in boundary["per_city"].values())
    assert diagnostic["status"]=="succeeded", diagnostic
    assert diagnostic["failure_policy"]=="fail_open", diagnostic
    assert diagnostic["production_output_mutation"] is False, diagnostic
    assert int(diagnostic["city_count"])==23, diagnostic
    assert int(diagnostic["canonical_episode_count"])==boundary["total_episode_count"], diagnostic
    assert diagnostic["corpus_sha256"]==boundary["corpus_sha256"], (diagnostic,boundary["corpus_sha256"])
    assert int(diagnostic.get("episodes_updated",0))==0, diagnostic

    import psycopg
    conn=psycopg.connect(args.db_url)
    try:
        pty=parity(conn,boundary["episodes"])
        assert all(pty[k]==0 for k in (
            "missing","extra","boundary_mismatches","legacy_id_mismatches",
            "city_mismatches","state_mismatches","canonicalization_version_mismatches"
        )), pty
        c=conn.cursor()
        try:
            c.execute("""SELECT
              (SELECT count(*) FROM ingestion_runs),
              (SELECT count(*) FROM alert_episodes),
              (SELECT count(*) FROM alert_episode_sources),
              (SELECT count(*) FROM ingestion_checkpoints),
              (SELECT max(checkpoint_seq) FROM ingestion_checkpoints),
              (SELECT count(*) FROM alert_episode_sources WHERE source_key='alerts_in_ua'),
              to_regclass('public.alert_state_snapshots')::text,
              to_regclass('public.alert_threat_observations')::text,
              to_regclass('public.attack_events')::text
            """)
            row=c.fetchone()
            db_counts={
                "ingestion_runs":int(row[0]),"alert_episodes":int(row[1]),
                "alert_episode_sources":int(row[2]),"ingestion_checkpoints":int(row[3]),
                "max_checkpoint_seq":int(row[4]),"alerts_in_ua_sources":int(row[5]),
                "alert_state_snapshots_table":row[6],
                "alert_threat_observations_table":row[7],
                "attack_events_table":row[8],
            }
            assert db_counts["alert_episodes"]==boundary["total_episode_count"], db_counts
            assert db_counts["alert_episode_sources"]==143, db_counts
            assert db_counts["ingestion_checkpoints"]==18 and db_counts["max_checkpoint_seq"]==18, db_counts
            assert db_counts["alerts_in_ua_sources"]==3, db_counts
            assert db_counts["alert_state_snapshots_table"] is None, db_counts
            assert db_counts["alert_threat_observations_table"] is None, db_counts
            assert db_counts["attack_events_table"] is None, db_counts

            persistence_run_id=diagnostic.get("run_id")
            existing_rows_updated=0
            new_rows_for_run=0
            if persistence_run_id:
                c.execute("""SELECT
                    count(*) FILTER (WHERE updated_by_run_id::text=%s AND created_by_run_id::text<>%s),
                    count(*) FILTER (WHERE created_by_run_id::text=%s AND updated_by_run_id::text=%s)
                  FROM alert_episodes""",
                  (persistence_run_id,persistence_run_id,persistence_run_id,persistence_run_id))
                a,b=c.fetchone()
                existing_rows_updated=int(a); new_rows_for_run=int(b)
                assert existing_rows_updated==0
                assert new_rows_for_run==int(diagnostic.get("episodes_inserted",0))
        finally:
            c.close()

        cp=checkpoint_fingerprint(conn)
        assert cp==args.expected_checkpoint_fingerprint,(cp,args.expected_checkpoint_fingerprint)
        out={
            "workflow_run_id":args.expected_run_id,
            "diagnostic":diagnostic,
            "published_corpus":{
                "sha256":boundary["corpus_sha256"],
                "episode_count":boundary["total_episode_count"],
                "city_count":boundary["city_count"],
                "per_city_counts":{k:v["episode_count"] for k,v in boundary["per_city"].items()},
                "production_parity":"PASS",
            },
            "db_parity":pty,
            "db_counts":db_counts,
            "checkpoint_fingerprint_sha256":cp,
            "checkpoint_fingerprint_unchanged":True,
            "existing_rows_updated_by_this_shadow_run":existing_rows_updated,
            "new_rows_created_by_this_shadow_run":new_rows_for_run,
            "previous_episode_uids_preserved":existing_rows_updated==0,
            "differentiated_writes":False,
            "attack_event_writes":False,
        }
        Path(args.output).write_text(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
        print(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True))
    finally:
        conn.close()


if __name__=="__main__":
    main()
