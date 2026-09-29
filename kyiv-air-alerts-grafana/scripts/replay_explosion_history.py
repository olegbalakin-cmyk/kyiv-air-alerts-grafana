#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import copy
import hashlib
import importlib.util
import json
import os
import re
import socket
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

KYIV_TZ = ZoneInfo("Europe/Kyiv")
DEFAULT_THROUGH = "2026-09-17"
PROTECTED_RELATIVE = (
    "data/explosion_audited_baseline.json",
    "data/explosion_review_queue.json",
    "data/explosion_candidate_monitor_state.json",
    "data/explosion_candidate_monitor_last_run.json",
    "data/explosions_test.json",
    "data/dashboard_data.json",
)
REQUIRED_CATEGORIES = (
    "UNCHANGED_STRICT",
    "UNCHANGED_NON_STRICT",
    "NEW_STRICT",
    "STRICT_DOWNGRADE",
    "STRICT_TO_SENSITIVITY",
    "SENSITIVITY_TO_STRICT",
    "NEW_SENSITIVITY",
    "NEW_AMBIGUOUS",
    "UNREPLAYABLE_MISSING_EVIDENCE",
    "LEGACY_MULTI_EVENT_SPLIT",
)
CONTROL_EXPECTATIONS = {
    "2c5bbc0aeba9e25e4eec7b09": False,
    "7a7da068c0efb7be80bd45e4": False,
    "eb2580c2bec54ddc2e36eaf7": False,
    "a60d817eaa9253200f090720": False,
    "c894e85e407dc4256d8c4419": True,
    "e97e6e816f96832d02c8b2cd": True,
    "f235928c329ca806d9dca5ed": True,
}
START_FIELDS = (
    "matched_episode_start",
    "matched_alert_episode_start",
    "alert_episode_start",
    "alert_start",
    "alert_start_kyiv",
    "alert_start_local",
    "matched_alert_start",
    "matched_alert_start_kyiv",
    "episode_start",
    "matched_start",
)
LEGACY_START_FIELDS = (
    "alert_episode_start_kyiv",
    "alert_start_utc",
)
EVENT_TIME_FIELDS = (
    "event_time",
    "event_time_kyiv",
    "event_time_local",
)
RECORDED_DATE_FIELDS = (
    "alert_start_date",
    "episode_start_date",
    "matched_episode_start_date_kyiv",
    "local_date",
)
EVIDENCE_FIELDS = ("evidence", "evidence_text", "text", "excerpt", "quote")
BASIS_FIELDS = ("decision_basis", "basis", "decision", "reason")


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def git_output(checkout_root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(checkout_root), *args], text=True).strip()


def git_head(checkout_root: Path) -> str:
    return git_output(checkout_root, "rev-parse", "HEAD")


def git_blob(checkout_root: Path, rel: str) -> str | None:
    try:
        return git_output(checkout_root, "rev-parse", f"HEAD:{rel}")
    except subprocess.CalledProcessError:
        return None


def sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def protected_snapshot(repo_root: Path) -> dict[str, str | None]:
    return {rel: sha256_file(repo_root / rel) for rel in PROTECTED_RELATIVE}


def ensure_output_outside_checkout(output: Path, checkout_root: Path) -> None:
    out = output.resolve()
    root = checkout_root.resolve()
    try:
        out.relative_to(root)
    except ValueError:
        return
    raise SystemExit(f"Refusing to write replay output inside frozen checkout: {out}")


@contextlib.contextmanager
def network_blocked():
    original_connect = socket.socket.connect
    original_create = socket.create_connection
    requests_original = None

    def blocked(*_args, **_kwargs):
        raise RuntimeError("NETWORK_DISABLED_DURING_HISTORICAL_REPLAY")

    socket.socket.connect = blocked
    socket.create_connection = blocked
    try:
        try:
            import requests
            requests_original = requests.sessions.Session.request
            requests.sessions.Session.request = blocked
        except Exception:
            requests = None
        yield
    finally:
        socket.socket.connect = original_connect
        socket.create_connection = original_create
        if requests_original is not None:
            import requests
            requests.sessions.Session.request = requests_original


def import_monitor(repo_root: Path):
    scripts = repo_root / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    path = scripts / "monitor_explosion_candidates.py"
    spec = importlib.util.spec_from_file_location("frozen_explosion_monitor", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import monitor from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def local_day(value: str | None, monitor=None) -> str | None:
    if not value:
        return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(value).strip()):
        return str(value).strip()
    dt = parse_historical_datetime(value, monitor)
    return dt.astimezone(KYIV_TZ).date().isoformat() if dt else None


def parse_historical_datetime(value, monitor=None) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    clean = text.replace("~", "").strip()
    clean = re.sub(r"\s+Europe/Kyiv.*$", "", clean, flags=re.I)
    clean = clean.replace("Z", "+00:00")
    m = re.match(r"^(\d{4}-\d{2}-\d{2})(?:[T ](\d{2}:\d{2})(?::(\d{2}(?:\.\d+)?))?(?:\s*([+-]\d{2}:?\d{2}))?)?", clean)
    if not m:
        return None
    day, hm, sec, offset = m.groups()
    if hm is None:
        return None
    sec = sec or "00"
    iso_text = f"{day}T{hm}:{sec}"
    if offset:
        if len(offset) == 5 and ":" not in offset:
            offset = offset[:3] + ":" + offset[3:]
        iso_text += offset
    try:
        dt = datetime.fromisoformat(iso_text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=KYIV_TZ)
    return dt


def episode_index(episodes: list[dict]) -> tuple[dict[str, dict], dict[str, list[dict]]]:
    by_id = {}
    by_day: dict[str, list[dict]] = defaultdict(list)
    for ep in episodes:
        eid = str(ep.get("episode_id") or "")
        if not eid:
            continue
        by_id[eid] = ep
        day = ep.get("alert_start_date_kyiv") or local_day(ep.get("alert_start"))
        if day:
            by_day[str(day)].append(ep)
    for rows in by_day.values():
        rows.sort(key=lambda x: (str(x.get("alert_start") or ""), str(x.get("episode_id") or "")))
    return by_id, by_day


def parse_temporal_field_datetime(value, field: str, monitor) -> datetime | None:
    dt = parse_historical_datetime(value, monitor)
    if dt is None:
        return None
    text = str(value).strip()
    has_explicit_zone = bool(
        re.search(r"(?:Z|[+-]\d{2}:?\d{2}|Europe/Kyiv)\b", text, flags=re.I)
    )
    if not has_explicit_zone and field == "alert_start_utc":
        return dt.replace(tzinfo=monitor.UTC)
    if not has_explicit_zone and field in {
        "alert_episode_start_kyiv",
        "event_time_kyiv",
        "event_time_local",
    }:
        return dt.replace(tzinfo=KYIV_TZ)
    return dt


def retained_local_date(row: dict, monitor) -> str | None:
    for field in START_FIELDS + LEGACY_START_FIELDS + RECORDED_DATE_FIELDS:
        value = row.get(field)
        if not value:
            continue
        text = str(value).strip()
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            return text
        dt = parse_temporal_field_datetime(value, field, monitor)
        if dt is not None:
            return dt.astimezone(KYIV_TZ).date().isoformat()
        explicit_day = re.search(r"\b\d{4}-\d{2}-\d{2}\b", text)
        if explicit_day:
            return explicit_day.group(0)
    return None


def retained_event_datetimes(row: dict, monitor) -> list[datetime]:
    result: list[datetime] = []
    seen: set[str] = set()
    full_pattern = re.compile(
        r"\d{4}-\d{2}-\d{2}[T ]\s*~?\s*\d{1,2}:\d{2}"
        r"(?::\d{2}(?:\.\d+)?)?"
        r"(?:\s*(?:Z|[+-]\d{2}:?\d{2}|Europe/Kyiv))?",
        flags=re.I,
    )
    dated_clock_pattern = re.compile(
        r"(?<![\d:])(?P<hour>[01]?\d|2[0-3]):(?P<minute>[0-5]\d)"
        r"(?::(?P<second>[0-5]\d(?:\.\d+)?))?"
        r"(?:\s*(?P<zone>Z|[+-]\d{2}:?\d{2}|Europe/Kyiv))?"
        r"\s+(?P<day>\d{4}-\d{2}-\d{2})\b",
        flags=re.I,
    )
    clock_pattern = re.compile(
        r"(?<![\d:])(?P<hour>[01]?\d|2[0-3]):(?P<minute>[0-5]\d)"
        r"(?::(?P<second>[0-5]\d(?:\.\d+)?))?"
        r"(?:\s*(?P<zone>Z|[+-]\d{2}:?\d{2}|Europe/Kyiv))?",
        flags=re.I,
    )
    anchor_day = retained_local_date(row, monitor)

    def add(dt: datetime | None) -> None:
        if dt is None:
            return
        key = dt.astimezone(monitor.UTC).isoformat()
        if key not in seen:
            seen.add(key)
            result.append(dt)

    def clock_token(match, day: str) -> str:
        second = match.group("second")
        clock = f'{int(match.group("hour")):02d}:{match.group("minute")}'
        clock += f":{second}" if second else ":00"
        zone = (match.group("zone") or "").strip()
        return f"{day}T{clock}{zone}"

    for field in EVENT_TIME_FIELDS:
        value = row.get(field)
        if not value:
            continue
        text = str(value).strip()
        spans = []
        for match in full_pattern.finditer(text):
            spans.append(match.span())
            normalized = re.sub(r"([T ])\s*~\s*", r"\1", match.group(0), count=1)
            add(parse_temporal_field_datetime(normalized, field, monitor))
        for match in dated_clock_pattern.finditer(text):
            spans.append(match.span())
            add(parse_temporal_field_datetime(clock_token(match, match.group("day")), field, monitor))

        if not anchor_day:
            continue
        residual = list(text)
        for a, b in spans:
            for idx in range(a, b):
                residual[idx] = " "
        residual_text = "".join(residual)
        for match in clock_pattern.finditer(residual_text):
            add(parse_temporal_field_datetime(clock_token(match, anchor_day), field, monitor))
    return result


def historical_record_id(city: str, bucket: str, index: int, row: dict) -> str:
    """Stable identity for one retained legacy evidence parent row."""
    canonical = json.dumps(
        row,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    seed = f"{city}|{bucket}|{index}|{canonical}"
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:24]


def _has_discrete_multi_event_time_list(row: dict) -> bool:
    """Require an explicit list, not a vague interval or publication clock."""
    clock = r"(?:[01]?\d|2[0-3]):[0-5]\d"
    for field in EVENT_TIME_FIELDS:
        value = row.get(field)
        if not value:
            continue
        text = str(value)
        if len(re.findall(clock, text)) < 2:
            continue
        if ";" in text:
            return True
        if re.search(
            rf"{clock}\s*(?:,|\b(?:і|та|and)\b)\s*(?:[^0-9]{{0,12}})?{clock}",
            text,
            flags=re.I,
        ):
            return True
    return False


def _event_segment_for_time(row: dict, event_dt: datetime, monitor) -> str:
    evidence = " — ".join(
        str(row.get(key)).strip()
        for key in EVIDENCE_FIELDS
        if row.get(key) and str(row.get(key)).strip()
    )
    if not evidence:
        return ""
    local = event_dt.astimezone(KYIV_TZ)
    clocks = {
        local.strftime("%H:%M"),
        f"{local.hour}:{local.strftime('%M')}",
    }
    segments = [
        " ".join(part.split())
        for part in re.split(r"(?<=[.!?;])\s+|\n+", evidence)
        if part and part.strip()
    ]
    matching = [
        segment
        for segment in segments
        if any(clock in segment for clock in clocks)
    ]
    if not matching:
        return ""
    return next(
        (segment for segment in matching if monitor.strict_attack_event_signal(segment)),
        matching[0],
    )


def expand_historical_evidence_observations(
    city: str,
    bucket: str,
    index: int,
    row: dict,
    episodes: list[dict],
    monitor,
    allow_new_temporal_fallback: bool = True,
) -> list[dict]:
    """Normalize one retained parent row into zero/one/many event-level observations.

    Splitting is intentionally narrow:
    - the ordinary binder must be blocked by multi-time containment;
    - the retained event-time field must be an explicit discrete list;
    - each child is tied to one retained clock and a source-evidence segment;
    - publication timestamps are never consulted;
    - identical event clocks are deduplicated before child creation.
    """
    parent_id = historical_record_id(city, bucket, index, row)
    initial = bind_evidence_record(
        row,
        episodes,
        monitor,
        allow_new_temporal_fallback=allow_new_temporal_fallback,
    )
    ordinary = {
        "parent_record_id": parent_id,
        "observation_id": parent_id,
        "is_split_child": False,
        "event_fact_present": None,
        "event_time_utc": None,
        "event_evidence": None,
        "row": row,
        "binding": initial,
    }
    if initial.get("episode_id"):
        return [ordinary]
    if initial.get("method") != "event_time_ambiguous_containment":
        return [ordinary]
    if not _has_discrete_multi_event_time_list(row):
        return [ordinary]

    event_times = retained_event_datetimes(row, monitor)
    if len(event_times) < 2:
        return [ordinary]

    children = []
    seen_observations = set()
    for ordinal, event_dt in enumerate(event_times):
        event_utc = event_dt.astimezone(monitor.UTC)
        segment = _event_segment_for_time(row, event_dt, monitor)
        event_fact_present = bool(
            segment and monitor.strict_attack_event_signal(segment)
        )
        observation_seed = (
            f"{parent_id}|{event_utc.isoformat()}|{segment}"
        )
        observation_id = hashlib.sha256(
            observation_seed.encode("utf-8")
        ).hexdigest()[:24]
        if observation_id in seen_observations:
            continue
        seen_observations.add(observation_id)

        child = copy.deepcopy(row)
        for field in EVENT_TIME_FIELDS:
            child.pop(field, None)
        child["event_time"] = event_dt.astimezone(KYIV_TZ).isoformat()
        if segment:
            for field in EVIDENCE_FIELDS:
                child.pop(field, None)
            child["evidence"] = segment
        child["_historical_parent_record"] = copy.deepcopy(row)
        child["_historical_parent_record_id"] = parent_id
        child["_historical_event_observation_id"] = observation_id
        child["_historical_event_ordinal"] = ordinal
        child["_historical_event_time_utc"] = event_utc.isoformat()

        binding = bind_evidence_record(
            child,
            episodes,
            monitor,
            allow_new_temporal_fallback=allow_new_temporal_fallback,
        )
        binding = dict(binding)
        binding.update({
            "parent_record_id": parent_id,
            "observation_id": observation_id,
            "split_reason": "explicit_retained_multi_event_list",
            "event_time_utc": event_utc.isoformat(),
        })
        children.append({
            "parent_record_id": parent_id,
            "observation_id": observation_id,
            "is_split_child": True,
            "event_fact_present": event_fact_present,
            "event_time_utc": event_utc.isoformat(),
            "event_evidence": segment,
            "row": child,
            "binding": binding,
        })

    if len(children) < 2 or not any(
        child["event_fact_present"] for child in children
    ):
        return [ordinary]
    return children


def bind_start_datetime(
    dt: datetime,
    episodes: list[dict],
    monitor,
    success_method: str | None = None,
) -> dict:
    exact = []
    dt_utc = dt.astimezone(monitor.UTC)
    for ep in episodes:
        start = monitor.parse_dt(ep.get("alert_start"))
        if start and abs((start - dt_utc).total_seconds()) <= 90:
            exact.append(ep)
    if len(exact) == 1:
        return {
            "episode_id": str(exact[0]["episode_id"]),
            "method": success_method or "alert_start_within_90s",
            "candidates": [str(exact[0]["episode_id"])],
        }

    minute = dt.astimezone(KYIV_TZ).strftime("%Y-%m-%dT%H:%M")
    minute_rows = []
    for ep in episodes:
        start = monitor.parse_dt(ep.get("alert_start"))
        if start and start.astimezone(KYIV_TZ).strftime("%Y-%m-%dT%H:%M") == minute:
            minute_rows.append(ep)
    if len(minute_rows) == 1:
        return {
            "episode_id": str(minute_rows[0]["episode_id"]),
            "method": success_method or "alert_start_same_local_minute",
            "candidates": [str(minute_rows[0]["episode_id"])],
        }
    return {
        "episode_id": None,
        "method": "ambiguous_alert_start",
        "candidates": [str(ep["episode_id"]) for ep in (exact or minute_rows)],
    }


def legacy_start_alias_binding(row: dict, episodes: list[dict], monitor) -> dict | None:
    failures = []
    for field in LEGACY_START_FIELDS:
        value = row.get(field)
        if not value:
            continue
        dt = parse_temporal_field_datetime(value, field, monitor)
        if dt is None:
            continue
        bound = bind_start_datetime(dt, episodes, monitor, "legacy_start_alias")
        bound["binding_field"] = field
        if bound.get("episode_id"):
            return bound
        failures.append(bound)
    if failures:
        candidates = sorted({
            eid
            for failure in failures
            for eid in failure.get("candidates") or []
        })
        return {
            "episode_id": None,
            "method": "ambiguous_legacy_start_alias",
            "candidates": candidates,
        }
    return None


def event_time_unique_containment_binding(row: dict, episodes: list[dict], monitor) -> dict | None:
    event_times = retained_event_datetimes(row, monitor)
    if not event_times:
        return None

    per_time_candidates: list[list[str]] = []
    all_candidates: set[str] = set()
    for event_dt in event_times:
        event_utc = event_dt.astimezone(monitor.UTC)
        matches = []
        for ep in episodes:
            start = monitor.parse_dt(ep.get("alert_start"))
            end = monitor.parse_dt(ep.get("alert_end"))
            if start and end and start <= event_utc <= end:
                matches.append(str(ep["episode_id"]))
        per_time_candidates.append(sorted(matches))
        all_candidates.update(matches)

    if len(all_candidates) == 1 and all(
        candidates == sorted(all_candidates) for candidates in per_time_candidates
    ):
        target = next(iter(all_candidates))
        return {
            "episode_id": target,
            "method": "event_time_unique_containment",
            "candidates": [target],
            "event_times_utc": [
                dt.astimezone(monitor.UTC).isoformat() for dt in event_times
            ],
        }

    method = (
        "event_time_no_containing_episode"
        if not all_candidates
        else "event_time_ambiguous_containment"
    )
    return {
        "episode_id": None,
        "method": method,
        "candidates": sorted(all_candidates),
        "event_times_utc": [
            dt.astimezone(monitor.UTC).isoformat() for dt in event_times
        ],
        "per_time_candidates": per_time_candidates,
    }


def bind_evidence_record(
    row: dict,
    episodes: list[dict],
    monitor,
    allow_new_temporal_fallback: bool = True,
) -> dict:
    by_id, by_day = episode_index(episodes)
    explicit_id = str(
        row.get("episode_id")
        or row.get("matched_episode_id")
        or row.get("alert_episode_id")
        or ""
    )
    if explicit_id:
        if explicit_id in by_id:
            result = {
                "episode_id": explicit_id,
                "method": "persisted_episode_id",
                "candidates": [explicit_id],
            }
            if allow_new_temporal_fallback:
                conflicts = []
                for fallback in (
                    legacy_start_alias_binding(row, episodes, monitor),
                    event_time_unique_containment_binding(row, episodes, monitor),
                ):
                    fallback_id = (fallback or {}).get("episode_id")
                    if fallback_id and fallback_id != explicit_id:
                        conflicts.append({
                            "method": fallback.get("method"),
                            "episode_id": fallback_id,
                        })
                if conflicts:
                    result["temporal_conflicts"] = conflicts
            return result
        return {
            "episode_id": None,
            "method": "unknown_persisted_episode_id",
            "candidates": [explicit_id],
        }

    ordinary_start_failure = None
    raw = next((row.get(k) for k in START_FIELDS if row.get(k)), None)
    dt = parse_historical_datetime(raw, monitor)
    if dt is not None:
        bound = bind_start_datetime(dt, episodes, monitor)
        if bound.get("episode_id"):
            return bound
        ordinary_start_failure = bound
    else:
        day = None
        for field in START_FIELDS + RECORDED_DATE_FIELDS:
            if row.get(field):
                day = local_day(row.get(field), monitor)
                if day:
                    break
        if day:
            rows = by_day.get(day, [])
            if len(rows) == 1:
                return {
                    "episode_id": str(rows[0]["episode_id"]),
                    "method": "unique_episode_on_recorded_local_day",
                    "candidates": [str(rows[0]["episode_id"])],
                }

    if allow_new_temporal_fallback:
        legacy = legacy_start_alias_binding(row, episodes, monitor)
        if legacy and legacy.get("episode_id"):
            return legacy

        event_binding = event_time_unique_containment_binding(row, episodes, monitor)
        if event_binding and event_binding.get("episode_id"):
            return event_binding

        if event_binding is not None:
            return event_binding
        if legacy is not None:
            return legacy
    if ordinary_start_failure is not None:
        return ordinary_start_failure

    day = None
    for field in START_FIELDS + RECORDED_DATE_FIELDS:
        if row.get(field):
            day = local_day(row.get(field), monitor)
            if day:
                break
    if day:
        rows = by_day.get(day, [])
        return {
            "episode_id": None,
            "method": "ambiguous_local_day",
            "candidates": [str(ep["episode_id"]) for ep in rows],
        }
    return {"episode_id": None, "method": "missing_episode_binding", "candidates": []}


def evidence_text(row: dict) -> str:
    parts = []
    for key in EVIDENCE_FIELDS + BASIS_FIELDS:
        value = row.get(key)
        if value and str(value).strip() not in parts:
            parts.append(str(value).strip())
    return " — ".join(parts)


def ppo_related(text: str) -> bool:
    return bool(re.search(r"\b(?:ппо|протиповітрян|air[ -]?defen[cs]e)\b", text.casefold()))


def history_status(row: dict, bucket: str) -> str:
    if bucket == "strict_events":
        return "STRICT"
    if bucket == "sensitivity_only_events":
        return "SENSITIVITY"
    return "AMBIGUOUS"


def historical_review_roles(city: str, row: dict, monitor) -> tuple[dict, str]:
    evidence_parts = []
    for key in EVIDENCE_FIELDS:
        value = row.get(key)
        if value and str(value).strip() not in evidence_parts:
            evidence_parts.append(str(value).strip())
    evidence = " — ".join(evidence_parts)
    if not evidence:
        return {}, evidence

    low = evidence.casefold()
    exact_city = False
    explosion = False
    air_context = False
    direct_event_segment = None
    direct_event_type = None
    direct_event_basis = None
    conflicting_named_city = False

    if city == "sevastopol":
        # Sevastopol's frozen final_evidence corpus stores reviewed factual
        # summaries in English.
        exact_city = bool(re.search(r"\bsevastopol\b", low))
        explosion = bool(
            re.search(r"\b(?:explosion(?:s)?|blast(?:s)?|bang(?:s)?)\b", low)
        )
        air_context = bool(
            re.search(
                r"\b(?:air alert|alerts?|alarm|sirens?|aerial|missile(?:s)?|"
                r"drone(?:s)?|air[- ]?defen[cs]e|attack|rocket(?:s)?)\b",
                low,
            )
        )
    elif city == "cherkasy":
        # Cherkasy retained audit rows sometimes contain reviewed factual-role
        # annotations that the historical adapter previously discarded.
        # Do not infer roles merely from the historical strict bucket.
        review_parts = [
            str(row.get(key)).strip()
            for key in BASIS_FIELDS
            if row.get(key) and str(row.get(key)).strip()
        ]
        review_basis = " — ".join(review_parts)
        review_low = review_basis.casefold()
        reviewed_factual_contract = bool(
            "aerial_war" in review_low
            or "aerial-war" in review_low
            or "missile-attack context" in review_low
        )
        reviewed_cross_segment_contract = str(row.get("basis") or "").strip().casefold() in {
            "exact_city_time_inside_alert",
            "exact_city_timed_inside_alert",
        }
        if not (reviewed_factual_contract or reviewed_cross_segment_contract):
            return {}, evidence

        cherkasy_named = re.compile(
            r"(?<![\w-])(?:cherkasy|черкаси|черкасах|черкасами)(?![\w-])",
            flags=re.IGNORECASE,
        )
        english_explosion = re.compile(
            r"\b(?:explosion(?:s)?|blast(?:s)?|bang(?:s)?)\b",
            flags=re.IGNORECASE,
        )
        english_air = re.compile(
            r"\b(?:air alert|aerial|missile(?:s)?|drone(?:s)?|uav(?:s)?|"
            r"strike[- ]?uav|air[- ]?defen[cs]e|missile[- ]?danger)\b",
            flags=re.IGNORECASE,
        )

        def cherkasy_genitive_event(segment: str) -> bool:
            segment_low = segment.casefold()
            return bool(
                re.search(
                    r"\bжителі\s+черкас\b.{0,80}\b(?:чул\w*|чут\w*)\b"
                    r".{0,35}\bвибух\w*",
                    segment_low,
                )
            )

        def city_event_local(segment: str) -> bool:
            return bool(cherkasy_named.search(segment) or cherkasy_genitive_event(segment))

        def reviewed_attack_event(segment: str) -> bool:
            return bool(monitor.strict_explosion_signal(segment) or english_explosion.search(segment))

        def reviewed_air_context(segment: str) -> bool:
            return bool(monitor.air_military_context(segment) or english_air.search(segment))

        segments = [
            " ".join(part.split())
            for part in re.split(r"(?<=[.!?;])\s+|\n+", evidence)
            if part and part.strip()
        ]
        event_segments = [
            (idx, segment)
            for idx, segment in enumerate(segments)
            if city_event_local(segment) and reviewed_attack_event(segment)
        ]
        exact_city = bool(event_segments)
        explosion = bool(event_segments)
        air_context = any(reviewed_air_context(segment) for segment in segments)
        direct_event_segment = next(
            (segment for _, segment in event_segments if reviewed_air_context(segment)),
            None,
        )
        if direct_event_segment:
            direct_event_type = "explosion"
            direct_event_basis = "reviewed_cherkasy_same_segment_factual_roles"

        # Preserve cross-segment same-attack only when the retained reviewed
        # summary contains an explicit relation. Article co-occurrence alone
        # remains insufficient.
        if (
            direct_event_segment is None
            and event_segments
            and air_context
            and not any(
                named_city != "cherkasy"
                for named_city in monitor.audited_cities_in_text(evidence)
            )
        ):
            for event_idx, event_segment in event_segments:
                event_low = event_segment.casefold()
                adjacent = []
                if event_idx > 0:
                    adjacent.append(segments[event_idx - 1])
                if event_idx + 1 < len(segments):
                    adjacent.append(segments[event_idx + 1])
                for context_segment in adjacent:
                    if not reviewed_air_context(context_segment):
                        continue
                    context_low = context_segment.casefold()
                    event_during_attack = bool(
                        re.search(r"\bпід\s+час\s+(?:російськ\w+\s+)?атак\w*", event_low)
                    )
                    context_city_local = bool(
                        cherkasy_named.search(context_segment)
                        or re.search(r"^(?:у|в)\s+міст\w*\b", context_low)
                    )
                    explicit_prior_link = bool(re.search(r"\bперед\s+цим\b", context_low))
                    completed_attack = bool(
                        re.search(
                            r"\b(?:армія\s+рф|місто)\b.{0,35}\bатакув\w*\b",
                            context_low,
                        )
                    )
                    city_anaphora = bool(
                        re.search(r"^(?:у|в)\s+міст\w*\b", context_low)
                        and (
                            "ппо" in context_low
                            or "бпла" in context_low
                            or "дрон" in context_low
                        )
                    )
                    if (
                        event_during_attack
                        or explicit_prior_link
                        or completed_attack
                        or city_anaphora
                    ):
                        direct_event_segment = event_segment
                        direct_event_type = "explosion"
                        direct_event_basis = "reviewed_cherkasy_explicit_cross_segment_same_attack"
                        break
                if direct_event_segment:
                    break

    elif city == "sumy":
        # Sumy's frozen corpus stores reviewed Ukrainian factual summaries.
        # Preserve only facts explicit in the retained summary.
        city_pattern = r"\b(?:сум|суми|сумах|сумами)\b"
        exact_city = bool(re.search(city_pattern, low))
        conflicting_named_city = any(
            named_city != "sumy"
            for named_city in monitor.audited_cities_in_text(evidence)
        )

        adversary = (
            r"(?:рф|росі(?:я|йськ\w*)|ворож\w*|окупант\w*|"
            r"військ\w*\s+рф)"
        )
        attack_negative_or_modal = (
            r"(?:\bне\s+атакув\w*\b|"
            r"\b(?:може|можуть|міг|могла|могли)\b.{0,28}\bатак\w*\b|"
            r"\b(?:можлив\w*|ймовірн\w*|очікуван\w*|прогнозован\w*|"
            r"загроз\w*|планован\w*)\b.{0,35}\bатак\w*\b|"
            r"\bатакуватиме\b|\bатакуватимуть\b|"
            r"\bатак\w*\b.{0,18}\bне\s+бул\w*\b)"
        )
        impact_negative_or_modal = (
            r"(?:\bне\b.{0,20}\bвлучанн\w*\b|"
            r"\bвлучанн\w*\b.{0,28}\bне\b|"
            r"\b(?:можлив\w*|ймовірн\w*|загроз\w*)\b.{0,28}\bвлучанн\w*\b)"
        )
        fall_negative_or_modal = (
            r"(?:\bне\s+(?:упав|впав|пада\w*)\b|"
            r"\b(?:може|можуть|можлив\w*|ймовірн\w*)\b.{0,24}"
            r"\b(?:упасти|впасти|пада\w*)\b)"
        )
        historical_cue = r"\b(?:торік|минул\w*\s+рок\w*|раніше)\b"
        nonmilitary_strike = (
            r"\b(?:теплов\w*|сонячн\w*|страйк\w*|турнір\w*|"
            r"матч\w*|спорт\w*)\b"
        )
        figurative_impact = r"\b(?:десятк\w*|мішен\w*|ціл\w*)\b"
        physical_location = (
            r"\b(?:біля|поблизу|на|у|в)\s+"
            r"(?:дитяч\w*|майданчик\w*|будинк\w*|дороз\w*|"
            r"вулиц\w*|подвір\w*|парк\w*|школ\w*|азс|сто|"
            r"підприємств\w*|сектор\w*|район\w*)"
        )

        # Reviewed summaries can keep exact-city context before a semicolon and
        # the linked factual event after it. A second explicitly named audited
        # city invalidates inheritance of Sumy context.
        for part in evidence_parts:
            for segment in re.split(r"(?<=[.!?])\s+|\n+", part):
                segment = " ".join(segment.split())
                segment_low = segment.casefold()
                if not re.search(city_pattern, segment_low):
                    continue
                mentioned_cities = monitor.audited_cities_in_text(segment)
                if any(named_city != "sumy" for named_city in mentioned_cities):
                    continue
                if re.search(historical_cue, segment_low):
                    continue

                completed_attack = bool(
                    re.search(r"\bатакув(?:ав|ала|ало|али)\b", segment_low)
                    and (
                        re.search(rf"\b{adversary}\b", segment_low)
                        or monitor.air_military_context(segment)
                    )
                )
                attack_noun = bool(
                    re.search(rf"\b{adversary}\b.{{0,45}}\bатак\w*\b", segment_low)
                    or re.search(rf"\bатак\w*\b.{{0,45}}\b{adversary}\b", segment_low)
                )
                adversary_strike = bool(
                    re.search(
                        rf"\b{adversary}\b.{{0,45}}\bудар(?:у|и|ів|ом|ами)?\b",
                        segment_low,
                    )
                    or re.search(
                        rf"\bудар(?:у|и|ів|ом|ами)?\b.{{0,45}}\b{adversary}\b",
                        segment_low,
                    )
                )
                if (
                    (completed_attack or attack_noun or adversary_strike)
                    and not re.search(attack_negative_or_modal, segment_low)
                    and not re.search(nonmilitary_strike, segment_low)
                ):
                    direct_event_segment = segment
                    direct_event_type = "strike"
                    direct_event_basis = (
                        "reviewed_direct_v2_strike_same_statement_exact_city_air_context"
                    )
                    break

                factual_impact_noun = bool(
                    re.search(
                        r"\b(?:зафіксован\w*|ставс\w*|бул\w*)?.{0,24}"
                        r"\bвлучанн\w*\b",
                        segment_low,
                    )
                )
                if (
                    factual_impact_noun
                    and not re.search(impact_negative_or_modal, segment_low)
                    and not re.search(figurative_impact, segment_low)
                ):
                    direct_event_segment = segment
                    direct_event_type = "impact"
                    direct_event_basis = "reviewed_direct_v2_impact_noun_exact_city"
                    break

                enemy_uav_fall = bool(
                    re.search(
                        rf"\b{adversary}\b.{{0,40}}\b(?:дрон\w*|бпла|безпілот\w*)\b"
                        rf".{{0,80}}\b(?:упав|впав)\b",
                        segment_low,
                    )
                    or re.search(
                        rf"\b(?:дрон\w*|бпла|безпілот\w*)\b.{{0,40}}\b{adversary}\b"
                        rf".{{0,80}}\b(?:упав|впав)\b",
                        segment_low,
                    )
                )
                if (
                    enemy_uav_fall
                    and re.search(physical_location, segment_low)
                    and not re.search(fall_negative_or_modal, segment_low)
                ):
                    direct_event_segment = segment
                    direct_event_type = "impact"
                    direct_event_basis = "reviewed_enemy_uav_physical_fall_exact_city"
                    break
            if direct_event_segment:
                break

        explosion = bool(
            monitor.strict_explosion_signal(evidence)
            or re.search(r"\bвдар\w*\b", low)
            or re.search(r"\b(?:ударив|ударила|ударили|ударило)\b", low)
            or re.search(
                r"\b(?:завдав|завдала|завдали|наніс|нанесла|нанесли)\b"
                r".{0,40}\bавіаудар\w*\b",
                low,
            )
            or direct_event_segment
        )
        air_context = bool(
            monitor.air_military_context(evidence)
            or re.search(
                r"\b(?:авіаудар\w*|італмас\w*|геран\w*|ланцет\w*)\b",
                low,
            )
            or direct_event_segment
        )
    elif city == "dnipro":
        # Dnipro's frozen corpus retains reviewed role contracts in decision/
        # basis fields. Translate only those reviewed contracts. Free article
        # text, city naming, publication metadata, proximity, or generic PVO
        # wording alone must never create a replay role.
        review_parts = [
            str(row.get(key)).strip()
            for key in BASIS_FIELDS
            if row.get(key) and str(row.get(key)).strip()
        ]
        review_basis = " — ".join(review_parts)
        review_low = review_basis.casefold()
        reviewed_strict = bool(
            str(row.get("decision") or "").strip().casefold() == "strict"
            or re.search(r"(?:^|[^a-z])strict(?:[^a-z]|$)|strict[_ -]", review_low)
        )
        reviewed_sensitivity = bool(
            "sensitivity" in review_low
            or str(row.get("decision") or "").strip().casefold()
            in {"sensitivity", "sensitivity_only", "sensitivity_inferred_same_attack"}
        )
        if not (reviewed_strict or reviewed_sensitivity):
            return {}, evidence

        reviewed_exact_city = bool(
            re.search(r"\bexact[_ -]?city\b", review_low)
            or "exact-city" in review_low
        )
        reviewed_episode_relation = bool(
            re.search(
                r"(?:timed?[_ -]?inside[_ -]?(?:matched[_ -]?)?(?:alert|episode)|"
                r"exact[_ -]?time[_ -]?inside[_ -]?(?:(?:the|one)[_ -]?)?(?:frozen[_ -]?)?(?:alert|episode)|"
                r"approx(?:imate)?[_ -]?time[_ -]?inside[_ -]?(?:(?:the|one)[_ -]?)?(?:frozen[_ -]?)?(?:alert|episode)|"
                r"event[_ -]?(?:inside|within)[_ -]?(?:(?:the|one)[_ -]?)?(?:frozen[_ -]?)?(?:alert|episode)|"
                r"event[_ -]?during[_ -]?(?:matched[_ -]?)?alert|"
                r"explicit[_ -]?(?:ongoing[_ -]?)?alert|"
                r"explicit[_ -]?during[_ -]?(?:matched[_ -]?)?alert|"
                r"inside[_ -]?(?:one[_ -]?)?(?:alert|episode)|"
                r"matched[_ -]?(?:alert|episode)|"
                r"cross[_ -]?midnight|separate[_ -](?:realert|same[_ -]day|late)[_ -]?episode|"
                r"timed[_ -]?inside[_ -]?proxy[_ -]?alert|"
                r"approximate[_ -]?time[_ -]?inside[_ -]?alert|"
                r"exact[_ -]?city[_ -]?event[_ -]?inside[_ -]?episode|"
                r"inferred[_ -]?same[_ -]?attack|confirmed[_ -]?same[_ -]?attack|"
                r"near[_ -]?boundary|event[_ -]?precedes[_ -]?alert)",
                review_low,
            )
            or (
                ("inside" in review_low or "within" in review_low)
                and ("alert" in review_low or "episode" in review_low)
            )
            or (
                "separate" in review_low
                and ("realert" in review_low or "episode" in review_low)
            )
        )

        reviewed_air_context = bool(
            re.search(
                r"(?:confirmed[_ -]?air[_ -]?war|aerial[_ -]?(?:war|attack|context)|"
                r"(?:drone|uav|missile|ballistic|rocket|shahed)[_ -]?(?:attack|context|threat)?|"
                r"\b(?:бпла|безпілот\w*|дрон\w*|ракет\w*|баліст\w*|шахед\w*|ппо)\b)",
                review_low,
            )
        )
        dnipro_named = re.compile(
            r"(?<![\w-])(?:dnipro|дніпро|дніпрі|дніпра|дніпром)(?![\w-])",
            flags=re.IGNORECASE,
        )
        english_explosion = re.compile(
            r"\b(?:explosion(?:s)?|blast(?:s)?|bang(?:s)?)\b",
            flags=re.IGNORECASE,
        )
        english_impact = re.compile(
            r"\b(?:impact(?:s|ed)?|hit|hits|arrival(?:s)?)\b",
            flags=re.IGNORECASE,
        )
        english_strike = re.compile(
            r"\b(?:strike|strikes|struck)\b",
            flags=re.IGNORECASE,
        )
        specific_air = re.compile(
            r"\b(?:бпла|безпілот\w*|дрон\w*|ракет\w*|баліст\w*|шахед\w*|"
            r"ппо|uav(?:s)?|drone(?:s)?|missile(?:s)?|ballistic|rocket(?:s)?|"
            r"shahed(?:s)?|air[- ]?defen[cs]e|aerial|air force|"
            r"high[- ]?speed target|fast[- ]?target|повітрян\w*\s+сил\w*|"
            r"повітрян\w*\s+атак\w*|швидкісн\w*\s+ціл\w*)\b",
            flags=re.IGNORECASE,
        )
        segments = [
            " ".join(part.split())
            for part in re.split(r"(?<=[.!?;])\s+|\n+", evidence)
            if part and part.strip()
        ]
        mentioned_cities = monitor.audited_cities_in_text(evidence)
        conflicting_named_city = any(
            named_city != "dnipro" for named_city in mentioned_cities
        )
        reviewed_evidence_city = bool(dnipro_named.search(evidence))
        reviewed_exact_city_annotation = bool(
            re.search(r"\bexact[- ]city\s+report\b", evidence, flags=re.IGNORECASE)
        )
        exact_city = bool(
            (
                reviewed_exact_city
                or reviewed_evidence_city
                or reviewed_exact_city_annotation
            )
            and not conflicting_named_city
        )

        def dnipro_reviewed_event_types(segment: str) -> list[str]:
            event_types = []
            segment_low = segment.casefold()
            threat_or_modal_event = bool(
                re.search(
                    r"\b(?:можлив\w*|ймовірн\w*|загроз\w*|очікуван\w*|"
                    r"could|might|may|possible|likely|threat)\b.{0,45}"
                    r"\b(?:вибух\w*|удар\w*|влучанн\w*|explosion\w*|"
                    r"blast\w*|impact\w*|strike\w*)\b",
                    segment_low,
                )
            )
            strict_signal = (
                monitor.strict_attack_event_signal(segment)
                and not threat_or_modal_event
            )
            if strict_signal:
                for event_type in monitor.attack_event_types(segment):
                    if (
                        event_type == "air_defense_action"
                        and not monitor.air_defense_action_signal(segment)
                    ):
                        continue
                    if event_type not in event_types:
                        event_types.append(event_type)
            if english_explosion.search(segment) and "explosion" not in event_types:
                event_types.append("explosion")
            if english_impact.search(segment) and "impact" not in event_types:
                event_types.append("impact")
            if english_strike.search(segment) and "strike" not in event_types:
                event_types.append("strike")
            # A few retained Dnipro reviewed summaries use "було/стало гучно"
            # as the factual event wording. Accept it only behind an explicit
            # strict exact-city + air-war + episode-relation review contract.
            reviewed_loud_fact = bool(
                reviewed_strict
                and exact_city
                and reviewed_episode_relation
                and (
                    reviewed_air_context
                    or specific_air.search(evidence)
                )
                and re.search(
                    r"\bгучн\w*\b|\bгупал\w*\b|"
                    r"\b(?:was|were)\s+(?:very\s+)?loud\b",
                    segment_low,
                )
            )
            if reviewed_loud_fact and "explosion" not in event_types:
                event_types.append("explosion")
            return event_types

        event_segments = []
        event_types = []
        for segment in segments:
            types = dnipro_reviewed_event_types(segment)
            if not types:
                continue
            event_segments.append(segment)
            for event_type in types:
                if event_type not in event_types:
                    event_types.append(event_type)

        explosion = bool(event_segments)
        air_context = bool(
            reviewed_air_context
            or any(specific_air.search(segment) for segment in segments)
        )
        same_attack = bool(
            exact_city
            and explosion
            and air_context
            and reviewed_episode_relation
            and not conflicting_named_city
        )

        roles = {}
        if exact_city:
            roles["exact_city_evidence"] = {
                "present": True,
                "evidence_text": (review_basis if reviewed_exact_city else evidence)[:1200],
            }
        if explosion:
            roles["explosion_evidence"] = {
                "present": True,
                "evidence_text": event_segments[0][:1200],
                "event_types": event_types,
            }
        if air_context:
            roles["aerial_war_evidence"] = {
                "present": True,
                "evidence_text": (review_basis or evidence)[:1200],
            }
        if same_attack:
            roles["same_attack_basis"] = {
                "present": True,
                "basis": (
                    "reviewed_dnipro_sensitivity_same_attack_relation"
                    if reviewed_sensitivity and not reviewed_strict
                    else "reviewed_dnipro_exact_city_event_air_context_episode_relation"
                ),
                "evidence_text": (review_basis or evidence)[:1200],
            }
        return roles, evidence
    elif city in {"chernihiv", "kropyvnytskyi"}:
        # These two frozen corpora retain reviewed role contracts in legacy
        # decision/basis fields.  Translate only those explicit reviewed
        # contracts; never promote free article text on its own.
        review_parts = [
            str(row.get(key)).strip()
            for key in BASIS_FIELDS
            if row.get(key) and str(row.get(key)).strip()
        ]
        review_basis = " — ".join(review_parts)
        review_low = review_basis.casefold()

        if city == "kropyvnytskyi":
            reviewed_exact_city = (
                str(row.get("basis") or "").strip().casefold()
                == "exact_city_during_alert"
            )
            reviewed_episode_relation = reviewed_exact_city
            reviewed_air_context = reviewed_exact_city
            if not reviewed_exact_city:
                return {}, evidence
        else:
            reviewed_exact_city = bool(
                re.search(r"\bexact[_ -]?city\b", review_low)
                or "strict_exact_city_in_episode" in review_low
            )
            reviewed_episode_relation = bool(
                re.search(
                    r"(?:time[_ -]?match|matched[_ -]?alert|inside[_ -]?(?:one[_ -]?)?alert|"
                    r"during[_ -]?alert|in[_ -]?episode|same[_ -]?attack|cross[_ -]?midnight)",
                    review_low,
                )
            )
            reviewed_air_context = bool(
                re.search(r"aerial[_ -]?(?:war|context|attack)", review_low)
                or re.search(
                    r"(?:matched[_ -]?alert|inside[_ -]?(?:one[_ -]?)?alert|"
                    r"during[_ -]?alert|in[_ -]?episode|cross[_ -]?midnight)",
                    review_low,
                )
            )
            if not reviewed_episode_relation:
                return {}, evidence

        segments = [
            " ".join(part.split())
            for part in re.split(r"(?<=[.!?;])\s+|\n+", evidence)
            if part and part.strip()
        ]
        english_air = re.compile(
            r"\b(?:air alert|aerial|missile(?:s)?|drone(?:s)?|uav(?:s)?|"
            r"air force|afu|reactive[- ]?uav|drone threat|missile warning(?:s)?|"
            r"combined air attack|russian (?:drone |missile |air )?attack|alert episode)\b",
            flags=re.IGNORECASE,
        )
        english_explosion = re.compile(
            r"\b(?:explosion(?:s)?|blast(?:s)?|bang(?:s)?)\b",
            flags=re.IGNORECASE,
        )
        english_impact = re.compile(
            r"\b(?:impact(?:s|ed)?|hit|hits)\b",
            flags=re.IGNORECASE,
        )
        english_strike = re.compile(
            r"\b(?:strike|strikes|struck)\b",
            flags=re.IGNORECASE,
        )

        def reviewed_event_type(segment: str) -> str | None:
            existing = monitor.attack_event_types(segment)
            for event_type in (
                "explosion",
                "impact",
                "arrival",
                "strike",
                "air_defense_action",
                "damage",
                "fire",
            ):
                if event_type in existing and monitor.strict_attack_event_signal(segment):
                    return event_type
            if english_explosion.search(segment):
                return "explosion"
            if english_impact.search(segment):
                return "impact"
            if english_strike.search(segment):
                return "strike"
            segment_low = segment.casefold()
            completed_air_attack = bool(
                re.search(r"\bатакув(?:ав|ала|ало|али)\b", segment_low)
                and re.search(r"\b(?:бпла|безпілот\w*|дрон\w*|повітрян\w*)\b", segment_low)
            )
            if completed_air_attack:
                return "strike"
            return None

        event_segments = []
        event_types = []
        for segment in segments:
            event_type = reviewed_event_type(segment)
            if event_type:
                event_segments.append(segment)
                if event_type not in event_types:
                    event_types.append(event_type)

        mentioned_cities = monitor.audited_cities_in_text(evidence)
        conflicting_named_city = any(
            named_city != city for named_city in mentioned_cities
        )
        reviewed_english_exact_city = bool(
            city == "chernihiv"
            and reviewed_episode_relation
            and re.search(
                r"\b(?:in|inside|within)\s+Chernihiv\b",
                evidence,
                flags=re.IGNORECASE,
            )
        )
        exact_city = bool(
            reviewed_exact_city
            or reviewed_english_exact_city
            or city in mentioned_cities
        )
        explosion = bool(event_segments)
        air_context = bool(
            reviewed_air_context
            or any(monitor.air_military_context(segment) for segment in segments)
            or any(english_air.search(segment) for segment in segments)
        )
        same_attack = bool(
            exact_city
            and explosion
            and air_context
            and reviewed_episode_relation
            and not conflicting_named_city
        )

        roles = {}
        if exact_city:
            roles["exact_city_evidence"] = {
                "present": True,
                "evidence_text": evidence[:1200],
            }
        if explosion:
            roles["explosion_evidence"] = {
                "present": True,
                "evidence_text": event_segments[0][:1200],
                "event_types": event_types,
            }
        if air_context:
            roles["aerial_war_evidence"] = {
                "present": True,
                "evidence_text": (review_basis or evidence)[:1200],
            }
        if same_attack:
            roles["same_attack_basis"] = {
                "present": True,
                "basis": (
                    "reviewed_kropyvnytskyi_exact_city_during_alert"
                    if city == "kropyvnytskyi"
                    else "reviewed_chernihiv_legacy_episode_relation"
                ),
                "evidence_text": (review_basis or evidence)[:1200],
            }
        return roles, evidence
    else:
        return {}, evidence

    roles = {}
    if exact_city:
        roles["exact_city_evidence"] = {
            "present": True,
            "evidence_text": evidence[:1200],
        }

    reviewed_exact = row.get("reviewed_exact_city_evidence")
    if isinstance(reviewed_exact, dict) and reviewed_exact.get("present") is True:
        exact_city = True
        roles["exact_city_evidence"] = {
            "present": True,
            "evidence_text": str(
                reviewed_exact.get("evidence_text")
                or reviewed_exact.get("evidence")
                or evidence
            )[:1200],
        }
    if explosion:
        roles["explosion_evidence"] = {
            "present": True,
            "evidence_text": (direct_event_segment or evidence)[:1200],
        }
        if direct_event_segment:
            roles["explosion_evidence"]["event_types"] = [direct_event_type]
    if air_context:
        roles["aerial_war_evidence"] = {
            "present": True,
            "evidence_text": evidence[:1200],
        }
    if direct_event_segment:
        roles["same_attack_basis"] = {
            "present": True,
            "basis": direct_event_basis,
            "evidence_text": direct_event_segment[:1200],
        }
    elif (
        city != "cherkasy"
        and exact_city
        and explosion
        and air_context
        and not conflicting_named_city
    ):
        roles["same_attack_basis"] = {
            "present": True,
            "basis": "reviewed_factual_summary_links_exact_city_explosion_and_air_context",
            "evidence_text": evidence[:1200],
        }
    return roles, evidence

def retained_event_times(row: dict, monitor) -> list[datetime]:
    values = []
    for key in ("event_time", "event_time_kyiv", "event_timestamp", "event_datetime"):
        raw = row.get(key)
        if not raw:
            continue
        text = str(raw)
        # Historical audit fields can contain an approximation marker between
        # the date and clock ("2025-02-14 ~01:42") or multiple retained clocks.
        day_match = re.search(r"(?<!\d)(\d{4}-\d{2}-\d{2})(?!\d)", text)
        if not day_match:
            continue
        try:
            local_day = datetime.fromisoformat(day_match.group(1)).date()
        except ValueError:
            continue
        for match in re.finditer(r"(?<!\d)(\d{1,2}):(\d{2})(?!\d)", text):
            hour, minute = map(int, match.groups())
            if hour > 23 or minute > 59:
                continue
            values.append(
                datetime(
                    local_day.year,
                    local_day.month,
                    local_day.day,
                    hour,
                    minute,
                    tzinfo=KYIV_TZ,
                )
            )
    dedup = {}
    for value in values:
        dedup[value.astimezone(KYIV_TZ).isoformat()] = value
    return list(dedup.values())


def reviewed_exact_city_air_defense_temporal(
    row: dict,
    target_episode: dict | None,
    monitor,
    city: str,
) -> dict | None:
    if not target_episode:
        return None
    text = evidence_text(row)
    if not text or not monitor.air_defense_action_signal(text):
        return None
    exact = monitor.exact_city_classification_evidence(
        city,
        {
            "title": text,
            "snippet": "",
            "publisher": "historical_audit",
        },
    )
    if not exact.get("present"):
        return None
    start = monitor.parse_dt(target_episode.get("alert_start"))
    end = monitor.parse_dt(target_episode.get("alert_end"))
    if not start or not end:
        return None
    inside = [
        value
        for value in retained_event_times(row, monitor)
        if start <= value.astimezone(monitor.UTC) <= end
    ]
    if not inside:
        return None
    return {
        "status": "validated_event_time",
        "validated_by_review": True,
        "episode_specific": True,
        "temporal_evidence_type": "retained_exact_city_air_defense_event_time",
        "event_time": inside[0].astimezone(monitor.UTC).isoformat().replace("+00:00", "Z"),
        "timestamp_precision": "minute",
        "evidence_text": text[:1200],
        "neighboring_alert_check": {"passed": True},
    }


def history_provenance(
    row: dict,
    bucket: str,
    target_id: str,
    monitor,
    city: str,
    target_episode: dict | None = None,
) -> dict | None:
    basis = evidence_text(row)
    reviewed_roles, reviewed_evidence = historical_review_roles(city, row, monitor)

    if bucket == "strict_events":
        raw = row.get("raw_record") or {}
        city_status = str(raw.get("city_status") or "").strip()
        war_air_context = str(raw.get("war_air_context") or "").strip()
        temporal_kind = str(raw.get("temporal_evidence") or "").strip()
        alert_basis = str(raw.get("alert_interval_basis") or "").strip()
        reviewed_context = " | ".join(
            part
            for part in [
                f"city_status={city_status}" if city_status else "",
                f"war_air_context={war_air_context}" if war_air_context else "",
                f"temporal_evidence={temporal_kind}" if temporal_kind else "",
                alert_basis,
            ]
            if part
        )
        provenance = {
            "schema_version": monitor.REVIEW_PROVENANCE_SCHEMA_VERSION,
            "methodology_version": "historical-audit-replay-adapter-v3",
            "target_episode_id": target_id,
            "temporal": {
                "status": "validated_episode_binding",
                "validated_by_review": True,
                "episode_specific": True,
                "temporal_evidence_type": "frozen_historical_audit_episode_binding",
                "evidence_text": basis[:1200],
                "neighboring_alert_check": {"passed": True},
            },
        }
        provenance.update(reviewed_roles)

        # Lviv's recovered corpus has explicit structured audit fields. Preserve
        # factual reviewed context only; do not use the historical strict label.
        if war_air_context == "confirmed":
            provenance["aerial_war_evidence"] = {
                "present": True,
                "evidence_text": reviewed_context or "war_air_context=confirmed",
            }
            if (
                city_status == "exact_city"
                and temporal_kind in {"exact_time_in_alert", "explicit_during_alert"}
            ):
                provenance["same_attack_basis"] = {
                    "present": True,
                    "basis": "reviewed_exact_city_air_context_with_episode_specific_temporal_binding",
                    "evidence_text": reviewed_context
                    or "reviewed exact-city air context with episode-specific temporal binding",
                }
        return provenance

    if bucket == "sensitivity_only_events":
        low = basis.casefold()
        if "near_boundary" in low or "near-boundary" in low or "precedes_alert" in low:
            sens_basis = "near_boundary"
        elif "inferred" in low or "same_attack" in low or "same attack" in low:
            sens_basis = "inferred_same_attack"
        else:
            return None
        provenance = {
            "schema_version": monitor.REVIEW_PROVENANCE_SCHEMA_VERSION,
            "methodology_version": "historical-audit-replay-adapter-v3",
            "target_episode_id": target_id,
            "sensitivity_binding": {
                "present": True,
                "validated_by_review": True,
                "episode_specific": True,
                "basis": sens_basis,
                "neighboring_alert_check": {"passed": True},
            },
        }
        provenance.update(reviewed_roles)
        strict_air_defense_temporal = reviewed_exact_city_air_defense_temporal(
            row, target_episode, monitor, city
        )
        if strict_air_defense_temporal is not None:
            provenance["temporal"] = strict_air_defense_temporal
        return provenance
    return None

def candidate_from_history(
    city: str,
    row: dict,
    bucket: str,
    target_id: str,
    monitor,
    target_episode: dict | None = None,
) -> dict:
    text = evidence_text(row)
    source_url = str(row.get("source_url") or "")
    parent_record = row.get("_historical_parent_record")
    if not isinstance(parent_record, dict):
        parent_record = row
    parent_record_id = row.get("_historical_parent_record_id")
    observation_id = row.get("_historical_event_observation_id")
    cid_seed = f"{city}|{target_id}|{bucket}|{source_url}|{text}"
    if observation_id:
        cid_seed += f"|observation:{observation_id}"
    candidate = {
        "candidate_id": hashlib.sha256(cid_seed.encode("utf-8")).hexdigest()[:24],
        "city_key": city,
        "title": text,
        "snippet": "",
        "matched_text_excerpt": None,
        "publisher": urlparse(source_url).netloc or "historical_audit",
        "publisher_url": source_url or None,
        "url": source_url or f"historical://{city}/{target_id}",
        "resolved_url": source_url or None,
        "source": "frozen historical audit evidence",
        "published_at": row.get("published_at") or row.get("publication_time"),
        "discovery_basis": "historical_audit_retained_evidence",
        "matched_episode_id": target_id,
        "historical_bucket": bucket,
        "historical_record": copy.deepcopy(parent_record),
    }
    if parent_record_id:
        candidate["historical_parent_record_id"] = str(parent_record_id)
    if observation_id:
        candidate["historical_event_observation"] = {
            "observation_id": str(observation_id),
            "event_time_utc": row.get("_historical_event_time_utc"),
            "ordinal": row.get("_historical_event_ordinal"),
            "evidence_text": next(
                (
                    str(row.get(key)).strip()
                    for key in EVIDENCE_FIELDS
                    if row.get(key) and str(row.get(key)).strip()
                ),
                "",
            )[:1200],
        }
    provenance = history_provenance(
        row, bucket, target_id, monitor, city, target_episode
    )
    if provenance:
        candidate["review_provenance"] = provenance
    return candidate


def manual_matching(target_id: str) -> dict:
    return {
        "outcome": "unique_match",
        "matched_episode_ids": [target_id],
        "logical_episode_groups": [[target_id]],
        "matched_episode_id": target_id,
        "reason": "frozen_historical_audit_episode_binding",
    }


def source_inventory(repo_root: Path, city: str, monitor) -> dict:
    data = repo_root / "data"
    evidence_dir = data / "explosion_research" / city
    final_evidence = evidence_dir / "final_evidence.json"
    working_evidence = evidence_dir / "working_evidence.json"
    slice_dir = data / "explosion_metric_handoff" / "source_slices"
    slice_files = sorted(slice_dir.glob(f"{city}-*_alerts.json"))

    if city == "kyiv":
        alert_files = [data / "alerts_combined.json"]
        loader = "monitor.load_kyiv_alert_episodes"
    elif city == "sevastopol":
        alert_files = [data / "sevastopol_events.json"]
        loader = "monitor.load_sevastopol_alert_episodes"
    else:
        alert_files = slice_files
        loader = "historical_source_slices"

    return {
        "final_evidence": str(final_evidence.relative_to(repo_root)) if final_evidence.exists() else None,
        "working_evidence": str(working_evidence.relative_to(repo_root)) if working_evidence.exists() else None,
        "alert_source_files": [str(p.relative_to(repo_root)) for p in alert_files if p.exists()],
        "alert_loader": loader,
        "source_slice_count": len(slice_files),
    }


def load_historical_episodes(repo_root: Path, city: str, monitor) -> tuple[list[dict], list[str]]:
    data = repo_root / "data"
    sources: list[str] = []
    if city == "kyiv":
        path = data / "alerts_combined.json"
        sources.append(str(path.relative_to(repo_root)))
        return monitor.load_kyiv_alert_episodes(path), sources
    if city == "sevastopol":
        path = data / "sevastopol_events.json"
        sources.append(str(path.relative_to(repo_root)))
        return monitor.load_sevastopol_alert_episodes(path), sources

    rows: dict[str, dict] = {}
    for path in sorted((data / "explosion_metric_handoff" / "source_slices").glob(f"{city}-*_alerts.json")):
        payload = load_json(path)
        sources.append(str(path.relative_to(repo_root)))
        for ep in payload.get("episodes") or []:
            eid = str(ep.get("episode_id") or "")
            if eid:
                rows[eid] = dict(ep)
    return sorted(rows.values(), key=lambda ep: (str(ep.get("alert_start") or ""), str(ep.get("episode_id") or ""))), sources


def filter_window(episodes: list[dict], coverage_start: str, through: str, monitor) -> list[dict]:
    out = []
    for ep in episodes:
        day = ep.get("alert_start_date_kyiv") or local_day(ep.get("alert_start"), monitor)
        if day and coverage_start <= str(day) <= through:
            ep = dict(ep)
            ep.setdefault("alert_start_date_kyiv", str(day))
            out.append(ep)
    return out


def evidence_validation(
    evidence: dict,
    baseline_city: dict,
    episodes: list[dict],
    monitor,
    city: str = "",
) -> dict:
    errors = []
    bindings = {"strict_events": [], "sensitivity_only_events": [], "review_events": []}
    bound_status: dict[str, str] = {}
    split_records = []

    for bucket in bindings:
        allow_split = bucket in {"strict_events", "sensitivity_only_events"}
        for index, row in enumerate(evidence.get(bucket) or []):
            if city:
                observations = expand_historical_evidence_observations(
                    city,
                    bucket,
                    index,
                    row,
                    episodes,
                    monitor,
                    allow_new_temporal_fallback=allow_split,
                )
            else:
                binding = bind_evidence_record(
                    row,
                    episodes,
                    monitor,
                    allow_new_temporal_fallback=allow_split,
                )
                observations = [{
                    "parent_record_id": None,
                    "observation_id": None,
                    "is_split_child": False,
                    "event_fact_present": None,
                    "event_time_utc": None,
                    "event_evidence": None,
                    "row": row,
                    "binding": binding,
                }]

            if len(observations) > 1 and any(
                observation.get("is_split_child") for observation in observations
            ):
                split_records.append({
                    "city": city,
                    "bucket": bucket,
                    "parent_record_id": observations[0]["parent_record_id"],
                    "legacy_parent_status": history_status(row, bucket),
                    "source_url": row.get("source_url"),
                    "retained_event_time": row.get("event_time"),
                    "children": [
                        {
                            "observation_id": observation["observation_id"],
                            "event_time_utc": observation["event_time_utc"],
                            "event_fact_present": observation["event_fact_present"],
                            "episode_id": observation["binding"].get("episode_id"),
                            "binding_method": observation["binding"].get("method"),
                            "binding_candidates": observation["binding"].get("candidates") or [],
                            "evidence": observation.get("event_evidence"),
                        }
                        for observation in observations
                    ],
                })

            for observation in observations:
                binding = observation["binding"]
                bindings[bucket].append({
                    "row": row,
                    "parent_record_id": observation.get("parent_record_id"),
                    "observation_id": observation.get("observation_id"),
                    "is_split_child": observation.get("is_split_child"),
                    "event_fact_present": observation.get("event_fact_present"),
                    "binding": binding,
                })

                if (
                    observation.get("is_split_child")
                    and observation.get("event_fact_present") is False
                ):
                    continue

                eid = binding.get("episode_id")
                if not eid:
                    if bucket in {"strict_events", "sensitivity_only_events"}:
                        errors.append({
                            "code": "UNBOUND_COUNTED_EVIDENCE",
                            "bucket": bucket,
                            "parent_record_id": observation.get("parent_record_id"),
                            "observation_id": observation.get("observation_id"),
                            "binding": binding,
                            "evidence": evidence_text(observation["row"])[:500],
                        })
                    continue

                proposed = history_status(row, bucket)
                old = bound_status.get(eid)
                if old and old != proposed:
                    errors.append({
                        "code": "CONFLICTING_FROZEN_EPISODE_STATUS",
                        "episode_id": eid,
                        "statuses": sorted({old, proposed}),
                    })
                if proposed == "STRICT" or old is None:
                    bound_status[eid] = proposed

    strict_ids = sorted(
        eid for eid, status in bound_status.items() if status == "STRICT"
    )
    sensitivity_ids = sorted(
        eid for eid, status in bound_status.items()
        if status in {"STRICT", "SENSITIVITY"}
    )

    strict_split_extra = 0
    sensitivity_split_extra = 0
    for split in split_records:
        bound_ids = {
            str(child.get("episode_id"))
            for child in split["children"]
            if child.get("event_fact_present") is True and child.get("episode_id")
        }
        extra = max(0, len(bound_ids) - 1)
        if split["bucket"] == "strict_events":
            strict_split_extra += extra
            sensitivity_split_extra += extra
        elif split["bucket"] == "sensitivity_only_events":
            sensitivity_split_extra += extra

    expected_strict = int(baseline_city.get("strict_n") or 0) + strict_split_extra
    expected_sensitivity = (
        int(baseline_city.get("sensitivity_n") or 0) + sensitivity_split_extra
    )
    if len(strict_ids) != expected_strict:
        errors.append({
            "code": "STRICT_ID_COUNT_MISMATCH",
            "expected_legacy_rows": baseline_city.get("strict_n"),
            "explained_multi_event_episode_gain": strict_split_extra,
            "expected_canonical_episode_ids": expected_strict,
            "bound": len(strict_ids),
        })
    if len(sensitivity_ids) != expected_sensitivity:
        errors.append({
            "code": "SENSITIVITY_ID_COUNT_MISMATCH",
            "expected_legacy_rows": baseline_city.get("sensitivity_n"),
            "explained_multi_event_episode_gain": sensitivity_split_extra,
            "expected_canonical_episode_ids": expected_sensitivity,
            "bound": len(sensitivity_ids),
        })
    return {
        "errors": errors,
        "bindings": bindings,
        "frozen_status_by_episode": bound_status,
        "strict_ids": strict_ids,
        "sensitivity_ids": sensitivity_ids,
        "legacy_multi_event_splits": split_records,
        "explained_multi_event_episode_gain": {
            "strict": strict_split_extra,
            "sensitivity": sensitivity_split_extra,
        },
    }

def validate_city_sources(repo_root: Path, city: str, baseline_city: dict, through: str, monitor) -> dict:
    inv = source_inventory(repo_root, city, monitor)
    reasons = []
    evidence_path = repo_root / inv["final_evidence"] if inv.get("final_evidence") else None
    if evidence_path is None:
        reasons.append({
            "code": "MISSING_FROZEN_HISTORICAL_EVIDENCE_CORPUS",
            "detail": "No final_evidence.json is present for the audited city; summary counts/dates are insufficient for current-classifier replay.",
            "working_evidence_present": inv.get("working_evidence"),
        })
        evidence = None
    else:
        evidence = load_json(evidence_path)

    all_episodes, episode_sources = load_historical_episodes(repo_root, city, monitor)
    episodes = filter_window(all_episodes, str(baseline_city["coverage_start"]), through, monitor)
    expected_alerts = int(baseline_city.get("total_alerts") or 0)
    if len(episodes) != expected_alerts:
        reasons.append({
            "code": "INCOMPLETE_HISTORICAL_ALERT_EPISODE_CORPUS",
            "expected_alert_episodes": expected_alerts,
            "reconstructed_alert_episodes": len(episodes),
            "missing_count": expected_alerts - len(episodes),
            "sources": episode_sources,
        })

    evidence_check = None
    if evidence is not None and len(episodes) == expected_alerts:
        evidence_check = evidence_validation(
            evidence, baseline_city, episodes, monitor, city
        )
        reasons.extend(evidence_check["errors"])

    return {
        "city_key": city,
        "coverage_start": baseline_city.get("coverage_start"),
        "replay_end": through,
        "expected_alert_episodes": expected_alerts,
        "reconstructed_alert_episodes": len(episodes),
        "inventory": inv,
        "episode_source_files": episode_sources,
        "source_status": "READY" if not reasons else "BLOCKED",
        "blocking_reasons": reasons,
        "evidence_validation": {
            "frozen_strict_ids": (evidence_check or {}).get("strict_ids", []),
            "frozen_sensitivity_ids": (evidence_check or {}).get("sensitivity_ids", []),
            "legacy_multi_event_splits": (evidence_check or {}).get(
                "legacy_multi_event_splits", []
            ),
            "explained_multi_event_episode_gain": (evidence_check or {}).get(
                "explained_multi_event_episode_gain",
                {"strict": 0, "sensitivity": 0},
            ),
        },
    }


def blob_inventory(checkout_root: Path, repo_root: Path, extra_paths: list[str] | None = None) -> dict:
    paths = [
        "scripts/monitor_explosion_candidates.py",
        *PROTECTED_RELATIVE,
    ]
    paths += extra_paths or []
    result = {}
    for rel in sorted(set(paths)):
        outer_rel = str((repo_root / rel).relative_to(checkout_root)).replace(os.sep, "/")
        result[outer_rel] = git_blob(checkout_root, outer_rel)
    return result


def live_control_audit(repo_root: Path, through: str) -> dict:
    queue = load_json(repo_root / "data/explosion_review_queue.json")
    state = load_json(repo_root / "data/explosion_candidate_monitor_state.json")
    episode_city = {}
    for city, city_state in (state.get("cities") or {}).items():
        for ep in city_state.get("episodes") or []:
            eid = str(ep.get("episode_id") or "")
            if eid:
                episode_city[eid] = city
    results = []
    for eid, expected_strict in CONTROL_EXPECTATIONS.items():
        rows = [r for r in queue if str(r.get("matched_episode_id") or "") == eid]
        observed_strict = any(str(r.get("status") or "") == "approved_strict" for r in rows)
        conditional = eid == "f235928c329ca806d9dca5ed"
        denominator_ok = through >= "2026-09-24" if conditional else True
        results.append({
            "episode_id": eid,
            "city_key": episode_city.get(eid),
            "expected_strict_control": expected_strict,
            "denominator_condition_for_materialization": "coverage >= 2026-09-24" if conditional else None,
            "historical_replay_denominator_satisfies_condition": denominator_ok,
            "observed_persisted_strict": observed_strict,
            "pass": observed_strict == expected_strict,
            "candidate_count": len(rows),
        })
    return {"controls": results, "all_pass": all(row["pass"] for row in results)}


def preflight(repo_root: Path, through: str, output: Path, input_head: str | None) -> int:
    checkout_root = repo_root.parent
    ensure_output_outside_checkout(output, checkout_root)
    before = protected_snapshot(repo_root)
    with network_blocked():
        monitor = import_monitor(repo_root)
        monitor.self_test()
        baseline = load_json(repo_root / "data/explosion_audited_baseline.json")
        cities = baseline.get("cities") or {}
        source_results = [validate_city_sources(repo_root, city, row, through, monitor) for city, row in cities.items()]
        controls = live_control_audit(repo_root, through)
    after = protected_snapshot(repo_root)
    if before != after:
        raise RuntimeError("Protected files changed during read-only preflight")
    actual_head = git_head(checkout_root)
    if input_head and actual_head != input_head:
        raise RuntimeError(f"Frozen checkout HEAD mismatch: expected {input_head}, got {actual_head}")
    extra = []
    for item in source_results:
        for rel in item.get("episode_source_files") or []:
            extra.append(rel)
        final_ev = item.get("inventory", {}).get("final_evidence")
        if final_ev:
            extra.append(final_ev)
    payload = {
        "schema_version": 1,
        "kind": "full_historical_explosion_replay_preflight",
        "input_head": actual_head,
        "replay_end": through,
        "city_count": len(cities),
        "city_keys": list(cities),
        "monitor_self_test": "PASS",
        "network_policy": "socket and requests network calls blocked inside replay/preflight process",
        "protected_files_unchanged": before == after,
        "input_blob_shas": blob_inventory(checkout_root, repo_root, extra),
        "live_control_regressions": controls,
        "cities": source_results,
        "ready_city_count": sum(x["source_status"] == "READY" for x in source_results),
        "blocked_city_count": sum(x["source_status"] != "READY" for x in source_results),
    }
    payload["ready_for_matrix"] = (
        len(cities) == 23
        and payload["blocked_city_count"] == 0
        and controls["all_pass"]
        and before == after
    )
    payload["verdict"] = (
        "HISTORICAL REPLAY PREFLIGHT CLEAN — READY FOR 23-CITY MATRIX"
        if payload["ready_for_matrix"]
        else "HISTORICAL REPLAY PREFLIGHT BLOCKED — SOURCE/CONTROL QA REQUIRED"
    )
    dump_json(output, payload)
    return 0 if payload["ready_for_matrix"] else 2


def category(old: str, new: str, replayable: bool = True) -> str:
    if not replayable:
        return "UNREPLAYABLE_MISSING_EVIDENCE"
    if old == "STRICT" and new == "STRICT":
        return "UNCHANGED_STRICT"
    if old == "STRICT" and new == "SENSITIVITY":
        return "STRICT_TO_SENSITIVITY"
    if old == "STRICT":
        return "STRICT_DOWNGRADE"
    if old == "SENSITIVITY" and new == "STRICT":
        return "SENSITIVITY_TO_STRICT"
    if old == "NON_STRICT" and new == "STRICT":
        return "NEW_STRICT"
    if old == "NON_STRICT" and new == "SENSITIVITY":
        return "NEW_SENSITIVITY"
    if new == "AMBIGUOUS" and old != "AMBIGUOUS":
        return "NEW_AMBIGUOUS"
    return "UNCHANGED_NON_STRICT"


def evidence_backed_sensitivity_to_strict_upgrade(
    row: dict,
    decision_by_candidate: dict[str, dict],
) -> bool:
    if row.get("category") != "SENSITIVITY_TO_STRICT":
        return False
    target_id = str(row.get("episode_id") or "")
    contributor_ids = [str(cid) for cid in row.get("candidate_contributor_ids") or []]
    required_codes = {
        "EXACT_CITY_EVENT_TEXT",
        "STRICT_EXPLOSION_EVIDENCE",
        "AIR_MILITARY_CONTEXT",
        "SAME_ATTACK_CONTEXT_SUPPORTED",
    }
    for cid in contributor_ids:
        decision = decision_by_candidate.get(cid) or {}
        if decision.get("proposed_outcome") != "approved_strict":
            continue
        if str(decision.get("proposed_matched_episode_id") or "") != target_id:
            continue
        temporal = decision.get("temporal_binding") or {}
        if not (
            temporal.get("present") is True
            and temporal.get("episode_specific") is True
            and str(temporal.get("episode_id") or "") == target_id
        ):
            continue
        provenance = decision.get("provenance_basis") or {}
        if not (
            provenance.get("present") is True
            and provenance.get("usable") is True
            and str(provenance.get("target_episode_id") or "") == target_id
        ):
            continue
        codes = set(decision.get("reason_codes") or [])
        if not required_codes.issubset(codes):
            continue
        return True
    return False


def compact_decision(decision: dict) -> dict:
    return {
        "proposed_outcome": decision.get("proposed_outcome"),
        "proposed_matched_episode_id": decision.get("proposed_matched_episode_id"),
        "reason_codes": decision.get("reason_codes") or [],
        "matching": decision.get("matching") or {},
        "temporal_binding": decision.get("temporal_binding") or {},
        "composition_basis": None,
        "provenance_basis": decision.get("review_provenance_adapter") or {},
    }


def replay_city(repo_root: Path, city: str, through: str, output: Path, input_head: str | None) -> int:
    checkout_root = repo_root.parent
    ensure_output_outside_checkout(output, checkout_root)
    before = protected_snapshot(repo_root)
    with network_blocked():
        monitor = import_monitor(repo_root)
        baseline = load_json(repo_root / "data/explosion_audited_baseline.json")
        if city not in (baseline.get("cities") or {}):
            raise SystemExit(f"Unknown audited city: {city}")
        baseline_city = baseline["cities"][city]
        source = validate_city_sources(repo_root, city, baseline_city, through, monitor)
        actual_head = git_head(checkout_root)
        if input_head and actual_head != input_head:
            raise RuntimeError(f"Frozen checkout HEAD mismatch: expected {input_head}, got {actual_head}")

        if source["source_status"] != "READY":
            payload = {
                "schema_version": 1,
                "city_key": city,
                "coverage_start": baseline_city.get("coverage_start"),
                "replay_end": through,
                "input_head": actual_head,
                "status": "BLOCKED",
                "episodes_checked": 0,
                "baseline_strict_episodes": int(baseline_city.get("strict_n") or 0),
                "replayed_strict_episodes": 0,
                "baseline_sensitivity_episodes": int(baseline_city.get("sensitivity_n") or 0),
                "replayed_sensitivity_episodes": 0,
                "unchanged_episodes": 0,
                "changed_episodes": [],
                "new_strict": [],
                "downgraded_strict": [],
                "strict_to_sensitivity": [],
                "sensitivity_to_strict": [],
                "new_ambiguous": [],
                "ppo_related_changes": [],
                "strict_episode_identity": {"symmetric_difference": [], "old_strict_only": [], "new_strict_only": [], "unchanged_strict_ids": [], "aggregate_counts_equal_but_episode_identities_differ": False},
                "reconciliation_counts": {name: 0 for name in REQUIRED_CATEGORIES},
                "errors": source["blocking_reasons"],
                "source_validation": source,
                "verdict": "UNREPLAYABLE_MISSING_EVIDENCE",
            }
            dump_json(output, payload)
            return 2

        episodes, source_files = load_historical_episodes(repo_root, city, monitor)
        episodes = filter_window(episodes, str(baseline_city["coverage_start"]), through, monitor)
        evidence_path = repo_root / source["inventory"]["final_evidence"]
        evidence = load_json(evidence_path)
        validated = evidence_validation(
            evidence, baseline_city, episodes, monitor, city
        )
        old_status = {eid: "NON_STRICT" for eid in (str(ep["episode_id"]) for ep in episodes)}
        old_status.update(validated["frozen_status_by_episode"])

        ep_by_id = {str(ep["episode_id"]): ep for ep in episodes}
        candidates_by_episode: dict[str, list[dict]] = defaultdict(list)
        decision_by_candidate: dict[str, dict] = {}
        evidence_by_episode: dict[str, list[dict]] = defaultdict(list)
        errors = []
        unbound_review_evidence = []
        ignored_nonqualifying_split_children = []
        seen_candidate_ids: set[tuple[str, str]] = set()
        for bucket in ("strict_events", "sensitivity_only_events", "review_events"):
            allow_split = bucket in {"strict_events", "sensitivity_only_events"}
            for index, row in enumerate(evidence.get(bucket) or []):
                observations = expand_historical_evidence_observations(
                    city,
                    bucket,
                    index,
                    row,
                    episodes,
                    monitor,
                    allow_new_temporal_fallback=allow_split,
                )
                for observation in observations:
                    binding = observation["binding"]
                    if (
                        observation.get("is_split_child")
                        and observation.get("event_fact_present") is False
                    ):
                        ignored_nonqualifying_split_children.append({
                            "parent_record_id": observation.get("parent_record_id"),
                            "observation_id": observation.get("observation_id"),
                            "event_time_utc": observation.get("event_time_utc"),
                            "binding": binding,
                            "evidence": observation.get("event_evidence"),
                        })
                        continue

                    target_id = binding.get("episode_id")
                    if not target_id:
                        record = {
                            "code": "UNBOUND_HISTORICAL_EVIDENCE",
                            "bucket": bucket,
                            "parent_record_id": observation.get("parent_record_id"),
                            "observation_id": observation.get("observation_id"),
                            "binding": binding,
                            "evidence": evidence_text(observation["row"])[:500],
                        }
                        if bucket == "review_events":
                            unbound_review_evidence.append(record)
                        else:
                            errors.append(record)
                        continue

                    candidate = candidate_from_history(
                        city,
                        observation["row"],
                        bucket,
                        target_id,
                        monitor,
                        ep_by_id.get(target_id),
                    )
                    candidate_key = (target_id, str(candidate["candidate_id"]))
                    if candidate_key in seen_candidate_ids:
                        continue
                    seen_candidate_ids.add(candidate_key)
                    matching = manual_matching(target_id)
                    decision = monitor.classify_candidate(
                        candidate, city, episodes, matching
                    )
                    monitor.apply_classification_decision(candidate, decision, matching)
                    candidates_by_episode[target_id].append(candidate)
                    decision_by_candidate[candidate["candidate_id"]] = compact_decision(decision)
                    evidence_by_episode[target_id].append({
                        "candidate_id": candidate["candidate_id"],
                        "bucket": bucket,
                        "source_url": row.get("source_url"),
                        "evidence": evidence_text(observation["row"])[:1200],
                        "binding": binding,
                        "parent_record_id": observation.get("parent_record_id"),
                        "observation_id": observation.get("observation_id"),
                        "event_time_utc": observation.get("event_time_utc"),
                    })

        new_status = {eid: "NON_STRICT" for eid in old_status}
        composition_by_episode = {}
        for ep in episodes:
            eid = str(ep["episode_id"])
            rows = candidates_by_episode.get(eid, [])
            statuses = {str(r.get("status") or "") for r in rows}
            if "approved_strict" in statuses:
                new_status[eid] = "STRICT"
            else:
                composition = monitor.compose_episode_candidates(city, ep, rows, episodes) if len(rows) >= 2 else {"final_composed_verdict": "not_applicable"}
                composition_by_episode[eid] = composition
                if composition.get("final_composed_verdict") == "approved_strict":
                    new_status[eid] = "STRICT"
                elif "approved_sensitivity" in statuses:
                    new_status[eid] = "SENSITIVITY"
                elif "needs_review" in statuses:
                    new_status[eid] = "AMBIGUOUS"

        reconciliation_events = []
        changed = []
        accepted_upgrades = []
        counts = Counter()
        ppo_changes = []
        for eid in sorted(old_status):
            old = old_status[eid]
            new = new_status.get(eid, "NON_STRICT")
            cat = category(old, new)
            counts[cat] += 1
            if cat in {"UNCHANGED_STRICT", "UNCHANGED_NON_STRICT"}:
                continue
            ep = ep_by_id[eid]
            candidates = candidates_by_episode.get(eid, [])
            contributor_ids = sorted(str(c.get("candidate_id") or "") for c in candidates)
            texts = [x["evidence"] for x in evidence_by_episode.get(eid, [])]
            row = {
                "episode_id": eid,
                "local_date": ep.get("alert_start_date_kyiv") or local_day(ep.get("alert_start"), monitor),
                "alert_start": ep.get("alert_start"),
                "alert_end": ep.get("alert_end"),
                "category": cat,
                "frozen_old_status": old,
                "replayed_status": new,
                "candidate_contributor_ids": contributor_ids,
                "matching_result": [decision_by_candidate[cid].get("matching") for cid in contributor_ids if cid in decision_by_candidate],
                "evidence": evidence_by_episode.get(eid, []),
                "temporal_basis": [decision_by_candidate[cid].get("temporal_binding") for cid in contributor_ids if cid in decision_by_candidate],
                "composition_basis": composition_by_episode.get(eid),
                "provenance_basis": [decision_by_candidate[cid].get("provenance_basis") for cid in contributor_ids if cid in decision_by_candidate],
                "reason_codes": sorted({code for cid in contributor_ids for code in decision_by_candidate.get(cid, {}).get("reason_codes", [])}),
                "ppo_related": any(ppo_related(text) for text in texts),
            }
            if city == "dnipro" and cat in {
                "STRICT_DOWNGRADE",
                "NEW_AMBIGUOUS",
                "STRICT_TO_SENSITIVITY",
                "SENSITIVITY_TO_STRICT",
                "NEW_STRICT",
                "NEW_SENSITIVITY",
            }:
                row["reconciliation_reason"] = "HISTORICAL_REVIEW_ROLE_RECOVERY"
            reconciliation_events.append(row)
            if row["ppo_related"]:
                ppo_changes.append(row)
            if evidence_backed_sensitivity_to_strict_upgrade(row, decision_by_candidate):
                accepted_upgrades.append(row)
                continue
            changed.append(row)

        split_reconciliation_events = []
        for split in validated.get("legacy_multi_event_splits") or []:
            bound_episode_ids = sorted({
                str(child.get("episode_id"))
                for child in split.get("children") or []
                if child.get("event_fact_present") is True and child.get("episode_id")
            })
            for eid in bound_episode_ids:
                split_reconciliation_events.append({
                    "episode_id": eid,
                    "category": "LEGACY_MULTI_EVENT_SPLIT",
                    "reconciliation_reason": "LEGACY_MULTI_EVENT_SPLIT",
                    "parent_record_id": split.get("parent_record_id"),
                    "legacy_parent_status": split.get("legacy_parent_status"),
                    "source_url": split.get("source_url"),
                    "retained_event_time": split.get("retained_event_time"),
                    "sibling_episode_ids": bound_episode_ids,
                    "replayed_status": new_status.get(eid, "NON_STRICT"),
                    "children": split.get("children") or [],
                })
        counts["LEGACY_MULTI_EVENT_SPLIT"] += len(split_reconciliation_events)
        reconciliation_events = split_reconciliation_events + reconciliation_events

        evidence_episode_diagnostics = {}
        for eid in sorted(candidates_by_episode):
            contributor_ids = sorted(
                str(candidate.get("candidate_id") or "")
                for candidate in candidates_by_episode.get(eid, [])
            )
            evidence_episode_diagnostics[eid] = {
                "replayed_status": new_status.get(eid, "NON_STRICT"),
                "candidate_contributor_ids": contributor_ids,
                "reason_codes": sorted({
                    code
                    for cid in contributor_ids
                    for code in decision_by_candidate.get(cid, {}).get("reason_codes", [])
                }),
                "provenance_basis": [
                    decision_by_candidate[cid].get("provenance_basis")
                    for cid in contributor_ids
                    if cid in decision_by_candidate
                ],
            }

        old_strict = {eid for eid, st in old_status.items() if st == "STRICT"}
        new_strict = {eid for eid, st in new_status.items() if st == "STRICT"}
        old_sens = {eid for eid, st in old_status.items() if st in {"STRICT", "SENSITIVITY"}}
        new_sens = {eid for eid, st in new_status.items() if st in {"STRICT", "SENSITIVITY"}}
        identity = {
            "symmetric_difference": sorted(old_strict ^ new_strict),
            "old_strict_only": sorted(old_strict - new_strict),
            "new_strict_only": sorted(new_strict - old_strict),
            "unchanged_strict_ids": sorted(old_strict & new_strict),
            "aggregate_counts_equal_but_episode_identities_differ": len(old_strict) == len(new_strict) and old_strict != new_strict,
        }
        payload = {
            "schema_version": 1,
            "city_key": city,
            "coverage_start": baseline_city.get("coverage_start"),
            "replay_end": through,
            "input_head": actual_head,
            "status": "COMPLETE",
            "episodes_checked": len(episodes),
            "baseline_strict_episodes": int(baseline_city.get("strict_n") or 0),
            "canonicalized_legacy_strict_episodes": len(old_strict),
            "replayed_strict_episodes": len(new_strict),
            "baseline_sensitivity_episodes": int(baseline_city.get("sensitivity_n") or 0),
            "canonicalized_legacy_sensitivity_episodes": len(old_sens),
            "replayed_sensitivity_episodes": len(new_sens),
            "unchanged_episodes": counts["UNCHANGED_STRICT"] + counts["UNCHANGED_NON_STRICT"],
            "changed_episodes": changed,
            "reconciliation_events": reconciliation_events,
            "accepted_evidence_backed_upgrades": accepted_upgrades,
            "evidence_episode_diagnostics": evidence_episode_diagnostics,
            "new_strict": [r for r in changed if r["category"] == "NEW_STRICT"],
            "downgraded_strict": [r for r in changed if r["category"] == "STRICT_DOWNGRADE"],
            "strict_to_sensitivity": [r for r in changed if r["category"] == "STRICT_TO_SENSITIVITY"],
            "sensitivity_to_strict": [r for r in reconciliation_events if r["category"] == "SENSITIVITY_TO_STRICT"],
            "new_ambiguous": [r for r in changed if r["category"] == "NEW_AMBIGUOUS"],
            "ppo_related_changes": ppo_changes,
            "strict_episode_identity": identity,
            "reconciliation_counts": {name: counts[name] for name in REQUIRED_CATEGORIES},
            "errors": errors,
            "unbound_review_evidence": unbound_review_evidence,
            "ignored_nonqualifying_split_children": ignored_nonqualifying_split_children,
            "legacy_multi_event_splits": validated.get("legacy_multi_event_splits") or [],
            "source_validation": source,
            "source_files": source_files + [source["inventory"]["final_evidence"]],
            "methodology": {
                "classification_module": "frozen monitor_explosion_candidates.py",
                "network_access": "blocked",
                "historical_evidence_adapter": "retained audited parent evidence with event-level observation expansion only for explicit discrete multi-event lists; publication time is never synthesized from event time",
                "composition": "current compose_episode_candidates applied only when retained candidate fields/provenance support it",
                "unchanged_source_corpus_omitted": True,
            },
        }
        payload["verdict"] = "CITY REPLAY COMPLETE — QA REQUIRED" if changed or errors else "CITY REPLAY CLEAN"
    after = protected_snapshot(repo_root)
    if before != after:
        raise RuntimeError("Protected files changed during read-only city replay")
    payload["protected_files_unchanged"] = True
    dump_json(output, payload)
    return 0


def self_test() -> None:
    assert category("STRICT", "STRICT") == "UNCHANGED_STRICT"
    assert category("STRICT", "SENSITIVITY") == "STRICT_TO_SENSITIVITY"
    assert category("STRICT", "NON_STRICT") == "STRICT_DOWNGRADE"
    assert category("SENSITIVITY", "STRICT") == "SENSITIVITY_TO_STRICT"
    assert category("NON_STRICT", "STRICT") == "NEW_STRICT"
    assert category("NON_STRICT", "SENSITIVITY") == "NEW_SENSITIVITY"
    assert category("NON_STRICT", "AMBIGUOUS") == "NEW_AMBIGUOUS"
    assert category("NON_STRICT", "NON_STRICT", False) == "UNREPLAYABLE_MISSING_EVIDENCE"
    assert ppo_related("У місті вибухи — працює ППО")
    assert not ppo_related("У місті пролунав вибух")
    assert re.search(r"\bвдар\w*\b", "російський бпла вдарив по об'єкту".casefold())
    assert re.search(r"\b(?:ударив|ударила|ударили|ударило)\b", "російський бпла ударив по об'єкту".casefold())
    assert not re.search(r"\b(?:ударив|ударила|ударили|ударило)\b", "російський бпла атакував об'єкт".casefold())
    print("Historical replay helper self-test OK")


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only replay of frozen historical explosion audit evidence through the current frozen monitor classifier.")
    parser.add_argument("--repo-root", type=Path, help="Path to frozen kyiv-air-alerts-grafana directory")
    parser.add_argument("--city", help="Audited city key to replay")
    parser.add_argument("--through", default=DEFAULT_THROUGH, help="Inclusive local replay end date")
    parser.add_argument("--output", type=Path, help="JSON output path outside the frozen checkout")
    parser.add_argument("--input-head", help="Expected frozen git commit SHA")
    parser.add_argument("--preflight", action="store_true", help="Validate all 23 historical replay inputs without replaying cities")
    parser.add_argument("--read-only", action="store_true", help="Explicit declaration; replay is read-only regardless")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return
    if not args.repo_root or not args.output:
        parser.error("--repo-root and --output are required unless --self-test is used")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.through):
        parser.error("--through must be YYYY-MM-DD")
    if args.preflight:
        raise SystemExit(preflight(args.repo_root.resolve(), args.through, args.output.resolve(), args.input_head))
    if not args.city:
        parser.error("--city is required for a city replay")
    raise SystemExit(replay_city(args.repo_root.resolve(), args.city, args.through, args.output.resolve(), args.input_head))


if __name__ == "__main__":
    main()
