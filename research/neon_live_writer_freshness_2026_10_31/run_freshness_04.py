#!/usr/bin/env python3
"""RESEARCH ONLY: one authorized fresh HTTP GET, one bounded Phase-1 poll on existing Neon child.
No production publication; no automatic retries, recaptures, or second GET.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

CHILD = "br-crimson-star-b59u7ge3"
PARENT = "br-bold-mode-b5rub8pq"
HOST = "ep-wild-dust-b5efhza1.c-7.us-east-2.aws.neon.tech"
ROLE = "c6_writer_probe"
EXPIRES = "2026-11-01T12:20:00Z"
SOURCE_KEY = "kyiv_digital_live_http_prospective"
SOURCE_VERSION = "c6-kyiv-digital-html-observation-v1"
STREAM = "proof:kyiv_digital_html"
SOURCE_URL = "https://kyiv.digital/storage/air-alert/stats.html"
ROOT = Path(__file__).resolve().parent
UTC = timezone.utc
PINNED_BLOBS = {
    "scripts/update_data.py": "cebc2b455fb08ee16e03b9e4fcdb17aa2d9d6833",
    "scripts/db_phase1_core.py": "dda23c268e08f74367f33b189a8bafc1358aadd2",
    "scripts/db_phase1_persistence.py": "ed014e61fc6186fa9daf91c763c847e7df2f0306",
}

class GateBlocked(RuntimeError):
    pass

def check(ok, code):
    if not ok:
        raise GateBlocked(code)

def utc(value):
    d = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    check(d.tzinfo is not None, "NAIVE_TIMESTAMP")
    return d.astimezone(UTC)

def iso(value):
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")

def sha(b):
    return hashlib.sha256(b).hexdigest()

def blob(b):
    return hashlib.sha1(b"blob " + str(len(b)).encode() + b"\0" + b).hexdigest()

def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")

def record_hash(record):
    return sha(json.dumps(record, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode())

def readback_connection(psycopg, url):
    from psycopg.rows import dict_row
    c = psycopg.connect(url, autocommit=True, connect_timeout=15, row_factory=dict_row)
    c.execute("SET default_transaction_read_only = on")
    check(c.execute("SHOW transaction_read_only").fetchone()["transaction_read_only"] == "on", "READBACK_NOT_READ_ONLY")
    return c

def run(args, out, verdict):
    import psycopg
    import requests
    from psycopg.rows import dict_row

    url = os.environ.get("NEON_ISOLATED_PROOF_DATABASE_URL", "")
    check(bool(url), "MISSING_PROTECTED_ENV_SECRET")
    u = urlparse(url)
    check(u.scheme in ("postgres", "postgresql"), "DATABASE_SCHEME_INVALID")
    check(u.hostname == HOST, "CHILD_HOSTNAME_MISMATCH")
    check(unquote(u.username or "") == ROLE and u.path == "/neondb" and bool(u.password), "CHILD_ROLE_DATABASE_MISMATCH")
    q = parse_qs(u.query)
    check(set(q) <= {"sslmode", "channel_binding", "connect_timeout", "application_name"}, "CONNECTION_PARAMS_UNEXPECTED")
    check(q.get("sslmode", [""])[0] in ("require", "verify-ca", "verify-full"), "SSL_REQUIRED")
    check(datetime.now(UTC) < utc(EXPIRES), "CHILD_EXPIRED")

    for path, expected in PINNED_BLOBS.items():
        check(blob((args.site / path).read_bytes()) == expected, "PINNED_SITE_CODE_CHANGED")
    scope = json.loads((ROOT / "proof/physical_03/role_scope.json").read_text())
    check(scope["role_scope"] == "new_child_only" and len(scope["branches"]) == 10, "ROLE_SCOPE_NOT_ATTESTED")
    check(all(b["probe_role_present"] == (b["branch_id"] == CHILD) for b in scope["branches"]), "ROLE_EXISTS_OUTSIDE_CHILD")
    # The same isolated branch was also independently checked through Neon before this run.
    sys.path.insert(0, str((args.site / "scripts").resolve()))
    from update_data import parse_live_history
    from db_phase1_core import legacy_episode_id, CANONICALIZATION_VERSION
    from db_phase1_persistence import persist_phase1_payload

    with readback_connection(psycopg, url) as cn:
        ident = cn.execute("SELECT current_user AS role, current_database() AS database").fetchone()
        check(ident["role"] == ROLE and ident["database"] == "neondb", "DATABASE_IDENTITY_MISMATCH")
        before = cn.execute(
            "SELECT checkpoint_id::text AS checkpoint_id, checkpoint_seq, checked_at, metadata "
            "FROM public.current_ingestion_checkpoints "
            "WHERE source_key=%s AND city_key='kyiv' AND stream_key=%s",
            (SOURCE_KEY, STREAM),
        ).fetchall()
        check(len(before) == 1 and int(before[0]["checkpoint_seq"]) == 1, "EXPECTED_SINGLE_BOOTSTRAP_NOT_PRESENT")
        previous = before[0]
        check(previous["metadata"]["source_record_key"] == "5fcbb24d76a7ec946154c2ea5e55cbea953357f795e65ee67f3899cdbab89f68", "PREVIOUS_SOURCE_IDENTITY_CHANGED")
        check(utc(previous["checked_at"]) == utc("2026-10-30T22:56:24.503909Z"), "PREVIOUS_CAPTURE_CHANGED")

    # Exactly one externally authorized GET. No client retry and no redirect.
    verdict["http_attempts"] = 1
    verdict["stage"] = "single_authorized_http_get"
    ses = requests.Session()
    ses.mount("https://", requests.adapters.HTTPAdapter(max_retries=0))
    try:
        with ses.get(SOURCE_URL, headers={
            "Accept": "text/html",
            "Accept-Encoding": "identity",
            "Cache-Control": "no-cache",
            "User-Agent": "kyiv-air-alerts-grafana/research-one-freshness-capture",
        }, timeout=(10, 30), allow_redirects=False, stream=True) as response:
            response_status = response.status_code
            headers = dict(response.headers)
            body = response.raw.read(8 * 1024 * 1024 + 1, decode_content=True)
            captured_at = datetime.now(UTC)
    finally:
        ses.close()

    http = {"method": "GET", "url": SOURCE_URL, "status": response_status,
            "captured_at_utc": iso(captured_at), "entity_bytes": len(body),
            "raw_sha256": sha(body), "content_type": headers.get("Content-Type"),
            "last_modified": headers.get("Last-Modified"),
            "cache_control": headers.get("Cache-Control"),
            "server_date": headers.get("Date"),
            "body_cache_currency_not_proven": True}
    save(out / "http_capture.json", http)
    (out / "kyiv_digital_http_entity.bin").write_bytes(body)
    verdict["stage"] = "http_parse_and_canonicalize"
    check(response_status == 200 and "html" in str(headers.get("Content-Type", "")).lower(), "SOURCE_HTTP_NOT_200_HTML")
    check(0 < len(body) <= 8 * 1024 * 1024, "HTTP_BODY_SIZE_INVALID")
    alerts, _ = parse_live_history(body.decode("utf-8", errors="strict"))
    valid = sorted(
        (a for a in alerts if a.start.tzinfo and a.end.tzinfo and a.start < a.end <= captured_at),
        key=lambda a: (a.start, a.end),
    )
    check(bool(valid), "NO_COMPLETED_SOURCE_EPISODE")
    event = valid[-1]
    record = {"version": SOURCE_VERSION, "source_key": SOURCE_KEY, "city_key": "kyiv",
              "alert_type": "AIR", "source_native_id": None,
              "source_start_at": iso(event.start), "source_end_at": iso(event.end)}
    identity = record_hash(record)
    legacy_id = legacy_episode_id("kyiv", event.start, event.end)
    candidate = {"source_key": SOURCE_KEY, "source_version": SOURCE_VERSION,
                 "canonical_record": record, "source_record_key": identity,
                 "legacy_episode_id": legacy_id,
                 "start_at_utc": iso(event.start), "end_at_utc": iso(event.end),
                 "captured_at_utc": iso(captured_at), "raw_sha256": sha(body),
                 "parsed_completed_count": len(valid),
                 "identity_status": "PROSPECTIVE_NOT_APPROVED_FOR_PRODUCTION"}
    save(out / "canonical_candidate.json", candidate)
    check(captured_at > utc(previous["checked_at"]), "SOURCE_TIME_NOT_NEW")
    check(datetime.now(UTC) - captured_at < __import__("datetime").timedelta(hours=6), "SOURCE_ALREADY_STALE")

    # Phase-1 poll checkpoint: transaction derives checkpoint_seq=2 and previous_checkpoint_id.
    # A single HTML response is NOT sufficient to certify continuation or complete history.
    checkpoint = {
        "source_key": SOURCE_KEY, "city_key": "kyiv", "stream_key": STREAM,
        "checkpoint_kind": "poll", "checked_at": captured_at,
        "continuity_verified": False,
        "continuity_method": "single_html_response_no_continuity_claim",
        "continuity_anchor_at": None,
        "observed_oldest_start_at": event.start, "observed_latest_end_at": event.end,
        "observed_record_count": 1, "cursor": None,
        "metadata": {"scope": "bounded_single_response_poll_not_history_continuation",
                     "new_http_sha256": sha(body), "source_record_key": identity,
                     "prior_checkpoint_id": previous["checkpoint_id"],
                     "publication_allowed": False},
    }
    episodes = [{"legacy_episode_id": legacy_id, "city_key": "kyiv", "alert_type": "AIR",
                 "start_at": event.start, "end_at": event.end, "episode_state": "closed",
                 "canonicalization_version": CANONICALIZATION_VERSION}]
    observations = [{
        "episode_legacy_id": legacy_id, "source_key": SOURCE_KEY,
        "source_record_key_version": SOURCE_VERSION, "source_record_key": identity,
        "source_native_id": None, "city_key": "kyiv", "alert_type": "AIR",
        "source_start_at": event.start, "source_end_at": event.end,
        "source_retrieved_at": captured_at,
        "binding_state": "bound", "canonicalization_role": "canonical_input",
        "contributes_start_boundary": True, "contributes_end_boundary": True,
        "raw_sha256": sha(body),
        "provenance": {"scope": "research_single_fresh_poll",
                       "not_certified_for_live_production": True,
                       "not_certified_for_stream_continuity": True},
    }]
    provenance = {
        "run_kind": "shadow_poll", "schema_version": "001_phase1_core",
        "canonicalization_version": CANONICALIZATION_VERSION,
        "workflow_repository": "olegbalakin-cmyk/kyiv-air-alerts-grafana",
        "workflow_name": "C6 one authorized fresh HTTP poll",
        "workflow_ref": "research-neon-live-writer-freshness-2026-10-31",
        "workflow_sha": os.environ.get("GITHUB_SHA"),
        "input_repository": "olegbalakin-cmyk/kyiv-air-alerts-grafana",
        "input_ref": "site-prod",
        "input_sha": "c6636e838cc5ca1da3f250091bb1c5c0ff08229e",
        "parameters": {"scope": "isolated_research_one_poll", "continuity_verified": False,
                       "source_contract": "PROSPECTIVE_NOT_APPROVED_FOR_PRODUCTION"},
    }

    verdict["stage"] = "original_phase1_poll_write"
    # Original Phase-1 canonical writer: one transactional poll on the existing child only.
    with psycopg.connect(url, row_factory=dict_row, connect_timeout=15) as cn:
        result = persist_phase1_payload(
            cn, source_key=SOURCE_KEY, city_key="kyiv", stream_key=STREAM, db_branch=CHILD,
            run_provenance=provenance, episodes=episodes,
            source_observations=observations, checkpoint_candidate=checkpoint)
    save(out / "writer_receipt.json", result)
    check(result["stats"]["checkpoints_inserted"] == 1 and not result["stats"]["exact_retry"],
          "POLL_CHECKPOINT_NOT_INSERTED")

    verdict["stage"] = "independent_child_readonly_readback"
    with readback_connection(psycopg, url) as cn:
        ck = cn.execute(
            "SELECT checkpoint_id::text, previous_checkpoint_id::text, checkpoint_kind, "
            "checkpoint_seq, checked_at, continuity_verified, metadata, created_by_run_id::text "
            "FROM public.current_ingestion_checkpoints "
            "WHERE source_key=%s AND city_key='kyiv' AND stream_key=%s",
            (SOURCE_KEY, STREAM),
        ).fetchone()
        check(ck and int(ck["checkpoint_seq"]) == 2 and ck["checkpoint_kind"] == "poll",
              "POLL_CHECKPOINT_SEQUENCE_WRONG")
        check(ck["previous_checkpoint_id"] == previous["checkpoint_id"],
              "POLL_CHECKPOINT_CHAIN_WRONG")
        check(ck["continuity_verified"] is False and utc(ck["checked_at"]) == captured_at,
              "POLL_TIME_OR_CONTINUITY_MISMATCH")
        check(ck["metadata"]["new_http_sha256"] == sha(body) and
              ck["metadata"]["source_record_key"] == identity, "CHECKPOINT_HTTP_BINDING_MISMATCH")
        check(ck["created_by_run_id"] == result["run_id"], "CHECKPOINT_RUN_MISMATCH")
        rows = cn.execute(
            "SELECT e.episode_uid::text AS episode_uuid, e.legacy_episode_id, e.start_at, e.end_at, "
            "s.source_observation_id::text AS observation_uuid, s.source_record_key, "
            "s.source_retrieved_at, s.raw_sha256, s.last_seen_by_run_id::text, s.last_seen_at, "
            "i.status, i.ingest_committed_at, i.db_branch "
            "FROM public.alert_episodes e "
            "JOIN public.alert_episode_sources s ON s.episode_uid=e.episode_uid "
            "JOIN public.ingestion_runs i ON i.run_id=s.last_seen_by_run_id "
            "WHERE e.legacy_episode_id=%s AND s.source_key=%s "
            "AND s.source_record_key_version=%s AND s.source_record_key=%s",
            (legacy_id, SOURCE_KEY, SOURCE_VERSION, identity),
        ).fetchall()
        check(len(rows) == 1, "SOURCE_OBSERVATION_NOT_UNIQUE")
        row = rows[0]
        check(row["last_seen_by_run_id"] == result["run_id"] and row["status"] == "succeeded"
              and row["db_branch"] == CHILD, "SOURCE_OBSERVATION_NOT_FROM_NEW_POLL")
        check(utc(row["start_at"]) == utc(event.start) and utc(row["end_at"]) == utc(event.end),
              "EPISODE_TIME_READBACK_CONFLICT")
        check(row["source_record_key"] == identity, "SOURCE_IDENTITY_READBACK_MISMATCH")
        if result["stats"]["source_observations_inserted"] == 1:
            check(row["raw_sha256"] == sha(body) and utc(row["source_retrieved_at"]) == captured_at,
                  "NEW_SOURCE_OBSERVATION_RAW_MISMATCH")
        # If the episode/source identity was already present, the old first-capture
        # time and raw hash are immutable; new poll freshness is instead witnessed
        # by the checkpoint and latest last_seen_by_run_id on that source identity.
        checked_at = datetime.now(UTC)
        check(cn.execute("SHOW transaction_read_only").fetchone()["transaction_read_only"] == "on",
              "INDEPENDENT_READBACK_NOT_READ_ONLY")
    save(out / "independent_readback.json", {
        "branch_id": CHILD, "readback_at_utc": iso(checked_at),
        "read_only": True, "independent_connection": True,
        "checkpoint": ck, "episode_source": row,
        "observation_reused": result["stats"]["source_observations_existing"] == 1,
        "poll_http_hash_source": "checkpoint.metadata.new_http_sha256",
    })

    verdict["stage"] = "bounded_single_episode_site_json"
    # No network calls are allowed after the one authorized HTTP capture.
    requests.sessions.Session.request = lambda *_a, **_kw: (_ for _ in ()).throw(GateBlocked("SECOND_HTTP_NOT_AUTHORIZED"))
    update = importlib.import_module("update_data")
    generated = datetime.now(UTC)
    dashboard = update.build_outputs(
        [update.Alert(row["start_at"], row["end_at"], SOURCE_KEY)],
        generated.astimezone(update.TZ),
        {"scope": "RESEARCH_ONLY_SINGLE_EPISODE_FRESH_POLL", "branch_id": CHILD,
         "source_data_as_of_utc": iso(captured_at), "publication_allowed": False,
         "continuity_verified": False})
    dashboard["physical_provenance"] = {
        "episode_uuid": row["episode_uuid"],
        "source_observation_uuid": row["observation_uuid"],
        "source_record_key": identity,
        "checkpoint_id": ck["checkpoint_id"],
        "checkpoint_seq": int(ck["checkpoint_seq"]),
        "poll_http_sha256": sha(body),
        "observation_reused": result["stats"]["source_observations_existing"] == 1,
    }
    save(out / "site/dashboard_data.json", dashboard)
    rendered_sha = sha((out / "site/dashboard_data.json").read_bytes())
    check(dashboard["physical_provenance"]["episode_uuid"] == row["episode_uuid"]
          and dashboard["meta"]["source_data_as_of_utc"] == iso(captured_at),
          "RENDER_SOURCE_LINK_MISMATCH")
    evidence = {
        "evaluated_at_utc": iso(datetime.now(UTC)),
        "source": {"http_status": response_status, "parsed": True, "completed": True,
                   "raw_sha256": sha(body), "source_record_key": identity,
                   "captured_at_utc": iso(captured_at), "event_end_utc": iso(event.end)},
        "writer": {"transaction_status": row["status"], "isolated_branch_verified": True,
                   "branch_id": CHILD, "committed_at_utc": iso(row["ingest_committed_at"]),
                   "episode_uuid": row["episode_uuid"],
                   "source_observation_uuid": row["observation_uuid"]},
        "readback": {"independent_connection": True, "transaction_read_only": True,
                     "branch_id": CHILD, "episode_uuid": row["episode_uuid"],
                     "source_observation_uuid": row["observation_uuid"],
                     "source_record_key": identity, "ingestion_status": row["status"],
                     "at_utc": iso(checked_at)},
        "output": {"branch_id": CHILD, "contains_episode_uuid": True,
                   "contains_source_provenance": True, "site_json_sha256": rendered_sha,
                   "generated_at_utc": iso(generated),
                   "source_data_as_of_utc": iso(captured_at),
                   "unverified_fallback": False},
    }
    from freshness_gate import gate
    fresh_result = gate(evidence)
    save(out / "freshness_gate_evidence.json", {
        "result": fresh_result, "source_poll_checkpoint_id": ck["checkpoint_id"],
        "continuity_verified": False, "publication_allowed": False,
        "full_23city_generator_executed": False,
        "source_last_modified": http["last_modified"],
        "source_payload_cache_freshness_not_independently_certified": True,
    })
    verdict.update(
        stage="complete", verdict="PASS_BOUNDED_FRESH_POLL_FRESHNESS_GATE",
        physical_poll="PASS_NEW_HTTP_POLL_CHECKPOINT_AND_SOURCE_READBACK",
        freshness="PASS_BOUNDED_ONE_POLL_ONLY",
        post_write_json="PASS_SINGLE_EPISODE_ONLY",
        new_episode_uuid_allocation="PASS" if result["stats"]["episodes_inserted"] else "NOT_PROVEN_EXISTING_EPISODE_REUSED",
        observation_reused=result["stats"]["source_observations_existing"] == 1,
        checkpoint_seq=2, one_http_only=True,
        source_capture_utc=iso(captured_at), source_sha256=sha(body),
        episode_uuid=row["episode_uuid"], observation_uuid=row["observation_uuid"],
        site_json_sha256=rendered_sha,
    )

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    verdict = {
        "checkpoint": "C6-LIVE-FRESHNESS-04",
        "status": "BLOCKED", "verdict": "BLOCKED",
        "http_attempts": 0, "branch_id": CHILD, "new_child_created": False,
        "production_cutover_allowed": False, "production_writer_ready": False,
        "full_23city_generator_executed": False, "publication_allowed": False,
        "C6": "PARTIAL", "C3": "PARTIAL", "GLOBAL_CUTOVER": "NO",
        "github_sha": os.getenv("GITHUB_SHA"), "github_run_id": os.getenv("GITHUB_RUN_ID"),
    }
    exit_code = 1
    try:
        run(args, out, verdict)
    except Exception as error:
        verdict["error_code"] = str(error) if type(error) is GateBlocked else type(error).__name__
        verdict["sqlstate"] = getattr(error, "sqlstate", None)
    else:
        exit_code = 0
        verdict["status"] = "PASS_BOUNDED"
    finally:
        verdict["evaluated_at_utc"] = iso(datetime.now(UTC))
        save(out / "machine_verdict.json", verdict)
        save(out / "sha256_manifest.json", {
            "schema": "c6-live-freshness-04-v1",
            "files": {str(p.relative_to(out)): sha(p.read_bytes())
                      for p in sorted(out.rglob("*")) if p.is_file() and p.name != "sha256_manifest.json"},
        })
        print(json.dumps({k: verdict.get(k) for k in
              ("checkpoint", "verdict", "status", "http_attempts", "stage",
               "physical_poll", "freshness", "post_write_json", "error_code")}, sort_keys=True))
    return exit_code

if __name__ == "__main__":
    raise SystemExit(main())
