#!/usr/bin/env python3
"""Read-only 23-series provisional-duration proof from a single immutable C2 capture.

NEVER writes Neon, changes canonical episodes, invents an end, or contacts sources.
A source snapshot describes the state *at capture*, not current live alert status.
"""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, time, timezone, timedelta
from hashlib import sha256
import io
import json
from pathlib import Path
import re
import sys
from zoneinfo import ZoneInfo
import zipfile

from bs4 import BeautifulSoup

KYIV = ZoneInfo("Europe/Kyiv")
UTC = timezone.utc
EXPECTED_KEYS = {
    "cherkasy", "chernihiv", "chernivtsi", "dnipro", "ivano_frankivsk",
    "kharkiv", "kherson", "khmelnytskyi", "kropyvnytskyi", "kyiv",
    "lutsk", "lviv", "mykolaiv", "odesa", "poltava", "rivne", "sevastopol",
    "sumy", "ternopil", "uzhhorod", "vinnytsia", "zaporizhzhia", "zhytomyr",
}
UA_URL = "https://api.ukrainealarm.com/api/v3/alerts/regionHistory"
KYIV_URL = "https://kyiv.digital/storage/air-alert/stats.html"
SEV_URL = "https://t.me/s/razvozhaev"
KYIV_ROW = re.compile(r"^(\d{2}:\d{2})\s+(\d{2}\.\d{2}\.\d{2})\b")
MAX_OPEN_HOURS = 36


def require(condition, code):
    if not condition:
        raise ValueError(code)


def at(value):
    require(isinstance(value, str), "MISSING_AWARE_TIMESTAMP")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("INVALID_TIMESTAMP") from exc
    require(dt.tzinfo is not None, "NAIVE_TIMESTAMP")
    return dt.astimezone(UTC)


def content(zipfile_obj, filename, manifest):
    payload = zipfile_obj.read(filename)
    require(sha256(payload).hexdigest() == manifest["files"][filename],
            "ZIP_MANIFEST_BLOB_SHA_MISMATCH:" + filename)
    return payload


def source_receipt(row, city, run_id, attempt):
    require(row["city_key"] == city and row["github_run_id"] == run_id and
            row["github_run_attempt"] == attempt and row["schema"] == "c2-history-capture-v1" and
            row["continuity_verified"] is True and row["publication_allowed"] is False and
            row["source_payload_kind"] == "captured-response-pages-v1", "C2_RECEIPT_UNCERTIFIED:" + city)
    pages = row["pages"]
    require(bool(pages), "MISSING_CAPTURE_PAGES:" + city)
    raw = []
    for page in pages:
        blob = base64.b64decode(page["body_base64"], validate=True)
        require(sha256(blob).hexdigest() == page["body_sha256"], "PAGE_BLOB_SHA_MISMATCH:" + city)
        require(at(page["started_at"]) <= at(page["captured_at"]), "PAGE_CAPTURE_ORDER:" + city)
        raw.append(blob)
    checked = min(at(p["captured_at"]) for p in pages)
    require(checked == at(row["last_checked_at"]), "C2_CONSERVATIVE_CAPTURE_CLOCK:" + city)
    return pages, raw, checked


def ua_open(row, pages, raw, checked):
    identity = row["source_identity"]
    region_id = str(identity["region_id"])
    require(row["source_key"] == "ukrainealarm_region_history" and
            identity["url"] == UA_URL and len(pages) == 1 and
            pages[0]["url"] == UA_URL + "?regionId=" + region_id, "UA_SOURCE_IDENTITY")
    payload = json.loads(raw[0])
    require(isinstance(payload, list) and len(payload) == 1 and
            str(payload[0].get("regionId")) == region_id and
            isinstance(payload[0].get("alarms"), list), "UA_REGION_GROUP_MISMATCH")
    rows = payload[0]["alarms"]
    candidates = []
    for alarm in rows:
        if str(alarm.get("alertType")).upper() != "AIR":
            continue
        require(str(alarm.get("regionId")) == region_id, "UA_EMBEDDED_REGION_MISMATCH")
        is_continue = alarm.get("isContinue")
        require(type(is_continue) is bool, "UA_CONTINUE_NOT_BOOLEAN")
        start = at(alarm["startDate"])
        if is_continue:
            require(alarm.get("endDate") in (None, "", "0001-01-01T00:00:00"),
                    "UA_CONTINUING_HAS_END")
            require(start < checked and (checked - start).total_seconds() <= MAX_OPEN_HOURS * 3600,
                    "UA_START_OUTSIDE_CAPTURE")
            candidates.append(start)
    require(len(candidates) <= 1, "UA_MULTIPLE_CONCURRENT_STARTS")
    if candidates:
        latest = max(at(a["startDate"]) for a in rows
                     if str(a.get("alertType")).upper() == "AIR")
        require(candidates[0] == latest, "UA_CONTINUATION_NOT_LATEST")
    return candidates[0] if candidates else None, {"region_id": region_id}


def kyiv_open(row, pages, raw, checked):
    require(row["source_key"] == "kyiv_digital" and
            row["source_identity"] == {"url": KYIV_URL} and
            len(pages) == 1 and pages[0]["url"] == KYIV_URL, "KYIV_SOURCE_IDENTITY")
    events = []
    for tr in BeautifulSoup(raw[0], "html.parser").find_all("tr"):
        text = " ".join(tr.stripped_strings)
        matched = KYIV_ROW.match(text)
        if not matched:
            continue
        if "🔴 Повітряна тривога" in text and "відбій" not in text.lower():
            kind = "start"
        elif "🟢 Відбій тривоги" in text and "повітряна тривога" not in text.lower():
            kind = "end"
        else:
            continue
        stamp = datetime.strptime(matched[2] + " " + matched[1], "%d.%m.%y %H:%M").replace(tzinfo=KYIV)
        require(stamp.astimezone(UTC).astimezone(KYIV).replace(tzinfo=None) ==
                stamp.replace(tzinfo=None), "KYIV_DST_INVALID_SOURCE_TIME")
        events.append((stamp.astimezone(UTC), kind))
    require(len(events) > 500 and len(events) == len(set(events)), "KYIV_SOURCE_ROWS_INCOMPLETE")
    events.sort(key=lambda x: (x[0], x[1]))
    start, kind = events[-1]
    require(start <= checked, "KYIV_FUTURE_EVENT")
    if kind != "start":
        return None, {}
    require((checked - start).total_seconds() <= MAX_OPEN_HOURS * 3600, "KYIV_START_TOO_OLD")
    return start, {}


def sev_open(row, pages, raw, checked, stored):
    require(row["source_key"] == "sevastopol_history" and
            row["source_identity"] == {"url": SEV_URL, "channel": "razvozhaev"} and
            all(p["url"] == SEV_URL or p["url"].startswith(SEV_URL + "?before=") for p in pages),
            "SEV_SOURCE_IDENTITY")
    from add_sevastopol_exact import parse_page, pair_recent, strict_kind
    by_id = {}
    for page, blob in zip(pages, raw):
        for msg in parse_page(blob.decode("utf-8")):
            prior = by_id.get(msg["id"])
            require(prior is None or prior == msg, "SEV_CONFLICTING_MESSAGE_ID")
            by_id[msg["id"]] = msg
    require(len(by_id) > 20, "SEV_INCOMPLETE_MESSAGES")
    messages = sorted(by_id.values(), key=lambda x: (x["at"], x["id"]))
    pairs, anomalies = pair_recent(messages)
    open_rows = [a for a in anomalies if a["type"] == "open_start"]
    require(len(open_rows) <= 1, "SEV_MULTIPLE_UNCLOSED_STARTS")
    # Accepted source-continuity already accounts for historic missing ends.
    # An unproven gap since the previous check remains a hard block.
    previous = at(row["previous_checked_at"])
    for anomaly in anomalies:
        if anomaly["type"] == "open_start":
            continue
        require(anomaly["type"] == "missing_end_before_new_start" and
                at(anomaly["next_start"]["at"]) <= previous and
                at(anomaly["start"]["at"]) < at(anomaly["next_start"]["at"]),
                "SEV_NEW_OR_UNEXPLAINED_MISSING_END")
    recent = stored.get("meta", {}).get("recent_anomalies")
    require(isinstance(recent, list) and len(recent) <= 1 and
            all(x.get("type") == "open_start" for x in recent),
            "SEV_UNRESOLVED_SOURCE_ANOMALIES")
    if not open_rows:
        require(not recent, "SEV_STORE_OPEN_DISAGREES_WITH_SOURCE")
        return None, {"pages": len(pages)}
    require(len(recent) == 1 and recent[0].get("start_id") == open_rows[0].get("start_id"),
            "SEV_STORE_OPEN_ID_NOT_MATCHED")
    open_item = open_rows[0]
    msg = max((m for m in messages if strict_kind(m["text"]) == "start"), key=lambda m: m["id"])
    require(msg["id"] == open_item["start_id"] == open_item["start"]["id"] and
            msg["at"] == at(open_item["start"]["at"]) and
            msg["at"] <= checked and
            (checked - msg["at"]).total_seconds() <= MAX_OPEN_HOURS * 3600,
            "SEV_OPEN_NOT_LATEST_VERIFIED_START")
    return msg["at"], {"pages": len(pages), "message_id": msg["id"]}


def closed_seconds_window(episodes, midnight, checked):
    intervals = []
    for episode in episodes:
        require(episode["episode_state"] == "closed" and episode["alert_type"] == "AIR",
                "NON_CLOSED_CANONICAL_EPISODE")
        start, end = at(episode["start_at"]), at(episode["end_at"])
        require(start < end and end <= checked, "INVALID_CLOSED_EPISODE_CLOCK")
        a, b = max(start, midnight), min(end, checked)
        if a < b:
            intervals.append((a, b))
    intervals.sort()
    merged = []
    for a, b in intervals:
        if not merged or a > merged[-1][1]:
            merged.append([a, b])
        elif b > merged[-1][1]:
            merged[-1][1] = b
    return sum((b-a).total_seconds() for a, b in merged), merged


def build(blob, expected_sha, run_id, attempt):
    require(sha256(blob).hexdigest() == expected_sha, "IMMUTABLE_C2_ARCHIVE_SHA_MISMATCH")
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        require(manifest["github_run_id"] == run_id and
                manifest["github_run_attempt"] == attempt and
                set(manifest["historical_capture_receipts"]["complete_cities"]) == EXPECTED_KEYS,
                "C2_ARCHIVE_ID_OR_23_CITIES")
        status = json.loads(content(archive, "status.json", manifest))
        receipt = json.loads(content(archive, "receipt.json", manifest))
        require(status.get("canonical_persistence_status") == "NEON_SUCCEEDED" and
                status.get("canonical_db_commit") == "CONFIRMED" and
                status.get("canonical_receipt_validated") is True and
                receipt.get("status") == "succeeded" and
                receipt.get("persistence_status") == "persisted" and
                receipt.get("city_count") == 23 and
                receipt.get("canonical_episode_count") == manifest["canonical_episode_count"],
                "SAME_RUN_NEON_CANONICAL_RECEIPT_NOT_CERTIFIED")
        original = content(archive, "payload.json", manifest)
        dashboard_bytes = content(archive, "site_data/dashboard_data.json", manifest)
        sev_bytes = content(archive, "site_data/sevastopol_events.json", manifest)
        dataset = json.loads(original)
        dashboard = json.loads(dashboard_bytes)
        sev_store = json.loads(sev_bytes)
    receipts = dataset["historical_source_receipts"]
    require(set(receipts) == EXPECTED_KEYS and set(dataset["cities"]) == EXPECTED_KEYS and
            set(dashboard["cities"]) == EXPECTED_KEYS, "C2_AND_DASHBOARD_23_CITY_SET")
    output = {}
    for city in sorted(EXPECTED_KEYS):
        row = receipts[city]
        pages, raw, checked = source_receipt(row, city, run_id, attempt)
        if city == "kyiv":
            started, identity = kyiv_open(row, pages, raw, checked)
        elif city == "sevastopol":
            started, identity = sev_open(row, pages, raw, checked, sev_store)
        else:
            started, identity = ua_open(row, pages, raw, checked)
        day = checked.astimezone(KYIV).date()
        midnight = datetime.combine(day, time.min, tzinfo=KYIV).astimezone(UTC)
        source_episodes = dataset["cities"][city]["episodes"]
        confirmed, intervals = closed_seconds_window(source_episodes, midnight, checked)
        provisional = 0
        if started is not None:
            require(started < checked, "ACTIVE_START_AFTER_CAPTURE")
            begin = max(started, midnight)
            require(all(end <= begin or a >= checked for a, end in intervals),
                    "ACTIVE_OVERLAPS_COMPLETED_NEON_EPISODE")
            provisional = max(0, (checked - begin).total_seconds())
        total = confirmed + provisional
        require(total <= (checked-midnight).total_seconds() + .001,
                "COMBINED_DAY_OVERRUN")
        periods = {}
        first = min(at(a["start_at"]).astimezone(KYIV).date() for a in source_episodes)
        starts = {
            "day": day,
            "week": day - timedelta(days=day.weekday()),
            "last7": day - timedelta(days=6),
            "last28": day - timedelta(days=27),
            "last30": day - timedelta(days=29),
            "last90": day - timedelta(days=89),
            "last180": day - timedelta(days=179),
            "month": day.replace(day=1),
            "quarter": day.replace(month=1+3*((day.month-1)//3),day=1),
            "allTime": first,
        }
        for name, day_start in starts.items():
            lo = datetime.combine(day_start, time.min, tzinfo=KYIV).astimezone(UTC)
            done, accepted = closed_seconds_window(source_episodes, lo, checked)
            pending = 0.0
            if started is not None:
                begin = max(started, lo)
                require(all(end <= begin or a >= checked for a,end in accepted),
                        "ACTIVE_OVERLAPS_CONFIRMED_PERIOD:"+name)
                pending = max(0, (checked-begin).total_seconds())
            require(done+pending <= (checked-lo).total_seconds()+.001,
                    "ACTIVE_PERIOD_TOTAL_TOO_LONG:"+name)
            periods[name] = {"from":day_start.isoformat(),"through":day.isoformat(),
                             "closed_seconds":round(done,3),
                             "provisional_seconds":round(pending,3),
                             "combined_seconds":round(done+pending,3)}
        require(abs(periods["day"]["combined_seconds"]-total) < .01,
                "TODAY_PERIOD_SUM_MISMATCH")
        output[city] = {
            "city_key": city,
            "state": "open_at_source_capture" if started is not None else "no_open_at_source_capture",
            "date": day.isoformat(),
            "source_key": row["source_key"],
            "source_record": identity,
            "capture_at": checked.isoformat().replace("+00:00", "Z"),
            "start_at": started.isoformat().replace("+00:00", "Z") if started else None,
            "source_sha256": row["source_sha256"],
            "closed_seconds_today": round(confirmed, 3),
            "provisional_seconds_today": round(provisional, 3),
            "combined_seconds_today": round(total, 3),
            "closed_episode_count": len(source_episodes),
            "periods": periods,
            "source_provenance": ("city" if city in ("kyiv", "sevastopol", "kharkiv", "zaporizhzhia") else "raion_proxy"),
        }
    open_count = sum(x["state"] == "open_at_source_capture" for x in output.values())
    return {
        "schema": "c2-active-23-source-snapshot-test-v1",
        "test_only": True,
        "publication_allowed": False,
        "c2_run_id": run_id,
        "c2_run_attempt": attempt,
        "archive_sha256": expected_sha,
        "same_run_dashboard_sha256": sha256(dashboard_bytes).hexdigest(),
        "timezone": "Europe/Kyiv",
        "count_cities": len(output),
        "count_source_open": open_count,
        "count_source_no_open": 23 - open_count,
        "message": "Historical source-capture test only. Status was observed at capture time; no live status is certified.",
        "cities": output,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--bundle", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--expected-sha256", required=True)
    p.add_argument("--run-id", type=int, required=True)
    p.add_argument("--attempt", type=int, default=1)
    args = p.parse_args()
    result = build(args.bundle.read_bytes(), args.expected_sha256, args.run_id, args.attempt)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                           encoding="utf-8")
    print("C2_ACTIVE_23_SOURCE_PROOF_PASS", result["count_cities"],
          result["count_source_open"], result["count_source_no_open"], args.output)


if __name__ == "__main__":
    main()
