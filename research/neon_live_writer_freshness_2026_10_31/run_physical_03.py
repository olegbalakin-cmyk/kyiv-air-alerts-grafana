#!/usr/bin/env python3
"""One authorized child-only physical proof; no HTTP capture or publication."""
from __future__ import annotations
import argparse
import hashlib
import importlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse, parse_qs

CHILD = "br-crimson-star-b59u7ge3"
HOST = "ep-wild-dust-b5efhza1.c-7.us-east-2.aws.neon.tech"
ROLE = "c6_writer_probe"
ROOT = Path(__file__).resolve().parent

def now():
    return datetime.now(timezone.utc)

def utc(value):
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))

def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, default=str) + "\n")

def load(path):
    return json.loads(path.read_text())

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def need(value, code):
    if not value:
        raise RuntimeError(code)

def execute(args, out, verdict):
    import psycopg
    from psycopg.rows import dict_row
    url = os.environ.get("NEON_ISOLATED_PROOF_DATABASE_URL", "")
    need(url, "MISSING_ENVIRONMENT_CHILD_SECRET")
    parsed = urlparse(url)
    need(parsed.scheme in ("postgres", "postgresql"), "INVALID_DATABASE_SCHEME")
    need(parsed.hostname in (HOST, HOST.replace(".c-7", "-pooler.c-7")), "CHILD_HOST_MISMATCH")
    need(unquote(parsed.username or "") == ROLE, "CHILD_ROLE_MISMATCH")
    need(parsed.path == "/neondb" and bool(parsed.password), "DATABASE_OR_PASSWORD_MISSING")
    query = parse_qs(parsed.query)
    need(set(query) <= {"sslmode", "channel_binding", "connect_timeout", "application_name"}, "UNAPPROVED_CONNECTION_OPTIONS")
    need(query.get("sslmode", [""])[0] in ("require", "verify-ca", "verify-full"), "TLS_REQUIRED")
    need(now() < utc("2026-11-01T12:20:00Z"), "CHILD_EXPIRED")
    scope = load(ROOT / "proof/physical_03/role_scope.json")
    need(scope["role_scope"] == "new_child_only" and len(scope["branches"]) == 10, "ROLE_SCOPE_NOT_ATTESTED")
    need(all(b["probe_role_present"] == (b["branch_id"] == CHILD) for b in scope["branches"]), "ROLE_NOT_CHILD_ONLY")
    need(0 <= (now() - utc(scope["checked_at_utc"])).total_seconds() < 21600, "CONTROL_PLANE_ATTESTATION_STALE")
    capture_path = ROOT / "proof/canonical_candidate.json"
    need(digest(capture_path) == "a318e79e3ca0dda2ebcb2e37128d447e67e7eb340235f4b1171758b79dfce4e6", "CAPTURE_BYTES_CHANGED")
    need(digest(ROOT / "proof/http_capture.json") == "1332976f194a5206eb831d15daa788a5c0a39010137d534338f70be3d048542c", "HTTP_METADATA_CHANGED")
    need(digest(ROOT / "proof/kyiv_digital_http_entity.bin") == "13298e1a0206f60a10683976ecb50163d2f7c383f60d8b8d9b4bb8c7f8cf50da", "HTTP_ENTITY_CHANGED")
    need(digest(ROOT / "isolated_writer.py") == "ad89b8dd6745472d5ac85870e43388bf2c6d4142c5de0c9edf429c3114ac5835", "ORIGINAL_WRITER_CHANGED")
    need(digest(ROOT / "freshness_gate.py") == "2ecdb77e4b70c2a3c86dde20edb7f948ceace3c32fadd7010db768ce9d419487", "ORIGINAL_GATE_CHANGED")
    builder = (args.site / "scripts/update_data.py").read_bytes()
    need(hashlib.sha1(b"blob " + str(len(builder)).encode() + b"\0" + builder).hexdigest() == "cebc2b455fb08ee16e03b9e4fcdb17aa2d9d6833", "PINNED_CONSUMER_BUILDER_CHANGED")
    source = load(capture_path)
    verdict["source_captured_at_utc"] = source["captured_at_utc"]
    tables = ["alert_episodes", "alert_episode_sources", "ingestion_runs", "ingestion_checkpoints", "current_ingestion_checkpoints"]
    with psycopg.connect(url, connect_timeout=15, autocommit=True, row_factory=dict_row) as cn:
        cn.execute("SET default_transaction_read_only=on")
        identity = cn.execute("SELECT current_user AS role, current_database() AS database, current_setting('transaction_read_only') AS read_only").fetchone()
        need(identity["role"] == ROLE and identity["database"] == "neondb" and identity["read_only"] == "on", "CONNECTED_IDENTITY_MISMATCH")
        privileges = []
        for table in tables:
            p = cn.execute("SELECT has_table_privilege(current_user,%s,'SELECT') AS can_select, has_table_privilege(current_user,%s,'INSERT') AS can_insert, has_table_privilege(current_user,%s,'UPDATE') AS can_update", ("public."+table,)*3).fetchone()
            need(p["can_select"] and (table == "current_ingestion_checkpoints" or (p["can_insert"] and p["can_update"])), "MISSING_REQUIRED_PRIVILEGE_"+table)
            privileges.append(dict(table=table, **p))
        baseline = cn.execute("SELECT count(*) AS checkpoints FROM public.ingestion_checkpoints WHERE source_key=%s AND city_key='kyiv' AND stream_key='proof:kyiv_digital_html'", (source["source_key"],)).fetchone()
        need(baseline["checkpoints"] == 0, "CHILD_PROOF_STREAM_ALREADY_EXISTS_NO_BLIND_REPLAY")
    verdict["credential_preflight"] = "PASS_CHILD_HOST_ROLE_IDENTITY_AND_REQUIRED_PRIVILEGES"
    save(out / "credential_preflight.json", {"identity": identity, "hostname_matches_independent_child_endpoint": True, "required_privileges": privileges, "role_scope": scope, "baseline": baseline, "connection_string_omitted": True})
    meta = {"id": CHILD, "parent_id": "br-bold-mode-b5rub8pq", "name": "c6-live-writer-freshness-isolated-2026-10-31-resume", "default": False, "protected": False, "current_state": "ready", "approved_connection_hostname": parsed.hostname, "connection_role_scope": "new_child_only", "expires_at": "2026-11-01T12:20:00Z"}
    save(out / "branch_attestation.json", meta)
    base = [sys.executable, str(ROOT / "isolated_writer.py"), "--site", str(args.site), "--capture", str(capture_path), "--branch-attestation", str(out / "branch_attestation.json"), "--proof-dir", str(out)]
    verdict["writer_invoked"] = True
    for phase, expected in (("first-commit-crash", 86), ("retry-readback", 0)):
        result = subprocess.run(base + ["--phase", phase], capture_output=True, timeout=180)
        # Never emit driver tracebacks, URI fragments or unsanitized subprocess logs.
        save(out / (phase+"_process.json"), {"phase": phase, "exit_code": result.returncode, "expected_exit_code": expected, "stdout_sha256": hashlib.sha256(result.stdout).hexdigest(), "stderr_sha256": hashlib.sha256(result.stderr).hexdigest(), "stderr_bytes": len(result.stderr), "logs_omitted": True})
        need(result.returncode == expected, "ORIGINAL_PROCESS_FAILED_"+phase)
    first = load(out / "first_commit_receipt.json")
    retry = load(out / "independent_readback.json")
    need(first["stats"]["checkpoints_inserted"] == 1 and retry["retry"]["stats"]["exact_retry"], "RETRY_NOT_EXACT")
    need(retry["retry"]["stats"]["episodes_inserted"] == 0 and retry["retry"]["stats"]["source_observations_inserted"] == 0 and retry["retry"]["stats"]["checkpoints_inserted"] == 0, "RETRY_INSERTED_DUPLICATE")
    with psycopg.connect(url, connect_timeout=15, autocommit=True, row_factory=dict_row) as cn:
        cn.execute("SET default_transaction_read_only=on")
        row = cn.execute("""SELECT e.episode_uid::text AS episode_uuid, e.legacy_episode_id, e.city_key, e.start_at, e.end_at,
          s.source_observation_id::text AS source_observation_uuid, s.source_record_key, s.raw_sha256,
          s.source_retrieved_at, s.source_key, s.source_record_key_version, s.provenance,
          i.run_id::text AS original_run_id, i.status AS ingestion_status, i.ingest_committed_at,
          i.db_branch, k.checked_at, k.checkpoint_seq
          FROM public.alert_episodes e JOIN public.alert_episode_sources s ON s.episode_uid=e.episode_uid
          JOIN public.ingestion_runs i ON i.run_id=s.first_persisted_by_run_id
          JOIN public.current_ingestion_checkpoints k ON k.source_key=s.source_key AND k.city_key=s.city_key
          WHERE e.legacy_episode_id=%s AND s.source_key=%s AND s.source_record_key=%s AND k.stream_key='proof:kyiv_digital_html'""", (source["legacy_episode_id"], source["source_key"], source["source_record_key"])).fetchall()
        need(len(row) == 1, "INDEPENDENT_SOURCE_READBACK_NOT_UNIQUE")
        row = row[0]
        runs = cn.execute("SELECT run_id::text,status,db_branch,stats FROM public.ingestion_runs WHERE run_id=ANY(%s::uuid[]) ORDER BY run_id", ([first["run_id"], retry["retry"]["run_id"]],)).fetchall()
        need(len(runs) == 2 and all(r["status"] == "succeeded" and r["db_branch"] == CHILD for r in runs), "DURABLE_RUN_READBACK_FAILED")
        need(cn.execute("SHOW transaction_read_only").fetchone()["transaction_read_only"] == "on", "READBACK_NOT_READ_ONLY")
    read_at = now()
    need(row["episode_uuid"] == retry["physical_ids"]["episode_uuid"] and row["source_observation_uuid"] == retry["physical_ids"]["observation_uuid"], "PHYSICAL_UUID_MISMATCH")
    need(row["source_record_key"] == source["source_record_key"] and row["raw_sha256"] == source["raw_sha256"], "SOURCE_HASH_READBACK_MISMATCH")
    need(row["source_retrieved_at"] == utc(source["captured_at_utc"]) == row["checked_at"], "SOURCE_CAPTURE_TIME_CHANGED")
    need(row["start_at"] == utc(source["start_at_utc"]) and row["end_at"] == utc(source["end_at_utc"]), "EVENT_TIME_CHANGED")
    need(row["original_run_id"] == first["run_id"] and row["checkpoint_seq"] == 1 and row["db_branch"] == CHILD, "SOURCE_RECEIPT_MISMATCH")
    save(out / "extended_independent_readback.json", {"at_utc": read_at, "independent_connection": True, "transaction_read_only": True, "row": row, "runs": runs})
    verdict["persistence"] = "PASS_PHYSICAL_COMMIT_CRASH86_RETRY_UUID_SOURCE_READBACK"
    # A bounded single-episode consumer JSON witness, never the 23-city publisher.
    # Reuse original production math; all interval/provenance inputs come from readback.
    sys.path.insert(0, str((args.site / "scripts").resolve()))
    import requests
    def no_http(*a, **kw):
        raise RuntimeError("HTTP_CAPTURE_NOT_AUTHORIZED")
    requests.sessions.Session.request = no_http
    update = importlib.import_module("update_data")
    generated = now()
    json_payload = update.build_outputs([update.Alert(row["start_at"], row["end_at"], row["source_key"])], generated.astimezone(update.TZ), {"scope": "RESEARCH_SINGLE_EPISODE_CONSUMER_WITNESS", "branch_id": CHILD, "source_data_as_of_utc": source["captured_at_utc"], "publication_allowed": False})
    json_payload["physical_provenance"] = row
    save(out / "site/dashboard_data.json", json_payload)
    rendered = load(out / "site/dashboard_data.json")
    need(rendered["physical_provenance"]["episode_uuid"] == row["episode_uuid"] and rendered["physical_provenance"]["source_observation_uuid"] == row["source_observation_uuid"], "RENDERED_IDENTITY_MISMATCH")
    need(rendered["meta"]["source_data_as_of_utc"] == source["captured_at_utc"], "RENDER_FALSE_FRESHNESS")
    need(rendered["kpis"][0]["alerts_28d"] == 1 and sum(r["alerts_started"] for r in rendered["daily28"]) == 1, "CONSUMER_JSON_WITNESS_MISSING")
    verdict["post_write_site_json"] = "PASS_BOUNDED_SINGLE_EPISODE_ORIGINAL_CONSUMER_BUILDER"
    evidence = {"evaluated_at_utc": now().isoformat(), "source": {"http_status": 200, "parsed": True, "completed": True, "raw_sha256": source["raw_sha256"], "source_record_key": source["source_record_key"], "captured_at_utc": source["captured_at_utc"], "event_end_utc": source["end_at_utc"]}, "writer": {"transaction_status": row["ingestion_status"], "isolated_branch_verified": True, "branch_id": CHILD, "committed_at_utc": row["ingest_committed_at"].isoformat(), "episode_uuid": row["episode_uuid"], "source_observation_uuid": row["source_observation_uuid"]}, "readback": {"independent_connection": True, "transaction_read_only": True, "branch_id": CHILD, "episode_uuid": row["episode_uuid"], "source_observation_uuid": row["source_observation_uuid"], "source_record_key": row["source_record_key"], "ingestion_status": row["ingestion_status"], "at_utc": read_at.isoformat()}, "output": {"branch_id": CHILD, "contains_episode_uuid": True, "contains_source_provenance": True, "site_json_sha256": digest(out / "site/dashboard_data.json"), "generated_at_utc": generated.isoformat(), "source_data_as_of_utc": source["captured_at_utc"], "unverified_fallback": False}}
    import freshness_gate
    try:
        freshness_gate.gate(evidence)
    except freshness_gate.GateClosed as error:
        need(str(error) == "STALE_SOURCE_CAPTURE", "UNEXPECTED_FRESHNESS_FAILURE")
        verdict["freshness"] = "BLOCKED_STALE_SOURCE_CAPTURE_NO_FRESH_CAPTURE_AUTHORIZED"
    else:
        raise RuntimeError("UNEXPECTED_FRESHNESS_PASS_OLD_SOURCE")
    save(out / "freshness_gate_evidence.json", {"evidence": evidence, "publication_allowed": False, "reason": "STALE_SOURCE_CAPTURE", "max_age_seconds": 21600, "source_age_seconds": (now()-utc(source["captured_at_utc"])).total_seconds()})
    verdict.update(verdict="PASS_PERSISTENCE_FRESHNESS_BLOCKED", episode_uuid=row["episode_uuid"], source_observation_uuid=row["source_observation_uuid"], source_record_key=row["source_record_key"], site_json_sha256=digest(out / "site/dashboard_data.json"))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    verdict = {"schema": "c6-live-writer-physical-03-v1", "checkpoint": "C6-LIVE-WRITER-PHYSICAL-03", "verdict": "BLOCKED", "branch_id": CHILD, "persistence": "NOT_EXECUTED", "freshness": "NOT_EXECUTED", "post_write_site_json": "NOT_EXECUTED", "writer_invoked": False, "source_timestamp_modified": False, "new_http_capture": False, "production_writer_ready": False, "production_cutover_allowed": False, "full_23city_generator_executed": False, "C6": "PARTIAL", "C3": "PARTIAL", "GLOBAL_CUTOVER": "NO", "github_sha": os.environ.get("GITHUB_SHA"), "github_run_id": os.environ.get("GITHUB_RUN_ID")}
    status = 0
    try:
        execute(args, out, verdict)
    except Exception as error:
        status = 1
        # Only predefined errors are safe to expose; never stringify DB exceptions.
        code = str(error) if type(error) is RuntimeError and str(error).replace('_','').replace('-','').isalnum() else type(error).__name__
        verdict["blocker"] = code
        verdict["sqlstate"] = getattr(error, "sqlstate", None)
    finally:
        verdict["evaluated_at_utc"] = now().isoformat()
        save(out / "machine_verdict.json", verdict)
        save(out / "sha256_manifest.json", {"schema": "c6-physical-03-artifact-manifest-v1", "files": {str(p.relative_to(out)): digest(p) for p in sorted(out.rglob('*')) if p.is_file() and p.name != "sha256_manifest.json"}})
        print(json.dumps({k:verdict.get(k) for k in ("verdict","persistence","freshness","post_write_site_json","blocker")}, sort_keys=True))
    return status

if __name__ == "__main__":
    raise SystemExit(main())
