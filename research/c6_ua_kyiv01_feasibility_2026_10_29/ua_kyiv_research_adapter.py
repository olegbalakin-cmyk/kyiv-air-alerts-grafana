"""C6-UA-KYIV-01 isolated offline adapter. No network, tokens, filesystem writes or production imports.

All API inputs are caller-supplied evidence, not presumed live API payloads.
Observed poll transitions MUST NOT be represented as exact publisher ON/OFF times.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

UTC = timezone.utc
KYIV_CITY_NAMES = {"Київ", "м. Київ"}
KYIV_OBLAST_NAMES = {"Київська область", "Київська обл.", "Kyiv Oblast"}
MIN_REQUEST_GAP_SECONDS = 70


class ScopeNotProven(ValueError):
    pass


class SchemaError(ValueError):
    pass


def utc(value: str | datetime) -> datetime:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise SchemaError("invalid timestamp") from exc
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise SchemaError("naive or missing timestamp: refuse timezone inference")
    return value.astimezone(UTC)


def iso(value: datetime) -> str:
    return utc(value).isoformat().replace("+00:00", "Z")


def region_nodes(tree: Any) -> list[dict]:
    """Traverse the official v3 states/regionChildIds schema; do not confuse ancestors."""
    out = []
    seen_paths = set()

    def visit(obj: Any, parents: tuple[str, ...] = ()) -> None:
        if isinstance(obj, list):
            for child in obj:
                visit(child, parents)
            return
        if not isinstance(obj, dict):
            return
        if "regionId" not in obj:
            for key in ("states", "regionChildIds"):
                if key in obj:
                    visit(obj[key], parents)
            return
        region_id = str(obj["regionId"])
        name = str(obj.get("regionName") or "").strip()
        if not region_id or not name:
            raise SchemaError("regionId or regionName missing in region tree")
        record = {
            "regionId": region_id,
            "regionName": name,
            "regionType": obj.get("regionType"),
            "ancestors": list(parents),
        }
        key = (region_id, name, parents)
        if key not in seen_paths:
            out.append(record)
            seen_paths.add(key)
        visit(obj.get("regionChildIds", []), (*parents, name))
    visit(tree)
    return out


def verified_city_scope(
    tree: Any,
    region_id: str | None,
    *,
    primary_tree_hash: str | None = None,
    independent_city_scope_parity: bool = False,
) -> dict:
    """Fail closed until a captured /regions SHA AND independent municipal parity exist.

    A city-like label alone is not a certified city-vs-oblast territory mapping.
    """
    if not region_id or not primary_tree_hash or not independent_city_scope_parity:
        raise ScopeNotProven("primary /regions identity and exact city scope parity required")
    nodes = region_nodes(tree)
    matches = [n for n in nodes if n["regionId"] == str(region_id)]
    if len(matches) != 1:
        raise ScopeNotProven("regionId is not uniquely resolved in primary tree")
    node = matches[0]
    if node["regionName"] not in KYIV_CITY_NAMES:
        raise ScopeNotProven("region name is not the city of Kyiv")
    if node["regionType"] not in ("State", "Community"):
        raise ScopeNotProven("unexpected region type for exact city")
    if set(node["ancestors"]) & KYIV_OBLAST_NAMES:
        raise ScopeNotProven("Kyiv Oblast descendant is not independently city-scoped")
    oblast_ids = {n["regionId"] for n in nodes if n["regionName"] in KYIV_OBLAST_NAMES}
    if str(region_id) in oblast_ids or not oblast_ids:
        raise ScopeNotProven("distinct Kyiv Oblast node not established")
    return node


def history_air(payload: Any, region_id: str) -> dict:
    """Extract completed AIR only; preserve schema evidence, never fabricate an OFF."""
    groups = [payload] if isinstance(payload, dict) else payload
    if not isinstance(groups, list):
        raise SchemaError("history must be object or list")
    intervals = set()
    source_rows = 0
    air_rows = 0
    open_rows = 0
    for group in groups:
        if not isinstance(group, dict):
            raise SchemaError("invalid history group")
        if str(group.get("regionId")) != str(region_id):
            raise ScopeNotProven("history group region differs from exact city")
        alarms = group.get("alarms")
        if not isinstance(alarms, list):
            raise SchemaError("missing history alarms list")
        source_rows += len(alarms)
        for row in alarms:
            if not isinstance(row, dict):
                raise SchemaError("invalid history row")
            if str(row.get("alertType", "")).upper() != "AIR":
                continue
            air_rows += 1
            if not row.get("endDate"):
                open_rows += 1
                continue
            start, end = utc(row.get("startDate")), utc(row.get("endDate"))
            if end <= start:
                raise SchemaError("invalid AIR start/end order")
            intervals.add((iso(start), iso(end)))
    return {
        "completed": [{"start": s, "end": e} for s, e in sorted(intervals)],
        "source_rows": source_rows,
        "air_rows": air_rows,
        "open_air_rows": open_rows,
        "history_limit_documented": 25,
        "window_truncation_possible": source_rows >= 25,
        "reason_in_observed_history": any(
            isinstance(g, dict) and any(
                isinstance(r, dict) and ("reason" in r or "Reason" in r
                  or "activeAlertLevels" in r or "ActiveAlertLevels" in r)
                for r in (g.get("alarms") or [])
            ) for g in groups
        ),
    }


def current_air(payload: Any, region_id: str) -> dict:
    """Parse active AIR state and retain raw reasons as opaque data, not threat taxonomy."""
    groups = [payload] if isinstance(payload, dict) else payload
    if not isinstance(groups, list):
        raise SchemaError("current status must be object or list")
    matches = [g for g in groups if isinstance(g, dict) and str(g.get("regionId")) == str(region_id)]
    if len(matches) != 1:
        raise ScopeNotProven("current response lacks unique exact city region")
    group = matches[0]
    alerts = group.get("activeAlerts")
    if not isinstance(alerts, list):
        raise SchemaError("activeAlerts missing; cannot infer OFF")
    air = [a for a in alerts if isinstance(a, dict) and str(a.get("type", "")).upper() == "AIR"]
    reasons: set[str] = set()
    reason_keys_seen = False
    for a in air:
        levels = a.get("activeAlertLevels", a.get("ActiveAlertLevels"))
        if levels is None:
            continue
        if not isinstance(levels, list):
            raise SchemaError("activeAlertLevels is not a list")
        for lvl in levels:
            if not isinstance(lvl, dict):
                raise SchemaError("invalid level")
            if "reason" in lvl or "Reason" in lvl:
                reason_keys_seen = True
                v = lvl.get("reason", lvl.get("Reason"))
                if isinstance(v, list):
                    reasons.update(str(s) for s in v if s is not None and str(s))
                elif v is not None and str(v):
                    reasons.add(str(v))
    return {"active": bool(air), "reasons": sorted(reasons),
            "reason_field_seen": reason_keys_seen, "reason_field_unknown": bool(air) and not reason_keys_seen}


@dataclass
class PollJournal:
    """Observed state transitions, NOT exact publisher timestamps."""
    region_id: str
    active: bool = False
    previous_reasons: tuple[str, ...] | None = None
    episode_index: int = 0
    last_seen: datetime | None = None
    events: list[dict] = field(default_factory=list)

    def observe(self, at: str, snapshot: dict) -> list[dict]:
        stamp = utc(at)
        if self.last_seen and stamp < self.last_seen:
            raise SchemaError("out-of-order poll")
        is_on = snapshot["active"]
        reasons = tuple(sorted(set(snapshot.get("reasons") or ()))) if snapshot.get("reason_field_seen") else None
        emitted = []
        def add(kind: str):
            row = {"event": kind, "observed_at": iso(stamp), "regionId": self.region_id,
                   "episode_index": self.episode_index, "reasons": list(reasons) if reasons is not None else None,
                   "timestamp_semantics": "poll_observed_not_publisher_transition"}
            self.events.append(row)
            emitted.append(row)

        if is_on and not self.active:
            self.episode_index += 1
            add("AIR_ON_OBSERVED")
        elif not is_on and self.active:
            add("AIR_OFF_OBSERVED")
        elif is_on and self.active and self.previous_reasons != reasons:
            add("REASONS_CHANGED_OBSERVED")
        self.active = is_on
        self.previous_reasons = reasons if is_on else None
        self.last_seen = stamp
        return emitted


def compare_exact(history: dict, expected: list[dict]) -> dict:
    """Only compare start AND end to the second, no minute tolerance or assumed 184 aliases."""
    seen = {(row["start"], row["end"]) for row in history["completed"]}
    dates = [utc(row["start"]) for row in history["completed"]]
    low = min(dates) if dates else None
    high = max(utc(row["end"]) for row in history["completed"]) if dates else None
    matched, eligible, outside, mismatched = 0, 0, 0, 0
    for item in expected:
        start, end = utc(item["start"]), utc(item["end"])
        if low is None or start < low or start > high:
            outside += 1
            continue
        eligible += 1
        if (iso(start), iso(end)) in seen:
            matched += 1
        else:
            mismatched += 1
    return {"matched": matched, "eligible": eligible, "out_of_coverage": outside,
            "missing_or_mismatched_in_window": mismatched,
            "truncated_window_possible": history["window_truncation_possible"],
            "full_city_completeness_proven": False}


def assess_transport(status: int | None = None, *, error: str | None = None) -> str:
    """No retries or requests here: bounded retry policy stays in production client."""
    if error in ("Timeout", "ConnectionError", "NetworkError"):
        return "TRANSPORT_UNAVAILABLE"
    if error:
        return "FAIL_CLOSED"
    if status == 401:
        return "AUTH_BLOCKED"
    if status == 429:
        return "RATE_LIMIT_COOLDOWN"
    if status == 200:
        return "PASS"
    return "FAIL_CLOSED"


def next_safe_request_time(last_attempt_monotonic: float, *, retry_after: float = 0) -> float:
    return last_attempt_monotonic + max(float(MIN_REQUEST_GAP_SECONDS), retry_after)
