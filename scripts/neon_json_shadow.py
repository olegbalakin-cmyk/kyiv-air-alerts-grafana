#!/usr/bin/env python3
"""Opt-in, non-publishing C2 -> Neon read-only canonical JSON shadow.

Only the AIR episode intervals are Neon-derived. This is NOT the accepted C6
frontend projection: B2 Kyiv selection, derived views and current status remain
separate release gates. The script deliberately never creates dashboard_data.json.
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
            verifier=None, reader=None) -> dict:
    site = site.resolve()
    output = output.resolve()
    require(not output.is_relative_to(site) and not site.is_relative_to(output), "OUTPUT_MUST_BE_ISOLATED")
    require(not output.exists(), "OUTPUT_ALREADY_EXISTS")
    output.mkdir(parents=True)
    verdict = {"status": "BLOCKED", "publication_allowed": False, "neon_writes": 0,
               "upstream_http_gets": 0, "production_file_writes": 0,
               "frontend_compatible": False, "source_current_certified": False,
               "dst_repair_certified": False, "kyiv_current_provenance_certified": False}
    try:
        receipt, keys, episodes = verified_inputs(
            site=site, receipt_path=receipt_path, status_path=status_path,
            payload_path=payload_path, dashboard_path=dashboard_path, verifier=verifier)
        reader = reader or neon_readback
        rows, snapshot = reader(database_url, [r["legacy_episode_id"] for r in episodes])
        cities = validated_neon_rows(episodes, keys, rows)
        # All validation precedes artifact creation. Never write in site/data/.
        with tempfile.TemporaryDirectory(prefix="shadow-stage-", dir=output) as tmp:
            staged = Path(tmp)
            write(staged / "neon_canonical_air.json", {
                "format": "neon-canonical-readback-23city-v1", "city_keys": keys,
                "city_count": 23, "episode_count": len(episodes), "cities": cities,
                "c2_corpus_sha256": receipt["corpus_sha256"],
                "read_only_snapshot": snapshot,
                "publication_allowed": False,
                "consumer_status": "RAW_CANONICAL_ONLY_NOT_FRONTEND_JSON",
            })
            auxiliaries = {}
            for name in AUXILIARIES:
                source = site / "data" / name
                require(source.is_file(), "MISSING_GIT_AUXILIARY")
                shutil.copyfile(source, staged / name)
                auxiliaries[name] = digest(staged / name)
            files = {p.name: digest(p) for p in sorted(staged.iterdir())}
            os.replace(staged, output / "candidate")
        verdict.update(status="PARTIAL", reason="READBACK_VERIFIED_FRONTEND_GENERATOR_NOT_WIRED",
                       neon_readback_verified=True, city_count=23, episode_count=len(episodes),
                       candidate_files=files, git_auxiliaries=auxiliaries)
    except Exception as exc:
        verdict.update(error_type=type(exc).__name__, reason=(str(exc) if isinstance(exc, ShadowBlocked)
                                                              else "RECEIPT_READBACK_OR_FILE_ERROR"),
                       candidate_files={})
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
                          database_url=os.environ.get("NEON_JSON_SHADOW_READONLY_DATABASE_URL", ""))
    except Exception:
        print("Neon JSON shadow BLOCKED; verdict is stored without credentials or candidate publication", file=sys.stderr)
        return 1
    print(json.dumps({k: verdict[k] for k in ("status", "reason", "city_count", "episode_count",
                                             "publication_allowed", "frontend_compatible")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
