#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urljoin

import requests
from bs4 import BeautifulSoup

CHANNEL = "razvozhaev"
QUERY = "воздушная тревога"
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


def parse_page(html: str) -> tuple[list[Msg], list[str]]:
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
    more = []
    for a in soup.select("a.tme_messages_more, a.tgme_widget_message_more"):
        href = a.get("href")
        if href:
            more.append(urljoin("https://t.me", href))
    return rows, more


def fetch_search_graph() -> tuple[list[Msg], dict]:
    sess = requests.Session()
    sess.headers.update(HEADERS)
    initial = f"https://t.me/s/{CHANNEL}?q={quote(QUERY)}"
    queue = [initial]
    seen_urls = set()
    found: dict[int, Msg] = {}
    page_meta = []

    while queue and len(seen_urls) < 1000:
        url = queue.pop(0)
        if url in seen_urls:
            continue
        seen_urls.add(url)
        r = sess.get(url, timeout=30)
        r.raise_for_status()
        rows, more = parse_page(r.text)
        for x in rows:
            if "тревог" in x.text.lower():
                found[x.mid] = x
        page_meta.append({"url": url, "messages": len(rows), "more": more})
        for u in more:
            if u not in seen_urls:
                queue.append(u)
        time.sleep(0.06)

    # Supplement graph traversal by walking backwards from oldest result.
    if found:
        before = min(found)
        last_min = before
        for _ in range(1000):
            url = f"{initial}&before={before}"
            if url in seen_urls:
                break
            seen_urls.add(url)
            r = sess.get(url, timeout=30)
            r.raise_for_status()
            rows, more = parse_page(r.text)
            matched = [x for x in rows if "тревог" in x.text.lower()]
            for x in matched:
                found[x.mid] = x
            page_meta.append({"url": url, "messages": len(rows), "more": more})
            if not matched:
                break
            cur_min = min(x.mid for x in matched)
            if cur_min >= last_min:
                break
            last_min = cur_min
            before = cur_min
            time.sleep(0.06)

    return sorted(found.values(), key=lambda x: (x.dt, x.mid)), {
        "pages_requested": len(seen_urls),
        "unique_search_messages": len(found),
    }


def classify(text: str) -> str | None:
    low = " ".join(text.lower().replace("ё", "е").split())
    if "отбой" in low and "тревог" in low:
        return "end"
    if "воздушная тревога" in low and "отбой" not in low:
        return "start"
    return None


def pair(messages: list[Msg]) -> tuple[list[dict], list[dict], list[dict]]:
    typed = [(m, classify(m.text)) for m in messages]
    typed = [(m, k) for m, k in typed if k]
    active: Msg | None = None
    pairs = []
    anomalies = []
    rows = []
    for msg, kind in typed:
        rows.append({"id": msg.mid, "at": msg.dt.isoformat(), "kind": kind, "url": msg.url, "text": msg.text[:300]})
        if kind == "start":
            if active is not None:
                anomalies.append({"type": "repeated_start", "previous_id": active.mid, "current_id": msg.mid, "gap_min": round((msg.dt-active.dt).total_seconds()/60, 2)})
            active = msg
        else:
            if active is None:
                anomalies.append({"type": "orphan_end", "id": msg.mid, "at": msg.dt.isoformat()})
                continue
            if msg.dt <= active.dt:
                anomalies.append({"type": "nonpositive_pair", "start_id": active.mid, "end_id": msg.mid})
                active = None
                continue
            duration = (msg.dt-active.dt).total_seconds()/60
            pairs.append({
                "start": active.dt.isoformat(), "end": msg.dt.isoformat(),
                "duration_min": round(duration, 3),
                "start_id": active.mid, "end_id": msg.mid,
                "start_url": active.url, "end_url": msg.url,
            })
            active = None
    if active is not None:
        anomalies.append({"type": "open_start", "id": active.mid, "at": active.dt.isoformat()})
    return pairs, anomalies, rows


def main() -> None:
    messages, fetch_meta = fetch_search_graph()
    pairs, anomalies, typed = pair(messages)
    starts = [x for x in typed if x["kind"] == "start"]
    by_year: dict[str, dict] = {}
    for p in pairs:
        year = p["start"][:4]
        row = by_year.setdefault(year, {"events": 0, "hours": 0.0})
        row["events"] += 1
        row["hours"] += p["duration_min"] / 60
    for row in by_year.values():
        row["hours"] = round(row["hours"], 3)

    start_dts = [datetime.fromisoformat(x["at"]) for x in starts]
    max_gap = None
    if len(start_dts) > 1:
        max_gap = round(max((b-a).total_seconds()/86400 for a,b in zip(start_dts,start_dts[1:])), 2)

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": f"https://t.me/s/{CHANNEL}",
        "provenance": "occupation administration of Sevastopol; use as descriptive source provenance only",
        "geography": "Sevastopol city-level alert signal",
        "fetch": fetch_meta,
        "typed_messages": len(typed),
        "starts": len(starts),
        "paired_events": len(pairs),
        "anomaly_count": len(anomalies),
        "first_start": starts[0] if starts else None,
        "last_start": starts[-1] if starts else None,
        "max_gap_between_starts_days": max_gap,
        "by_year": by_year,
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
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
