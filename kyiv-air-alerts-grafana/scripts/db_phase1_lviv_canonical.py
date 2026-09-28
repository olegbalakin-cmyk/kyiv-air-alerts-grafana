#!/usr/bin/env python3
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, time, timezone
from typing import Any, TypedDict
from zoneinfo import ZoneInfo

from db_phase1_core import (
    CANONICALIZATION_VERSION,
    SOURCE_KEYS,
    SOURCE_KEY_VERSIONS,
    Interval,
    legacy_episode_id,
    legacy_timestamp,
    merge_intervals,
    normalize_text,
    parse_timestamp,
    source_key_timestamp,
    ukrainealarm_source_record_key,
    vadimkin_source_record_key,
)

CITY_KEY = "lviv"
ASSEMBLY_PROFILE = "lviv-historical-v1"
OBLAST = "Львівська область"
RAION = "Львівський район"
KYIV_TZ = ZoneInfo("Europe/Kyiv")
COVERAGE_START = date(2025, 9, 1)
HISTORICAL_END_EXCLUSIVE = date(2026, 9, 18)


class CanonicalPayload(TypedDict, total=False):
    canonicalization_version: str
    assembly_profile: str
    episodes: list[dict[str, Any]]
    source_observations: list[dict[str, Any]]
    source_record_keys: list[str]
    checkpoint_candidate: dict[str, Any] | None
    boundary_errors: list[dict[str, Any]]
    serial: list[tuple[str, str, str]]
    historical_merged_count: int
    ukrainealarm_interval_count: int
    api_overlap_refinement_count: int
    api_additions: int


def vadimkin_rows_to_observations(rows: list[dict]) -> tuple[list[dict], dict]:
    """Pure accepted Vadimkin raw-row adapter for the Lviv Phase-1 profile."""
    cutoff = datetime.combine(COVERAGE_START, time.min, tzinfo=KYIV_TZ).astimezone(timezone.utc)
    seen_marker: set[tuple[str, str, str]] = set()
    seen_key: dict[str, dict] = {}
    eligible: list[dict] = []
    diagnostics = Counter()

    for index, row in enumerate(rows):
        diagnostics["raw_rows"] += 1
        if normalize_text(row.get("oblast", "")) != OBLAST:
            diagnostics["geography_rejected"] += 1
            continue
        level = normalize_text(row.get("level", ""))
        raion = normalize_text(row.get("raion", ""))
        if level != "oblast" and not (level == "raion" and raion == RAION):
            diagnostics["geography_rejected"] += 1
            continue
        started = normalize_text(row.get("started_at", ""))
        finished = normalize_text(row.get("finished_at", ""))
        if not started or not finished:
            diagnostics["missing_interval"] += 1
            continue

        marker = (level, started, finished)
        if marker in seen_marker:
            diagnostics["duplicate_marker_rows"] += 1
            continue
        seen_marker.add(marker)

        try:
            start = parse_timestamp(started)
            end = parse_timestamp(finished)
        except (TypeError, ValueError):
            diagnostics["invalid_timestamp"] += 1
            continue
        if end <= start:
            diagnostics["invalid_interval"] += 1
            continue
        if end <= cutoff:
            diagnostics["before_coverage"] += 1
            continue

        key_fields = dict(row)
        key_fields["start_at"] = started
        key_fields["end_at"] = finished
        canonical, key = vadimkin_source_record_key(key_fields)
        if key in seen_key:
            diagnostics["duplicate_semantic_key"] += 1
            continue

        effective_start = max(start, cutoff)
        obs = {
            "source_key": SOURCE_KEYS["vadimkin"],
            "source_record_key_version": SOURCE_KEY_VERSIONS[SOURCE_KEYS["vadimkin"]],
            "source_record_key": key,
            "source_native_id": None,
            "city_key": CITY_KEY,
            "alert_type": "AIR",
            "source_start_at": source_key_timestamp(start),
            "source_end_at": source_key_timestamp(end),
            "source_retrieved_at": None,
            "binding_state": "bound",
            "canonicalization_role": "canonical_input",
            "provenance": {
                "fixture_row_index": index,
                "canonical_preimage": canonical,
                "original_level": row.get("level", ""),
                "original_oblast": row.get("oblast", ""),
                "original_raion": row.get("raion", ""),
                "original_hromada": row.get("hromada", ""),
                "original_source": row.get("source", ""),
                "coverage_clipped_start": effective_start != start,
            },
            "effective_interval": Interval(effective_start, end),
            "contributes_start_boundary": False,
            "contributes_end_boundary": False,
        }
        seen_key[key] = obs
        eligible.append(obs)
        diagnostics["semantic_observations"] += 1
    return eligible, dict(diagnostics)


def ukrainealarm_rows_to_observations(
    events: list[dict],
    *,
    historical_end_exclusive: date | None = HISTORICAL_END_EXCLUSIVE,
) -> list[dict]:
    """Pure accepted UkraineAlarm regionHistory adapter."""
    end_exclusive = (
        datetime.combine(historical_end_exclusive, time.min, tzinfo=KYIV_TZ).astimezone(timezone.utc)
        if historical_end_exclusive is not None
        else None
    )
    by_key: dict[str, dict] = {}
    for index, row in enumerate(events):
        if row.get("city_key") != CITY_KEY:
            continue
        if normalize_text(row.get("alert_type", "")).upper() != "AIR":
            continue
        start = parse_timestamp(str(row["start"]))
        end = parse_timestamp(str(row["end"]))
        if end <= start:
            raise AssertionError(f"Invalid bridge interval: {row}")
        if end_exclusive is not None and start >= end_exclusive:
            continue
        fields = {
            "city_key": row["city_key"],
            "region_id": row["region_id"],
            "alert_type": row["alert_type"],
            "start_at": row["start"],
            "end_at": row["end"],
        }
        canonical, key = ukrainealarm_source_record_key(fields)
        by_key.setdefault(
            key,
            {
                "source_key": SOURCE_KEYS["ukrainealarm"],
                "source_record_key_version": SOURCE_KEY_VERSIONS[SOURCE_KEYS["ukrainealarm"]],
                "source_record_key": key,
                "source_native_id": None,
                "city_key": CITY_KEY,
                "alert_type": "AIR",
                "source_start_at": source_key_timestamp(start),
                "source_end_at": source_key_timestamp(end),
                "source_retrieved_at": None,
                "binding_state": "bound",
                "canonicalization_role": "canonical_input",
                "provenance": {
                    "fixture_row_index": index,
                    "api_region_name": row.get("api_region_name"),
                    "region_id": str(row["region_id"]),
                    "canonical_preimage": canonical,
                },
                "effective_interval": Interval(start, end),
                "contributes_start_boundary": False,
                "contributes_end_boundary": False,
            },
        )
    return sorted(
        by_key.values(),
        key=lambda x: (
            x["effective_interval"].start,
            x["effective_interval"].end,
            x["source_record_key"],
        ),
    )


def _dedupe_observations(observations: list[dict]) -> list[dict]:
    by_identity: dict[tuple[str, str, str], dict] = {}
    for source in observations:
        identity = (
            str(source["source_key"]),
            str(source["source_record_key_version"]),
            str(source["source_record_key"]),
        )
        by_identity.setdefault(identity, dict(source))
    return sorted(
        by_identity.values(),
        key=lambda x: (
            x["effective_interval"].start,
            x["effective_interval"].end,
            x["source_key"],
            x["source_record_key"],
        ),
    )


def checkpoint_candidate_from_state(checkpoint_state: dict) -> dict[str, Any]:
    return {
        "source_key": "ukrainealarm_region_history",
        "city_key": CITY_KEY,
        "stream_key": "region_id:90:AIR",
        "checkpoint_seq": 1,
        "checkpoint_kind": "bootstrap",
        "previous_checkpoint": None,
        "checked_at": checkpoint_state.get("last_checked_at"),
        "continuity_verified": bool(checkpoint_state.get("continuous")),
        "continuity_method": checkpoint_state.get("continuity_reason"),
        "continuity_anchor_at": None,
        "observed_oldest_start_at": checkpoint_state.get("oldest_history_start"),
        "observed_latest_end_at": checkpoint_state.get("latest_history_end"),
        "observed_record_count": checkpoint_state.get("history_completed_air_count"),
        "metadata": {
            "initial_static_match": checkpoint_state.get("initial_static_match"),
            "poll_overlap_verified": checkpoint_state.get("poll_overlap_verified"),
            "api_region_name": checkpoint_state.get("api_region_name"),
            "region_id": checkpoint_state.get("region_id"),
            "kind": checkpoint_state.get("kind"),
            "target": checkpoint_state.get("target"),
            "oblast": checkpoint_state.get("oblast"),
            "last_error": checkpoint_state.get("last_error"),
            "observed_latest_end_is_coverage_watermark": False,
        },
    }


def bootstrap_summary(checkpoint_state: dict) -> dict[str, Any]:
    return {
        "ingestion_run": {
            "run_kind": "bootstrap_import",
            "canonicalization_version": CANONICALIZATION_VERSION,
            "parameters": {"assembly_profile": ASSEMBLY_PROFILE},
        },
        "checkpoint_candidate": checkpoint_candidate_from_state(checkpoint_state),
        "alerts_in_ua_static_episode_observation_created": False,
    }


def canonicalize_lviv(
    vadimkin_observations: list[dict],
    ukrainealarm_observations: list[dict],
    *,
    checkpoint_state: dict | None = None,
) -> CanonicalPayload:
    """Pure deterministic Lviv Phase-1 canonical boundary."""
    vad_obs = _dedupe_observations(vadimkin_observations)
    ua_obs = _dedupe_observations(ukrainealarm_observations)

    frozen = merge_intervals(o["effective_interval"] for o in vad_obs)
    bridge = [o["effective_interval"] for o in ua_obs]
    bridge_overlap = [
        interval
        for interval in bridge
        if any(
            interval.start <= frozen_interval.end
            and frozen_interval.start <= interval.end
            for frozen_interval in frozen
        )
    ]
    bridge_new = [interval for interval in bridge if interval not in bridge_overlap]
    final = merge_intervals([*frozen, *bridge])

    episodes = [
        {
            "legacy_episode_id": legacy_episode_id(CITY_KEY, interval.start, interval.end),
            "start": legacy_timestamp(interval.start),
            "end": legacy_timestamp(interval.end),
            "interval": interval,
        }
        for interval in final
    ]

    all_obs = [dict(obs) for obs in [*vad_obs, *ua_obs]]
    for obs in all_obs:
        interval = obs["effective_interval"]
        candidates = [
            episode
            for episode in episodes
            if episode["interval"].start <= interval.start
            and episode["interval"].end >= interval.end
        ]
        if len(candidates) != 1:
            raise AssertionError(
                f"Observation binding ambiguity: {obs['source_record_key']} -> {len(candidates)}"
            )
        episode = candidates[0]
        obs["episode_id"] = episode["legacy_episode_id"]
        obs["contributes_start_boundary"] = (
            parse_timestamp(obs["source_start_at"]) == episode["interval"].start
        )
        obs["contributes_end_boundary"] = (
            parse_timestamp(obs["source_end_at"]) == episode["interval"].end
        )

    boundary_errors: list[dict[str, Any]] = []
    for episode in episodes:
        bound = [
            obs for obs in all_obs
            if obs["episode_id"] == episode["legacy_episode_id"]
        ]
        starters = [obs for obs in bound if obs["contributes_start_boundary"]]
        enders = [obs for obs in bound if obs["contributes_end_boundary"]]
        if not starters:
            boundary_errors.append(
                {
                    "episode_id": episode["legacy_episode_id"],
                    "boundary": "start",
                    "reason": "no_contributor",
                }
            )
        if not enders:
            boundary_errors.append(
                {
                    "episode_id": episode["legacy_episode_id"],
                    "boundary": "end",
                    "reason": "no_contributor",
                }
            )

    return {
        "canonicalization_version": CANONICALIZATION_VERSION,
        "assembly_profile": ASSEMBLY_PROFILE,
        "episodes": episodes,
        "source_observations": all_obs,
        "source_record_keys": sorted(obs["source_record_key"] for obs in all_obs),
        "checkpoint_candidate": (
            checkpoint_candidate_from_state(checkpoint_state)
            if checkpoint_state is not None
            else None
        ),
        "boundary_errors": boundary_errors,
        "serial": [
            (episode["legacy_episode_id"], episode["start"], episode["end"])
            for episode in episodes
        ],
        "historical_merged_count": len(frozen),
        "ukrainealarm_interval_count": len(bridge),
        "api_overlap_refinement_count": len(bridge_overlap),
        "api_additions": len(bridge_new),
        "frozen_intervals": frozen,
        "bridge_intervals": bridge,
        "bridge_overlap": bridge_overlap,
        "bridge_new": bridge_new,
    }
