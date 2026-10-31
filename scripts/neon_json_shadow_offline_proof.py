#!/usr/bin/env python3
"""Reproduce the six-file shadow from pinned stored evidence. No network or SQL.

The readback is original accepted evidence; its C2 wrapper and missing version
column are explicitly reconstructed contract fixtures, never physical receipts.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import math
import os
import socket
import subprocess
import tempfile
import zipfile
from collections import Counter
from datetime import datetime, time, timedelta
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from scripts import neon_json_shadow as shadow

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "research/neon_json_shadow_frontend_2026_10_31"
FIXTURES = RESEARCH / "fixtures"
FILES = {"dashboard_data.json", "site_derived.json", "alerts_combined.json",
         "historical-daily-kpi.json", "kyiv_threat_mix.json", "sevastopol_events.json"}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n")


def prepare_fixture(root):
    provenance = shadow.load(FIXTURES / "provenance.json")
    for archive, destination in (("site-inputs.zip", root / "site"),
                                 ("readback-c2-fixture.zip", root / "inputs")):
        raw = (FIXTURES / archive).read_bytes()
        shadow.require(sha(raw) == provenance["files"][archive], "BLOCKED_FIXTURE:ARCHIVE_SHA")
        with zipfile.ZipFile(FIXTURES / archive) as z:
            expected = provenance["members"][archive]
            shadow.require(set(z.namelist()) == set(expected), "BLOCKED_FIXTURE:MEMBER_SET")
            for name, want in expected.items():
                target = (destination / name).resolve()
                shadow.require(target.is_relative_to(destination.resolve()) and
                               sha(z.read(name)) == want, "BLOCKED_FIXTURE:MEMBER_SHA")
            z.extractall(destination)
    snap = shadow.load(root / "inputs/neon_readback.original.json")
    overlay = shadow.load(root / "inputs/snapshot_overlay.json")
    for row in snap["episodes"]:
        row["canonicalization_version"] = overlay["canonicalization_version"]
    snap["runs"].append(overlay["synthetic_run"])
    snap["meta"]["offline_reconstructed_fixture"] = True
    return root / "site", root / "inputs", snap, provenance


def arguments(site, inputs, snapshot, output):
    receipt = shadow.load(inputs / "receipt.json")
    return dict(site=site, receipt_path=inputs / "receipt.json", status_path=inputs / "status.json",
                payload_path=inputs / "payload.json", dashboard_path=site / "data/dashboard_data.json",
                output=output, database_url="postgresql://fixture:unused@offline.invalid/neondb?sslmode=require",
                writer_database_url="postgresql://offline.invalid/neondb",
                expected_branch=receipt["db_branch"], workflow_sha=receipt["workflow_sha"],
                input_sha=receipt["input_sha"], generated_at=snapshot["meta"]["read_at"],
                reader=lambda *args, **kwargs: snapshot)


@contextlib.contextmanager
def no_network():
    import requests
    import psycopg
    attempts = []

    def blocked(*args, **kwargs):
        attempts.append("NETWORK_OR_SQL_ATTEMPT")
        raise AssertionError("OFFLINE_NETWORK_OR_SQL_FORBIDDEN")

    with contextlib.ExitStack() as stack:
        for obj, name in ((socket.socket, "connect"), (socket.socket, "connect_ex"),
                          (socket, "create_connection"), (socket, "getaddrinfo"),
                          (requests.sessions.Session, "request"), (psycopg, "connect")):
            stack.enter_context(patch.object(obj, name, blocked))
        yield attempts


def file_hashes(root):
    return {str(p.relative_to(root)): sha(p.read_bytes())
            for p in sorted(root.rglob("*")) if p.is_file() and "__pycache__" not in p.parts}


def validate_candidate(output, snapshot, site):
    candidate = output / "candidate"
    assert {p.name for p in candidate.iterdir()} == FILES
    objs = {p.name: shadow.load(p) for p in candidate.iterdir()}
    dashboard = objs["dashboard_data.json"]
    keys = dashboard["multicity_meta"]["production_city_keys"]
    expected = {r["city_key"] for r in snapshot["episodes"]}
    assert len(keys) == len(set(keys)) == 23 and set(keys) == set(dashboard["cities"]) == expected
    derived = objs["site_derived.json"]
    assert set(derived["explorations"]["daily28_current"]["cities"]) == expected
    kpi = objs["historical-daily-kpi.json"]
    assert kpi == dashboard["historical_daily_kpi"] and set(kpi["cities"]) == expected
    assert kpi["meta"]["verified_count"] == 23
    assert kpi["meta"]["source_dashboard_generated_at"] == dashboard["meta"]["generated_at"]
    selection = shadow.load(output / "kyiv_selection.json")
    assert selection["counts"]["raw"] == 382 and selection["counts"]["display"] == 198
    assert selection["counts"]["classifications"] == 55 and selection["counts"]["source_links"] == 223
    assert selection["enrichment"]["rebinds"] == 0
    lineage = shadow.load(output / "projection_lineage.json")
    index = {r["uid"]: r for r in snapshot["episodes"]}
    parse = lambda v: datetime.fromisoformat(v.replace("Z", "+00:00"))
    counts = {k: Counter() for k in keys}
    started_seconds = {k: Counter() for k in keys}
    intervals = {k: [] for k in keys}
    kyiv_tz = ZoneInfo("Europe/Kyiv")
    for row in lineage:
        parents = [index[uid] for uid in row["physical_uids"]]
        assert parents and all(p["city_key"] == row["city_key"] for p in parents)
        assert min(parse(p["start_at"]) for p in parents) == parse(row["start_utc"])
        assert max(parse(p["end_at"]) for p in parents) == parse(row["end_utc"])
        start, end = parse(row["start_utc"]), parse(row["end_utc"])
        day = start.astimezone(kyiv_tz).date()
        counts[row["city_key"]][day] += 1
        started_seconds[row["city_key"]][day] += (end - start).total_seconds()
        intervals[row["city_key"]].append((start.timestamp(), end.timestamp()))
    elapsed_seconds = {k: Counter() for k in keys}
    for key in keys:
        merged = []
        for start, end in sorted(intervals[key]):
            if merged and start <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], end)
            else:
                merged.append([start, end])
        for start, end in merged:
            while start < end:
                day = datetime.fromtimestamp(start, kyiv_tz).date()
                next_midnight = datetime.combine(day + timedelta(days=1), time.min, kyiv_tz).timestamp()
                stop = min(end, next_midnight)
                elapsed_seconds[key][day] += stop - start
                start = stop
    original_meta = shadow.load(site / "data/dashboard_data.json")["multicity_meta"]["cities"]
    for key in keys:
        city = dashboard["cities"][key]
        assert city["meta"]["timezone"] == "Europe/Kyiv"
        for section in ("kpis", "monthly", "weekly", "daily28", "rolling30", "rolling90"):
            assert isinstance(city[section], list) and city[section]
        record = kpi["cities"][key]
        assert record["status"] == "verified" and record["checked_complete_months"] > 0
        start = datetime.fromisoformat(record["start"]).date()
        assert record["counts"] == [counts[key][start + timedelta(days=i)] for i in range(len(record["counts"]))]
        for field, independent in (("daily_started_alert_duration_seconds", started_seconds[key]),
                                   ("daily_total_alert_duration_seconds", elapsed_seconds[key])):
            assert all(math.isclose(value, independent[start + timedelta(days=i)], abs_tol=0.001)
                       for i, value in enumerate(record[field])), (key, field)
        mm = dashboard["multicity_meta"]["cities"][key]
        original = original_meta[key]
        assert (mm["source_type"], mm.get("proxy_raion")) == (original["source_type"], original.get("proxy_raion"))
    for name in shadow.AUXILIARIES:
        assert (candidate / name).read_bytes() == (site / "data" / name).read_bytes()
    verdict = shadow.load(output / "verdict.json")
    assert verdict["status"] == "PASS" and verdict["publication_allowed"] is False
    assert verdict["generation_verdict"] == "OFFLINE_GENERATION_PASS"
    assert verdict["physical_readback_verdict"] == "PHYSICAL_NEON_READBACK_NOT_RUN"
    assert verdict["physical_neon_readback_run"] is False
    assert verdict["candidate_files"] == {p.name: sha(p.read_bytes()) for p in candidate.iterdir()}
    return {"schema_city_count": 23, "historical_kpi_verified_cities": 23,
            "lineage_intervals_verified": len(lineage), "b2_raw_display": [382, 198],
            "classification_source_link_counts": [55, 223], "rebinds": 0,
            "source_types": {"exact_city": 4, "raion_proxy": 19},
            "all_interval_boundaries_from_stored_neon_parents": True,
            "independent_daily_start_counts_and_both_duration_series_match": True,
            "auxiliary_hashes_match_pinned_git_inputs": True}


def run(output):
    output = output.resolve()
    assert not output.exists()
    with tempfile.TemporaryDirectory(prefix="neon-offline-inputs-") as td:
        site, inputs, snap, provenance = prepare_fixture(Path(td))
        before = file_hashes(site)
        with no_network() as attempts:
            verdict = shadow.execute(**arguments(site, inputs, snap, output))
        checks = validate_candidate(output, snap, site)
        assert before == file_hashes(site) and attempts == []
        save(output / "offline_checks.json", {**checks, "input_files_unchanged": True,
                                              "network_or_sql_attempts": len(attempts),
                                              "fixture_provenance": provenance})
        save(output / "sha256_manifest.json", {"schema": "neon-shadow-offline-proof-v1",
                                              "files": file_hashes(output)})
    return verdict


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    print(json.dumps(run(args.output), sort_keys=True))


if __name__ == "__main__":
    main()
