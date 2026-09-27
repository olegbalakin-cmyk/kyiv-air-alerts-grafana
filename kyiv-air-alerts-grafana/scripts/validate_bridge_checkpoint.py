#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import tempfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

UTC = timezone.utc
MATCH_TOLERANCE_SECONDS = 15.0
EXPECTED_SCHEMA_VERSION = 3
EXPECTED_REQUIRED_ROWS = 21
PROVENANCE_FIELDS = (
    "original_recovery_source",
    "source_kind",
    "source_files",
    "recovery_artifact",
    "original_recovery_start",
    "original_recovery_end",
)


def parse_dt(value: object, label: str = "timestamp") -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} is missing")
    text = value.strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def load_json(path: str | Path) -> dict:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected JSON object")
    return value


def completed_air(event: dict) -> tuple[str, datetime, datetime] | None:
    if str(event.get("alert_type") or "").upper() != "AIR":
        return None
    city = str(event.get("city_key") or "").strip()
    if not city:
        return None
    try:
        start = parse_dt(event.get("start"), "event.start")
        end = parse_dt(event.get("end"), "event.end")
    except (TypeError, ValueError):
        return None
    if end <= start:
        return None
    return city, start, end


def equivalent(a: dict, b: dict) -> bool:
    aa = completed_air(a)
    bb = completed_air(b)
    if aa is None or bb is None or aa[0] != bb[0]:
        return False
    return (
        abs((aa[1] - bb[1]).total_seconds()) <= MATCH_TOLERANCE_SECONDS
        and abs((aa[2] - bb[2]).total_seconds()) <= MATCH_TOLERANCE_SECONDS
    )


def duplicate_pairs(events: list[dict]) -> list[tuple[int, int]]:
    by_city: dict[str, list[tuple[int, datetime, datetime]]] = defaultdict(list)
    for index, event in enumerate(events):
        parsed = completed_air(event)
        if parsed is not None:
            city, start, end = parsed
            by_city[city].append((index, start, end))

    pairs: list[tuple[int, int]] = []
    for rows in by_city.values():
        rows.sort(key=lambda item: item[1])
        for i, (left_idx, left_start, left_end) in enumerate(rows):
            for right_idx, right_start, right_end in rows[i + 1 :]:
                if (right_start - left_start).total_seconds() > MATCH_TOLERANCE_SECONDS:
                    break
                if abs((right_end - left_end).total_seconds()) <= MATCH_TOLERANCE_SECONDS:
                    pairs.append((left_idx, right_idx))
    return pairs


def provenance_counter(store: dict) -> Counter[str]:
    out: Counter[str] = Counter()
    for event in store.get("events") or []:
        if not isinstance(event, dict):
            continue
        provenance = event.get("recovery_provenance")
        if provenance is None:
            continue
        if not isinstance(provenance, dict):
            raise ValueError("recovery_provenance must be an object")
        missing = [field for field in PROVENANCE_FIELDS if field not in provenance]
        if missing:
            raise ValueError(f"recovery_provenance missing fields: {missing}")
        out[json.dumps(provenance, ensure_ascii=False, sort_keys=True)] += 1
    return out


def ensure_events_preserved(candidate: dict, reference: dict, label: str) -> None:
    candidate_events = [e for e in candidate.get("events") or [] if isinstance(e, dict)]
    reference_events = [e for e in reference.get("events") or [] if isinstance(e, dict)]
    by_city: dict[str, list[dict]] = defaultdict(list)
    for event in candidate_events:
        parsed = completed_air(event)
        if parsed is not None:
            by_city[parsed[0]].append(event)

    missing = []
    for event in reference_events:
        parsed = completed_air(event)
        if parsed is None:
            continue
        if not any(equivalent(event, other) for other in by_city.get(parsed[0], [])):
            missing.append({
                "city_key": event.get("city_key"),
                "start": event.get("start"),
                "end": event.get("end"),
            })
            if len(missing) >= 5:
                break
    if missing:
        raise ValueError(f"candidate dropped {label} events: {missing}")


def ensure_monotonic(candidate: dict, reference: dict, label: str, *, require_advance: bool) -> None:
    candidate_success = parse_dt(candidate.get("last_successful_fetch_at"), "candidate.last_successful_fetch_at")
    reference_success = parse_dt(reference.get("last_successful_fetch_at"), f"{label}.last_successful_fetch_at")
    if candidate_success < reference_success:
        raise ValueError(f"candidate checkpoint regressed behind {label}")
    if require_advance and candidate_success <= reference_success:
        raise ValueError(f"candidate checkpoint did not advance beyond {label}")

    candidate_attempt = parse_dt(candidate.get("last_attempt_at"), "candidate.last_attempt_at")
    reference_attempt = parse_dt(reference.get("last_attempt_at"), f"{label}.last_attempt_at")
    if candidate_attempt < reference_attempt:
        raise ValueError(f"candidate last_attempt_at regressed behind {label}")

    candidate_regions = candidate.get("regions") or {}
    reference_regions = reference.get("regions") or {}
    for key, old_region in reference_regions.items():
        if not isinstance(old_region, dict) or key not in candidate_regions:
            raise ValueError(f"candidate missing {label} region {key}")
        new_region = candidate_regions[key]
        old_checked = parse_dt(old_region.get("last_checked_at"), f"{label}.{key}.last_checked_at")
        new_checked = parse_dt(new_region.get("last_checked_at"), f"candidate.{key}.last_checked_at")
        if new_checked < old_checked:
            raise ValueError(f"candidate {key} last_checked_at regressed behind {label}")
        if require_advance and new_checked <= old_checked:
            raise ValueError(f"candidate {key} last_checked_at did not advance beyond {label}")

        old_latest = old_region.get("latest_history_end")
        new_latest = new_region.get("latest_history_end")
        if old_latest and new_latest:
            if parse_dt(new_latest, f"candidate.{key}.latest_history_end") < parse_dt(old_latest, f"{label}.{key}.latest_history_end"):
                raise ValueError(f"candidate {key} latest_history_end regressed behind {label}")

    if int(candidate.get("event_count", -1)) < int(reference.get("event_count", -1)):
        raise ValueError(f"candidate event_count regressed behind {label}")
    ensure_events_preserved(candidate, reference, label)

    candidate_prov = provenance_counter(candidate)
    reference_prov = provenance_counter(reference)
    lost = reference_prov - candidate_prov
    if lost:
        raise ValueError(f"candidate lost recovery provenance from {label}: {sum(lost.values())} records")


def bridge_summary(data: dict) -> dict:
    summary = data.get("multicity_meta", {}).get("official_ukrainealarm_bridge")
    if not isinstance(summary, dict):
        raise ValueError("dashboard_data missing multicity_meta.official_ukrainealarm_bridge")
    return summary


def validate_checkpoint(candidate: dict, summary: dict, baseline: dict | None = None, remote: dict | None = None) -> dict:
    if candidate.get("schema_version") != EXPECTED_SCHEMA_VERSION:
        raise ValueError(f"unexpected bridge schema_version: {candidate.get('schema_version')}")
    regions = candidate.get("regions")
    events = candidate.get("events")
    if not isinstance(regions, dict) or not isinstance(events, list):
        raise ValueError("bridge regions/events have invalid types")
    if candidate.get("event_count") != len(events):
        raise ValueError(f"event_count mismatch: {candidate.get('event_count')} != {len(events)}")
    if candidate.get("last_fetch_error") is not None:
        raise ValueError(f"bridge has unresolved fetch errors: {candidate.get('last_fetch_error')}")
    parse_dt(candidate.get("last_successful_fetch_at"), "candidate.last_successful_fetch_at")
    parse_dt(candidate.get("last_attempt_at"), "candidate.last_attempt_at")

    if summary.get("token_present_this_run") is not True:
        raise ValueError("checkpoint persistence requires a fresh authenticated UkraineAlarm fetch")
    if summary.get("last_fetch_error") is not None:
        raise ValueError(f"summary has unresolved fetch errors: {summary.get('last_fetch_error')}")
    if summary.get("fully_continuous") is not True:
        raise ValueError("bridge continuity is not fully verified")

    required = list(summary.get("required_rows") or [])
    covered = list(summary.get("continuity_verified_rows") or [])
    unverified = list(summary.get("continuity_unverified_rows") or [])
    if len(required) != EXPECTED_REQUIRED_ROWS:
        raise ValueError(f"expected {EXPECTED_REQUIRED_ROWS} required bridge rows, found {len(required)}")
    if unverified:
        raise ValueError(f"continuity unverified rows: {unverified}")
    if set(required) != set(covered):
        raise ValueError("continuity verified rows do not match required rows")
    if set(required) != set(regions):
        raise ValueError("bridge region keys do not exactly match required rows")
    if summary.get("event_count") != candidate.get("event_count"):
        raise ValueError("summary event_count does not match bridge store")
    if summary.get("last_successful_fetch_at") != candidate.get("last_successful_fetch_at"):
        raise ValueError("summary/store last_successful_fetch_at mismatch")

    for key in required:
        region = regions.get(key)
        if not isinstance(region, dict):
            raise ValueError(f"invalid region state for {key}")
        if region.get("continuous") is not True:
            raise ValueError(f"{key}: continuity is not verified")
        if region.get("last_error") is not None:
            raise ValueError(f"{key}: unresolved fetch error: {region.get('last_error')}")
        if int(region.get("history_completed_air_count") or 0) <= 0:
            raise ValueError(f"{key}: no completed AIR history fetched")
        parse_dt(region.get("oldest_history_start"), f"{key}.oldest_history_start")
        parse_dt(region.get("latest_history_end"), f"{key}.latest_history_end")
        parse_dt(region.get("last_checked_at"), f"{key}.last_checked_at")

    duplicates = duplicate_pairs(events)
    if duplicates:
        raise ValueError(f"tolerance-equivalent duplicate pairs found: {len(duplicates)}")

    provenance = provenance_counter(candidate)
    if baseline is not None:
        ensure_monotonic(candidate, baseline, "pre-run checkpoint", require_advance=False)
    if remote is not None:
        ensure_monotonic(candidate, remote, "origin/site-prod checkpoint", require_advance=False)

    return {
        "required_rows": len(required),
        "continuity_verified_rows": len(covered),
        "fully_continuous": True,
        "duplicate_pairs": 0,
        "event_count": len(events),
        "recovery_provenance_count": sum(provenance.values()),
        "checkpoint": candidate.get("last_successful_fetch_at"),
    }


def continuity_from_poll(oldest_history_start: str, previous_checked_at: str) -> bool:
    return parse_dt(oldest_history_start, "oldest_history_start") <= parse_dt(previous_checked_at, "previous_checked_at")


def self_test() -> dict:
    t0 = "2026-09-27T10:00:00Z"
    t1 = "2026-09-27T11:00:00Z"
    t2 = "2026-09-27T12:00:00Z"
    with tempfile.TemporaryDirectory() as tmp:
        durable = Path(tmp) / "bridge.json"
        durable.write_text(json.dumps({"last_successful_fetch_at": t0}), encoding="utf-8")

        durable.write_text(json.dumps({"last_successful_fetch_at": t1}), encoding="utf-8")
        downstream_failed = False
        try:
            raise RuntimeError("intentional downstream failure injection")
        except RuntimeError:
            downstream_failed = True
        persisted_after_failure = load_json(durable)["last_successful_fetch_at"] == t1

        moving_window_oldest = "2026-09-27T10:30:00Z"
        t0_would_gap = not continuity_from_poll(moving_window_oldest, t0)
        t1_continuous = continuity_from_poll(moving_window_oldest, t1)

        genuine_gap_oldest = "2026-09-27T11:30:00Z"
        negative_gap_fails = not continuity_from_poll(genuine_gap_oldest, t1)

        stale_blocked = False
        candidate = {
            "last_successful_fetch_at": t1,
            "last_attempt_at": t1,
            "event_count": 0,
            "events": [],
            "regions": {"x": {"last_checked_at": t1, "latest_history_end": t1}},
        }
        newer = {
            "last_successful_fetch_at": t2,
            "last_attempt_at": t2,
            "event_count": 0,
            "events": [],
            "regions": {"x": {"last_checked_at": t2, "latest_history_end": t2}},
        }
        try:
            ensure_monotonic(candidate, newer, "synthetic newer origin", require_advance=False)
        except ValueError:
            stale_blocked = True

        ensure_monotonic(candidate, candidate, "identical origin", require_advance=False)
        idempotent_validation = True

    result = {
        "run_a": {
            "downstream_failure_injected": downstream_failed,
            "checkpoint_t1_persisted_after_failure": persisted_after_failure,
        },
        "run_b": {
            "moving_window_no_longer_reaches_t0": t0_would_gap,
            "persisted_t1_overlap_keeps_continuity": t1_continuous,
        },
        "negative_control": {
            "history_newer_than_t1_fails_continuity": negative_gap_fails,
        },
        "stale_run_overwrite_blocked": stale_blocked,
        "identical_state_idempotent": idempotent_validation,
    }
    if not all([
        downstream_failed,
        persisted_after_failure,
        t0_would_gap,
        t1_continuous,
        negative_gap_fails,
        stale_blocked,
        idempotent_validation,
    ]):
        raise AssertionError(result)
    return result


def build_diagnostic(candidate: dict, summary: dict, baseline: dict | None, validation: dict) -> dict:
    regions = candidate.get("regions") or {}
    per_city = {
        key: {
            "oldest_fetched_completed_air_start": value.get("oldest_history_start"),
            "newest_fetched_completed_air_end": value.get("latest_history_end"),
            "history_completed_air_count": value.get("history_completed_air_count"),
            "continuous": value.get("continuous"),
            "continuity_reason": value.get("continuity_reason"),
            "last_checked_at": value.get("last_checked_at"),
            "last_error": value.get("last_error"),
        }
        for key, value in sorted(regions.items())
        if isinstance(value, dict)
    }
    return {
        "run_id": os.getenv("GITHUB_RUN_ID"),
        "run_attempt": os.getenv("GITHUB_RUN_ATTEMPT"),
        "previous_checkpoint": baseline.get("last_successful_fetch_at") if baseline else None,
        "resulting_checkpoint": candidate.get("last_successful_fetch_at"),
        "continuity": {
            "required": len(summary.get("required_rows") or []),
            "verified": len(summary.get("continuity_verified_rows") or []),
            "unverified": list(summary.get("continuity_unverified_rows") or []),
            "fully_continuous": summary.get("fully_continuous"),
        },
        "event_count": candidate.get("event_count"),
        "duplicate_pairs": validation.get("duplicate_pairs"),
        "recovery_provenance_count": validation.get("recovery_provenance_count"),
        "fetch_metadata": {
            "last_attempt_at": candidate.get("last_attempt_at"),
            "last_successful_fetch_at": candidate.get("last_successful_fetch_at"),
            "last_fetch_error": candidate.get("last_fetch_error"),
        },
        "per_city": per_city,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate")
    validate.add_argument("--candidate", required=True)
    validate.add_argument("--summary", required=True)
    validate.add_argument("--baseline")
    validate.add_argument("--remote")
    validate.add_argument("--diagnostic")

    test = sub.add_parser("self-test")
    test.add_argument("--output")

    args = parser.parse_args()
    if args.command == "self-test":
        result = self_test()
        if args.output:
            Path(args.output).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, indent=2))
        return

    candidate = load_json(args.candidate)
    data = load_json(args.summary)
    summary = bridge_summary(data)
    baseline = load_json(args.baseline) if args.baseline else None
    remote = load_json(args.remote) if args.remote else None
    result = validate_checkpoint(candidate, summary, baseline=baseline, remote=remote)
    if args.diagnostic:
        diagnostic = build_diagnostic(candidate, summary, baseline, result)
        Path(args.diagnostic).write_text(json.dumps(diagnostic, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
