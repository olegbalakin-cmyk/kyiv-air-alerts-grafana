#!/usr/bin/env python3
"""OFF-by-default official Telegram threat evidence shadow. No Neon or publication."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit
from bs4 import BeautifulSoup

CHANNELS = ("air_alert_ua", "kpszsu")
# These are explicit CITY mentions, not oblast-to-city inferred matches.
CITY_NAMES = {
    "kyiv": ("Київ", "Києві", "Києва"), "kharkiv": ("Харків", "Харкові", "Харкова"),
    "zaporizhzhia": ("Запоріжжя", "Запоріжжю"),
    "cherkasy": ("Черкаси", "Черкасах"), "zhytomyr": ("Житомир", "Житомирі"),
    "dnipro": ("Дніпро", "Дніпра", "Дніпрі"),
    "khmelnytskyi": ("Хмельницький", "Хмельницькому"),
    "poltava": ("Полтава", "Полтаві", "Полтаву"),
    "rivne": ("Рівне", "Рівному"), "sumy": ("Суми", "Сумах"),
    "vinnytsia": ("Вінниця", "Вінниці", "Вінницю"),
    "kropyvnytskyi": ("Кропивницький", "Кропивницькому"),
    "lviv": ("Львів", "Львова", "Львові"),
    "chernihiv": ("Чернігів", "Чернігові", "Чернігова"),
    "odesa": ("Одеса", "Одесі", "Одесу"),
    "sevastopol": ("Севастополь", "Севастополі"),
    "kherson": ("Херсон", "Херсоні", "Херсона"),
    "mykolaiv": ("Миколаїв", "Миколаєві", "Миколаєва"),
    "lutsk": ("Луцьк", "Луцьку"), "uzhhorod": ("Ужгород", "Ужгороді"),
    "ivano-frankivsk": ("Івано-Франківськ", "Івано-Франківську"),
    "ternopil": ("Тернопіль", "Тернополі"),
    "chernivtsi": ("Чернівці", "Чернівцях"),
}
assert len(CITY_NAMES) == 23
THREATS = {
    "uav": r"\b(?:бпла|дрон(?:и|ів|ами|а|у)?|безпілотник(?:и|ів)?|шахед(?:и|ів)?|shahed)\b",
    "ballistic": r"\b(?:балістичн\w*|балістик\w*|аеробалістичн\w*|кинджал\w*|кінжал\w*)",
    "cruise_missile": r"\b(?:крилат\w*\s+ракет\w*|калібр\w*|x-101|х-101|х-555|x-555)\b",
    "guided_bomb": r"\b(?:каб(?:и|ів|ами)?|керован\w*\s+авіабомб\w*)\b",
    "aviation": r"\b(?:тактичн\w*\s+авіаці\w*|ворож\w*\s+авіаці\w*)\b",
    "unspecified_missile": r"\b(?:ракетн\w*\s+загроз\w*|ракет\w*)",
}
NEGATIONS = re.compile(r"відбій|загроз[ауи]?\s+знят|загроза\s+минул|загроз[аи]\s+немає|відсутн\w*\s+загроз|не\s+підтверджено|підсумки|зведення\s+за|знищено\s+\d+", re.I)
MAX_BYTES = 2 * 1024 * 1024
SAFE_OUT = {"dashboard_data.json", "alerts_combined.json", "site_derived.json", "kyiv_threat_mix.json"}


def aware(value: str) -> datetime:
    dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("Timestamp without timezone is not evidence")
    return dt.astimezone(timezone.utc)


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def validate_message(msg: dict) -> dict:
    channel = msg.get("channel")
    if channel not in CHANNELS:
        raise ValueError("Only the pinned official channels are accepted")
    url = str(msg.get("url") or "")
    p = urlsplit(url)
    if (p.scheme != "https" or p.hostname != "t.me" or p.query or p.fragment or
            not re.fullmatch(rf"/{channel}/[0-9]+", p.path)):
        raise ValueError("Message URL must identify a post in its official channel")
    txt = str(msg.get("text") or "").strip()
    if not txt or len(txt) > 16000:
        raise ValueError("Empty/oversized Telegram message")
    return {"channel": channel, "url": url,
            "published_at": aware(str(msg["published_at"])).isoformat(),
            "text": txt, "text_sha256": sha(txt.encode("utf-8"))}


def parse_saved_html(raw: bytes, channel: str) -> list[dict]:
    if channel not in CHANNELS or len(raw) > MAX_BYTES:
        raise ValueError("Source not allowed or captured HTML too large")
    soup = BeautifulSoup(raw, "html.parser")
    out = []
    for card in soup.select("div.tgme_widget_message[data-post]"):
        post = card.get("data-post", "")
        if not re.fullmatch(rf"{channel}/[0-9]+", post):
            continue
        node = card.select_one(".tgme_widget_message_text")
        clock = card.select_one("time[datetime]")
        if node is None or clock is None:
            continue
        out.append(validate_message({"channel": channel, "url": f"https://t.me/{post}",
                                    "published_at": clock["datetime"],
                                    "text": node.get_text(" ", strip=True)}))
    if not out:
        raise ValueError("No parseable dated official Telegram posts; fail closed")
    return out


def fetch_one_public_preview(channel: str, *, http_go: bool = False, session=None) -> bytes:
    """Manual, bounded one-shot HTTP only; NOT called during ordinary shadow matching."""
    if channel not in CHANNELS or not http_go or os.environ.get("THREAT_SHADOW_HTTP_GO") != "YES":
        raise PermissionError("One-shot read-only HTTP GO was not provided")
    import requests
    s = session or requests.Session()
    response = s.get(f"https://t.me/s/{channel}", timeout=15, allow_redirects=False, stream=True)
    if response.status_code != 200:
        raise ValueError("Expected HTTP 200; redirects are forbidden")
    size, chunks = 0, []
    for chunk in response.iter_content(chunk_size=65536):
        size += len(chunk)
        if size > MAX_BYTES:
            raise ValueError("HTTP preview exceeds 2 MiB")
        chunks.append(chunk)
    return b"".join(chunks)


def normalize_messages(messages: list[dict]) -> list[dict]:
    seen = {}
    for msg in messages:
        item = validate_message(msg)
        old = seen.get(item["url"])
        if old is not None and old != item:
            raise ValueError("Conflicting Telegram evidence for same post; manual review")
        seen[item["url"]] = item
    return sorted(seen.values(), key=lambda x: (x["published_at"], x["url"]))


def threats_and_city_mentions(text: str) -> tuple[list[str], list[str]]:
    if NEGATIONS.search(text):
        return [], []
    threats = [k for k, pattern in THREATS.items() if re.search(pattern, text, re.I)]
    if threats and "unspecified_missile" in threats and ("ballistic" in threats or "cruise_missile" in threats):
        threats.remove("unspecified_missile")
    cities = [key for key, aliases in CITY_NAMES.items() if any(
        re.search(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", text, re.I) for alias in aliases)]
    return threats, cities


def normalize_alerts(payload: list[dict]) -> list[dict]:
    if not isinstance(payload, list):
        raise ValueError("Alerts must be a bounded JSON array")
    out = []
    for row in payload:
        city = row.get("city_key")
        if city not in CITY_NAMES or not row.get("end"):
            raise ValueError("Only known 23-city completed alerts can be used in shadow join")
        start, end = aware(str(row["start"])), aware(str(row["end"]))
        if start >= end:
            raise ValueError("Non-positive alert interval")
        out.append({"city_key": city, "start": start.isoformat(), "end": end.isoformat(),
                    "alert_id": row.get("alert_id") or sha(f"{city}|{start.isoformat()}|{end.isoformat()}".encode())[:24]})
    ids = [r["alert_id"] for r in out]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate alert IDs")
    return sorted(out, key=lambda r: (r["city_key"], r["start"]))


def join_evidence(alerts: list[dict], messages: list[dict]) -> dict:
    intervals = normalize_alerts(alerts)
    evidence = normalize_messages(messages)
    result = {r["alert_id"]: {**r, "threat_types": [], "evidence": [],
                              "reason_confirmed": False} for r in intervals}
    unmatched = []
    matched_messages = 0
    for msg in evidence:
        types, cities = threats_and_city_mentions(msg["text"])
        if not types:
            unmatched.append({"url": msg["url"], "reason": "NO_POSITIVE_CLASSIFIED_THREAT"})
            continue
        if not cities:
            unmatched.append({"url": msg["url"], "reason": "NO_EXPLICIT_CITY_SCOPE"})
            continue
        when = aware(msg["published_at"])
        matches = 0
        for city in cities:
            relevant = [r for r in intervals if r["city_key"] == city and
                        aware(r["start"]) - timedelta(minutes=10) <= when <= aware(r["end"])]
            if len(relevant) != 1:
                continue
            row = relevant[0]
            mins_from_start = (when - aware(row["start"])).total_seconds() / 60
            cause_candidate = (msg["channel"] == "air_alert_ua" and
                               -5 <= mins_from_start <= 5 and
                               bool(re.search(r"загроз|тривог", msg["text"], re.I)))
            item = {"url": msg["url"], "published_at": msg["published_at"],
                    "channel": msg["channel"], "text_sha256": msg["text_sha256"],
                    "threat_types": types,
                    "relationship": "ONSET_REASON_CANDIDATE" if cause_candidate else "THREAT_DURING_ALERT",
                    "reason_confirmed": False}
            result[row["alert_id"]]["evidence"].append(item)
            result[row["alert_id"]]["threat_types"] = sorted(set(result[row["alert_id"]]["threat_types"]) | set(types))
            matches += 1
        if matches:
            matched_messages += 1
        else:
            unmatched.append({"url": msg["url"], "reason": "NO_UNAMBIGUOUS_CITY_ALERT_MATCH"})
    return {"schema": "official-threat-evidence-shadow-v1", "publish_allowed": False,
            "neon_write_allowed": False, "claims_alert_cause": False,
            "metrics": {"alerts": len(intervals), "messages": len(evidence),
                        "messages_associated": matched_messages,
                        "alerts_with_evidence": sum(bool(r["evidence"]) for r in result.values()),
                        "unmatched_messages": len(unmatched)},
            "episodes": list(result.values()), "unmatched": unmatched}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--saved-html", action="append", default=[], help="channel:/path/to/previously-captured.html")
    p.add_argument("--one-shot-http-channel", choices=CHANNELS, action="append", default=[])
    p.add_argument("--one-shot-http-go", action="store_true")
    p.add_argument("--messages", type=Path, help="Already normalized official messages JSON array")
    p.add_argument("--alerts", type=Path, help="Pinned completed 23-city interval JSON array for matching")
    p.add_argument("--out", type=Path, required=True, help="New shadow JSON, never canonical data")
    args = p.parse_args()
    if args.out.name in SAFE_OUT or args.out.exists():
        p.error("Refusing canonical or existing output")
    msgs = []
    if args.messages:
        msgs.extend(json.loads(args.messages.read_text(encoding="utf-8")))
    for spec in args.saved_html:
        channel, sep, path = spec.partition(":")
        if not sep:
            p.error("Invalid saved HTML spec")
        msgs.extend(parse_saved_html(Path(path).read_bytes(), channel))
    if len(args.one_shot_http_channel) != len(set(args.one_shot_http_channel)):
        p.error("No repeated channel GET in a single run")
    for channel in args.one_shot_http_channel:
        raw = fetch_one_public_preview(channel, http_go=args.one_shot_http_go)
        msgs.extend(parse_saved_html(raw, channel))
    if not msgs:
        p.error("No evidence input")
    normalized = normalize_messages(msgs)
    if args.alerts:
        result = join_evidence(json.loads(args.alerts.read_text(encoding="utf-8")), normalized)
    else:
        result = {"schema": "official-threat-messages-shadow-v1", "publish_allowed": False,
                  "messages": normalized}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
