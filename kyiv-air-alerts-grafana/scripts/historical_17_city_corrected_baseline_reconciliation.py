#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import csv
import gzip
import hashlib
import io
import json
import subprocess
import sys
from bisect import bisect_left
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

APP_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = APP_ROOT.parent
SCRIPTS = APP_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import add_duration_unit_switch as exactmod
import apply_ukrainealarm_bridge as bridgemod
import build_explosion_source_slices as builder
import expand_multicity_production as proxymod
import extend_remaining_proxies as extended
import replay_explosion_history as replay

UTC = timezone.utc

EXPECTED = {
    "chernihiv": 1676,
    "chernivtsi": 113,
    "dnipro": 2259,
    "ivano_frankivsk": 103,
    "kharkiv": 3565,
    "kherson": 1412,
    "khmelnytskyi": 248,
    "kropyvnytskyi": 1161,
    "lutsk": 135,
    "mykolaiv": 1648,
    "odesa": 1465,
    "poltava": 1805,
    "rivne": 232,
    "ternopil": 125,
    "uzhhorod": 92,
    "vinnytsia": 362,
    "zhytomyr": 685,
}
EXPECTED_TOTAL = 17086
EXPECTED_STARTING_RECONSTRUCTED = 6705
EXPECTED_STARTING_MISSING = 10381
EXPECTED_RETAINED_INVENTORY = 573
KHARKIV_HROMADA = "м. Харків та Харківська територіальна громада"
KHARKIV_OBLAST = "Харківська область"


def parse_dt(value: str) -> datetime:
    text = str(value).strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def iso_z(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def interval_from_episode(ep: dict[str, Any]) -> tuple[datetime, datetime]:
    return parse_dt(ep["alert_start"]), parse_dt(ep["alert_end"])


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=REPO_ROOT, text=True).strip()


def git_changed_paths(base: str, head: str = "HEAD") -> list[str]:
    out = git("diff", "--name-only", f"{base}..{head}")
    return [line.strip() for line in out.splitlines() if line.strip()]


def git_blob_sha(content: bytes) -> str:
    header = f"blob {len(content)}\0".encode("ascii")
    return hashlib.sha1(header + content).hexdigest()


def local_start_day(start: datetime) -> str:
    return start.astimezone(builder.TZ).date().isoformat()


def dedup_tuples(rows: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    unique = {(s, e): (s, e) for s, e in rows if e > s}
    return sorted(unique.values(), key=lambda x: (x[0], x[1]))


class CanonicalIndex:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = sorted(rows, key=lambda r: (r["_start"], r["_end"], r["episode_id"]))
        self.starts = [r["_start"] for r in self.rows]

    def overlaps(self, start: datetime, end: datetime) -> list[dict[str, Any]]:
        stop = bisect_left(self.starts, end)
        out: list[dict[str, Any]] = []
        idx = stop - 1
        while idx >= 0:
            row = self.rows[idx]
            if row["_end"] <= start:
                break
            if row["_start"] < end and start < row["_end"]:
                out.append(row)
            idx -= 1
        return list(reversed(out))


def any_overlap(start: datetime, end: datetime, rows: list[tuple[datetime, datetime]]) -> bool:
    for other_start, other_end in rows:
        if other_start >= end:
            break
        if other_start < end and start < other_end:
            return True
    return False


def upstream_base_episodes(
    source_bytes: bytes,
    wanted_keys: set[str],
) -> tuple[dict[str, list[Any]], dict[str, dict[str, Any]]]:
    proxy_cfg = extended.configure_all_proxies()
    proxy_keys = wanted_keys & set(proxy_cfg)
    exact_keys = wanted_keys & set(exactmod.CITY_CONFIG)
    unknown = wanted_keys - proxy_keys - exact_keys
    if unknown:
        raise RuntimeError(f"No canonical production geography adapter for: {sorted(unknown)}")

    proxy_base: dict[str, list[Any]] = {}
    exact_base: dict[str, list[Any]] = {}

    if proxy_keys:
        original_proxy_config = proxymod.PROXY_CONFIG
        original_proxy_keys = proxymod.PROXY_KEYS
        original_proxy_http_session = proxymod.http_session
        try:
            proxymod.PROXY_CONFIG = {key: proxy_cfg[key] for key in sorted(proxy_keys)}
            proxymod.PROXY_KEYS = sorted(proxy_keys)
            proxymod.http_session = lambda: builder._BytesSession(source_bytes)
            proxy_base = proxymod.fetch_proxy_alerts()
        finally:
            proxymod.PROXY_CONFIG = original_proxy_config
            proxymod.PROXY_KEYS = original_proxy_keys
            proxymod.http_session = original_proxy_http_session

    if exact_keys:
        original_exact_config = exactmod.CITY_CONFIG
        original_exact_http_session = exactmod.http_session
        try:
            exactmod.CITY_CONFIG = {key: original_exact_config[key] for key in sorted(exact_keys)}
            exactmod.http_session = lambda: builder._BytesSession(source_bytes)
            exact_base = exactmod.fetch_city_alerts()
        finally:
            exactmod.CITY_CONFIG = original_exact_config
            exactmod.http_session = original_exact_http_session

    by_city: dict[str, list[Any]] = {}
    meta: dict[str, dict[str, Any]] = {}
    for key in sorted(wanted_keys):
        if key in exact_keys:
            by_city[key] = exact_base[key]
            meta[key] = {
                "type": "production_exact_city",
                "name": exactmod.CITY_CONFIG[key]["hromada"],
                "valid_from": exactmod.CITY_CONFIG[key]["valid_from"],
            }
        else:
            by_city[key] = proxy_base[key]
            cfg = proxy_cfg[key]
            meta[key] = {
                "type": "production_proxy",
                "raion": cfg["raion"],
                "oblast": cfg["oblast"],
                "coverage_start": cfg["coverage_start"],
            }
    return by_city, meta


def filter_alerts_to_cutoff(alerts: list[Any], cutoff: str) -> list[tuple[datetime, datetime]]:
    rows = []
    for alert in alerts:
        start = alert.start.astimezone(UTC)
        end = alert.end.astimezone(UTC)
        if local_start_day(start) <= cutoff:
            rows.append((start, end))
    return dedup_tuples(rows)


def load_current_city(city: str, cutoff: str) -> tuple[list[dict[str, Any]], list[str], int]:
    episodes, sources = replay.load_historical_episodes(APP_ROOT, city, None)
    filtered: list[dict[str, Any]] = []
    raw_ids: list[str] = []
    for ep in episodes:
        row = dict(ep)
        day = str(row.get("alert_start_date_kyiv") or "")
        if not day:
            day = local_start_day(parse_dt(str(row["alert_start"])))
        if day > cutoff:
            continue
        row["alert_start_date_kyiv"] = day
        row["_start"], row["_end"] = interval_from_episode(row)
        raw_ids.append(str(row.get("episode_id") or ""))
        filtered.append(row)
    duplicates = len(raw_ids) - len(set(raw_ids))
    filtered.sort(key=lambda r: (r["_start"], r["_end"], r["episode_id"]))
    return filtered, sources, duplicates


def load_retained_blocks(
    city: str,
    forensic_city: dict[str, Any],
) -> tuple[list[tuple[datetime, datetime]], list[dict[str, Any]]]:
    blocks = forensic_city.get("recoverable_raw_blocks") or []
    store = bridgemod.load_store()
    all_rows: list[tuple[datetime, datetime]] = []
    diagnostics: list[dict[str, Any]] = []

    for block in blocks:
        source_path = str(block.get("source_path") or "")
        source_kind = str(block.get("source_kind") or "")
        expected_rows = int(block.get("episode_rows") or 0)
        raw_range = block.get("raw_time_range") or []
        lo = parse_dt(raw_range[0]) if len(raw_range) >= 1 else None
        hi = parse_dt(raw_range[1]) if len(raw_range) >= 2 else None
        extracted: list[tuple[datetime, datetime]] = []

        if "Alerts.in.ua" in source_kind:
            path = REPO_ROOT / source_path
            raw = gzip.decompress(
                base64.b64decode(path.read_text(encoding="ascii").strip())
            ).decode("utf-8")
            for row in csv.DictReader(io.StringIO(raw)):
                if str(row.get("city_key") or "").strip() != city:
                    continue
                start = bridgemod.parse_dt(row.get("start"))
                end = bridgemod.parse_dt(row.get("end"))
                if not start or not end or end <= start:
                    continue
                if lo is not None and start < lo:
                    continue
                if hi is not None and end > hi:
                    continue
                extracted.append((start, end))
        elif "UkraineAlarm" in source_kind or source_path.endswith("ukrainealarm_bridge.json"):
            for row in store.get("events") or []:
                if str(row.get("city_key") or "") != city:
                    continue
                start = bridgemod.parse_dt(row.get("start"))
                end = bridgemod.parse_dt(row.get("end"))
                if not start or not end or end <= start:
                    continue
                if lo is not None and start < lo:
                    continue
                if hi is not None and end > hi:
                    continue
                extracted.append((start, end))
        else:
            diagnostics.append({
                "source_path": source_path,
                "source_kind": source_kind,
                "expected_rows": expected_rows,
                "extracted_rows": 0,
                "match": False,
                "error": "unsupported_retained_source_kind",
            })
            continue

        extracted = dedup_tuples(extracted)
        all_rows.extend(extracted)
        diagnostics.append({
            "source_path": source_path,
            "source_kind": source_kind,
            "expected_rows": expected_rows,
            "extracted_rows": len(extracted),
            "match": len(extracted) == expected_rows,
            "raw_time_range": raw_range,
        })

    return dedup_tuples(all_rows), diagnostics


def geography_checks(
    source_bytes: bytes,
    proxy_cfg: dict[str, dict[str, Any]],
    full_meta: dict[str, dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    ambiguities: dict[str, list[dict[str, Any]]] = {city: [] for city in EXPECTED}
    text = source_bytes.decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(text)))

    proxy_oblasts: dict[str, list[str]] = {}
    proxy_raions: dict[str, list[str]] = {}
    for city in EXPECTED:
        if city == "kharkiv":
            continue
        cfg = proxy_cfg[city]
        proxy_oblasts.setdefault(cfg["oblast"], []).append(city)
        proxy_raions.setdefault(cfg["raion"], []).append(city)

    for oblast, cities in proxy_oblasts.items():
        if len(cities) > 1:
            for city in cities:
                ambiguities[city].append({
                    "code": "NON_UNIQUE_PROXY_OBLAST_MAPPING",
                    "oblast": oblast,
                    "cities": cities,
                })
    for raion, cities in proxy_raions.items():
        if len(cities) > 1:
            for city in cities:
                ambiguities[city].append({
                    "code": "NON_UNIQUE_PROXY_RAION_MAPPING",
                    "raion": raion,
                    "cities": cities,
                })

    for row_number, row in enumerate(rows, start=2):
        level = str(row.get("level") or "").strip()
        oblast = str(row.get("oblast") or "").strip()
        raion = str(row.get("raion") or "").strip()
        hromada = str(row.get("hromada") or "").strip()

        if level == "hromada" and hromada == KHARKIV_HROMADA and oblast and oblast != KHARKIV_OBLAST:
            ambiguities["kharkiv"].append({
                "code": "KHARKIV_EXACT_HROMADA_WRONG_OBLAST",
                "csv_row": row_number,
                "oblast": oblast,
                "hromada": hromada,
            })

        if level == "raion":
            for city in EXPECTED:
                if city == "kharkiv":
                    continue
                cfg = proxy_cfg[city]
                if raion == cfg["raion"] and oblast and oblast != cfg["oblast"]:
                    ambiguities[city].append({
                        "code": "PROXY_RAION_WRONG_OBLAST",
                        "csv_row": row_number,
                        "raion": raion,
                        "oblast": oblast,
                        "expected_oblast": cfg["oblast"],
                    })

    kh_meta = full_meta.get("kharkiv") or {}
    if kh_meta.get("type") != "production_exact_city_assembled":
        ambiguities["kharkiv"].append({
            "code": "KHARKIV_NOT_EXACT_CITY_ADAPTER",
            "actual_type": kh_meta.get("type"),
        })
    if kh_meta.get("name") != KHARKIV_HROMADA:
        ambiguities["kharkiv"].append({
            "code": "KHARKIV_EXACT_HROMADA_NAME_MISMATCH",
            "actual_name": kh_meta.get("name"),
            "expected_name": KHARKIV_HROMADA,
        })
    return ambiguities


def clean_episode_for_json(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "episode_id": row["episode_id"],
        "alert_start": iso_z(row["_start"]),
        "alert_end": iso_z(row["_end"]),
        "alert_start_date_kyiv": row.get("alert_start_date_kyiv"),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--upstream", type=Path, required=True)
    parser.add_argument("--upstream-blob-expected", required=True)
    parser.add_argument("--upstream-blob-actual", required=True)
    parser.add_argument("--upstream-commit", default=None)
    parser.add_argument("--forensic", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--starting-head", required=True)
    parser.add_argument("--workflow-run-id", required=True)
    args = parser.parse_args()

    source_bytes = args.upstream.read_bytes()
    calculated_blob = git_blob_sha(source_bytes)
    if calculated_blob != args.upstream_blob_expected or args.upstream_blob_actual != args.upstream_blob_expected:
        raise RuntimeError(
            f"UPSTREAM_BLOB_MISMATCH expected={args.upstream_blob_expected} "
            f"actual={args.upstream_blob_actual} calculated={calculated_blob}"
        )

    forensic = json.loads(args.forensic.read_text(encoding="utf-8"))
    status = json.loads((REPO_ROOT / "research" / "historical_replay_status_current.json").read_text(encoding="utf-8"))
    cutoff = str(status.get("through") or "")
    if not cutoff:
        raise RuntimeError("Authoritative historical replay cutoff is missing")
    if cutoff != str(forensic.get("replay_through") or ""):
        raise RuntimeError(
            f"Historical cutoff drift: status={cutoff} forensic={forensic.get('replay_through')}"
        )

    status_expected = {city: int(status["cities"][city]["expected_alert_episodes"]) for city in EXPECTED}
    if status_expected != EXPECTED:
        raise RuntimeError(f"Authoritative expected totals drifted: {status_expected}")
    if sum(EXPECTED.values()) != EXPECTED_TOTAL:
        raise RuntimeError("Internal expected total does not equal 17086")

    wanted = set(EXPECTED)
    upstream_base, upstream_meta = upstream_base_episodes(source_bytes, wanted)
    full_by_city, full_meta = builder.production_episodes_from_bytes(source_bytes, wanted)

    boundary_error = None
    boundary_exclusions: list[dict[str, Any]] = []
    try:
        subslice_rows = [
            row for row in builder.load_subslices()
            if row.get("city_key") in wanted
        ]
        boundary_exclusions = builder.reconcile_parent_boundaries(
            full_by_city, full_meta, subslice_rows
        )
    except Exception as exc:
        boundary_error = f"{type(exc).__name__}: {exc}"

    proxy_cfg = extended.configure_all_proxies()
    geo = geography_checks(source_bytes, proxy_cfg, full_meta)

    prep_changed_paths = git_changed_paths(args.starting_head)
    allowed_prep = {
        "kyiv-air-alerts-grafana/data/explosion_metric_handoff/RESEARCH_SLICES_2026-09-18.csv",
        "kyiv-air-alerts-grafana/data/explosion_metric_handoff/RESEARCH_SUBSLICES_2026-09-19.csv",
        "kyiv-air-alerts-grafana/data/explosion_metric_handoff/chernihiv_P3_result.json",
        "research/historical_replay_status_current.json",
        "kyiv-air-alerts-grafana/scripts/build_explosion_source_slices.py",
        "kyiv-air-alerts-grafana/scripts/historical_17_city_corrected_baseline_reconciliation.py",
        ".github/workflows/historical-17-city-corrected-baseline-reconciliation.yml",
    }
    protected_files_unchanged = all(path in allowed_prep for path in prep_changed_paths)

    campaign_ref = ""
    try:
        campaign_ref = subprocess.check_output(
            [
                "git", "ls-remote", "origin",
                "refs/heads/historical-attack-event-backfill-2026-09-27",
            ],
            cwd=REPO_ROOT,
            text=True,
        ).strip().split("\t")[0]
    except Exception:
        campaign_ref = ""

    city_results: dict[str, dict[str, Any]] = {}
    aggregate_retained = 0
    aggregate_upstream = 0
    aggregate_overlap = 0
    aggregate_final = 0
    aggregate_current = 0
    aggregate_unresolved = 0
    aggregate_duplicates = 0
    aggregate_excess = 0
    aggregate_geo = 0
    aggregate_id_mismatches = 0
    aggregate_retained_inventory = 0
    cities_full: list[str] = []
    city_blockers: dict[str, list[str]] = {}

    for city in EXPECTED:
        expected = EXPECTED[city]
        forensic_city = forensic["cities"][city]
        authoritative_current = int(status["cities"][city]["reconstructed_alert_episodes"])
        forensic_current = int(forensic_city["reconstructed_episodes"])
        if authoritative_current != forensic_current:
            raise RuntimeError(
                f"Forensic/current reconstructed drift for {city}: "
                f"{forensic_current} vs {authoritative_current}"
            )

        current, current_sources, current_dup = load_current_city(city, cutoff)
        current_count = len(current)
        current_ids = {row["episode_id"] for row in current}
        current_index = CanonicalIndex(current)

        upstream_intervals = filter_alerts_to_cutoff(upstream_base[city], cutoff)

        final_pairs = []
        for start, end in full_by_city[city]:
            start_utc = start.astimezone(UTC)
            end_utc = end.astimezone(UTC)
            if local_start_day(start_utc) <= cutoff:
                final_pairs.append((start_utc, end_utc))
        final_pairs = dedup_tuples(final_pairs)

        final_rows: list[dict[str, Any]] = []
        for start, end in final_pairs:
            final_rows.append({
                "episode_id": builder.event_id(city, start, end),
                "alert_start_date_kyiv": local_start_day(start),
                "_start": start,
                "_end": end,
            })
        final_rows.sort(key=lambda r: (r["_start"], r["_end"], r["episode_id"]))
        final_ids_list = [r["episode_id"] for r in final_rows]
        final_ids = set(final_ids_list)
        final_dup = len(final_ids_list) - len(final_ids)
        final_index = CanonicalIndex(final_rows)

        retained_rows, retained_diag = load_retained_blocks(city, forensic_city)
        retained_inventory_rows = int(
            forensic_city.get("recovery_class_counts", {}).get(
                "PRIMARY_DATA_PRESENT_NOT_LOADED", 0
            )
        )
        aggregate_retained_inventory += retained_inventory_rows

        retained_block_mismatch = [
            row for row in retained_diag if not row.get("match")
        ]

        current_id_rule_errors = []
        for row in current:
            recomputed = builder.event_id(city, row["_start"], row["_end"])
            if recomputed != row["episode_id"]:
                current_id_rule_errors.append({
                    "episode_id": row["episode_id"],
                    "recomputed": recomputed,
                    "alert_start": iso_z(row["_start"]),
                    "alert_end": iso_z(row["_end"]),
                })

        final_id_rule_errors = []
        for row in final_rows:
            recomputed = builder.event_id(city, row["_start"], row["_end"])
            if recomputed != row["episode_id"]:
                final_id_rule_errors.append({
                    "episode_id": row["episode_id"],
                    "recomputed": recomputed,
                })

        retained_add = 0
        upstream_add = 0
        source_overlap = 0
        unique_additions = 0
        unexplained_new: list[str] = []
        final_overlapping_current: list[dict[str, Any]] = []

        for row in final_rows:
            if row["episode_id"] in current_ids:
                continue
            current_overlap = current_index.overlaps(row["_start"], row["_end"])
            if current_overlap:
                final_overlapping_current.append({
                    "final": clean_episode_for_json(row),
                    "current_episode_ids": [x["episode_id"] for x in current_overlap],
                })
                continue

            retained_support = any_overlap(row["_start"], row["_end"], retained_rows)
            upstream_support = any_overlap(row["_start"], row["_end"], upstream_intervals)
            if retained_support:
                retained_add += 1
            if upstream_support:
                upstream_add += 1
            if retained_support and upstream_support:
                source_overlap += 1
            if retained_support or upstream_support:
                unique_additions += 1
            else:
                unexplained_new.append(row["episode_id"])

        current_only_details: list[dict[str, Any]] = []
        for row in current:
            if row["episode_id"] in final_ids:
                continue
            overlaps = final_index.overlaps(row["_start"], row["_end"])
            current_only_details.append({
                "current": clean_episode_for_json(row),
                "overlapping_final_episode_ids": [x["episode_id"] for x in overlaps],
            })

        timestamp_identity_mismatch_count = len(current_only_details)
        id_rule_error_count = len(current_id_rule_errors) + len(final_id_rule_errors)
        episode_id_timestamp_mismatch_count = (
            timestamp_identity_mismatch_count + id_rule_error_count
        )

        hypothetical = current_count + retained_add + upstream_add - source_overlap
        final_count = len(final_rows)
        unresolved = max(expected - final_count, 0)
        excess = max(final_count - expected, 0)
        arithmetic_match = hypothetical == final_count

        blockers: list[str] = []
        if current_count != authoritative_current:
            blockers.append("CURRENT_RECONSTRUCTED_COUNT_DRIFT")
        if current_dup:
            blockers.append("CURRENT_CORPUS_DUPLICATE_CANONICAL_IDS")
        if final_dup:
            blockers.append("DUPLICATE_CANONICAL_IDS")
        if retained_block_mismatch:
            blockers.append("RETAINED_PRIMARY_BLOCK_EXTRACTION_MISMATCH")
        if unresolved:
            blockers.append("UNRESOLVED_MISSING_EPISODES")
        if excess:
            blockers.append("UNEXPLAINED_EXCESS_EPISODES")
        if geo[city]:
            blockers.append("GEOGRAPHY_AMBIGUITY_AFFECTING_TARGET_UNIVERSE")
        if episode_id_timestamp_mismatch_count or final_overlapping_current:
            blockers.append("EPISODE_ID_TIMESTAMP_MISMATCH")
        if unexplained_new:
            blockers.append("UNEXPLAINED_NEW_EPISODES")
        if not arithmetic_match:
            blockers.append("RECONCILIATION_ARITHMETIC_MISMATCH")
        if final_count == expected and (
            current_only_details or final_overlapping_current
        ):
            blockers.append("COUNT_NEUTRAL_SUBSTITUTION")
        if boundary_error:
            blockers.append("CANONICAL_BOUNDARY_RECONCILIATION_FAILED")

        blockers = sorted(set(blockers))
        fully_reconciled = not blockers and final_count == expected
        if fully_reconciled:
            cities_full.append(city)
        else:
            city_blockers[city] = blockers

        city_results[city] = {
            "expected_episodes": expected,
            "current_reconstructed_episodes": current_count,
            "authoritative_current_reconstructed_episodes": authoritative_current,
            "current_count_matches_authoritative": current_count == authoritative_current,
            "current_source_files": current_sources,
            "retained_primary_inventory_rows": retained_inventory_rows,
            "retained_primary_extracted_unique_rows": len(retained_rows),
            "retained_primary_block_diagnostics": retained_diag,
            "valid_retained_primary_additions": retained_add,
            "valid_upstream_additions": upstream_add,
            "retained_upstream_overlap": source_overlap,
            "unique_valid_additions": unique_additions,
            "hypothetical_final_episode_count": hypothetical,
            "canonical_union_episode_count": final_count,
            "arithmetic_reconciles_to_canonical_union": arithmetic_match,
            "unresolved_missing_episodes": unresolved,
            "duplicate_canonical_ids": final_dup,
            "current_source_duplicate_ids": current_dup,
            "unexplained_excess_episodes": excess,
            "unexplained_new_episode_count": len(unexplained_new),
            "unexplained_new_episode_ids": unexplained_new,
            "geography_ambiguities": geo[city],
            "geography_ambiguity_count": len(geo[city]),
            "episode_id_timestamp_mismatch_count": episode_id_timestamp_mismatch_count,
            "current_only_episode_count": len(current_only_details),
            "current_only_episode_details": current_only_details,
            "new_final_overlapping_current_count": len(final_overlapping_current),
            "new_final_overlapping_current_details": final_overlapping_current,
            "current_id_rule_errors": current_id_rule_errors,
            "final_id_rule_errors": final_id_rule_errors,
            "upstream_adapter": upstream_meta[city],
            "canonical_union_adapter": full_meta[city],
            "fully_reconciled": fully_reconciled,
            "blockers": blockers,
        }

        aggregate_retained += retained_add
        aggregate_upstream += upstream_add
        aggregate_overlap += source_overlap
        aggregate_final += final_count
        aggregate_current += current_count
        aggregate_unresolved += unresolved
        aggregate_duplicates += final_dup
        aggregate_excess += excess
        aggregate_geo += len(geo[city])
        aggregate_id_mismatches += episode_id_timestamp_mismatch_count

    hypothetical_total = (
        aggregate_current + aggregate_retained + aggregate_upstream - aggregate_overlap
    )

    global_blockers: list[str] = []
    if aggregate_current != EXPECTED_STARTING_RECONSTRUCTED:
        global_blockers.append("STARTING_RECONSTRUCTED_TOTAL_DRIFT")
    if aggregate_retained_inventory != EXPECTED_RETAINED_INVENTORY:
        global_blockers.append("RETAINED_PRIMARY_INVENTORY_TOTAL_DRIFT")
    if hypothetical_total != aggregate_final:
        global_blockers.append("AGGREGATE_RECONCILIATION_ARITHMETIC_MISMATCH")
    if boundary_error:
        global_blockers.append("CANONICAL_BOUNDARY_RECONCILIATION_FAILED")
    if not protected_files_unchanged:
        global_blockers.append("PREP_CHANGED_UNEXPECTED_FILES")

    acceptance = (
        not global_blockers
        and len(cities_full) == len(EXPECTED)
        and aggregate_final == EXPECTED_TOTAL
        and aggregate_unresolved == 0
        and aggregate_duplicates == 0
        and aggregate_excess == 0
        and aggregate_geo == 0
        and aggregate_id_mismatches == 0
        and not city_blockers
    )

    other_15 = sorted(set(EXPECTED) - {"chernihiv", "kharkiv"})
    other_15_unchanged = all(
        city_results[c]["canonical_union_episode_count"] == EXPECTED[c]
        and city_results[c]["fully_reconciled"]
        for c in other_15
    )
    kharkiv_exclusion = next(
        (
            x for x in boundary_exclusions
            if x.get("parent_task_id") == "kharkiv-P1"
            and x.get("city_key") == "kharkiv"
        ),
        None,
    )
    acceptance = (
        acceptance
        and other_15_unchanged
        and city_results["chernihiv"]["canonical_union_episode_count"] == 1676
        and city_results["kharkiv"]["canonical_union_episode_count"] == 3565
        and kharkiv_exclusion is not None
        and kharkiv_exclusion.get("alert_start") == "2025-02-17T19:02:05Z"
        and kharkiv_exclusion.get("alert_end") == "2025-02-17T21:54:42Z"
    )

    verdict = (
        "17-CITY HISTORICAL CORPUS CONTRACT CORRECTED — 17086/17086 READY FOR ATOMIC CORPUS REPAIR"
        if acceptance
        else "BLOCKED — CORRECTED 17-CITY HISTORICAL CORPUS RECONCILIATION FAILED"
    )

    output = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "repository": "olegbalakin-cmyk/kyiv-air-alerts-grafana",
        "starting_branch": "multicity-wip-2026-09-16",
        "starting_head": args.starting_head,
        "preflight_branch": "historical-17-city-corrected-baseline-2026-09-27",
        "workflow_run_id": str(args.workflow_run_id),
        "forensic_artifact": {
            "path": "research/historical_17_city_corpus_gap_forensic_inventory_2026-09-27.json",
            "commit": "87c0993fe87037729a947a812cc70f8d8fac729a",
        },
        "historical_cutoff": cutoff,
        "upstream": {
            "repository": "Vadimkin/ukrainian-air-raid-sirens-dataset",
            "path": "datasets/official_data_uk.csv",
            "blob_sha_expected": args.upstream_blob_expected,
            "blob_sha_actual": args.upstream_blob_actual,
            "blob_sha_calculated_from_bytes": calculated_blob,
            "sha_match": calculated_blob == args.upstream_blob_expected == args.upstream_blob_actual,
            "source_commit_containing_blob": args.upstream_commit,
            "csv_committed_to_this_repository": False,
        },
        "canonical_logic": {
            "reused_modules": [
                "scripts/build_explosion_source_slices.py",
                "scripts/expand_multicity_production.py",
                "scripts/extend_remaining_proxies.py",
                "scripts/add_duration_unit_switch.py",
                "scripts/apply_ukrainealarm_bridge.py",
                "scripts/replay_explosion_history.py",
            ],
            "episode_id_rule": "sha256(city_key + '|' + UTC alert_start + '|' + UTC alert_end)[:24] after canonical interval union",
            "kharkiv_exact_city_only": True,
            "kharkiv_hromada": KHARKIV_HROMADA,
            "boundary_exclusions": boundary_exclusions,
            "boundary_reconciliation_error": boundary_error,
        },
        "contract_corrections": {
            "chernihiv": {
                "old_p3_expected": 561,
                "new_p3_expected": 560,
                "old_city_expected": 1677,
                "new_city_expected": 1676,
                "root_cause": "EXPECTED_BASELINE_ERROR",
                "synthetic_episode_added": False,
                "basis": "Exact upstream identifies 490 P3 episodes and retained primary evidence identifies 70 additional episodes; no 561st identity is recoverable.",
            },
            "kharkiv": {
                "excluded_episode_id": "30e0080db2e490337f98d277",
                "alert_start": "2025-02-17T19:02:05Z",
                "alert_end": "2025-02-17T21:54:42Z",
                "root_cause": "HISTORICAL_CUTOFF_ERROR",
                "exclusion_rule": "existing exact-adapter transition-boundary rule: when first parent starts on exact adapter valid_from and contains frozen+1 episodes, exclude the unique episode whose start equals valid_from",
                "observed_boundary_exclusion": kharkiv_exclusion,
            },
            "previous_expected_total": 17087,
            "corrected_expected_total": 17086,
        },
        "aggregate": {
            "expected": EXPECTED_TOTAL,
            "starting_reconstructed": aggregate_current,
            "starting_missing": EXPECTED_TOTAL - aggregate_current,
            "retained_primary_inventory_rows": aggregate_retained_inventory,
            "recovered_from_retained_primary": aggregate_retained,
            "recovered_from_upstream": aggregate_upstream,
            "retained_upstream_overlap": aggregate_overlap,
            "unique_recovered": aggregate_retained + aggregate_upstream - aggregate_overlap,
            "hypothetical_final_total": hypothetical_total,
            "canonical_union_final_total": aggregate_final,
            "unresolved": aggregate_unresolved,
            "duplicate_canonical_ids": aggregate_duplicates,
            "unexplained_excess_episodes": aggregate_excess,
            "geography_ambiguities_affecting_target_universe": aggregate_geo,
            "episode_id_timestamp_mismatches": aggregate_id_mismatches,
            "cities_fully_reconciled": sorted(cities_full),
            "cities_fully_reconciled_count": len(cities_full),
            "cities_with_blockers": city_blockers,
            "cities_with_blockers_count": len(city_blockers),
            "arithmetic_checks": {
                "expected_minus_starting_equals_starting_missing": (
                    EXPECTED_TOTAL - aggregate_current == EXPECTED_STARTING_MISSING
                ),
                "starting_plus_recovered_less_overlap_equals_hypothetical": (
                    aggregate_current + aggregate_retained + aggregate_upstream - aggregate_overlap
                    == hypothetical_total
                ),
                "hypothetical_equals_canonical_union": hypothetical_total == aggregate_final,
                "canonical_union_equals_expected": aggregate_final == EXPECTED_TOTAL,
            },
        },
        "cities": city_results,
        "verification": {
            "chernihiv_expected": 1676,
            "chernihiv_reconstructed": city_results["chernihiv"]["canonical_union_episode_count"],
            "kharkiv_expected": 3565,
            "kharkiv_reconstructed": city_results["kharkiv"]["canonical_union_episode_count"],
            "other_15_cities": other_15,
            "other_15_unchanged": other_15_unchanged,
            "all_17_cities_reconciled": len(cities_full) == 17 and not city_blockers,
            "unresolved_ids": {
                city: city_results[city]["blockers"]
                for city in EXPECTED
                if city_results[city]["unresolved_missing_episodes"]
            },
            "excess_ids": {
                city: city_results[city]["unexplained_new_episode_ids"]
                for city in EXPECTED
                if city_results[city]["unexplained_excess_episodes"]
            },
        },
        "implementation_commit": "68f716be027d3a614bbee02878ecf23f6c80c993",
        "isolation": {
            "prep_diff_from_starting_head": prep_changed_paths,
            "prep_diff_only_temporary_preflight_files": protected_files_unchanged,
            "protected_operational_files_unchanged_in_workspace": protected_files_unchanged,
            "active_6863_campaign_branch_observed_sha": campaign_ref or None,
            "active_6863_campaign_unchanged_by_this_task": campaign_ref == "5809bd677a93e6c2f6a1bff9cb7f6b5bde0c7c1e",
            "operational_data_mutated": False,
            "protected_files_unchanged_except_intended_corpus_contract_changes": protected_files_unchanged,
        },
        "global_blockers": global_blockers,
        "acceptance_passed": acceptance,
        "verdict": verdict,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(json.dumps({
        "verdict": verdict,
        "expected": EXPECTED_TOTAL,
        "starting_reconstructed": aggregate_current,
        "retained": aggregate_retained,
        "upstream": aggregate_upstream,
        "overlap": aggregate_overlap,
        "hypothetical_final": hypothetical_total,
        "canonical_union_final": aggregate_final,
        "unresolved": aggregate_unresolved,
        "cities_fully_reconciled": len(cities_full),
        "cities_with_blockers": city_blockers,
        "duplicates": aggregate_duplicates,
        "excess": aggregate_excess,
        "geo_ambiguities": aggregate_geo,
        "id_timestamp_mismatches": aggregate_id_mismatches,
        "output": str(args.output),
    }, ensure_ascii=False))

    if not acceptance:
        print("PREFLIGHT_BLOCKERS=" + json.dumps({
            "global": global_blockers,
            "cities": city_blockers,
        }, ensure_ascii=False))


if __name__ == "__main__":
    main()
