"""Fail-closed, owner-accepted historical AIR source corrections.

These rules correct source observations *before* union, aggregation and DB shadow.
A previously-corrected source is an idempotent no-op. Unrecognized source
versions fail rather than silently changing the wrong historical episode.
"""
from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CORRECTIONS_FILE = Path(__file__).resolve().parents[1] / "data" / "owner_accepted_air_corrections.json"
EXPECTED_CASE = "C4-KH-06"
EXPECTED_EXPORT_SHA256 = "dd70213acb7561d0e2cb0e7083f3bd57fcac8d835d20059cc456679942de4b23"
EXPECTED_CITY = "kharkiv"
EXPECTED_TERRITORY = "м. Харків та Харківська територіальна громада"


def _utc(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        raise ValueError("Historical correction timestamp must carry an explicit timezone")
    return dt.astimezone(timezone.utc)


def apply_owner_accepted_air_corrections(
    alerts_by_city: dict[str, list[Any]],
    correction_file: Path = CORRECTIONS_FILE,
) -> int:
    """Correct one pinned exact-city source row; return 1 on change, 0 if already correct."""
    correction = json.loads(correction_file.read_text(encoding="utf-8"))
    if correction.get("schema") != "owner-accepted-historical-city-air-correction-v1":
        raise ValueError("Unknown owner-accepted historical correction schema")
    if correction.get("case") != EXPECTED_CASE or correction.get("city_key") != EXPECTED_CITY:
        raise ValueError("Unexpected historical correction case or city")
    if correction.get("hromada") != EXPECTED_TERRITORY or correction.get("event_type") != "AIR":
        raise ValueError("Historical correction geography/type mismatch")
    if correction.get("source", {}).get("raw_html_sha256") != EXPECTED_EXPORT_SHA256:
        raise ValueError("Historical correction raw Telegram proof mismatch")
    if correction.get("source", {}).get("air_on_message_id") != 131515 or correction.get("source", {}).get("air_off_message_id") != 131583:
        raise ValueError("Historical correction Telegram event identity mismatch")
    old = correction["expected_previous_interval"]
    accepted = correction["accepted_interval"]
    start = _utc(old["start_at"])
    old_end = _utc(old["end_at"])
    new_start = _utc(accepted["start_at"])
    new_end = _utc(accepted["end_at"])
    if (
        start != datetime.fromisoformat("2025-03-05T19:08:24+00:00")
        or old_end != datetime.fromisoformat("2025-03-05T19:47:55+00:00")
        or new_end != datetime.fromisoformat("2025-03-06T03:28:47+00:00")
        or new_start != start or new_end <= old_end
    ):
        raise ValueError("Historical correction pinned UTC boundaries changed")
    city_alerts = alerts_by_city.get(EXPECTED_CITY)
    if not isinstance(city_alerts, list):
        raise ValueError("Historical correction city is missing")
    indexes = [i for i, a in enumerate(city_alerts) if a.start.astimezone(timezone.utc) == start]
    if len(indexes) != 1:
        raise ValueError(f"Historical correction expected one city AIR start; found {len(indexes)}")
    idx = indexes[0]
    current = city_alerts[idx]
    current_end = current.end.astimezone(timezone.utc)
    if current_end == new_end:
        return 0
    if current_end != old_end:
        raise ValueError("Historical correction upstream source ended at an unexpected timestamp")
    for i, other in enumerate(city_alerts):
        if i == idx:
            continue
        if other.start.astimezone(timezone.utc) < new_end and other.end.astimezone(timezone.utc) > start:
            raise ValueError("Historical correction overlaps another original city alert; review before merge")
    city_alerts[idx] = replace(current, end=new_end)
    return 1
