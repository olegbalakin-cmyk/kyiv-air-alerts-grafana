#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

CHANNEL = "razvozhaev"
START_AFTER_ID = 3980
QUERY = "воздушная тревога"
OUT = Path("kyiv-air-alerts-grafana/data/sevastopol_forward_audit.json")
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


def parse(html: str) -> list[Msg]:
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for wrap in soup.select(".tgme_widget_message_wrap"):
        msg = wrap.select_one(".tgme_widget_message")
        tm = wrap.select_one("time[datetime]")
        if not msg or not tm:
            continue
        m = re.search(r"/(\d+)$", msg.get("data-post", ""))
        if not m:
            continue
        mid = int(m.group(1))
        txt = wrap.select_one(".tgme_widget_message_text")
        text = " ".join(txt.stripped_strings) if txt else ""
        link = wrap.select_one("a.tgme_widget_message_date")
        url = link.get("href") if link else f"https://t.me/{CHANNEL}/{mid}"
        dt = datetime.fromisoformat(tm["datetime"].replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        out.append(Msg(mid, dt.astimezone(timezone.utc), text, url))
    return out


def classify(text: str) -> str | None:
    low = " ".join(text.lower().replace("ё", "е").split())
    if "отбой" in low and "тревог" in low:
        return "end"
    if "воздушная тревога" in low and "отбой" not in low:
        # explanatory posts are not activations
        if any(p in low for p in ("в случае воздушной тревоги", "при воздушной тревоге", "если воздушная тревога", "во время воздушной тревоги")):
            return None
        return "start"
    return None


def forward_pages(session: requests.Session, *, use_search: bool, max_pages: int) -> tuple[list[Msg], dict]:
    after = START_AFTER_ID
    found: dict[int, Msg] = {}
    pages = 0
    stalls = 0
    last_page_max = after
    query_arg = f"&q={quote(QUERY)}" if use_search else ""

    while pages < max_pages:
        url = f"https://t.me/s/{CHANNEL}?after={after}{query_arg}"
        r = session.get(url, timeout=30)
        r.raise_for_status()
        rows = parse(r.text)
        pages += 1
        if not rows:
            break

        for row in rows:
            if classify(row.text):
                found[row.mid] = row

        page_max = max(x.mid for x in rows)
        if page_max <= after or page_max <= last_page_max:
            stalls += 1
            if stalls >= 2:
                break
        else:
            stalls = 0
        last_page_max = page_max
        after = page_max
        time.sleep(0.02)

    return sorted(found.values(), key=lambda x: (x.dt, x.mid)), {
        "mode": "search_after" if use_search else "plain_after",
        "pages": pages,
        "last_after": after,
        "typed_found": len(found),
    }


def fetch_history() -> tuple[list[Msg], dict]:
    session = requests.Session()
    session.headers.update(HEADERS)

    # First try Telegram's search+after combination. If it advances through
    # historical matches, this is dramatically cheaper than loading every post.
    search_rows, search_meta = forward_pages(session, use_search=True, max_pages=300)
    search_span = (search_rows[-1].mid - search_rows[0].mid) if len(search_rows) >= 2 else 0
    if search_rows and search_meta["last_after"] > 20000 and search_span > 10000:
        return search_rows, {"strategy": "search_after", "search": search_meta}

    # Fallback: chronological public-channel pages from the known Sep-2023 id.
    plain_rows, plain_meta = forward_pages(session, use_search=False, max_pages=1300)
    return plain_rows, {"strategy": "plain_after", "search_probe": search_meta, "plain": plain_meta}


def pair(messages: list[Msg]) -> tuple[list[dict], list[dict], list[dict]]:
    active: Msg | None = None
    pairs = []
    anomalies = []
    typed = []
    for msg in messages:
        kind = classify(msg.text)
        if not kind:
            continue
        typed.append({"id": msg.mid, "at": msg.dt.isoformat(), "kind": kind, "url": msg.url, "text": msg.text[:400]})
        if kind == "start":
            if active is not None:
                anomalies.append({"type": "repeated_start", "previous_id": active.mid, "current_id": msg.mid, "gap_min": round((msg.dt-active.dt).total_seconds()/60, 2)})
                # Preserve earliest activation until an all-clear.
                continue
            active = msg
        else:
            if active is None:
                anomalies.append({"type": "orphan_end", "id": msg.mid, "at": msg.dt.isoformat()})
                continue
            duration = (msg.dt-active.dt).total_seconds()/60
            if duration <= 0:
                anomalies.append({"type": "nonpositive", "start_id": active.mid, "end_id": msg.mid})
                active = None
                continue
            pairs.append({
                "start": active.dt.isoformat(), "end": msg.dt.isoformat(),
                "duration_min": round(duration, 3),
                "start_id": active.mid, "end_id": msg.mid,
                "start_url": active.url, "end_url": msg.url,
            })
            active = None
    if active is not None:
        anomalies.append({"type": "open_start", "id": active.mid, "at": active.dt.isoformat()})
    return pairs, anomalies, typed


def main() -> None:
    messages, fetch_meta = fetch_history()
    pairs, anomalies, typed = pair(messages)
    starts = [x for x in typed if x["kind"] == "start"]
    by_year: dict[str, dict] = {}
    by_month: dict[str, dict] = {}
    for p in pairs:
        for key, bucket in ((p["start"][:4], by_year), (p["start"][:7], by_month)):
            row = bucket.setdefault(key, {"events": 0, "hours": 0.0})
            row["events"] += 1
            row["hours"] += p["duration_min"] / 60
    for bucket in (by_year, by_month):
        for row in bucket.values():
            row["hours"] = round(row["hours"], 3)

    start_dts = [datetime.fromisoformat(x["at"]) for x in starts]
    max_gap = round(max((b-a).total_seconds()/86400 for a,b in zip(start_dts,start_dts[1:])), 2) if len(start_dts) > 1 else None
    long_pairs = [p for p in pairs if p["duration_min"] > 12*60]

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": f"https://t.me/s/{CHANNEL}",
        "provenance": "occupation administration of Sevastopol; descriptive source provenance only",
        "coverage_start_external": "2023-09-25",
        "start_after_message_id": START_AFTER_ID,
        "fetch": fetch_meta,
        "typed_messages": len(typed),
        "starts": len(starts),
        "paired_events": len(pairs),
        "anomaly_count": len(anomalies),
        "long_pair_count_gt_12h": len(long_pairs),
        "first_start": starts[0] if starts else None,
        "last_start": starts[-1] if starts else None,
        "max_gap_between_starts_days": max_gap,
        "by_year": by_year,
        "by_month": by_month,
        "anomalies": anomalies,
        "long_pairs_gt_12h": long_pairs,
        "typed": typed,
        "pairs": pairs,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "fetch": fetch_meta,
        "typed_messages": len(typed), "starts": len(starts), "paired_events": len(pairs),
        "anomaly_count": len(anomalies), "long_pair_count_gt_12h": len(long_pairs),
        "first_start": out["first_start"], "last_start": out["last_start"],
        "max_gap_between_starts_days": max_gap, "by_year": by_year,
    }, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
