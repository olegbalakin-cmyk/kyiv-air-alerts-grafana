#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path

import requests

import add_duration_unit_switch as exactmod
import expand_multicity_production as proxymod
import extend_remaining_proxies as extended
import apply_ukrainealarm_bridge as bridgemod

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
HANDOFF = DATA / "explosion_metric_handoff"
SUBSLICES_CSV = HANDOFF / "RESEARCH_SUBSLICES_2026-09-19.csv"
PARENTS_CSV = HANDOFF / "RESEARCH_SLICES_2026-09-18.csv"
OUT_DIR = HANDOFF / "source_slices"
MANIFEST = HANDOFF / "SOURCE_SLICES_MANIFEST_2026-09-19.json"
SOURCE_URL = proxymod.CITY_SOURCE_URL
TZ = proxymod.TZ
UTC = timezone.utc
SUPPORTED_TASKS = {"kharkiv-P6", "sumy-P4", "zaporizhzhia-P4"}


def utc_z(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def event_id(city_key: str, start: datetime, end: datetime) -> str:
    return hashlib.sha256(
        f"{city_key}|{utc_z(start)}|{utc_z(end)}".encode("utf-8")
    ).hexdigest()[:24]


def git_blob_sha(content: bytes) -> str:
    header = f"blob {len(content)}\0".encode("ascii")
    return hashlib.sha1(header + content).hexdigest()


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_subslices() -> list[dict[str, str]]:
    return load_csv(SUBSLICES_CSV)


def merge_intervals(intervals: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    merged: list[list[datetime]] = []
    for start, end in sorted(intervals, key=lambda x: x[0]):
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        elif end > merged[-1][1]:
            merged[-1][1] = end
    return [(start, end) for start, end in merged]


class _BytesResponse:
    def __init__(self, content: bytes) -> None:
        self.content = content

    def raise_for_status(self) -> None:
        return None


class _BytesSession:
    def __init__(self, content: bytes) -> None:
        self._response = _BytesResponse(content)

    def get(self, *_args, **_kwargs) -> _BytesResponse:
        return self._response


def _assemble_production_episodes(
    proxy_cfg: dict[str, dict],
    proxy_base: dict,
    exact_base: dict,
    wanted_keys: set[str],
) -> tuple[dict[str, list[tuple[datetime, datetime]]], dict[str, dict]]:
    static, static_info = bridgemod.load_static_bridge()
    store = bridgemod.load_store()

    proxy_keys = wanted_keys & set(proxy_cfg)
    exact_keys = wanted_keys & set(exactmod.CITY_CONFIG)
    unknown = wanted_keys - proxy_keys - exact_keys
    if unknown:
        raise RuntimeError(f"No production adapter for: {sorted(unknown)}")

    episodes: dict[str, list[tuple[datetime, datetime]]] = {}
    meta: dict[str, dict] = {}
    for key in sorted(wanted_keys):
        if key in exact_keys:
            base_alerts = exact_base[key]
            cfg = exactmod.CITY_CONFIG[key]
            source_type = "production_exact_city_assembled"
            source_name = cfg["hromada"]
            source_extra = {"valid_from": cfg["valid_from"]}
        else:
            base_alerts = proxy_base[key]
            cfg = proxy_cfg[key]
            source_type = "production_proxy_assembled"
            source_name = f"{cfg['raion']} + explicit {cfg['oblast']}"
            source_extra = {"coverage_start": cfg["coverage_start"]}

        region = (store.get("regions") or {}).get(key) or {}
        continuous = bool(region.get("continuous"))
        api_alerts = bridgemod.api_store_alerts(store, key) if continuous else []
        static_alerts = static.get(key) or []
        combined = bridgemod.union_alerts(
            [*base_alerts, *static_alerts, *api_alerts],
            "historical_plus_alertsinua_plus_ukrainealarm",
        )
        episodes[key] = [(a.start, a.end) for a in combined]
        meta[key] = {
            "type": source_type,
            "name": source_name,
            **source_extra,
            "static_bridge_events": len(static_alerts),
            "ukrainealarm_bridge_events": len(api_alerts),
            "ukrainealarm_bridge_continuous": continuous,
            "static_bridge_coverage_start": static_info.get("coverage_start"),
            "static_bridge_coverage_end_exclusive": static_info.get("coverage_end_exclusive"),
        }
    return episodes, meta


def production_episodes(
    source_bytes: bytes,
    wanted_keys: set[str],
) -> tuple[dict[str, list[tuple[datetime, datetime]]], dict[str, dict]]:
    # Full-builder path: preserve the existing production fetch behavior.
    proxy_cfg = extended.configure_all_proxies()
    proxy_base = proxymod.fetch_proxy_alerts()
    exact_base = exactmod.fetch_city_alerts()
    return _assemble_production_episodes(
        proxy_cfg, proxy_base, exact_base, wanted_keys
    )


def production_episodes_from_bytes(
    source_bytes: bytes,
    wanted_keys: set[str],
) -> tuple[dict[str, list[tuple[datetime, datetime]]], dict[str, dict]]:
    # Task mode reuses the production parsers, but feeds them the already-downloaded
    # upstream bytes so no parser performs a second HTTP fetch.
    proxy_cfg = extended.configure_all_proxies()
    proxy_keys = wanted_keys & set(proxy_cfg)
    exact_keys = wanted_keys & set(exactmod.CITY_CONFIG)
    unknown = wanted_keys - proxy_keys - exact_keys
    if unknown:
        raise RuntimeError(f"No production adapter for: {sorted(unknown)}")

    proxy_base: dict = {}
    exact_base: dict = {}

    if proxy_keys:
        original_proxy_config = proxymod.PROXY_CONFIG
        original_proxy_keys = proxymod.PROXY_KEYS
        original_proxy_http_session = proxymod.http_session
        try:
            proxymod.PROXY_CONFIG = {
                key: proxy_cfg[key] for key in sorted(proxy_keys)
            }
            proxymod.PROXY_KEYS = sorted(proxy_keys)
            proxymod.http_session = lambda: _BytesSession(source_bytes)
            proxy_base = proxymod.fetch_proxy_alerts()
        finally:
            proxymod.PROXY_CONFIG = original_proxy_config
            proxymod.PROXY_KEYS = original_proxy_keys
            proxymod.http_session = original_proxy_http_session

    if exact_keys:
        original_exact_config = exactmod.CITY_CONFIG
        original_exact_http_session = exactmod.http_session
        try:
            exactmod.CITY_CONFIG = {
                key: original_exact_config[key] for key in sorted(exact_keys)
            }
            exactmod.http_session = lambda: _BytesSession(source_bytes)
            exact_base = exactmod.fetch_city_alerts()
        finally:
            exactmod.CITY_CONFIG = original_exact_config
            exactmod.http_session = original_exact_http_session

    return _assemble_production_episodes(
        proxy_cfg, proxy_base, exact_base, wanted_keys
    )


def reconcile_parent_boundaries(
    by_city: dict[str, list[tuple[datetime, datetime]]],
    source_meta: dict[str, dict],
    subslice_rows: list[dict[str, str]],
) -> list[dict]:
    parent_rows = {row["task_id"]: row for row in load_csv(PARENTS_CSV)}
    represented = sorted({row["parent_task_id"] for row in subslice_rows})
    exclusions: list[dict] = []

    for parent_id in represented:
        parent = parent_rows[parent_id]
        city_key = parent["city_key"]
        date_from = parent["episode_start_date_from"]
        date_to = parent["episode_start_date_to"]
        frozen = int(parent["frozen_denominator"])
        parent_events = [
            (start, end)
            for start, end in by_city[city_key]
            if date_from <= start.astimezone(TZ).date().isoformat() <= date_to
        ]
        if len(parent_events) == frozen:
            continue
        if len(parent_events) != frozen + 1:
            continue

        smeta = source_meta[city_key]
        boundary: datetime | None = None
        reason: str | None = None
        if smeta["type"] == "production_proxy_assembled":
            if date_from == smeta.get("coverage_start"):
                boundary = proxymod.coverage_start_dt(smeta["coverage_start"])
                reason = "exclude clipped carry-in at proxy coverage_start from alert-start denominator"
        elif smeta["type"] == "production_exact_city_assembled":
            valid_from = smeta.get("valid_from")
            if valid_from:
                candidate = datetime.fromisoformat(valid_from).astimezone(TZ)
                if date_from == candidate.date().isoformat():
                    boundary = candidate
                    reason = "exclude exact adapter transition-boundary seed to preserve frozen parent denominator"

        if boundary is None:
            continue
        matches = [
            (start, end)
            for start, end in parent_events
            if start == boundary
        ]
        if len(matches) != 1:
            continue

        target = matches[0]
        by_city[city_key] = [
            pair for pair in by_city[city_key] if pair != target
        ]
        exclusions.append(
            {
                "parent_task_id": parent_id,
                "city_key": city_key,
                "alert_start": utc_z(target[0]),
                "alert_end": utc_z(target[1]),
                "reason": reason,
                "before": frozen + 1,
                "after": frozen,
            }
        )

    # Parent denominators are the hard contract. Fail if any represented parent
    # still differs after the narrowly-defined boundary reconciliation.
    bad = []
    for parent_id in represented:
        parent = parent_rows[parent_id]
        city_key = parent["city_key"]
        date_from = parent["episode_start_date_from"]
        date_to = parent["episode_start_date_to"]
        frozen = int(parent["frozen_denominator"])
        actual = sum(
            1
            for start, _ in by_city[city_key]
            if date_from <= start.astimezone(TZ).date().isoformat() <= date_to
        )
        if actual != frozen:
            bad.append(f"{parent_id}:{actual}!={frozen}")
    if bad:
        raise RuntimeError(
            "Parent denominator mismatch after boundary reconciliation: "
            + ", ".join(bad)
        )
    return exclusions


def build_all() -> None:
    response = requests.get(
        SOURCE_URL,
        timeout=240,
        headers={"User-Agent": "kyiv-air-alerts-grafana source-slice builder"},
    )
    response.raise_for_status()
    source_bytes = response.content
    source_sha = git_blob_sha(source_bytes)

    rows = load_subslices()
    wanted_keys = {row["city_key"] for row in rows}
    by_city, source_meta = production_episodes(source_bytes, wanted_keys)
    boundary_exclusions = reconcile_parent_boundaries(by_city, source_meta, rows)

    built: list[tuple[Path, dict]] = []
    manifest_rows: list[dict] = []
    mismatches: list[dict] = []

    for row in rows:
        task_id = row["task_id"]
        city_key = row["city_key"]
        date_from = row["episode_start_date_from"]
        date_to = row["episode_start_date_to"]
        expected = int(row["frozen_denominator"])

        events = [
            (start, end)
            for start, end in by_city[city_key]
            if date_from <= start.astimezone(TZ).date().isoformat() <= date_to
        ]
        events.sort(key=lambda x: (x[0], x[1]))

        sigs = {(utc_z(start), utc_z(end)) for start, end in events}
        if len(sigs) != len(events):
            raise RuntimeError(f"Duplicate production episode signatures in {task_id}")

        actual = len(events)
        start_day_events = [
            utc_z(start)
            for start, _ in by_city[city_key]
            if start.astimezone(TZ).date().isoformat() == date_from
        ]
        start_day_count = len(start_day_events)
        smeta = source_meta[city_key]
        manifest_row = {
            "task_id": task_id,
            "parent_task_id": row["parent_task_id"],
            "city_key": city_key,
            "source_type": smeta["type"],
            "source_name": smeta["name"],
            "episode_start_range": [date_from, date_to],
            "frozen_denominator": expected,
            "episode_count": actual,
            "matches_frozen_denominator": actual == expected,
            "source_start_day_count": start_day_count,
            "source_start_day_starts": start_day_events,
        }
        manifest_rows.append(manifest_row)
        if actual != expected:
            mismatches.append(manifest_row)
            continue

        payload = {
            "schema_version": 1,
            "task_id": task_id,
            "parent_task_id": row["parent_task_id"],
            "city_key": city_key,
            "city": row["city_label"],
            "source": {
                "url": SOURCE_URL,
                "git_blob_sha": source_sha,
                **smeta,
            },
            "assignment_rule": "alert start date in Europe/Kyiv",
            "episode_start_range": [date_from, date_to],
            "frozen_denominator": expected,
            "episode_count": actual,
            "episodes": [
                {
                    "episode_id": event_id(city_key, start, end),
                    "alert_start": utc_z(start),
                    "alert_end": utc_z(end),
                    "alert_start_date_kyiv": start.astimezone(TZ).date().isoformat(),
                }
                for start, end in events
            ],
        }
        built.append((OUT_DIR / f"{task_id}_alerts.json", payload))

    manifest = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "source_url": SOURCE_URL,
        "source_git_blob_sha": source_sha,
        "adapter": "assembled WIP production episodes: historical adapter + Alerts.in.ua seam + persisted UkraineAlarm continuation",
        "boundary_exclusions": boundary_exclusions,
        "subslice_count": len(rows),
        "all_match_frozen_denominator": not mismatches,
        "mismatches": mismatches,
        "subslices": manifest_rows,
    }

    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if mismatches:
        details = ", ".join(
            f"{x['task_id']}:{x['episode_count']}!={x['frozen_denominator']}[startday={x['source_start_day_count']}:{'|'.join(x['source_start_day_starts'])}]"
            for x in mismatches
        )
        raise RuntimeError(
            f"Frozen denominator mismatch; source slices not written: {details}"
        )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for path, payload in built:
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        tmp_path.replace(path)

    print(
        json.dumps(
            {
                "source_git_blob_sha": source_sha,
                "subslice_count": len(rows),
                "written": len(built),
                "all_match_frozen_denominator": True,
                "min_denominator": min(int(r["frozen_denominator"]) for r in rows),
                "max_denominator": max(int(r["frozen_denominator"]) for r in rows),
            },
            ensure_ascii=False,
        )
    )


DEFAULT_MAX_EPISODES = 250


def _group_events_by_start_day(
    events: list[tuple[datetime, datetime]],
    max_episodes: int,
) -> list[tuple[str, list[tuple[datetime, datetime]]]]:
    groups: list[tuple[str, list[tuple[datetime, datetime]]]] = []
    for start, end in events:
        day = start.astimezone(TZ).date().isoformat()
        if not groups or groups[-1][0] != day:
            groups.append((day, []))
        groups[-1][1].append((start, end))

    oversized = [(day, len(group)) for day, group in groups if len(group) > max_episodes]
    if oversized:
        details = ", ".join(f"{day}:{count}" for day, count in oversized)
        raise RuntimeError(
            "Cannot split repair parent without cutting a Europe/Kyiv alert-start "
            f"day; day episode count exceeds --max-episodes={max_episodes}: {details}"
        )
    return groups


def _min_chunks_for_day_groups(
    day_groups: list[tuple[str, list[tuple[datetime, datetime]]]],
    max_episodes: int,
) -> int:
    chunks = 0
    current = 0
    for _, group in day_groups:
        count = len(group)
        if current and current + count > max_episodes:
            chunks += 1
            current = 0
        current += count
    if current:
        chunks += 1
    return chunks


def split_events_by_start_day(
    events: list[tuple[datetime, datetime]],
    max_episodes: int,
) -> list[list[tuple[datetime, datetime]]]:
    if max_episodes <= 0:
        raise ValueError("max_episodes must be positive")
    if not events:
        return []

    day_groups = _group_events_by_start_day(events, max_episodes)
    chunk_count = _min_chunks_for_day_groups(day_groups, max_episodes)
    chunks: list[list[tuple[datetime, datetime]]] = []
    group_start = 0

    for chunk_index in range(chunk_count - 1):
        chunks_left = chunk_count - chunk_index
        groups_left = day_groups[group_start:]
        remaining_total = sum(len(group) for _, group in groups_left)
        target = remaining_total / chunks_left
        remaining_chunks_after = chunks_left - 1
        max_cut = len(day_groups) - remaining_chunks_after

        candidates: list[tuple[float, int, int]] = []
        running = 0
        for cut in range(group_start + 1, max_cut + 1):
            running += len(day_groups[cut - 1][1])
            if running > max_episodes:
                break

            suffix = day_groups[cut:]
            if len(suffix) < remaining_chunks_after:
                continue
            if (
                _min_chunks_for_day_groups(suffix, max_episodes)
                > remaining_chunks_after
            ):
                continue

            candidates.append((abs(running - target), -running, cut))

        if not candidates:
            raise RuntimeError(
                f"Unable to find a day-preserving split for {len(events)} episodes "
                f"with --max-episodes={max_episodes}"
            )

        _, _, cut = min(candidates)
        chunk = [
            pair
            for _, group in day_groups[group_start:cut]
            for pair in group
        ]
        chunks.append(chunk)
        group_start = cut

    final_chunk = [
        pair
        for _, group in day_groups[group_start:]
        for pair in group
    ]
    chunks.append(final_chunk)

    if any(len(chunk) > max_episodes for chunk in chunks):
        raise RuntimeError("Internal error: chunk exceeds max_episodes after split")
    if sum(len(chunk) for chunk in chunks) != len(events):
        raise RuntimeError("Internal error: chunk episode total differs from parent")
    return chunks


def _episode_payload(
    city_key: str,
    start: datetime,
    end: datetime,
) -> dict[str, str]:
    return {
        "episode_id": event_id(city_key, start, end),
        "alert_start": utc_z(start),
        "alert_end": utc_z(end),
        "alert_start_date_kyiv": start.astimezone(TZ).date().isoformat(),
    }


def _episode_id_checksum(episode_ids: list[str]) -> str:
    return hashlib.sha256("\n".join(episode_ids).encode("utf-8")).hexdigest()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--task",
        choices=sorted(SUPPORTED_TASKS),
        help="Build one repair parent slice without reading RESEARCH_SUBSLICES.",
    )
    parser.add_argument(
        "--max-episodes",
        type=int,
        default=None,
        help=(
            "Maximum episodes per day-preserving repair chunk; "
            f"default for --task is {DEFAULT_MAX_EPISODES}."
        ),
    )
    args = parser.parse_args(argv)
    if args.max_episodes is not None and not args.task:
        parser.error("--max-episodes requires --task")
    if args.max_episodes is not None and args.max_episodes <= 0:
        parser.error("--max-episodes must be positive")
    return args


def load_parent_task(task_id: str) -> dict[str, str]:
    rows = {row["task_id"]: row for row in load_csv(PARENTS_CSV)}
    try:
        return rows[task_id]
    except KeyError as exc:
        raise RuntimeError(
            f"Task {task_id!r} is not present in {PARENTS_CSV.name}"
        ) from exc


def build_task(
    task_id: str,
    max_episodes: int = DEFAULT_MAX_EPISODES,
) -> None:
    if task_id not in SUPPORTED_TASKS:
        raise RuntimeError(
            f"Unsupported task {task_id!r}; supported: {sorted(SUPPORTED_TASKS)}"
        )
    if max_episodes <= 0:
        raise RuntimeError("max_episodes must be positive")

    row = load_parent_task(task_id)
    city_key = row["city_key"]
    date_from = row["episode_start_date_from"]
    date_to = row["episode_start_date_to"]
    expected = int(row["frozen_denominator"])

    response = requests.get(
        SOURCE_URL,
        timeout=240,
        headers={"User-Agent": "kyiv-air-alerts-grafana source-slice builder"},
    )
    response.raise_for_status()
    source_bytes = response.content
    source_sha = git_blob_sha(source_bytes)

    by_city, source_meta = production_episodes_from_bytes(
        source_bytes, {city_key}
    )
    events = [
        (start, end)
        for start, end in by_city[city_key]
        if date_from <= start.astimezone(TZ).date().isoformat() <= date_to
    ]
    events.sort(key=lambda x: (x[0], x[1]))

    sigs = {(utc_z(start), utc_z(end)) for start, end in events}
    if len(sigs) != len(events):
        raise RuntimeError(f"Duplicate production episode signatures in {task_id}")

    actual = len(events)
    matches = actual == expected
    smeta = source_meta[city_key]
    source = {
        "url": SOURCE_URL,
        "git_blob_sha": source_sha,
        **smeta,
    }

    event_chunks = split_events_by_start_day(events, max_episodes)
    if len(event_chunks) > 26:
        raise RuntimeError(
            f"Too many chunks for alphabetic chunk ids: {len(event_chunks)}"
        )

    parent_episodes = [
        _episode_payload(city_key, start, end)
        for start, end in events
    ]
    parent_ids = [episode["episode_id"] for episode in parent_episodes]
    if len(set(parent_ids)) != len(parent_ids):
        raise RuntimeError(f"Duplicate episode IDs in reconstructed parent {task_id}")

    assignment_rule = (
        "alert start date in Europe/Kyiv; keep each alert_start_date_kyiv "
        "wholly within one contiguous chunk; balance by episode count"
    )

    chunk_payloads: list[tuple[Path, dict]] = []
    chunk_manifest_rows: list[dict] = []
    union_ids: list[str] = []

    for index, chunk_events in enumerate(event_chunks):
        chunk_id = chr(ord("a") + index)
        chunk_task_id = f"{task_id}{chunk_id}"
        episodes = [
            _episode_payload(city_key, start, end)
            for start, end in chunk_events
        ]
        chunk_ids = [episode["episode_id"] for episode in episodes]
        union_ids.extend(chunk_ids)
        chunk_range = [
            episodes[0]["alert_start_date_kyiv"],
            episodes[-1]["alert_start_date_kyiv"],
        ]

        payload = {
            "schema_version": 1,
            "task_id": chunk_task_id,
            "parent_task_id": task_id,
            "chunk_id": chunk_id,
            "city_key": city_key,
            "city": row["city_label"],
            "episode_start_range": chunk_range,
            "episode_count": len(episodes),
            "parent_frozen_denominator": expected,
            "parent_reconstructed_denominator": actual,
            "matches_parent_frozen_denominator": matches,
            "max_episodes": max_episodes,
            "assignment_rule": assignment_rule,
            "source": source,
            "episodes": episodes,
        }
        path = OUT_DIR / f"{chunk_task_id}_alerts.json"
        chunk_payloads.append((path, payload))
        chunk_manifest_rows.append(
            {
                "task_id": chunk_task_id,
                "chunk_id": chunk_id,
                "file": path.name,
                "episode_count": len(episodes),
                "episode_start_range": chunk_range,
                "episode_ids_sha256": _episode_id_checksum(chunk_ids),
            }
        )

    duplicate_count = len(union_ids) - len(set(union_ids))
    parent_checksum = _episode_id_checksum(parent_ids)
    union_checksum = _episode_id_checksum(union_ids)
    sum_chunk_counts = sum(row["episode_count"] for row in chunk_manifest_rows)
    no_day_overlap = all(
        chunk_manifest_rows[i - 1]["episode_start_range"][1]
        < chunk_manifest_rows[i]["episode_start_range"][0]
        for i in range(1, len(chunk_manifest_rows))
    )
    union_equals_parent = union_ids == parent_ids

    validation = {
        "max_episodes": max_episodes,
        "no_chunk_exceeds_max_episodes": all(
            row["episode_count"] <= max_episodes
            for row in chunk_manifest_rows
        ),
        "chunks_contiguous_in_parent_episode_order": union_equals_parent,
        "date_ranges_non_overlapping": no_day_overlap,
        "duplicate_episode_id_count": duplicate_count,
        "no_duplicate_episode_ids_between_chunks": duplicate_count == 0,
        "sum_chunk_episode_count": sum_chunk_counts,
        "sum_matches_parent_reconstructed_denominator": sum_chunk_counts == actual,
        "reconstructed_parent_episode_ids_sha256": parent_checksum,
        "chunk_union_episode_ids_sha256": union_checksum,
        "checksum_match": parent_checksum == union_checksum,
        "union_equals_reconstructed_parent_list": union_equals_parent,
    }

    required_checks = [
        validation["no_chunk_exceeds_max_episodes"],
        validation["chunks_contiguous_in_parent_episode_order"],
        validation["date_ranges_non_overlapping"],
        validation["no_duplicate_episode_ids_between_chunks"],
        validation["sum_matches_parent_reconstructed_denominator"],
        validation["checksum_match"],
        validation["union_equals_reconstructed_parent_list"],
    ]
    if not all(required_checks):
        raise RuntimeError(
            f"Chunk validation failed for {task_id}: "
            + json.dumps(validation, ensure_ascii=False)
        )

    manifest = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "parent_task_id": task_id,
        "city_key": city_key,
        "city": row["city_label"],
        "parent_episode_start_range": [date_from, date_to],
        "parent_frozen_denominator": expected,
        "parent_reconstructed_denominator": actual,
        "matches_parent_frozen_denominator": matches,
        "chunk_count": len(chunk_manifest_rows),
        "max_episodes": max_episodes,
        "assignment_rule": assignment_rule,
        "source": source,
        "chunks": chunk_manifest_rows,
        "validation": validation,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    for path, payload in chunk_payloads:
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )

    manifest_path = OUT_DIR / f"{task_id}_chunks_manifest.json"
    manifest_tmp = manifest_path.with_suffix(manifest_path.suffix + ".tmp")
    manifest_tmp.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    wanted_names = {path.name for path, _ in chunk_payloads}
    for stale_path in OUT_DIR.glob(f"{task_id}[a-z]_alerts.json"):
        if stale_path.name not in wanted_names:
            stale_path.unlink()

    for path, _ in chunk_payloads:
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.replace(path)
    manifest_tmp.replace(manifest_path)

    print(
        json.dumps(
            {
                "task_id": task_id,
                "source_git_blob_sha": source_sha,
                "parent_reconstructed_denominator": actual,
                "parent_frozen_denominator": expected,
                "matches_parent_frozen_denominator": matches,
                "chunk_count": len(chunk_manifest_rows),
                "chunks": [
                    {
                        "task_id": chunk["task_id"],
                        "episode_count": chunk["episode_count"],
                        "episode_start_range": chunk["episode_start_range"],
                    }
                    for chunk in chunk_manifest_rows
                ],
                "manifest": str(manifest_path),
            },
            ensure_ascii=False,
        )
    )


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    if args.task:
        build_task(
            args.task,
            args.max_episodes
            if args.max_episodes is not None
            else DEFAULT_MAX_EPISODES,
        )
        return
    build_all()


if __name__ == "__main__":
    main()
