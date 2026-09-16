#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

CHANNEL = "razvozhaev"
START_DATE = datetime(2023, 9, 20, tzinfo=timezone.utc)
OUT = Path("kyiv-air-alerts-grafana/data/sevastopol_exact_city_audit.json")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/152 Safari/537.36",
    "Accept-Language": "ru,uk;q=0.8,en;q=0.7",
}


@dataclass(frozen=True)
class Msg:
    mid: int
    dt: datetime
    text: str
    url: str


def parse_page(html: str) -> list[Msg]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[Msg] = []
    for wrap in soup.select(".tgme_widget_message_wrap"):
        msg = wrap.select_one(".tgme_widget_message")
        t = wrap.select_one("time[datetime]")
        if not msg or not t:
            continue
        post = msg.get("data-post", "")
        m = re.search(r"/(\d+)$", post)
        if not m:
            continue
        mid = int(m.group(1))
        txt = wrap.select_one(".tgme_widget_message_text")
        text = " ".join(txt.stripped_strings) if txt else ""
        link = wrap.select_one("a.tgme_widget_message_date")
        url = link.get("href") if link else f"https://t.me/{CHANNEL}/{mid}"
        dt = datetime.fromisoformat(t["datetime"].replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        rows.append(Msg(mid, dt.astimezone(timezone.utc), text, url))
    return rows


def fetch_history() -> tuple[list[Msg], dict]:
    sess = requests.Session()
    sess.headers.update(HEADERS)
    found: dict[int, Msg] = {}
    before: int | None = None
    pages = 0
    stalled = 0

    while pages < 1500:
        url = f"https://t.me/s/{CHANNEL}" + (f"?before={before}" if before else "")
        r = sess.get(url, timeout=30)
        r.raise_for_status()
        rows = parse_page(r.text)
        pages += 1
        if not rows:
            break
        for row in rows:
            found[row.mid] = row
        oldest = min(rows, key=lambda x: x.mid)
        page_min_date = min(x.dt for x in rows)
        if page_min_date < START_DATE:
            break
        next_before = oldest.mid
        if before is not None and next_before >= before:
            stalled += 1
            if stalled >= 2:
                break
        else:
            stalled = 0
        before = next_before
        time.sleep(0.06)

    rows = sorted(found.values(), key=lambda x: (x.dt, x.mid))
    rows = [x for x in rows if x.dt >= START_DATE]
    return rows, {
        "pages_requested": pages,
        "messages_loaded_since_start_date": len(rows),
        "earliest_loaded_at": rows[0].dt.isoformat() if rows else None,
        "latest_loaded_at": rows[-1].dt.isoformat() if rows else None,
    }


def normalize(text: str) -> str:
    return " ".join(text.lower().replace("ё", "е").split())


def classify(text: str) -> str | None:
    low = normalize(text)
    if "отбой" in low and "тревог" in low:
        return "end"
    if "воздушная тревога" in low and "отбой" not in low:
        # Ignore explanatory/status posts that merely mention an alert continuing.
        if "продолжа" in low or "действует" in low and not low.startswith("воздушная тревога"):
            return None
        return "start"
    return None


def pair(messages: list[Msg]) -> tuple[list[dict], list[dict], list[dict]]:
    typed = [(m, classify(m.text)) for m in messages]
    typed = [(m, k) for m, k in typed if k]
    active: Msg | None = None
    pairs: list[dict] = []
    anomalies: list[dict] = []
    rows: list[dict] = []

    for msg, kind in typed:
        rows.append({"id": msg.mid, "at": msg.dt.isoformat(), "kind": kind, "url": msg.url, "text": msg.text[:300]})
        if kind == "start":
            if active is not None:
                anomalies.append({
                    "type": "repeated_activation",
                    "previous_id": active.mid,
                    "current_id": msg.mid,
                    "gap_min": round((msg.dt-active.dt).total_seconds()/60, 2),
                    "previous_text": active.text[:300],
                    "current_text": msg.text[:300],
                })
                continue
            active = msg
            continue

        if active is None:
            anomalies.append({"type": "orphan_end", "id": msg.mid, "at": msg.dt.isoformat(), "url": msg.url, "text": msg.text[:300]})
            continue
        if msg.dt <= active.dt:
            anomalies.append({"type": "nonpositive_pair", "start_id": active.mid, "end_id": msg.mid})
            active = None
            continue
        duration = (msg.dt-active.dt).total_seconds()/60
        pairs.append({
            "start": active.dt.isoformat(),
            "end": msg.dt.isoformat(),
            "duration_min": round(duration, 3),
            "start_id": active.mid,
            "end_id": msg.mid,
            "start_url": active.url,
            "end_url": msg.url,
        })
        active = None

    if active is not None:
        anomalies.append({"type": "open_start", "id": active.mid, "at": active.dt.isoformat(), "url": active.url, "text": active.text[:300]})
    return pairs, anomalies, rows


def main() -> None:
    messages, fetch_meta = fetch_history()
    pairs, anomalies, typed = pair(messages)
    starts = [x for x in typed if x["kind"] == "start"]
    by_year: dict[str, dict] = {}
    by_month: dict[str, dict] = {}
    for p in pairs:
        year = p["start"][:4]
        month = p["start"][:7]
        yr = by_year.setdefault(year, {"events": 0, "hours": 0.0})
        mo = by_month.setdefault(month, {"events": 0, "hours": 0.0})
        yr["events"] += 1
        yr["hours"] += p["duration_min"] / 60
        mo["events"] += 1
        mo["hours"] += p["duration_min"] / 60
    for rows in (by_year, by_month):
        for row in rows.values():
            row["hours"] = round(row["hours"], 3)

    start_dts = [datetime.fromisoformat(x["at"]) for x in starts]
    max_gap = None
    if len(start_dts) > 1:
        max_gap = round(max((b-a).total_seconds()/86400 for a,b in zip(start_dts,start_dts[1:])), 2)

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": f"https://t.me/s/{CHANNEL}",
        "provenance": "occupation administration of Sevastopol; descriptive source provenance only",
        "geography": "Sevastopol city-level alert signal",
        "scan_start_utc": START_DATE.isoformat(),
        "fetch": fetch_meta,
        "typed_messages": len(typed),
        "starts": len(starts),
        "paired_events": len(pairs),
        "anomaly_count": len(anomalies),
        "first_start": starts[0] if starts else None,
        "last_start": starts[-1] if starts else None,
        "max_gap_between_starts_days": max_gap,
        "by_year": by_year,
        "by_month": by_month,
        "anomalies": anomalies,
        "typed": typed,
        "pairs": pairs,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "fetch": fetch_meta,
        "starts": out["starts"], "paired_events": out["paired_events"],
        "anomaly_count": out["anomaly_count"], "first_start": out["first_start"],
        "last_start": out["last_start"], "max_gap_between_starts_days": max_gap,
        "by_year": by_year,
        "months": len(by_month),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
