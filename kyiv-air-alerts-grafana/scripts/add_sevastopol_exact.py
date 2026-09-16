#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

import expand_multicity_production as multi
from update_data import Alert, TZ, build_outputs

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "data" / "dashboard_data.json"
DASHBOARD = ROOT / "grafana" / "dashboard.json"
STRICT_AUDIT = ROOT / "data" / "sevastopol_strict_audit.json"
EVENTS_FILE = ROOT / "data" / "sevastopol_events.json"
CORRECTIONS_FILE = ROOT / "data" / "sevastopol_event_corrections.json"

CITY_KEY = "sevastopol"
CITY_LABEL = "Севастополь (сигнали окупаційної адміністрації)"
COVERAGE_START = "2023-09-25"
CHANNEL = "razvozhaev"
SOURCE_URL = f"https://t.me/s/{CHANNEL}"
LOOKBACK_DAYS = 21
UTC = timezone.utc
HEADERS = {
    "User-Agent": "kyiv-air-alerts-grafana/1.0 (+public dashboard updater)",
    "Accept-Language": "ru,uk;q=0.8,en;q=0.7",
}


def normalize(text: str) -> str:
    s = text.lower().replace("ё", "е").replace("\xa0", " ")
    s = re.sub(r"[⚡️❗‼️◻️✅]+", " ", s)
    return " ".join(s.split())


def strict_kind(text: str) -> str | None:
    s = normalize(text)
    if re.match(r"^отбой\s+воздушн(?:ой|ая)\s+тревог", s):
        return "end"
    if re.match(r"^внимание\s+всем[!,. ]+воздушная\s+тревога(?:\s+и\s+морская\s+опасность)?[!,. ]*", s):
        return "start"
    if re.match(r"^воздушная\s+тревога[!,. ]*$", s):
        return "start"
    if re.match(r"^воздушная\s+тревога[!,. ]+", s) and len(s) < 120:
        return "start"
    pos = s.find("внимание всем! воздушная тревога")
    if 0 <= pos <= 250 and any(token in s[:pos] for token in ("отражают атаку", "работает пво", "сбито")):
        return "start"
    return None


def parse_page(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows = []
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
        dt = datetime.fromisoformat(tm["datetime"].replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        rows.append({"id": mid, "at": dt.astimezone(UTC), "text": text})
    return rows


def fetch_recent_messages() -> tuple[list[dict], dict]:
    cutoff = datetime.now(UTC) - timedelta(days=LOOKBACK_DAYS)
    sess = requests.Session()
    sess.headers.update(HEADERS)
    found: dict[int, dict] = {}
    before = None
    pages = 0
    stalled = 0

    while pages < 100:
        url = SOURCE_URL + (f"?before={before}" if before else "")
        r = sess.get(url, timeout=30)
        r.raise_for_status()
        rows = parse_page(r.text)
        pages += 1
        if not rows:
            break
        for row in rows:
            found[row["id"]] = row
        oldest = min(rows, key=lambda x: x["id"])
        if min(x["at"] for x in rows) <= cutoff:
            break
        next_before = oldest["id"]
        if before is not None and next_before >= before:
            stalled += 1
            if stalled >= 2:
                break
        else:
            stalled = 0
        before = next_before
        time.sleep(0.05)

    messages = sorted(found.values(), key=lambda x: (x["at"], x["id"]))
    return messages, {
        "lookback_days": LOOKBACK_DAYS,
        "pages_requested": pages,
        "messages_loaded": len(messages),
        "earliest_loaded_at": messages[0]["at"].isoformat() if messages else None,
        "latest_loaded_at": messages[-1]["at"].isoformat() if messages else None,
    }


def msg_diag(msg: dict | None) -> dict | None:
    if msg is None:
        return None
    return {
        "id": msg["id"],
        "at": msg["at"].isoformat(),
        "text": msg.get("text", ""),
        "normalized": normalize(msg.get("text", "")),
        "url": f"https://t.me/{CHANNEL}/{msg['id']}",
    }


def pair_recent(messages: list[dict]) -> tuple[list[dict], list[dict]]:
    typed = [(m, strict_kind(m["text"])) for m in messages]
    typed = [(m, k) for m, k in typed if k]
    by_id = {m["id"]: m for m in messages}
    ordered_ids = sorted(by_id)
    active = None
    pairs = []
    anomalies = []
    for msg, kind in typed:
        if kind == "start":
            if active is not None:
                gap = (msg["at"] - active["at"]).total_seconds() / 60
                if gap <= 5:
                    continue
                between = [
                    msg_diag(by_id[mid])
                    for mid in ordered_ids
                    if active["id"] < mid < msg["id"]
                ]
                anomalies.append({
                    "type": "missing_end_before_new_start",
                    "start_id": active["id"],
                    "next_start_id": msg["id"],
                    "start": msg_diag(active),
                    "next_start": msg_diag(msg),
                    "messages_between": between,
                })
            active = msg
            continue
        if active is None:
            anomalies.append({
                "type": "orphan_end",
                "end_id": msg["id"],
                "end": msg_diag(msg),
            })
            continue
        if msg["at"] > active["at"]:
            pairs.append({
                "start": active["at"].isoformat(),
                "end": msg["at"].isoformat(),
                "start_id": active["id"],
                "end_id": msg["id"],
                "duration_min": round((msg["at"] - active["at"]).total_seconds() / 60, 3),
                "start_url": f"https://t.me/{CHANNEL}/{active['id']}",
                "end_url": f"https://t.me/{CHANNEL}/{msg['id']}",
            })
        active = None
    if active is not None:
        anomalies.append({
            "type": "open_start",
            "start_id": active["id"],
            "start": msg_diag(active),
        })
    return pairs, anomalies


def load_corrections() -> list[dict]:
    if not CORRECTIONS_FILE.exists():
        return []
    obj = json.loads(CORRECTIONS_FILE.read_text(encoding="utf-8"))
    return list(obj.get("corrections", []))


def apply_corrections(current: dict[int, dict], recent_anomalies: list[dict]) -> tuple[list[dict], list[dict]]:
    applied = []
    corrected_start_ids = set()
    for c in load_corrections():
        sid = int(c["start_id"])
        start = datetime.fromisoformat(c["start"]).astimezone(UTC)
        end = datetime.fromisoformat(c["end"]).astimezone(UTC)
        if end <= start:
            continue
        current[sid] = {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "start_id": sid,
            "end_id": None,
            "duration_min": round((end - start).total_seconds() / 60, 3),
            "start_url": c.get("start_url"),
            "end_url": c.get("end_evidence_url"),
            "correction": {
                "end_source": c.get("end_source"),
                "end_precision": c.get("end_precision"),
                "evidence_note": c.get("evidence_note"),
                "secondary_evidence_url": c.get("secondary_evidence_url"),
            },
        }
        corrected_start_ids.add(sid)
        applied.append(c)
    unresolved = [a for a in recent_anomalies if int(a.get("start_id", -1)) not in corrected_start_ids]
    return applied, unresolved


def initial_events() -> dict:
    audit = json.loads(STRICT_AUDIT.read_text(encoding="utf-8"))
    return {
        "meta": {
            "coverage_start": COVERAGE_START,
            "source": SOURCE_URL,
            "source_provenance": "occupation_administration",
            "source_note": "City-level air-alert signals published by the occupation administration in Sevastopol; retained as descriptive source provenance only.",
            "initial_strict_audit_generated_at": audit.get("source_audit_generated_at"),
            "initial_anomaly_count_excluded": audit.get("anomaly_count"),
        },
        "pairs": audit.get("pairs", []),
    }


def update_event_store() -> tuple[dict, dict]:
    store = json.loads(EVENTS_FILE.read_text(encoding="utf-8")) if EVENTS_FILE.exists() else initial_events()
    current = {int(p["start_id"]): p for p in store.get("pairs", [])}
    messages, fetch_meta = fetch_recent_messages()
    recent_pairs, recent_anomalies = pair_recent(messages)
    for p in recent_pairs:
        current[int(p["start_id"])] = p
    applied_corrections, unresolved_anomalies = apply_corrections(current, recent_anomalies)
    pairs = sorted(current.values(), key=lambda x: (x["start"], x["start_id"]))
    store["pairs"] = pairs
    store.setdefault("meta", {}).update({
        "updated_at": datetime.now(UTC).isoformat(),
        "complete_pair_count": len(pairs),
        "latest_complete_end": max((p["end"] for p in pairs), default=None),
        "recent_fetch": fetch_meta,
        "recent_incomplete_or_anomalous_count": len(unresolved_anomalies),
        "recent_anomalies": unresolved_anomalies,
        "verified_corrections_applied": len(applied_corrections),
        "verified_corrections": applied_corrections,
    })
    EVENTS_FILE.write_text(json.dumps(store, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return store, fetch_meta


def build_city_output(store: dict) -> dict:
    alerts = []
    for p in store.get("pairs", []):
        start = datetime.fromisoformat(p["start"]).astimezone(TZ)
        end = datetime.fromisoformat(p["end"]).astimezone(TZ)
        if end <= start:
            continue
        alerts.append(Alert(start=start, end=end, source="sevastopol_occupation_admin_telegram"))
    if not alerts:
        raise RuntimeError("Sevastopol event store produced no complete alerts")

    meta = {
        "city": CITY_KEY,
        "city_label": CITY_LABEL,
        "source_type": "exact_city",
        "coverage_start": COVERAGE_START,
        "coverage_start_basis": "externally_validated_city_signal_launch",
        "source_url": SOURCE_URL,
        "source_provenance": "occupation_administration",
        "source_scope_note": "City-level signal. Source provenance is the occupation administration; this label is descriptive and does not imply recognition.",
        "completed_alert_episodes_used": len(alerts),
        "incomplete_or_anomalous_historical_events_excluded": store.get("meta", {}).get("initial_anomaly_count_excluded", 0),
        "latest_complete_end": max(a.end for a in alerts).isoformat(),
        "verified_source_corrections_applied": store.get("meta", {}).get("verified_corrections_applied", 0),
    }
    output = build_outputs(alerts, datetime.now(TZ), meta)
    multi.enrich_weekly(output, alerts)
    multi.trim_to_complete_coverage(output, date.fromisoformat(COVERAGE_START))

    output["weekly"] = [r for r in output.get("weekly", []) if r["week_start"] >= "2023-10-02"]
    output["meta"]["first_complete_week_start"] = "2023-10-02"
    output["monthly"] = [r for r in output.get("monthly", []) if r["month"] >= "2023-10"]
    output["meta"]["first_complete_month"] = "2023-10"
    return output


def generic_comparison(cities: dict, keys: list[str], period: str) -> list[dict]:
    by_city = {key: {r["time"]: r for r in cities[key].get(period, [])} for key in keys}
    shared = set(by_city[keys[0]])
    for key in keys[1:]:
        shared &= set(by_city[key])
    out = []
    for timestamp in sorted(shared):
        row = {"time": timestamp}
        for key in keys:
            src = by_city[key][timestamp]
            row[f"{key}_alerts_per_day"] = src.get("alerts_per_day")
            row[f"{key}_avg_daily_alert_hours"] = src.get("avg_daily_alert_hours")
            row[f"{key}_avg_alert_duration_min"] = src.get("avg_alert_duration_min")
        out.append(row)
    return out


def main() -> None:
    store, fetch_meta = update_event_store()
    output = build_city_output(store)

    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    data.setdefault("cities", {})[CITY_KEY] = output
    mm = data.setdefault("multicity_meta", {})
    keys = list(mm.get("production_city_keys", []))
    if CITY_KEY not in keys:
        keys.append(CITY_KEY)
    mm["production_city_keys"] = keys
    mm.setdefault("cities", {})[CITY_KEY] = {
        "label": CITY_LABEL,
        "source_type": "exact_city",
        "coverage_start": COVERAGE_START,
        "first_complete_month": "2023-10",
        "first_complete_week_start": "2023-10-02",
        "proxy_raion": None,
        "source_provenance": "occupation_administration",
    }
    deferred = mm.setdefault("deferred", {})
    deferred.pop(CITY_KEY, None)

    data["comparison"] = {
        "monthly": generic_comparison(data["cities"], keys, "monthly"),
        "weekly": generic_comparison(data["cities"], keys, "weekly"),
    }
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    labels = {k: mm["cities"][k]["label"] for k in keys}
    multi.CITY_KEYS = keys
    multi.CITY_LABELS = labels
    obj = json.loads(DASHBOARD.read_text(encoding="utf-8"))
    multi.update_city_variable(obj)
    multi.update_comparison_panels(obj, data)
    methodology = next((p for p in obj.get("panels", []) if p.get("id") == 30), None)
    if methodology:
        existing = methodology.setdefault("options", {}).get("content", "")
        note = (
            "\n\n**Севастополь.** Ряд є exact-city і починається 25.09.2023. Джерело — city-level сигнали, "
            "опубліковані окупаційною адміністрацією Севастополя. Використовуються повні пари «тривога → відбій»; "
            "неповні епізоди не інтерполюються. Якщо одна сторона пари відсутня в Telegram, допускається лише "
            "окрема документована correction з прямим зовнішнім підтвердженням часу. Позначення джерела описує "
            "лише походження даних і не означає визнання окупаційної адміністрації."
        )
        if "**Севастополь.**" not in existing:
            methodology["options"]["content"] = existing + note
    DASHBOARD.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("Added Sevastopol exact-city series")
    print("Complete stored pairs:", len(store.get("pairs", [])))
    print("Recent fetch:", json.dumps(fetch_meta, ensure_ascii=False))
    print("Verified corrections:", store.get("meta", {}).get("verified_corrections_applied", 0))
    print("Recent anomalies:", json.dumps(store.get("meta", {}).get("recent_anomalies", []), ensure_ascii=False))
    print("Monthly shared comparison starts:", data["comparison"]["monthly"][0]["time"] if data["comparison"]["monthly"] else None)
    print("Weekly shared comparison starts:", data["comparison"]["weekly"][0]["time"] if data["comparison"]["weekly"] else None)


if __name__ == "__main__":
    main()
