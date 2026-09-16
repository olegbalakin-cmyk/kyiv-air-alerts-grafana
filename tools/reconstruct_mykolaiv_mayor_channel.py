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

CHANNEL = "senkevichonline"
START_DATE = datetime(2025, 7, 15, tzinfo=timezone.utc)
OUT = Path("kyiv-air-alerts-grafana/data/mykolaiv_mayor_channel_audit.json")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/152 Safari/537.36",
    "Accept-Language": "uk,en;q=0.8",
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
    min_seen_date = None
    stalled = 0

    while pages < 800:
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
        min_seen_date = page_min_date if min_seen_date is None else min(min_seen_date, page_min_date)

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
        time.sleep(0.08)

    rows = sorted(found.values(), key=lambda x: (x.dt, x.mid))
    rows = [x for x in rows if x.dt >= START_DATE]
    return rows, {
        "pages_requested": pages,
        "messages_loaded_since_start_date": len(rows),
        "earliest_loaded_at": rows[0].dt.isoformat() if rows else None,
        "latest_loaded_at": rows[-1].dt.isoformat() if rows else None,
    }


def normalize(text: str) -> str:
    return " ".join(text.lower().replace("‼️", " ").replace("❕", " ").replace("⚠️", " ").split())


def classify(text: str) -> str | None:
    low = normalize(text)
    # Exclude local non-air warnings.
    if any(token in low for token in ("артобстр", "артилер", "балістич", "ракетна небезпека", "загроза застосування")):
        return None
    if "відбій повітряної тривоги" in low or ("відбій" in low and "тривог" in low):
        return "end"
    if "повітряна тривога" in low and "відбій" not in low:
        return "start"
    return None


def pair_alerts(messages: list[Msg]) -> tuple[list[dict], list[dict], list[dict]]:
    typed = [(m, classify(m.text)) for m in messages]
    typed = [(m, k) for m, k in typed if k]
    active: Msg | None = None
    pairs: list[dict] = []
    anomalies: list[dict] = []
    typed_rows: list[dict] = []

    for msg, kind in typed:
        typed_rows.append({"id": msg.mid, "at": msg.dt.isoformat(), "kind": kind, "url": msg.url, "text": msg.text[:300]})
        if kind == "start":
            if active is not None:
                anomalies.append({"type": "repeated_start", "previous_id": active.mid, "current_id": msg.mid, "gap_min": round((msg.dt-active.dt).total_seconds()/60, 2)})
            active = msg
            continue

        if active is None:
            anomalies.append({"type": "orphan_end", "id": msg.mid, "at": msg.dt.isoformat(), "url": msg.url})
            continue
        if msg.dt <= active.dt:
            anomalies.append({"type": "nonpositive_pair", "start_id": active.mid, "end_id": msg.mid})
            active = None
            continue
        duration_min = (msg.dt - active.dt).total_seconds() / 60
        pairs.append({
            "start": active.dt.isoformat(),
            "end": msg.dt.isoformat(),
            "duration_min": round(duration_min, 3),
            "start_id": active.mid,
            "end_id": msg.mid,
            "start_url": active.url,
            "end_url": msg.url,
        })
        active = None

    if active is not None:
        anomalies.append({"type": "open_start", "id": active.mid, "at": active.dt.isoformat(), "url": active.url})

    return pairs, anomalies, typed_rows


def max_start_gap_days(typed_rows: list[dict]) -> float | None:
    starts = [datetime.fromisoformat(x["at"]) for x in typed_rows if x["kind"] == "start"]
    if len(starts) < 2:
        return None
    return round(max((b-a).total_seconds() / 86400 for a, b in zip(starts, starts[1:])), 2)


def main() -> None:
    messages, fetch_meta = fetch_history()
    pairs, anomalies, typed_rows = pair_alerts(messages)
    by_month: dict[str, dict] = {}
    for p in pairs:
        month = p["start"][:7]
        row = by_month.setdefault(month, {"events": 0, "hours": 0.0})
        row["events"] += 1
        row["hours"] += p["duration_min"] / 60
    for row in by_month.values():
        row["hours"] = round(row["hours"], 3)

    starts = [x for x in typed_rows if x["kind"] == "start"]
    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": f"https://t.me/s/{CHANNEL}",
        "source_note": "Official channel of Mykolaiv mayor Oleksandr Senkevych; reconstruction uses sequential public channel pages, not Telegram search results.",
        "scan_start_utc": START_DATE.isoformat(),
        "fetch": fetch_meta,
        "typed_alert_messages": len(typed_rows),
        "starts": len(starts),
        "paired_events": len(pairs),
        "anomaly_count": len(anomalies),
        "max_gap_between_starts_days": max_start_gap_days(typed_rows),
        "first_start": starts[0] if starts else None,
        "last_start": starts[-1] if starts else None,
        "by_month": by_month,
        "anomalies": anomalies,
        "typed_messages": typed_rows,
        "pairs": pairs,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "fetch": fetch_meta,
        "typed_alert_messages": out["typed_alert_messages"],
        "starts": out["starts"],
        "paired_events": out["paired_events"],
        "anomaly_count": out["anomaly_count"],
        "max_gap_between_starts_days": out["max_gap_between_starts_days"],
        "first_start": out["first_start"],
        "last_start": out["last_start"],
        "by_month_count": len(by_month),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
