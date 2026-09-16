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

CHANNEL = "air_alert_ua"
HASHTAG = "#м_Миколаїв_та_Миколаївська_територіальна_громада"
OUT = Path("kyiv-air-alerts-grafana/data/mykolaiv_exact_city_audit.json")
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
        text_el = wrap.select_one(".tgme_widget_message_text")
        text = " ".join(text_el.stripped_strings) if text_el else ""
        date_link = wrap.select_one("a.tgme_widget_message_date")
        url = date_link.get("href") if date_link else f"https://t.me/{CHANNEL}/{mid}"
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


def fetch_search() -> tuple[list[Msg], dict]:
    sess = requests.Session()
    sess.headers.update(HEADERS)
    initial = f"https://t.me/s/{CHANNEL}?q={quote(HASHTAG)}"
    queue = [initial]
    seen_urls = set()
    found: dict[int, Msg] = {}
    page_meta = []

    # Prefer Telegram's own navigation links if present.
    while queue and len(seen_urls) < 200:
        url = queue.pop(0)
        if url in seen_urls:
            continue
        seen_urls.add(url)
        r = sess.get(url, timeout=30)
        r.raise_for_status()
        rows, more = parse_page(r.text)
        for x in rows:
            if HASHTAG.lower() in x.text.lower():
                found[x.mid] = x
        page_meta.append({"url": url, "messages": len(rows), "matched": sum(HASHTAG.lower() in x.text.lower() for x in rows), "more": more})
        for u in more:
            if u not in seen_urls:
                queue.append(u)
        if more:
            time.sleep(0.15)

    # Telegram search sometimes exposes no navigation. Probe backwards by the
    # oldest returned message id; stop if the page does not move.
    if found:
        before = min(found)
        last_min = before
        for _ in range(200):
            url = f"{initial}&before={before}"
            if url in seen_urls:
                break
            seen_urls.add(url)
            r = sess.get(url, timeout=30)
            r.raise_for_status()
            rows, more = parse_page(r.text)
            matched = [x for x in rows if HASHTAG.lower() in x.text.lower()]
            for x in matched:
                found[x.mid] = x
            page_meta.append({"url": url, "messages": len(rows), "matched": len(matched), "more": more})
            ids = [x.mid for x in matched]
            if not ids:
                break
            cur_min = min(ids)
            if cur_min >= last_min:
                break
            last_min = cur_min
            before = cur_min
            time.sleep(0.15)

    return sorted(found.values(), key=lambda x: (x.dt, x.mid)), {
        "pages_requested": len(seen_urls),
        "page_meta": page_meta,
    }


def kind(text: str) -> str | None:
    low = text.lower()
    # This project is about air alerts; do not mix artillery-warning episodes.
    if "артобстр" in low or "артилер" in low:
        return None
    if "відбій тривоги" in low:
        return "end"
    if "повітряна тривога" in low and "відбій" not in low:
        return "start"
    return None


def pair(messages: list[Msg]) -> tuple[list[dict], dict]:
    air = [(m, kind(m.text)) for m in messages]
    air = [(m, k) for m, k in air if k]
    active: Msg | None = None
    pairs = []
    anomalies = []

    for msg, k in air:
        if k == "start":
            if active is not None:
                anomalies.append({"type": "repeated_start", "previous": active.url, "current": msg.url})
                # Mirror the source semantics conservatively: the newest start is
                # the authoritative current activation if no all-clear was seen.
            active = msg
        else:
            if active is None:
                anomalies.append({"type": "orphan_end", "url": msg.url})
                continue
            if msg.dt <= active.dt:
                anomalies.append({"type": "nonpositive_pair", "start": active.url, "end": msg.url})
                active = None
                continue
            pairs.append({
                "start": active.dt.isoformat(),
                "end": msg.dt.isoformat(),
                "duration_min": round((msg.dt - active.dt).total_seconds() / 60, 3),
                "start_id": active.mid,
                "end_id": msg.mid,
                "start_url": active.url,
                "end_url": msg.url,
            })
            active = None

    if active is not None:
        anomalies.append({"type": "open_start", "url": active.url, "at": active.dt.isoformat()})

    stats = {
        "air_messages": len(air),
        "starts": sum(k == "start" for _, k in air),
        "ends": sum(k == "end" for _, k in air),
        "paired_events": len(pairs),
        "anomalies": anomalies,
    }
    return pairs, stats


def main() -> None:
    messages, fetch_meta = fetch_search()
    pairs, stats = pair(messages)
    air_msgs = [m for m in messages if kind(m.text)]

    by_year = {}
    for p in pairs:
        y = p["start"][:4]
        by_year.setdefault(y, {"events": 0, "hours": 0.0})
        by_year[y]["events"] += 1
        by_year[y]["hours"] += p["duration_min"] / 60
    for y in by_year:
        by_year[y]["hours"] = round(by_year[y]["hours"], 3)

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": f"https://t.me/s/{CHANNEL}",
        "source_note": "Official Ukrainian air-alert channel; information is supplied by Ukrainian executive authorities.",
        "location": "м. Миколаїв та Миколаївська територіальна громада",
        "hashtag": HASHTAG,
        "scope": "air-alert episodes only; artillery-warning messages explicitly excluded",
        "fetch": fetch_meta,
        "message_count_matching_hashtag": len(messages),
        "air_message_count": len(air_msgs),
        "first_air_message": ({"at": air_msgs[0].dt.isoformat(), "id": air_msgs[0].mid, "url": air_msgs[0].url, "text": air_msgs[0].text} if air_msgs else None),
        "last_air_message": ({"at": air_msgs[-1].dt.isoformat(), "id": air_msgs[-1].mid, "url": air_msgs[-1].url, "text": air_msgs[-1].text} if air_msgs else None),
        "pair_stats": stats,
        "by_year": by_year,
        "pairs": pairs,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("message_count_matching_hashtag", "air_message_count", "first_air_message", "last_air_message", "pair_stats", "by_year")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
