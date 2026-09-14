#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import math
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from statistics import mean
from typing import Iterable
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

OFFICIAL_JSON_URL = (
    "https://data.kyivcity.gov.ua/dataset/"
    "statystyka-povitrianykh-tryvoh-u-misti-kyievi-dep-municipal/"
    "resource/5e4fb8a8-f0c8-4a12-885f-192d1f0dba75/data/download"
)
LIVE_HISTORY_URL = "https://kyiv.digital/storage/air-alert/stats.html"
TZ = ZoneInfo("Europe/Kyiv")
UTC = timezone.utc
ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"


@dataclass(frozen=True)
class Alert:
    start: datetime
    end: datetime
    source: str

    @property
    def duration_seconds(self) -> float:
        return max(0.0, (self.end.astimezone(UTC) - self.start.astimezone(UTC)).total_seconds())


def http_session() -> requests.Session:
    retry = Retry(
        total=4,
        connect=4,
        read=4,
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET"]),
    )
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers.update(
        {
            "User-Agent": "kyiv-air-alerts-grafana/1.0 (+public dashboard updater)",
            "Accept-Language": "uk,en;q=0.8",
        }
    )
    return session


def localize_naive(dt: datetime) -> datetime:
    """Treat source timestamps as Kyiv local civil time."""
    if dt.tzinfo is not None:
        return dt.astimezone(TZ)
    return dt.replace(tzinfo=TZ)


def parse_official(payload: object) -> list[Alert]:
    if not isinstance(payload, list):
        raise ValueError("Official JSON root is not a list")
    out: list[Alert] = []
    for row in payload:
        if not isinstance(row, dict):
            continue
        if row.get("type") != "Повітряна тривога":
            continue
        s = row.get("dateTimeStart")
        e = row.get("dateTimeEnd")
        if not s or not e:
            continue
        try:
            start = localize_naive(datetime.fromisoformat(str(s)))
            end = localize_naive(datetime.fromisoformat(str(e)))
        except ValueError:
            continue
        if end.astimezone(UTC) <= start.astimezone(UTC):
            continue
        out.append(Alert(start, end, "official_json"))
    out.sort(key=lambda a: a.start.astimezone(UTC))
    return out


LIVE_DT_RE = re.compile(r"(?P<hm>\d{2}:\d{2})\s+(?P<d>\d{2}\.\d{2}\.\d{2})(?!\d)")


def _kind_from_text(text: str) -> str | None:
    low = " ".join(text.lower().split())
    if "повітряна тривога" in low and "відбій" not in low:
        return "start"
    if "відбій тривоги" in low:
        return "end"
    return None


def _parse_live_dt(text: str) -> datetime | None:
    m = LIVE_DT_RE.search(text)
    if not m:
        return None
    try:
        dt = datetime.strptime(f"{m.group('hm')} {m.group('d')}", "%H:%M %d.%m.%y")
    except ValueError:
        return None
    return localize_naive(dt)


def parse_live_history(html: str) -> tuple[list[Alert], list[tuple[datetime, str]]]:
    """Parse Kyiv Digital's human-readable history into completed start/end pairs.

    The page is reverse chronological. We first extract timestamped rows/blocks,
    then sort them ascending and pair starts with the next all-clear.
    """
    soup = BeautifulSoup(html, "html.parser")
    events: list[tuple[datetime, str]] = []

    # Preferred path: table-like rows or list items that contain a complete event.
    candidates = soup.find_all(["tr", "li", "div", "p"])
    for node in candidates:
        text = " ".join(node.stripped_strings)
        kind = _kind_from_text(text)
        dt = _parse_live_dt(text)
        if kind and dt:
            events.append((dt, kind))

    # Fallback for simpler/changed markup: scan nearby text fragments.
    if not events:
        text = soup.get_text("\n", strip=True)
        lines = [" ".join(x.split()) for x in text.splitlines() if x.strip()]
        for i, line in enumerate(lines):
            window = " | ".join(lines[i : i + 4])
            kind = _kind_from_text(window)
            dt = _parse_live_dt(window)
            if kind and dt:
                events.append((dt, kind))

    # Deduplicate because nested divs can repeat the same row text.
    events = sorted(set(events), key=lambda x: (x[0].astimezone(UTC), x[1]))

    alerts: list[Alert] = []
    active: datetime | None = None
    for dt, kind in events:
        if kind == "start":
            if active is None:
                active = dt
            # Repeated start while an alert is already active is treated as a duplicate.
        elif kind == "end" and active is not None:
            if dt.astimezone(UTC) > active.astimezone(UTC):
                alerts.append(Alert(active, dt, "kyiv_digital_live"))
            active = None

    return alerts, events


def merge_sources(official: list[Alert], live: list[Alert]) -> tuple[list[Alert], int]:
    if not official:
        raise ValueError("Official JSON produced no completed alerts")
    cutoff = max(a.start.astimezone(UTC) for a in official)
    additions = [a for a in live if a.start.astimezone(UTC) > cutoff]
    merged = official + additions
    merged.sort(key=lambda a: a.start.astimezone(UTC))
    return merged, len(additions)


def daterange(start: date, end: date) -> Iterable[date]:
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def month_start(d: date) -> date:
    return d.replace(day=1)


def next_month(d: date) -> date:
    if d.month == 12:
        return date(d.year + 1, 1, 1)
    return date(d.year, d.month + 1, 1)


def month_days(d: date) -> int:
    return (next_month(month_start(d)) - month_start(d)).days


def iso_local_midnight(d: date) -> datetime:
    return datetime.combine(d, time.min, tzinfo=TZ)


def union_daily_seconds(alerts: list[Alert], start_day: date, end_day: date) -> dict[date, float]:
    buckets: dict[date, list[tuple[datetime, datetime]]] = defaultdict(list)
    start_bound = iso_local_midnight(start_day).astimezone(UTC)
    end_bound = iso_local_midnight(end_day + timedelta(days=1)).astimezone(UTC)

    for alert in alerts:
        a0 = alert.start.astimezone(UTC)
        a1 = alert.end.astimezone(UTC)
        if a1 <= start_bound or a0 >= end_bound:
            continue
        first = max(start_day, alert.start.astimezone(TZ).date())
        last = min(end_day, alert.end.astimezone(TZ).date())
        for d in daterange(first, last):
            d0 = iso_local_midnight(d).astimezone(UTC)
            d1 = iso_local_midnight(d + timedelta(days=1)).astimezone(UTC)
            s = max(a0, d0)
            e = min(a1, d1)
            if e > s:
                buckets[d].append((s, e))

    out: dict[date, float] = {}
    for d in daterange(start_day, end_day):
        segs = sorted(buckets.get(d, []), key=lambda x: x[0])
        merged: list[list[datetime]] = []
        for s, e in segs:
            if not merged or s > merged[-1][1]:
                merged.append([s, e])
            elif e > merged[-1][1]:
                merged[-1][1] = e
        out[d] = sum((e - s).total_seconds() for s, e in merged)
    return out


def day_counts_and_durations(alerts: list[Alert], end_day: date) -> tuple[dict[date, int], dict[date, list[float]]]:
    counts: dict[date, int] = defaultdict(int)
    durations: dict[date, list[float]] = defaultdict(list)
    for a in alerts:
        d = a.start.astimezone(TZ).date()
        if d > end_day:
            continue
        counts[d] += 1
        durations[d].append(a.duration_seconds / 60.0)
    return counts, durations


def round3(x: float | None) -> float | None:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return None
    return round(float(x), 3)


def build_outputs(alerts: list[Alert], now_local: datetime, meta: dict) -> dict:
    today = now_local.astimezone(TZ).date()
    end_day = today - timedelta(days=1)
    first_day = min(a.start.astimezone(TZ).date() for a in alerts)

    counts, durations_by_start = day_counts_and_durations(alerts, end_day)
    daily_seconds_all = union_daily_seconds(alerts, first_day, end_day)

    # Long horizon: complete months only.
    last_complete_month = month_start(today) - timedelta(days=1)
    monthly = []
    m = month_start(first_day)
    while m <= month_start(last_complete_month):
        ndays = month_days(m)
        mend = next_month(m) - timedelta(days=1)
        starts = sum(counts.get(d, 0) for d in daterange(m, mend))
        sec = sum(daily_seconds_all.get(d, 0.0) for d in daterange(m, mend))
        event_durs = [x for d in daterange(m, mend) for x in durations_by_start.get(d, [])]
        monthly.append(
            {
                "time": datetime.combine(m, time.min, tzinfo=TZ).isoformat(),
                "month": m.strftime("%Y-%m"),
                "alerts_per_day": round3(starts / ndays),
                "avg_daily_alert_hours": round3(sec / ndays / 3600.0),
                "avg_alert_duration_min": round3(mean(event_durs) if event_durs else None),
                "alerts_started": starts,
            }
        )
        m = next_month(m)

    # Long horizon: complete Monday-Sunday weeks only.
    first_monday = first_day - timedelta(days=first_day.weekday())
    if first_monday < first_day:
        first_monday += timedelta(days=7)
    last_sunday = end_day - timedelta(days=(end_day.weekday() + 1) % 7)
    weekly = []
    ws = first_monday
    while ws + timedelta(days=6) <= last_sunday:
        we = ws + timedelta(days=6)
        starts = sum(counts.get(d, 0) for d in daterange(ws, we))
        weekly.append(
            {
                "time": datetime.combine(ws, time.min, tzinfo=TZ).isoformat(),
                "week_start": ws.isoformat(),
                "week_end": we.isoformat(),
                "alerts_per_day": round3(starts / 7.0),
                "alerts_started": starts,
            }
        )
        ws += timedelta(days=7)

    # Short horizon: exactly 28 completed calendar days.
    short_start = end_day - timedelta(days=27)
    daily_seconds_short = union_daily_seconds(alerts, short_start, end_day)
    daily28 = []
    for d in daterange(short_start, end_day):
        durs = durations_by_start.get(d, [])
        daily28.append(
            {
                "time": datetime.combine(d, time.min, tzinfo=TZ).isoformat(),
                "date": d.isoformat(),
                "alerts_started": counts.get(d, 0),
                "total_alert_duration_minutes": round3(daily_seconds_short.get(d, 0.0) / 60.0),
                "total_alert_duration_hours": round3(daily_seconds_short.get(d, 0.0) / 3600.0),
                "avg_alert_duration_minutes": round3(mean(durs) if durs else None),
            }
        )

    total_alerts = sum(r["alerts_started"] for r in daily28)
    total_minutes = sum(r["total_alert_duration_minutes"] for r in daily28)
    short_event_durations = [
        x for d in daterange(short_start, end_day) for x in durations_by_start.get(d, [])
    ]
    max_count_row = max(daily28, key=lambda r: r["alerts_started"])
    max_time_row = max(daily28, key=lambda r: r["total_alert_duration_minutes"])

    kpis = [
        {
            "period_start": short_start.isoformat(),
            "period_end": end_day.isoformat(),
            "alerts_28d": total_alerts,
            "alert_hours_28d": round3(total_minutes / 60.0),
            "avg_alert_duration_min_28d": round3(mean(short_event_durations) if short_event_durations else None),
            "max_alerts_day": max_count_row["alerts_started"],
            "max_alerts_day_date": max_count_row["date"],
            "max_alert_hours_day": round3(max_time_row["total_alert_duration_minutes"] / 60.0),
            "max_alert_hours_day_date": max_time_row["date"],
        }
    ]

    out = {
        "meta": {
            **meta,
            "timezone": "Europe/Kyiv",
            "generated_at": now_local.astimezone(TZ).isoformat(),
            "analysis_end": end_day.isoformat(),
            "current_day_excluded": today.isoformat(),
            "last_complete_month": month_start(last_complete_month).strftime("%Y-%m"),
            "last_complete_week_start": weekly[-1]["week_start"] if weekly else None,
            "last_complete_week_end": weekly[-1]["week_end"] if weekly else None,
            "short_start": short_start.isoformat(),
            "short_end": end_day.isoformat(),
        },
        "kpis": kpis,
        "monthly": monthly,
        "weekly": weekly,
        "daily28": daily28,
    }
    return out


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    session = http_session()

    r = session.get(OFFICIAL_JSON_URL, timeout=30)
    r.raise_for_status()
    official_payload = r.json()
    official = parse_official(official_payload)

    live_response = session.get(LIVE_HISTORY_URL, timeout=30)
    live_response.raise_for_status()
    live_alerts, live_events = parse_live_history(live_response.text)
    if not live_events:
        raise RuntimeError("Kyiv Digital live history returned no parsable events")

    alerts, live_added = merge_sources(official, live_alerts)
    official_latest_start = max(a.start for a in official)
    official_latest_end = max(a.end for a in official)
    live_latest_event = max((x[0] for x in live_events), default=None)

    now_local = datetime.now(TZ)
    meta = {
        "official_json_url": OFFICIAL_JSON_URL,
        "live_history_url": LIVE_HISTORY_URL,
        "official_completed_alerts": len(official),
        "live_completed_alerts_parsed": len(live_alerts),
        "live_alerts_added_after_official_cutoff": live_added,
        "combined_completed_alerts": len(alerts),
        "official_latest_start": official_latest_start.isoformat(),
        "official_latest_end": official_latest_end.isoformat(),
        "live_latest_event_timestamp": live_latest_event.isoformat() if live_latest_event else None,
    }

    output = build_outputs(alerts, now_local, meta)
    (DATA_DIR / "dashboard_data.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    write_csv(
        DATA_DIR / "short_28d.csv",
        output["daily28"],
        [
            "time",
            "date",
            "alerts_started",
            "total_alert_duration_minutes",
            "total_alert_duration_hours",
            "avg_alert_duration_minutes",
        ],
    )
    write_csv(
        DATA_DIR / "monthly.csv",
        output["monthly"],
        [
            "time",
            "month",
            "alerts_per_day",
            "avg_daily_alert_hours",
            "avg_alert_duration_min",
            "alerts_started",
        ],
    )
    write_csv(
        DATA_DIR / "weekly.csv",
        output["weekly"],
        ["time", "week_start", "week_end", "alerts_per_day", "alerts_started"],
    )

    # Keep a compact copy of completed merged events for auditability.
    combined = [
        {
            "start": a.start.isoformat(),
            "end": a.end.isoformat(),
            "duration_minutes": round3(a.duration_seconds / 60.0),
            "source": a.source,
        }
        for a in alerts
    ]
    (DATA_DIR / "alerts_combined.json").write_text(
        json.dumps(combined, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(json.dumps(output["meta"], ensure_ascii=False, indent=2))
    print(json.dumps(output["kpis"][0], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
