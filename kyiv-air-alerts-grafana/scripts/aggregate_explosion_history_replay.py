#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

OUTPUT_NAME = "explosion_monitor_full_historical_replay_2026-09-25.json"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description="Aggregate read-only historical explosion replay city artifacts.")
    ap.add_argument("--preflight", type=Path, required=True)
    ap.add_argument("--results-dir", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    preflight = load(args.preflight)
    expected = list(preflight.get("city_keys") or [])
    city_results = {}
    for path in sorted(args.results_dir.rglob("*.json")):
        if path.resolve() == args.preflight.resolve() or path.name == OUTPUT_NAME:
            continue
        try:
            row = load(path)
        except Exception:
            continue
        city = row.get("city_key")
        if city in expected and city not in city_results:
            city_results[city] = row

    summaries = []
    all_changes = []
    all_errors = []
    ppo_changes = []
    category_counts = Counter()
    total_checked = 0
    baseline_strict = 0
    replayed_strict = 0
    baseline_sens = 0
    replayed_sens = 0
    unchanged = 0
    completed = 0
    cities_with_deltas = []
    identity_mismatch_cities = []

    preflight_by_city = {row["city_key"]: row for row in preflight.get("cities") or [] if row.get("city_key")}
    for city in expected:
        row = city_results.get(city)
        if row is None:
            source = preflight_by_city.get(city) or {}
            summaries.append({
                "city_key": city,
                "status": "NOT_REPLAYED",
                "coverage_start": source.get("coverage_start"),
                "replay_end": source.get("replay_end") or preflight.get("replay_end"),
                "blocking_reasons": source.get("blocking_reasons") or [{"code": "MISSING_CITY_ARTIFACT"}],
            })
            for err in source.get("blocking_reasons") or [{"code": "MISSING_CITY_ARTIFACT"}]:
                all_errors.append({"city_key": city, **err})
            continue

        if row.get("status") == "COMPLETE":
            completed += 1
        total_checked += int(row.get("episodes_checked") or 0)
        baseline_strict += int(row.get("baseline_strict_episodes") or 0)
        replayed_strict += int(row.get("replayed_strict_episodes") or 0)
        baseline_sens += int(row.get("baseline_sensitivity_episodes") or 0)
        replayed_sens += int(row.get("replayed_sensitivity_episodes") or 0)
        unchanged += int(row.get("unchanged_episodes") or 0)
        for key, value in (row.get("reconciliation_counts") or {}).items():
            category_counts[key] += int(value or 0)
        changes = row.get("changed_episodes") or []
        if changes:
            cities_with_deltas.append(city)
            all_changes.extend({"city_key": city, **change} for change in changes)
        ppo_changes.extend({"city_key": city, **change} for change in row.get("ppo_related_changes") or [])
        if (row.get("strict_episode_identity") or {}).get("aggregate_counts_equal_but_episode_identities_differ"):
            identity_mismatch_cities.append(city)
        for err in row.get("errors") or []:
            all_errors.append({"city_key": city, **err})
        summaries.append({
            "city_key": city,
            "status": row.get("status"),
            "coverage_start": row.get("coverage_start"),
            "replay_end": row.get("replay_end"),
            "episodes_checked": row.get("episodes_checked"),
            "baseline_strict_episodes": row.get("baseline_strict_episodes"),
            "replayed_strict_episodes": row.get("replayed_strict_episodes"),
            "baseline_sensitivity_episodes": row.get("baseline_sensitivity_episodes"),
            "replayed_sensitivity_episodes": row.get("replayed_sensitivity_episodes"),
            "changed_episode_count": len(changes),
            "reconciliation_counts": row.get("reconciliation_counts") or {},
            "strict_episode_identity": row.get("strict_episode_identity") or {},
            "error_count": len(row.get("errors") or []),
        })

    changed_count = len(all_changes)
    ambiguous_count = category_counts["NEW_AMBIGUOUS"] + category_counts["UNREPLAYABLE_MISSING_EVIDENCE"]
    preflight_ready = bool(preflight.get("ready_for_matrix"))
    complete_23 = len(expected) == 23 and completed == 23
    if complete_23 and not all_errors and changed_count == 0:
        verdict = "FULL HISTORICAL REPLAY CLEAN — NO BASELINE RECONCILIATION REQUIRED"
    elif complete_23 and not all_errors:
        verdict = "FULL HISTORICAL REPLAY COMPLETE — RECONCILIATION QA REQUIRED"
    else:
        verdict = "FULL HISTORICAL REPLAY BLOCKED — MANUAL QA REQUIRED"

    payload = {
        "schema_version": 1,
        "kind": "full_historical_explosion_replay",
        "artifact_name": OUTPUT_NAME,
        "frozen_input_head": preflight.get("input_head"),
        "input_blob_shas": preflight.get("input_blob_shas") or {},
        "monitor_code_sha": (preflight.get("input_blob_shas") or {}).get("kyiv-air-alerts-grafana/scripts/monitor_explosion_candidates.py"),
        "historical_source_shas": {k: v for k, v in (preflight.get("input_blob_shas") or {}).items() if "explosion_research/" in k or "source_slices/" in k or k.endswith("alerts_combined.json") or k.endswith("sevastopol_events.json")},
        "methodology": {
            "replay_end_inclusive_local_date": preflight.get("replay_end"),
            "network": "disabled inside replay/preflight process",
            "input_commit": "all replay jobs must use frozen_input_head",
            "comparison_unit": "episode_id/status, not aggregate counts only",
            "control_period": "2026-09-18+ excluded from historical replay counts",
            "baseline_mutation": "forbidden",
        },
        "preflight_ready_for_matrix": preflight_ready,
        "preflight_verdict": preflight.get("verdict"),
        "completion": {"completed_cities": completed, "expected_cities": len(expected), "all_23_complete": complete_23},
        "total_episodes_checked": total_checked,
        "baseline_strict_episodes": baseline_strict,
        "replayed_strict_episodes": replayed_strict,
        "baseline_sensitivity_episodes": baseline_sens,
        "replayed_sensitivity_episodes": replayed_sens,
        "unchanged_episodes": unchanged,
        "changed_episode_count": changed_count,
        "reconciliation_counts": dict(sorted(category_counts.items())),
        "new_strict": [r for r in all_changes if r.get("category") == "NEW_STRICT"],
        "strict_downgrades": [r for r in all_changes if r.get("category") == "STRICT_DOWNGRADE"],
        "strict_to_sensitivity": [r for r in all_changes if r.get("category") == "STRICT_TO_SENSITIVITY"],
        "sensitivity_to_strict": [r for r in all_changes if r.get("category") == "SENSITIVITY_TO_STRICT"],
        "new_sensitivity": [r for r in all_changes if r.get("category") == "NEW_SENSITIVITY"],
        "ambiguous_or_unreplayable_count": ambiguous_count + len(all_errors),
        "changed_episodes": all_changes,
        "ppo_related_changes": ppo_changes,
        "cities_with_any_deltas": cities_with_deltas,
        "aggregate_counts_equal_but_episode_identities_differ_cities": identity_mismatch_cities,
        "city_summaries": summaries,
        "errors_or_missing_evidence": all_errors,
        "live_control_regressions": preflight.get("live_control_regressions") or {},
        "protected_files_unchanged_in_preflight": preflight.get("protected_files_unchanged"),
        "readiness_verdict": verdict,
    }
    dump(args.output, payload)
    print(verdict)


if __name__ == "__main__":
    main()
