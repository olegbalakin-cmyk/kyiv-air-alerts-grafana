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

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "telegram_source_audit.json"

UA_DISTRICTS = {
    "kherson": ("Херсон", "Херсонський район", "Херсонський_район"),
    "lutsk": ("Луцьк", "Луцький район", "Луцький_район"),
    "uzhhorod": ("Ужгород", "Ужгородський район", "Ужгородський_район"),
    "ivano_frankivsk": ("Івано-Франківськ", "Івано-Франківський район", "Івано-Франківський_район"),
    "chernivtsi": ("Чернівці", "Чернівецький район", "Чернівецький_район"),
    "ternopil": ("Тернопіль", "Тернопільський район", "Тернопільський_район"),
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/152 Safari/537.36",
    "Accept-Language": "uk,en;q=0.8,ru;q=0.7",
}

@dataclass(frozen=True)
class TgMessage:
    message_id: int
    dt: datetime
    text: str
    url: str


def parse_dt(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def fetch_search(channel: str, query: str, max_pages: int = 250) -> list[TgMessage]:
    session = requests.Session()
    session.headers.update(HEADERS)
    before = None
    seen: dict[int, TgMessage] = {}
    last_min = None

    for _ in range(max_pages):
        params = f"q={quote(query)}"
        if before is not None:
            params += f"&before={before}"
        url = f"https://t.me/s/{channel}?{params}"
        resp = session.get(url, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        page_ids = []
        for wrap in soup.select(".tgme_widget_message_wrap"):
            msg = wrap.select_one(".tgme_widget_message")
            time_el = wrap.select_one("time[datetime]")
            if not msg or not time_el:
                continue
            post = msg.get("data-post", "")
            m = re.search(r"/(\d+)$", post)
            if not m:
                continue
            mid = int(m.group(1))
            text_el = wrap.select_one(".tgme_widget_message_text")
            text = " ".join(text_el.stripped_strings) if text_el else ""
            link_el = wrap.select_one("a.tgme_widget_message_date")
            link = link_el.get("href") if link_el else f"https://t.me/{channel}/{mid}"
            seen[mid] = TgMessage(mid, parse_dt(time_el["datetime"]), text, link)
            page_ids.append(mid)

        if not page_ids:
            break
        cur_min = min(page_ids)
        if last_min is not None and cur_min >= last_min:
            break
        last_min = cur_min
        if cur_min <= 1:
            break
        before = cur_min
        time.sleep(0.15)

    return sorted(seen.values(), key=lambda x: (x.dt, x.message_id))


def first_last_summary(messages: list[TgMessage], predicate=None) -> dict:
    rows = [m for m in messages if predicate(m) if predicate is not None] if predicate is not None else list(messages)
    return {
        "count": len(rows),
        "first_at": rows[0].dt.isoformat() if rows else None,
        "first_url": rows[0].url if rows else None,
        "first_text": rows[0].text[:300] if rows else None,
        "last_at": rows[-1].dt.isoformat() if rows else None,
        "last_url": rows[-1].url if rows else None,
        "last_text": rows[-1].text[:300] if rows else None,
    }


def classify_sevastopol(text: str) -> str | None:
    low = text.lower().replace("ё", "е")
    if "отбой" in low and "тревог" in low:
        return "end"
    if "воздушная тревога" in low and "отбой" not in low:
        return "start"
    return None


def classify_mykolaiv(text: str) -> str | None:
    low = text.lower()
    if "відбій повітряної тривоги" in low:
        return "end"
    if "миколаїв" in low and "повітряна тривога" in low and "відбій" not in low:
        return "start"
    return None


def pair_events(messages: list[TgMessage], classifier) -> dict:
    typed = [(m, classifier(m.text)) for m in messages]
    typed = [(m, kind) for m, kind in typed if kind]
    active = None
    pairs = []
    repeated_starts = 0
    orphan_ends = 0
    for msg, kind in typed:
        if kind == "start":
            if active is None:
                active = msg
            else:
                repeated_starts += 1
        elif kind == "end":
            if active is None:
                orphan_ends += 1
            elif msg.dt > active.dt:
                pairs.append({
                    "start": active.dt.isoformat(),
                    "end": msg.dt.isoformat(),
                    "duration_minutes": round((msg.dt - active.dt).total_seconds() / 60, 2),
                    "start_url": active.url,
                    "end_url": msg.url,
                })
                active = None
    return {
        "typed_messages": len(typed),
        "starts": sum(1 for _, k in typed if k == "start"),
        "ends": sum(1 for _, k in typed if k == "end"),
        "paired_events": len(pairs),
        "repeated_starts": repeated_starts,
        "orphan_ends": orphan_ends,
        "open_start_at_end": active.dt.isoformat() if active else None,
        "first_pair": pairs[0] if pairs else None,
        "last_pair": pairs[-1] if pairs else None,
        "total_paired_hours": round(sum(x["duration_minutes"] for x in pairs) / 60, 3),
        "pairs_2026": sum(1 for x in pairs if x["start"].startswith("2026-")),
        "hours_2026": round(sum(x["duration_minutes"] for x in pairs if x["start"].startswith("2026-")) / 60, 3),
    }


def main() -> None:
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "district_official_channel": {},
        "mykolaiv_exact_city": {},
        "sevastopol_exact_city_occupation_authority": {},
    }

    # Official Ukrainian air-alert channel. Search is by district hashtag, so the first
    # returned message is evidence that the district was represented separately by then.
    for key, (city, raion, tag) in UA_DISTRICTS.items():
        messages = fetch_search("air_alert_ua", f"#{tag}", max_pages=80)
        result["district_official_channel"][key] = {
            "city": city,
            "raion": raion,
            "hashtag": f"#{tag}",
            "channel": "@air_alert_ua",
            **first_last_summary(messages),
        }
        print(key, result["district_official_channel"][key]["first_at"], len(messages))

    # Mykolaiv mayor's official channel: explicit city alarm / all-clear messages.
    myk_start = fetch_search("senkevichonline", "Повітряна тривога", max_pages=250)
    myk_end = fetch_search("senkevichonline", "Відбій повітряної тривоги", max_pages=250)
    myk = sorted({m.message_id: m for m in myk_start + myk_end}.values(), key=lambda x: (x.dt, x.message_id))
    result["mykolaiv_exact_city"] = {
        "channel": "@senkevichonline",
        "channel_description": "official channel of Mykolaiv mayor Oleksandr Senkevych",
        "message_summary": first_last_summary(myk, lambda m: classify_mykolaiv(m.text) is not None),
        "pairing": pair_events(myk, classify_mykolaiv),
    }
    print("mykolaiv", result["mykolaiv_exact_city"]["message_summary"]["first_at"], result["mykolaiv_exact_city"]["pairing"]["paired_events"])

    # Sevastopol occupation authority: explicit city alarm / all-clear messages.
    sev = fetch_search("razvozhaev", "тревога", max_pages=350)
    result["sevastopol_exact_city_occupation_authority"] = {
        "channel": "@razvozhaev",
        "source_note": "occupation administration source; city-level signal for Sevastopol",
        "message_summary": first_last_summary(sev, lambda m: classify_sevastopol(m.text) is not None),
        "pairing": pair_events(sev, classify_sevastopol),
    }
    print("sevastopol", result["sevastopol_exact_city_occupation_authority"]["message_summary"]["first_at"], result["sevastopol_exact_city_occupation_authority"]["pairing"]["paired_events"])

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
