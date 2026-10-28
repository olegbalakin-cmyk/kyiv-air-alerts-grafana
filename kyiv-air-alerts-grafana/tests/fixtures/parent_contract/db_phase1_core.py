#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

UTC = timezone.utc
CANONICALIZATION_VERSION = "alert-canonicalization-v1"

SOURCE_KEYS = {
    "ukrainealarm": "ukrainealarm_region_history",
    "alerts_in_ua": "alerts_in_ua",
    "vadimkin": "vadimkin_official_data_uk",
}
SOURCE_KEY_VERSIONS = {
    "ukrainealarm_region_history": "ukrainealarm-region-history-v1",
    "alerts_in_ua": "alerts-in-ua-v1",
    "vadimkin_official_data_uk": "vadimkin-official-data-uk-v1",
}


def normalize_text(value: Any) -> str:
    return unicodedata.normalize("NFC", str(value)).strip()


def parse_timestamp(value: str) -> datetime:
    text = normalize_text(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        raise ValueError(f"Expected timezone-aware timestamp, got {value!r}")
    return dt.astimezone(UTC)


def source_key_timestamp(value: str | datetime) -> str:
    dt = value if isinstance(value, datetime) else parse_timestamp(value)
    if dt.tzinfo is None:
        raise ValueError("Timestamp must be timezone-aware")
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def legacy_timestamp(value: str | datetime) -> str:
    dt = value if isinstance(value, datetime) else parse_timestamp(value)
    if dt.tzinfo is None:
        raise ValueError("Timestamp must be timezone-aware")
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def canonical_json(obj: Any) -> str:
    return json.dumps(
        obj,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _digest(preimage: dict[str, Any]) -> tuple[str, str]:
    text = canonical_json(preimage)
    return text, hashlib.sha256(text.encode("utf-8")).hexdigest()


def ukrainealarm_source_record_key(fields: dict[str, Any]) -> tuple[str, str]:
    preimage = {
        "version": SOURCE_KEY_VERSIONS["ukrainealarm_region_history"],
        "city_key": normalize_text(fields["city_key"]),
        "region_id": normalize_text(fields["region_id"]),
        "alert_type": normalize_text(fields["alert_type"]),
        "start_at": source_key_timestamp(fields["start_at"]),
        "end_at": source_key_timestamp(fields["end_at"]),
    }
    return _digest(preimage)


def alerts_in_ua_source_record_key(fields: dict[str, Any]) -> tuple[str, str]:
    preimage = {
        "version": SOURCE_KEY_VERSIONS["alerts_in_ua"],
        "city_key": normalize_text(fields["city_key"]),
        "alert_type": normalize_text(fields["alert_type"]),
        "start_at": source_key_timestamp(fields["start_at"]),
        "end_at": source_key_timestamp(fields["end_at"]),
    }
    return _digest(preimage)


def vadimkin_source_record_key(fields: dict[str, Any]) -> tuple[str, str]:
    preimage = {
        "version": SOURCE_KEY_VERSIONS["vadimkin_official_data_uk"],
        "level": normalize_text(fields.get("level", "")),
        "oblast": normalize_text(fields.get("oblast", "")),
        "raion": normalize_text(fields.get("raion", "")),
        "hromada": normalize_text(fields.get("hromada", "")),
        "source": normalize_text(fields.get("source", "")),
        "start_at": source_key_timestamp(fields["start_at"]),
        "end_at": source_key_timestamp(fields["end_at"]),
    }
    return _digest(preimage)


def legacy_episode_id(city_key: str, start_at: str | datetime, end_at: str | datetime) -> str:
    payload = f"{city_key}|{legacy_timestamp(start_at)}|{legacy_timestamp(end_at)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


@dataclass(frozen=True)
class Interval:
    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise ValueError("Interval timestamps must be aware")
        if self.end <= self.start:
            raise ValueError("Interval end must be after start")


def merge_intervals(intervals: Iterable[Interval]) -> list[Interval]:
    xs = sorted(intervals, key=lambda x: (x.start, x.end))
    out: list[Interval] = []
    for interval in xs:
        if not out or interval.start > out[-1].end:
            out.append(interval)
        elif interval.end > out[-1].end:
            out[-1] = Interval(out[-1].start, interval.end)
    return out


def intervals_overlap_or_touch(a: Interval, b: Interval) -> bool:
    return a.start <= b.end and b.start <= a.end


def reconcile_api_manual(
    api: dict[str, Any], manual: dict[str, Any], tolerance_seconds: float = 15.0
) -> dict[str, Any]:
    if normalize_text(api["city_key"]) != normalize_text(manual["city_key"]):
        return {"matched": False, "reason": "different_city"}
    if normalize_text(api["alert_type"]).upper() != normalize_text(manual["alert_type"]).upper():
        return {"matched": False, "reason": "different_alert_type"}
    if normalize_text(api["alert_type"]).upper() != "AIR":
        return {"matched": False, "reason": "not_air"}

    api_start, api_end = parse_timestamp(api["start_at"]), parse_timestamp(api["end_at"])
    manual_start, manual_end = parse_timestamp(manual["start_at"]), parse_timestamp(manual["end_at"])
    start_delta_ms_exact = round((manual_start - api_start).total_seconds() * 1000.0, 6)
    end_delta_ms_exact = round((manual_end - api_end).total_seconds() * 1000.0, 6)
    if abs(start_delta_ms_exact) > tolerance_seconds * 1000:
        return {"matched": False, "reason": "start_tolerance", "start_delta_ms_exact": start_delta_ms_exact, "end_delta_ms_exact": end_delta_ms_exact}
    if abs(end_delta_ms_exact) > tolerance_seconds * 1000:
        return {"matched": False, "reason": "end_tolerance", "start_delta_ms_exact": start_delta_ms_exact, "end_delta_ms_exact": end_delta_ms_exact}

    return {
        "matched": True,
        "sign_convention": "manual_minus_api",
        "start_delta_ms_exact": start_delta_ms_exact,
        "end_delta_ms_exact": end_delta_ms_exact,
        "start_delta_ms": int(round(start_delta_ms_exact)),
        "end_delta_ms": int(round(end_delta_ms_exact)),
        "effective_start_at": source_key_timestamp(api_start),
        "effective_end_at": source_key_timestamp(api_end),
        "api_role": "canonical_input",
        "manual_role": "duplicate_alias",
    }
