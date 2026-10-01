#!/usr/bin/env python3
"""Ephemeral same-run canonical parent payload for the production DB shadow.

This module has no database dependency. Production builders call record_city_alerts()
with the exact canonical Alert lists they already use for JSON aggregation. When the
payload env is unset, every function is a no-op.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterable

from db_phase1_core import CANONICALIZATION_VERSION, legacy_episode_id, legacy_timestamp

PAYLOAD_ENV = "MULTICITY_CANONICAL_PAYLOAD_PATH"


def payload_path() -> Path | None:
    raw = os.environ.get(PAYLOAD_ENV, "").strip()
    return Path(raw) if raw else None


def _episode(city_key: str, alert: Any) -> dict[str, Any]:
    start = alert.start
    end = alert.end
    return {
        "city_key": city_key,
        "alert_type": "AIR",
        "start_at": legacy_timestamp(start),
        "end_at": legacy_timestamp(end),
        "episode_state": "closed",
        "legacy_episode_id": legacy_episode_id(city_key, start, end),
        "canonicalization_version": CANONICALIZATION_VERSION,
    }


def _read(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "format": "multicity-canonical-same-run-v1",
            "canonicalization_version": CANONICALIZATION_VERSION,
            "cities": {},
        }
    obj = json.loads(path.read_text(encoding="utf-8"))
    if obj.get("format") != "multicity-canonical-same-run-v1":
        raise RuntimeError("unexpected multicity canonical payload format")
    if obj.get("canonicalization_version") != CANONICALIZATION_VERSION:
        raise RuntimeError("canonical payload canonicalization version drift")
    cities = obj.get("cities")
    if not isinstance(cities, dict):
        raise RuntimeError("canonical payload cities must be an object")
    return obj


def record_city_alerts(city_key: str, alerts: Iterable[Any], *, producer: str) -> None:
    path = payload_path()
    if path is None:
        return
    rows = [_episode(city_key, alert) for alert in sorted(alerts, key=lambda x: (x.start, x.end))]
    if not rows:
        raise RuntimeError(f"{city_key}: refusing to record empty canonical alert list")
    obj = _read(path)
    obj["cities"][city_key] = {
        "producer": producer,
        "episode_count": len(rows),
        "episodes": rows,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def load_same_run_payload(path: str | Path) -> dict[str, Any]:
    return _read(Path(path))
