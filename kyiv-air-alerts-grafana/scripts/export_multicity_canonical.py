#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import add_duration_unit_switch as exactmod
import add_sevastopol_exact as sevastopol
import apply_ukrainealarm_bridge as bridge
import expand_multicity_production as base
import extend_remaining_proxies as extended
import update_data
from db_phase1_core import (
    CANONICALIZATION_VERSION,
    canonical_json,
    legacy_episode_id,
    legacy_timestamp,
)

UTC = timezone.utc
ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
ALERT_TYPE = "AIR"


class _FrozenResponse:
    def __init__(self, content: bytes) -> None:
        self.content = content

    def raise_for_status(self) -> None:
        return None


class _FrozenSession:
    def __init__(self, content: bytes) -> None:
        self.content = content

    def get(self, url: str, timeout: int | float | None = None) -> _FrozenResponse:
        if url != exactmod.CITY_SOURCE_URL or url != base.CITY_SOURCE_URL:
            raise RuntimeError(f"unexpected frozen-source URL: {url}")
        return _FrozenResponse(self.content)


def _install_frozen_vadimkin(payload: bytes) -> None:
    exactmod.http_session = lambda: _FrozenSession(payload)
    base.http_session = lambda: _FrozenSession(payload)


def _expected_count(meta: dict[str, Any], city_key: str) -> int:
    for field in (
        "combined_completed_alerts",
        "city_completed_alerts",
        "proxy_completed_alert_episodes",
        "completed_alert_episodes_used",
    ):
        value = meta.get(field)
        if value is not None:
            return int(value)
    raise RuntimeError(f"{city_key}: production dashboard has no episode-count field")


def _sevastopol_alerts() -> list[update_data.Alert]:
    store = json.loads((DATA_DIR / "sevastopol_events.json").read_text(encoding="utf-8"))
    alerts: list[update_data.Alert] = []
    for row in store.get("pairs", []):
        start = datetime.fromisoformat(str(row["start"])).astimezone(update_data.TZ)
        end = datetime.fromisoformat(str(row["end"])).astimezone(update_data.TZ)
        if end <= start:
            raise RuntimeError(f"sevastopol invalid retained pair: {row!r}")
        alerts.append(
            update_data.Alert(
                start=start,
                end=end,
                source="sevastopol_occupation_admin_telegram",
            )
        )
    alerts.sort(key=lambda x: (x.start, x.end))
    if not alerts:
        raise RuntimeError("sevastopol retained event store is empty")
    return alerts


def _build_production_boundary(
    dashboard: dict[str, Any],
) -> tuple[dict[str, list[update_data.Alert]], dict[str, Any]]:
    production_keys = list(dashboard.get("multicity_meta", {}).get("production_city_keys", []))
    if len(production_keys) != 23 or len(set(production_keys)) != 23:
        raise RuntimeError(f"production city-key boundary is not exactly 23 unique keys: {production_keys!r}")

    proxy_cfg = extended.configure_all_proxies()
    static, static_info = bridge.load_static_bridge()
    store = bridge.load_store()
    exact_base = exactmod.fetch_city_alerts()
    proxy_base, _ = base.fetch_proxy_alerts_with_phase1()

    by_city: dict[str, list[update_data.Alert]] = {}

    kyiv_raw = json.loads((DATA_DIR / "alerts_combined.json").read_text(encoding="utf-8"))
    by_city["kyiv"] = update_data.parse_committed_alerts(kyiv_raw)

    bridge_status: dict[str, Any] = {}
    for key in exactmod.CITY_CONFIG:
        region_status = store.get("regions", {}).get(key, {})
        continuous = bool(region_status.get("continuous"))
        api_alerts = bridge.api_store_alerts(store, key) if continuous else []
        by_city[key] = bridge.union_alerts(
            [*exact_base[key], *static[key], *api_alerts],
            "historical_plus_alertsinua_plus_ukrainealarm",
        )
        bridge_status[key] = {
            "continuous": continuous,
            "static_events": len(static[key]),
            "api_events": len(api_alerts),
        }

    for key in proxy_cfg:
        region_status = store.get("regions", {}).get(key, {})
        continuous = bool(region_status.get("continuous"))
        api_alerts = bridge.api_store_alerts(store, key) if continuous else []
        by_city[key] = bridge.union_alerts(
            [*proxy_base[key], *static[key], *api_alerts],
            "historical_proxy_plus_alertsinua_plus_ukrainealarm",
        )
        bridge_status[key] = {
            "continuous": continuous,
            "static_events": len(static[key]),
            "api_events": len(api_alerts),
        }

    by_city["sevastopol"] = _sevastopol_alerts()

    missing = [key for key in production_keys if key not in by_city]
    extra = [key for key in by_city if key not in production_keys]
    if missing or extra:
        raise RuntimeError(f"production boundary mismatch: missing={missing}, extra={extra}")

    return {key: by_city[key] for key in production_keys}, {
        "static_bridge": static_info,
        "bridge_status": bridge_status,
    }


def _daily_signature(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fields = (
        "date",
        "alerts_started",
        "total_alert_duration_minutes",
        "total_alert_duration_hours",
        "avg_alert_duration_minutes",
    )
    return [{field: row.get(field) for field in fields} for row in rows]


def _episode_rows(
    city_key: str,
    alerts: list[update_data.Alert],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    previous: update_data.Alert | None = None
    seen_intervals: set[tuple[str, str]] = set()
    for index, alert in enumerate(sorted(alerts, key=lambda x: (x.start, x.end))):
        start = alert.start.astimezone(UTC)
        end = alert.end.astimezone(UTC)
        if end <= start:
            errors.append({"kind": "non_positive_interval", "index": index})
            continue
        if previous is not None and start <= previous.end.astimezone(UTC):
            errors.append(
                {
                    "kind": "overlap_or_touch_not_canonical",
                    "index": index,
                    "previous_end": legacy_timestamp(previous.end),
                    "start": legacy_timestamp(start),
                }
            )
        previous = alert
        marker = (legacy_timestamp(start), legacy_timestamp(end))
        if marker in seen_intervals:
            errors.append({"kind": "duplicate_interval", "index": index, "interval": marker})
        seen_intervals.add(marker)
        rows.append(
            {
                "city_key": city_key,
                "alert_type": ALERT_TYPE,
                "start_at": legacy_timestamp(start),
                "end_at": legacy_timestamp(end),
                "episode_state": "closed",
                "legacy_episode_id": legacy_episode_id(city_key, start, end),
                "canonicalization_version": CANONICALIZATION_VERSION,
            }
        )
    return rows, errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vadimkin-csv", required=True)
    parser.add_argument("--site-prod-sha", required=True)
    parser.add_argument("--vadimkin-sha", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    dashboard = json.loads((DATA_DIR / "dashboard_data.json").read_text(encoding="utf-8"))
    production_keys = list(dashboard.get("multicity_meta", {}).get("production_city_keys", []))
    _install_frozen_vadimkin(Path(args.vadimkin_csv).read_bytes())

    by_city, boundary_inputs = _build_production_boundary(dashboard)

    per_city: dict[str, Any] = {}
    episodes: list[dict[str, Any]] = []
    boundary_errors: list[dict[str, Any]] = []
    legacy_ids: set[str] = set()

    for city_key in production_keys:
        alerts = by_city[city_key]
        city_rows, city_errors = _episode_rows(city_key, alerts)
        for error in city_errors:
            boundary_errors.append({"city_key": city_key, **error})

        duplicate_ids = [
            row["legacy_episode_id"]
            for row in city_rows
            if row["legacy_episode_id"] in legacy_ids
        ]
        if duplicate_ids:
            boundary_errors.append(
                {"city_key": city_key, "kind": "duplicate_legacy_episode_id", "ids": duplicate_ids}
            )
        legacy_ids.update(row["legacy_episode_id"] for row in city_rows)

        prod_city = dashboard.get("cities", {}).get(city_key, {})
        meta = prod_city.get("meta", {})
        expected_count = _expected_count(meta, city_key)
        count_match = expected_count == len(city_rows)
        if not count_match:
            boundary_errors.append(
                {
                    "city_key": city_key,
                    "kind": "production_episode_count_mismatch",
                    "expected": expected_count,
                    "actual": len(city_rows),
                }
            )

        generated_at = meta.get("generated_at")
        if not generated_at:
            raise RuntimeError(f"{city_key}: missing production generated_at")
        rebuilt = update_data.build_outputs(
            alerts,
            datetime.fromisoformat(str(generated_at)),
            {},
        )
        expected_daily = _daily_signature(prod_city.get("daily28", []))
        actual_daily = _daily_signature(rebuilt.get("daily28", []))
        daily_match = expected_daily == actual_daily
        if not daily_match:
            boundary_errors.append(
                {
                    "city_key": city_key,
                    "kind": "production_daily28_mismatch",
                    "expected_sha256": hashlib.sha256(canonical_json(expected_daily).encode("utf-8")).hexdigest(),
                    "actual_sha256": hashlib.sha256(canonical_json(actual_daily).encode("utf-8")).hexdigest(),
                }
            )

        per_city[city_key] = {
            "episode_count": len(city_rows),
            "production_expected_episode_count": expected_count,
            "production_count_match": count_match,
            "first_episode": city_rows[0] if city_rows else None,
            "last_episode": city_rows[-1] if city_rows else None,
            "open_episode_count": sum(1 for row in city_rows if row["episode_state"] == "open"),
            "daily28_parity": daily_match,
        }
        episodes.extend(city_rows)

    serial_for_hash = {
        "canonicalization_version": CANONICALIZATION_VERSION,
        "production_city_keys": production_keys,
        "episodes": episodes,
    }
    corpus_hash = hashlib.sha256(canonical_json(serial_for_hash).encode("utf-8")).hexdigest()

    result = {
        "proof_kind": "multicity_canonical_boundary",
        "production_frozen_site_prod_sha": args.site_prod_sha,
        "vadimkin_frozen_sha": args.vadimkin_sha,
        "canonical_boundary": {
            "source": "current production builder boundary before aggregation",
            "kyiv": "data/alerts_combined.json via update_data.parse_committed_alerts",
            "kharkiv_zaporizhzhia": "add_duration_unit_switch.fetch_city_alerts + apply_ukrainealarm_bridge.union_alerts",
            "proxy_cities": "expand_multicity_production.fetch_proxy_alerts_with_phase1 / extend_remaining_proxies.configure_all_proxies + apply_ukrainealarm_bridge.union_alerts",
            "sevastopol": "data/sevastopol_events.json retained complete pairs",
            "bridge_store": "data/ukrainealarm_bridge.json",
        },
        "canonicalization_version": CANONICALIZATION_VERSION,
        "canonicalization_version_guard": {
            "same_overlap_touch_union_semantics": True,
            "final_sets_are_merge_fixed_points": not any(
                error.get("kind") == "overlap_or_touch_not_canonical"
                for error in boundary_errors
            ),
        },
        "production_city_keys": production_keys,
        "city_count": len(production_keys),
        "per_city": per_city,
        "total_episode_count": len(episodes),
        "open_episode_count": sum(1 for row in episodes if row["episode_state"] == "open"),
        "corpus_sha256": corpus_hash,
        "source_provenance": {
            "coverage": "partial",
            "explanation": (
                "The production boundary exposes final canonical intervals losslessly, but does not expose "
                "a uniform lossless source-observation record for every contributing source/city. "
                "This proof therefore does not fabricate alert_episode_sources for newly persisted parent episodes."
            ),
        },
        "input_diagnostics": boundary_inputs,
        "boundary_errors": boundary_errors,
        "boundary_proven": (
            len(production_keys) == 23
            and len(set(production_keys)) == 23
            and not boundary_errors
            and all(v["production_count_match"] for v in per_city.values())
            and all(v["daily28_parity"] for v in per_city.values())
        ),
        "episodes": episodes,
    }

    Path(args.output).write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    safe = {
        "boundary_proven": result["boundary_proven"],
        "city_count": result["city_count"],
        "total_episode_count": result["total_episode_count"],
        "open_episode_count": result["open_episode_count"],
        "corpus_sha256": result["corpus_sha256"],
        "per_city_counts": {
            key: value["episode_count"] for key, value in per_city.items()
        },
        "boundary_error_count": len(boundary_errors),
        "boundary_errors": boundary_errors,
    }
    print(json.dumps(safe, ensure_ascii=False, indent=2, sort_keys=True))
    if not result["boundary_proven"]:
        raise SystemExit("MULTICITY CANONICAL BOUNDARY NOT YET PROVEN")


if __name__ == "__main__":
    main()
