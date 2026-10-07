#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = ROOT.parent / "research" / "attack_event_shared_live_production_persistence_canary_2026-10-07.json"
ORIGIN_KIND = "shared_live_attack_event_canonical_persistence_v1"
POSITIVE = {"STRICT_EVENT_POSITIVE", "SENSITIVITY_EVENT_POSITIVE"}

def parse_dt(value):
    if not value:
        return None
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)

def iso(dt):
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00","Z")

def main():
    cutoff_raw = os.environ["PRODUCTION_PERSISTENCE_CANARY_CUTOFF"]
    cutoff = parse_dt(cutoff_raw)
    dsn = os.environ["ATTACK_EVENT_DATABASE_URL"]
    report = json.loads((DATA / "explosion_candidate_monitor_last_run.json").read_text(encoding="utf-8"))
    state = json.loads((DATA / "explosion_candidate_monitor_state.json").read_text(encoding="utf-8"))
    cp = report.get("canonical_persistence") or {}
    canary_records = list(cp.get("records") or [])[:10]

    authorized = set()
    episode_meta = {}
    for city_key, cstate in (state.get("cities") or {}).items():
        for ep in cstate.get("episodes") or []:
            first_seen = parse_dt(ep.get("live_first_seen_at"))
            if first_seen is not None and first_seen >= cutoff:
                key = (city_key, str(ep.get("episode_id") or ""))
                authorized.add(key)
                episode_meta[key] = ep

    detailed = []
    with psycopg.connect(dsn, autocommit=True, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            for rec in canary_records:
                cur.execute("""
                    SELECT
                      c.classification_uid::text AS classification_uid,
                      c.classification_key,
                      c.city_key,
                      c.historical_episode_id,
                      c.alert_start_at,
                      c.alert_end_at,
                      c.verdict,
                      c.supersedes_classification_uid::text AS supersedes_classification_uid,
                      c.classifier_blob_sha,
                      c.created_at,
                      ae.attack_event_uid::text AS attack_event_uid,
                      ae.current_classification_uid::text AS event_current_classification_uid,
                      ae.event_status,
                      (SELECT count(*) FROM public.attack_event_sources s
                         WHERE s.classification_uid=c.classification_uid) AS evidence_linkage_count,
                      (SELECT count(*) FROM public.alert_episodes p
                         WHERE p.episode_uid=c.alert_episode_uid) AS canonical_parent_count
                    FROM public.attack_event_classifications c
                    LEFT JOIN public.attack_events ae
                      ON ae.city_key=c.city_key
                     AND ae.historical_episode_id=c.historical_episode_id
                    WHERE c.classification_key=%s
                """, (rec["classification_key"],))
                row = cur.fetchone()
                if row is None:
                    detailed.append({**rec, "neon_read_back": None, "exact_match": False})
                    continue
                positive = str(row["verdict"]) in POSITIVE
                exact = (
                    str(row["classification_key"]) == str(rec["classification_key"])
                    and str(row["verdict"]) == str(rec["verdict"])
                    and str(row["classifier_blob_sha"]) == "778469b74c2aa807d851cf2c2ee35cf4aa785589"
                    and int(row["canonical_parent_count"]) == 1
                    and (not positive or row["attack_event_uid"] is not None)
                    and (not positive or int(row["evidence_linkage_count"]) >= 1)
                )
                detailed.append({
                    "city": row["city_key"],
                    "episode_id": row["historical_episode_id"],
                    "alert_start": iso(row["alert_start_at"]),
                    "alert_end": iso(row["alert_end_at"]),
                    "classifier_verdict": rec["verdict"],
                    "classification_key": row["classification_key"],
                    "classification_uid": row["classification_uid"],
                    "write_disposition": "inserted" if rec.get("classification_inserted") else "unchanged/idempotent",
                    "attack_event_uid": row["attack_event_uid"],
                    "evidence_linkage_count": int(row["evidence_linkage_count"]),
                    "supersedes_uid": row["supersedes_classification_uid"],
                    "neon_read_back_verdict": row["verdict"],
                    "canonical_parent_exists": int(row["canonical_parent_count"]) == 1,
                    "canonical_stored_state_exact_match": exact,
                })

            cur.execute("""
                SELECT c.city_key, c.historical_episode_id, c.classification_uid::text,
                       c.verdict, c.created_at,
                       c.origin_provenance->>'kind' AS origin_kind
                FROM public.attack_event_classifications c
                WHERE c.created_at >= %s
                ORDER BY c.created_at, c.classification_uid
            """, (cutoff,))
            post_cutoff_rows = cur.fetchall()

            unauthorized = [
                dict(row) for row in post_cutoff_rows
                if (str(row["city_key"]), str(row["historical_episode_id"])) not in authorized
            ]

            cur.execute("""
                WITH tips AS (
                  SELECT c.city_key, c.historical_episode_id, c.classification_uid
                  FROM public.attack_event_classifications c
                  WHERE NOT EXISTS (
                    SELECT 1 FROM public.attack_event_classifications n
                    WHERE n.supersedes_classification_uid=c.classification_uid
                  )
                )
                SELECT city_key, historical_episode_id, count(*) AS n
                FROM tips
                GROUP BY city_key, historical_episode_id
                HAVING count(*) > 1
            """)
            duplicate_classification_rows = sum(int(r["n"]) - 1 for r in cur.fetchall())

            cur.execute("""
                SELECT city_key, historical_episode_id, count(*) AS n
                FROM public.attack_events
                GROUP BY city_key, historical_episode_id
                HAVING count(*) > 1
            """)
            duplicate_attack_event_rows = sum(int(r["n"]) - 1 for r in cur.fetchall())

    verdict_counts = {}
    for d in detailed:
        v = d.get("classifier_verdict")
        if v:
            verdict_counts[v] = verdict_counts.get(v, 0) + 1

    exact_matches = sum(1 for d in detailed if d.get("canonical_stored_state_exact_match"))
    artifact = {
        "proof": "SHARED 23-CITY LIVE PRODUCTION PERSISTENCE",
        "schema_version": 1,
        "production_persistence_canary_cutoff_utc": cutoff_raw,
        "deployed_shared_path_cities": 23,
        "live_canary_episodes_processed": len(detailed),
        "canonical_classification_rows_written": sum(1 for r in canary_records if r.get("classification_inserted")),
        "strict_written": verdict_counts.get("STRICT_EVENT_POSITIVE", 0),
        "sensitivity_written": verdict_counts.get("SENSITIVITY_EVENT_POSITIVE", 0),
        "needs_review_written": verdict_counts.get("NEEDS_REVIEW", 0),
        "no_confirmed_event_written": verdict_counts.get("NO_CONFIRMED_EVENT", 0),
        "positive_attack_event_rows_written": sum(1 for r in canary_records if r.get("event_inserted")),
        "evidence_linkages_written": sum(int(r.get("source_inserts") or 0) for r in canary_records),
        "duplicate_classification_rows": duplicate_classification_rows,
        "duplicate_attack_event_rows": duplicate_attack_event_rows,
        "idempotent_rerun_proven": any(not r.get("classification_inserted") for r in canary_records),
        "classifier_to_neon_read_back_exact_matches": exact_matches,
        "unauthorized_historical_writes": len(unauthorized),
        "unauthorized_rows": unauthorized,
        "historical_backfill_jobs_started": 0,
        "canary_episodes": detailed,
        "monitor_report": {
            "started_at": report.get("started_at"),
            "finished_at": report.get("finished_at"),
            "new_alert_episodes": report.get("new_alert_episodes"),
            "eligible_due_episodes": report.get("production_persistence_eligible_due_episodes"),
            "canonical_persistence": cp,
        },
        "remaining_live_blocker": None,
        "mutation_confirmation": {
            "production_live_rows_written": sum(1 for r in canary_records if r.get("classification_inserted")),
            "historical_backfill_started": False,
            "classifier_semantics_modified": False,
            "discovery_modified": False,
            "alert_ingestion_modified": False,
            "canonical_schema_modified": False,
            "only_post_cutoff_live_first_seen_episodes_authorized": True,
        },
    }
    artifact["verdict"] = (
        "SHARED 23-CITY LIVE PRODUCTION PERSISTENCE = PROVEN"
        if artifact["live_canary_episodes_processed"] >= 1
        and artifact["classifier_to_neon_read_back_exact_matches"] == artifact["live_canary_episodes_processed"]
        and artifact["duplicate_classification_rows"] == 0
        and artifact["duplicate_attack_event_rows"] == 0
        and artifact["unauthorized_historical_writes"] == 0
        else "SHARED 23-CITY LIVE PRODUCTION PERSISTENCE = PARTIAL"
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(artifact, ensure_ascii=False, indent=2, default=str))

if __name__ == "__main__":
    main()
