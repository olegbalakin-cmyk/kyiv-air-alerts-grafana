#!/usr/bin/env python3
"""Opt-in, non-publishing C2 -> Neon read-only canonical JSON shadow.

Reuses the accepted C6 frontend projection, with explicit unchanged Git
non-AIR auxiliaries, read-only C2-corpus binding and non-publishing gates.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

VERSION = "alert-canonicalization-v1"
AUXILIARIES = ("kyiv_threat_mix.json", "sevastopol_events.json")


class ShadowBlocked(ValueError):
    pass


def require(value: bool, reason: str) -> None:
    if not value:
        raise ShadowBlocked(reason)


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value) -> None:
    path.write_text(json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def utc(value) -> str:
    dt = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    require(dt.tzinfo is not None, "NAIVE_TIMESTAMP")
    return dt.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def verified_inputs(*, site: Path, receipt_path: Path, status_path: Path,
                    payload_path: Path, dashboard_path: Path, verifier=None):
    # Reuse the exact independent verifier from the checked-out site-prod code.
    if verifier is None:
        sys.path.insert(0, str(site / "scripts"))
        from verify_multicity_canonical_receipt import verify_receipt
        verifier = verify_receipt
    receipt = verifier(receipt_path)
    status = load(status_path)
    require(status.get("canonical_persistence_status") == "NEON_SUCCEEDED" and
            status.get("canonical_receipt_validated") is True and
            status.get("canonical_db_commit") == "CONFIRMED", "C2_GATE_NOT_CONFIRMED")
    for field in ("workflow_sha", "input_sha"):
        require(status.get(field) == receipt.get(field), "C2_STATUS_RECEIPT_MISMATCH")

    payload = load(payload_path)
    dashboard = load(dashboard_path)
    keys = dashboard.get("multicity_meta", {}).get("production_city_keys", [])
    require(isinstance(keys, list) and len(keys) == 23 and len(set(keys)) == 23, "CITY_BOUNDARY_NOT_23")
    require(payload.get("format") == "multicity-canonical-same-run-v1" and
            payload.get("canonicalization_version") == VERSION, "SAME_RUN_FORMAT_DRIFT")
    cities = payload.get("cities")
    require(isinstance(cities, dict) and set(cities) == set(keys), "SAME_RUN_CITY_MISMATCH")
    episodes = []
    for key in keys:
        block = cities[key]
        require(isinstance(block, dict) and isinstance(block.get("episodes"), list), "INVALID_CITY_EPISODES")
        require(type(block.get("episode_count")) is int and
                block["episode_count"] == len(block["episodes"]) and len(block["episodes"]) > 0,
                "INVALID_CITY_COUNT")
        for row in block["episodes"]:
            require(isinstance(row, dict) and row.get("city_key") == key and
                    row.get("alert_type") == "AIR" and row.get("episode_state") == "closed" and
                    row.get("canonicalization_version") == VERSION and
                    bool(row.get("legacy_episode_id")) and row.get("end_at"), "INVALID_EPISODE")
            require(utc(row["start_at"]) < utc(row["end_at"]), "INVALID_EPISODE_INTERVAL")
            episodes.append(row)
    ids = [row["legacy_episode_id"] for row in episodes]
    require(len(set(ids)) == len(ids), "DUPLICATE_PAYLOAD_ID")
    serial = {"canonicalization_version": VERSION, "production_city_keys": keys, "episodes": episodes}
    checksum = hashlib.sha256(json.dumps(serial, ensure_ascii=False, sort_keys=True,
                                         separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()
    require(checksum == receipt.get("corpus_sha256") and len(episodes) == receipt.get("canonical_episode_count") and
            receipt.get("city_count") == 23, "C2_CORPUS_BINDING_MISMATCH")
    return receipt, keys, episodes


def neon_readback(database_url: str, ids: list[str]):
    require(bool(database_url), "READ_ONLY_DATABASE_URL_MISSING")
    import psycopg
    from psycopg.rows import dict_row
    # A dedicated read-only credential is required at deployment. Transaction
    # protections also reject accidental writes even if the role is overpowered.
    with psycopg.connect(database_url, autocommit=True, row_factory=dict_row,
                         options="-c default_transaction_read_only=on") as connection:
        connection.execute("BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        try:
            meta = connection.execute("SELECT current_setting('transaction_read_only') AS read_only, "
                                      "pg_current_snapshot()::text AS snapshot").fetchone()
            require(meta["read_only"] == "on", "READ_ONLY_NOT_PROVEN")
            rows = connection.execute(
                "SELECT episode_uid::text AS episode_uid, legacy_episode_id, city_key, "
                "alert_type, episode_state, start_at, end_at, canonicalization_version "
                "FROM public.alert_episodes WHERE legacy_episode_id = ANY(%s)",
                (ids,),
            ).fetchall()
        finally:
            connection.execute("ROLLBACK")
    return rows, str(meta["snapshot"])


def validated_neon_rows(episodes: list[dict], keys: list[str], rows: list[dict]) -> dict:
    expected = {r["legacy_episode_id"]: r for r in episodes}
    require(len(rows) == len(expected), "READBACK_MISSING_OR_DUPLICATE")
    by_city = {key: [] for key in keys}
    seen = set()
    for row in rows:
        lid = row.get("legacy_episode_id")
        require(lid in expected and lid not in seen, "READBACK_ID_MISMATCH")
        seen.add(lid)
        source = expected[lid]
        require(all(row.get(k) == source.get(k) for k in
                    ("city_key", "alert_type", "episode_state", "canonicalization_version")) and
                utc(row["start_at"]) == utc(source["start_at"]) and
                utc(row["end_at"]) == utc(source["end_at"]), "READBACK_SEMANTIC_MISMATCH")
        try:
            uid = str(UUID(str(row["episode_uid"])))
        except (ValueError, TypeError, KeyError):
            raise ShadowBlocked("READBACK_UUID_INVALID") from None
        by_city[row["city_key"]].append({
            "episode_uid": uid, "legacy_episode_id": lid, "alert_type": "AIR",
            "episode_state": "closed", "start_at": utc(row["start_at"]),
            "end_at": utc(row["end_at"]),
        })
    require(all(by_city.values()) and set(seen) == set(expected), "READBACK_CITY_INCOMPLETE")
    return {key: sorted(by_city[key], key=lambda x: (x["start_at"], x["end_at"], x["episode_uid"]))
            for key in keys}



def execute(*, site: Path, receipt_path: Path, status_path: Path, payload_path: Path,
            dashboard_path: Path, output: Path, database_url: str,
            verifier=None, reader=None, workflow_sha=None, input_sha=None,
            writer_database_url=None, expected_branch=None) -> dict:
    """One branch-bound C2 Neon snapshot, then isolated six-file frontend candidate.

    The previously accepted canonical verifier remains the authority for C2.
    No candidate is ever a publication input. A failed generator retains only
    a machine-readable BLOCKED verdict and no successful candidate directory.
    """
    site = site.resolve()
    output = output.resolve()
    require(not output.is_relative_to(site) and not site.is_relative_to(output),
            "OUTPUT_MUST_BE_ISOLATED")
    require(not output.exists(), "OUTPUT_ALREADY_EXISTS")
    output.mkdir(parents=True)
    verdict = {
        "status": "BLOCKED", "publication_allowed": False,
        "neon_writes": 0, "upstream_http_gets": 0,
        "production_file_writes": 0, "frontend_compatible": False,
        "source_current_certified": False, "dst_repair_certified": False,
        "kyiv_current_provenance_certified": False,
        "candidate_files": {},
    }
    try:
        from urllib.parse import urlparse
        import importlib.util
        require(bool(workflow_sha) and bool(input_sha) and bool(expected_branch),
                "WORKFLOW_INPUT_BRANCH_BINDING_MISSING")
        require(bool(database_url) and bool(writer_database_url),
                "NEON_ENDPOINT_BRANCH_BINDING_MISSING")
        receipt, keys, episodes = verified_inputs(
            site=site, receipt_path=receipt_path, status_path=status_path,
            payload_path=payload_path, dashboard_path=dashboard_path, verifier=verifier)
        require(receipt.get("workflow_sha") == workflow_sha, "WORKFLOW_SHA_MISMATCH")
        require(receipt.get("input_sha") == input_sha, "INPUT_SHA_MISMATCH")
        require(receipt.get("db_branch") == expected_branch, "NEON_BRANCH_RECEIPT_MISMATCH")
        read_host = urlparse(database_url).hostname
        writer_host = urlparse(writer_database_url).hostname
        require(bool(read_host) and bool(writer_host) and
                read_host.lower().replace("-pooler.", ".") ==
                writer_host.lower().replace("-pooler.", "."),
                "NEON_ENDPOINT_BRANCH_MISMATCH")

        path = Path(__file__).with_name("neon_json_shadow_generator.py")
        spec = importlib.util.spec_from_file_location("neon_json_shadow_generator", path)
        require(spec is not None and spec.loader is not None,
                "BLOCKED_GENERATOR_INPUT:ADAPTER_MODULE_MISSING")
        generator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(generator)

        from types import SimpleNamespace
        args = SimpleNamespace(site=site, branch_id=expected_branch, input_sha=input_sha)
        with tempfile.TemporaryDirectory(prefix="neon-shadow-stage-", dir=output) as staging:
            work = Path(staging)
            try:
                adapter, b2, bundle = generator.prepare(args, work)
            except Exception as exc:
                raise ShadowBlocked("BLOCKED_GENERATOR_INPUT:ACCEPTED_C6_ASSETS_OR_BUILDERS") from exc
            # Reader can be injected by offline tests; no HTTP, no Neon writes.
            if reader is None:
                snap = generator.snapshot(database_url, b2, bundle,
                                          expected_host=writer_host)
            else:
                snap = reader(database_url, b2, bundle, expected_host=writer_host)

            require(snap.get("meta", {}).get("read_only") == "on" and
                    snap["meta"].get("isolation") == "repeatable read",
                    "READ_ONLY_SNAPSHOT_NOT_PROVEN")
            run_ids = {str(row["run_id"]): row for row in snap["runs"]}
            require(all(row.get("db_branch") == expected_branch for row in snap["runs"]
                        if row.get("db_branch") is not None),
                    "NEON_INGESTION_BRANCH_MISMATCH")
            # The accepted original C2 writer's success run, if present, must
            # belong to the same branch and commit in the snapshot.
            if receipt.get("run_id"):
                run = run_ids.get(str(receipt["run_id"]))
                require(run is not None and run.get("db_branch") == expected_branch and
                        run.get("status") == "succeeded",
                        "C2_RUN_NOT_IN_READONLY_SNAPSHOT")
                provenance = run.get("parameters") or {}
                require(provenance.get("corpus_sha256") == receipt["corpus_sha256"],
                        "C2_RUN_CORPUS_MISMATCH")
            rows = [
                {**row, "episode_uid": row["uid"]}
                for row in snap["episodes"]
                if row.get("legacy_episode_id") in
                {episode["legacy_episode_id"] for episode in episodes}
            ]
            validated_neon_rows(episodes, keys, rows)
            closed, active = generator.verify_snapshot(snap, adapter)
            reference = load(dashboard_path)
            require(reference["multicity_meta"]["production_city_keys"] == keys,
                    "FRONTEND_CITY_BOUNDARY_CHANGED")
            cities = generator.source_report(snap, keys, reference)
            try:
                result = generator.generate(args, work, adapter, b2, bundle,
                                            snap, closed, active, cities)
            except Exception as exc:
                raise ShadowBlocked("BLOCKED_GENERATOR_INPUT:FRONTEND_OR_PROVENANCE_CONTRACT") from exc
            names = {
                "dashboard_data.json", "site_derived.json", "alerts_combined.json",
                "historical-daily-kpi.json", "kyiv_threat_mix.json",
                "sevastopol_events.json",
            }
            candidate = work / "candidate"
            require(candidate.is_dir() and
                    {p.name for p in candidate.iterdir()} == names,
                    "BLOCKED_GENERATOR_INPUT:SIX_FILE_CONTRACT")
            hashes = {p.name: digest(p) for p in candidate.iterdir()}
            require(hashes == result.get("candidate_sha256"),
                    "FRONTEND_FILE_SHA256_MISMATCH")
            require(all(cities[k]["source_capture_verified"] is False for k in keys),
                    "UNPROVEN_SOURCE_FRESHNESS")
            shutil.copytree(candidate, output / "candidate")
            write(output / "source_gates.json", cities)
            verdict.update(status="PASS", frontend_compatible=True,
                           neon_readback_verified=True, city_count=23,
                           episode_count=len(episodes),
                           c2_corpus_sha256=receipt["corpus_sha256"],
                           neon_branch=expected_branch, read_only_snapshot=str(snap["meta"]["snapshot"]),
                           candidate_files=hashes, git_auxiliaries={
                               name: hashes[name] for name in AUXILIARIES},
                           **{"reason": "FRONTEND_SHADOW_READY_NOT_CURRENT_OR_PUBLISHABLE"})
    except Exception as exc:
        verdict.update(error_type=type(exc).__name__,
                       reason=str(exc) if isinstance(exc, ShadowBlocked) else
                       "RECEIPT_READBACK_OR_GENERATOR_ERROR", candidate_files={})
        shutil.rmtree(output / "candidate", ignore_errors=True)
        raise
    finally:
        write(output / "verdict.json", verdict)
    return verdict


def main(argv=None):
    p = argparse.ArgumentParser()
    for flag in ("site", "receipt", "status", "payload", "dashboard", "output"):
        p.add_argument("--" + flag, required=True, type=Path)
    a = p.parse_args(argv)
    try:
        verdict = execute(site=a.site, receipt_path=a.receipt, status_path=a.status,
                          payload_path=a.payload, dashboard_path=a.dashboard, output=a.output,
                          database_url=os.environ.get("NEON_JSON_SHADOW_READONLY_DATABASE_URL", ""),
                          writer_database_url=os.environ.get("MULTICITY_CANONICAL_DATABASE_URL", ""),
                          expected_branch=os.environ.get("MULTICITY_CANONICAL_DB_BRANCH"),
                          workflow_sha=os.environ.get("GITHUB_SHA"),
                          input_sha=os.environ.get("PHASE1_INPUT_SHA"))
    except Exception:
        print("Neon JSON shadow BLOCKED; verdict is stored without credentials or candidate publication", file=sys.stderr)
        return 1
    print(json.dumps({k: verdict[k] for k in ("status", "reason", "city_count", "episode_count",
                                             "publication_allowed", "frontend_compatible")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
