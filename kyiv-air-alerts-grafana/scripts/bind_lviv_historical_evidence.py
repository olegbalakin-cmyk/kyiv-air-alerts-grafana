#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

UTC = timezone.utc
KYIV_TZ = ZoneInfo("Europe/Kyiv")
CITY_KEY = "lviv"

EVENT_LEDGER_BASENAME = "lviv_explosion_reports_final.csv"
TELEGRAM_BASENAME = "lviv_tg_city_mentions.csv"

START_FIELDS = (
    "alert_start", "alert_episode_start", "matched_alert_start", "matched_episode_start",
    "alert_start_local", "alert_start_kyiv", "alert_start_utc", "production_alert_start",
    "production_episode_start", "episode_start", "alert_started_at",
)
END_FIELDS = (
    "alert_end", "alert_episode_end", "matched_alert_end", "matched_episode_end",
    "alert_end_local", "alert_end_kyiv", "alert_end_utc", "production_alert_end",
    "production_episode_end", "episode_end", "alert_finished_at",
)
DATE_FIELDS = ("date", "event_date", "explosion_date", "local_date", "report_date")
EVENT_TIME_FIELDS = (
    "explosion_time_local", "explosion_time", "event_time_local", "event_time", "event_time_kyiv",
    "time_local", "time",
)
MESSAGE_ID_FIELDS = (
    "telegram_message_id", "telegram_id", "tg_message_id", "message_id", "telegram_msg_id", "tg_id",
)
MESSAGE_TEXT_FIELDS = ("telegram_text", "message_text", "text", "raw_text", "source_text")
MESSAGE_TIME_FIELDS = (
    "telegram_datetime", "telegram_timestamp", "message_datetime", "message_timestamp", "datetime",
    "timestamp", "published_at", "publication_time",
)
SOURCE_URL_FIELDS = ("source_url", "url", "source_1", "source")
TEMPORAL_FIELDS = ("temporal_evidence", "temporal_basis", "timing_evidence", "time_evidence")
NOTES_FIELDS = ("notes", "note", "audit_notes", "comment", "comments")
LEGACY_FIELD_PATTERNS = (
    r"^final_status$", r"^strict_count$", r"^sensitivity_count$", r"^final_classification$",
    r"^classification$", r"^decision$", r"^decision_basis$", r"^include(?:d)?$",
    r"^strict$", r"^sensitivity$", r"^status$",
)


def norm_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")


def norm_row(row: dict[str, str]) -> dict[str, str]:
    return {
        norm_key(str(k)): ("" if v is None else str(v).strip())
        for k, v in row.items()
        if k is not None
    }


def first_value(row: dict[str, str], fields: tuple[str, ...]) -> tuple[str | None, str | None]:
    for field in fields:
        value = row.get(field)
        if value is not None and str(value).strip():
            return field, str(value).strip()
    return None, None


def parse_dt(value: str | None, *, default_tz=KYIV_TZ) -> datetime | None:
    if not value:
        return None
    text = str(value).strip().replace("~", "").strip()
    text = re.sub(r"\s+Europe/Kyiv.*$", "", text, flags=re.I)
    text = text.replace("Z", "+00:00")
    m = re.fullmatch(
        r"(\d{2})\.(\d{2})\.(\d{4})[ T,]+(\d{1,2}):(\d{2})(?::(\d{2}(?:\.\d+)?))?",
        text,
    )
    if m:
        dd, mm, yyyy, hh, mi, ss = m.groups()
        text = f"{yyyy}-{mm}-{dd}T{int(hh):02d}:{mi}:{ss or '00'}"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        m = re.match(
            r"^(\d{4}-\d{2}-\d{2})[ T](\d{1,2}):(\d{2})(?::(\d{2}(?:\.\d+)?))?",
            text,
        )
        if not m:
            return None
        day, hh, mm, ss = m.groups()
        try:
            dt = datetime.fromisoformat(f"{day}T{int(hh):02d}:{mm}:{ss or '00'}")
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=default_tz)
    return dt.astimezone(UTC)


def parse_local_event_dt(row: dict[str, str]) -> tuple[datetime | None, dict]:
    date_field, date_value = first_value(row, DATE_FIELDS)
    time_field, time_value = first_value(row, EVENT_TIME_FIELDS)
    meta = {
        "date_field": date_field,
        "date_value": date_value,
        "time_field": time_field,
        "time_value": time_value,
    }
    if not date_value or not time_value:
        return None, meta
    if re.search(r"\b(?:during|під час|вночі|ранок|вечір|ніч|day|night)\b", time_value, flags=re.I):
        return None, meta
    m = re.search(r"(\d{1,2}):(\d{2})(?::(\d{2}))?", time_value)
    if not m:
        return None, meta
    hh, mm, ss = m.groups()
    date_text = date_value.strip()
    if re.fullmatch(r"\d{2}\.\d{2}\.\d{4}", date_text):
        dd, mo, yr = date_text.split(".")
        date_text = f"{yr}-{mo}-{dd}"
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_text):
        return None, meta
    try:
        dt = datetime.fromisoformat(
            f"{date_text}T{int(hh):02d}:{mm}:{ss or '00'}"
        ).replace(tzinfo=KYIV_TZ)
    except ValueError:
        return None, meta
    return dt.astimezone(UTC), meta


def load_csv_from_zip(
    zf: zipfile.ZipFile, basename: str
) -> tuple[str, list[dict[str, str]], list[str]]:
    matches = [name for name in zf.namelist() if Path(name).name == basename]
    if len(matches) != 1:
        raise SystemExit(f"Expected exactly one {basename} in ZIP, found {matches}")
    name = matches[0]
    text = zf.read(name).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    rows = [dict(row) for row in reader]
    return name, rows, list(reader.fieldnames or [])


def load_corpus(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    episodes = payload.get("episodes") or []
    if payload.get("city_key") != CITY_KEY:
        raise SystemExit(f"Unexpected corpus city_key: {payload.get('city_key')}")
    if len(episodes) != 126:
        raise SystemExit(f"Expected 126 canonical Lviv episodes, got {len(episodes)}")
    out = []
    for ep in episodes:
        start = parse_dt(ep.get("start"), default_tz=UTC)
        end = parse_dt(ep.get("end"), default_tz=UTC)
        if not start or not end or end <= start or not ep.get("episode_id"):
            raise SystemExit(f"Invalid canonical episode: {ep}")
        out.append({**ep, "_start_dt": start, "_end_dt": end})
    return out


def overlap_seconds(a0: datetime, a1: datetime, b0: datetime, b1: datetime) -> float:
    return max(0.0, (min(a1, b1) - max(a0, b0)).total_seconds())


def bind_row(row_raw: dict[str, str], episodes: list[dict]) -> dict:
    row = norm_row(row_raw)
    sf, sv = first_value(row, START_FIELDS)
    ef, ev = first_value(row, END_FIELDS)
    start = parse_dt(sv)
    end = parse_dt(ev)
    inputs = {
        "start_field": sf,
        "start_value": sv,
        "end_field": ef,
        "end_value": ev,
    }

    if start and end and end > start:
        scored = []
        for ep in episodes:
            ov = overlap_seconds(start, end, ep["_start_dt"], ep["_end_dt"])
            if ov <= 0:
                continue
            sdelta = abs((start - ep["_start_dt"]).total_seconds())
            edelta = abs((end - ep["_end_dt"]).total_seconds())
            scored.append((ov, -(sdelta + edelta), ep, sdelta, edelta))
        scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
        if len(scored) == 1 or (len(scored) > 1 and scored[0][0] > scored[1][0]):
            _, _, ep, sd, ed = scored[0]
            return {
                "status": "matched",
                "episode_id": ep["episode_id"],
                "method": "alert_interval_overlap_unique_best",
                "candidates": [ep["episode_id"]],
                "binding_inputs": inputs,
                "start_delta_seconds": round(sd, 3),
                "end_delta_seconds": round(ed, 3),
            }
        if scored:
            return {
                "status": "ambiguous",
                "episode_id": None,
                "method": "alert_interval_overlap_tie",
                "candidates": [x[2]["episode_id"] for x in scored],
                "binding_inputs": inputs,
            }

    if start:
        near = []
        for ep in episodes:
            delta = abs((start - ep["_start_dt"]).total_seconds())
            if delta <= 300:
                near.append((delta, ep))
        near.sort(key=lambda x: x[0])
        if len(near) == 1 or (len(near) > 1 and near[0][0] < near[1][0]):
            delta, ep = near[0]
            return {
                "status": "matched",
                "episode_id": ep["episode_id"],
                "method": "alert_start_nearest_within_300s",
                "candidates": [ep["episode_id"]],
                "binding_inputs": inputs,
                "start_delta_seconds": round(delta, 3),
            }
        if near:
            return {
                "status": "ambiguous",
                "episode_id": None,
                "method": "alert_start_nearest_tie",
                "candidates": [x[1]["episode_id"] for x in near],
                "binding_inputs": inputs,
            }

    event_dt, event_meta = parse_local_event_dt(row)
    inputs["event_time"] = event_meta
    if event_dt:
        inside = [
            ep
            for ep in episodes
            if ep["_start_dt"] <= event_dt <= ep["_end_dt"]
        ]
        if len(inside) == 1:
            return {
                "status": "matched",
                "episode_id": inside[0]["episode_id"],
                "method": "event_time_inside_unique_episode",
                "candidates": [inside[0]["episode_id"]],
                "binding_inputs": inputs,
            }
        if len(inside) > 1:
            return {
                "status": "ambiguous",
                "episode_id": None,
                "method": "event_time_inside_multiple_episodes",
                "candidates": [ep["episode_id"] for ep in inside],
                "binding_inputs": inputs,
            }

    _, date_value = first_value(row, DATE_FIELDS)
    if date_value:
        date_text = date_value.strip()
        if re.fullmatch(r"\d{2}\.\d{2}\.\d{4}", date_text):
            dd, mo, yr = date_text.split(".")
            date_text = f"{yr}-{mo}-{dd}"
        day_eps = [
            ep
            for ep in episodes
            if ep["_start_dt"].astimezone(KYIV_TZ).date().isoformat() == date_text
        ]
        if len(day_eps) == 1:
            return {
                "status": "matched",
                "episode_id": day_eps[0]["episode_id"],
                "method": "unique_episode_on_event_local_day",
                "candidates": [day_eps[0]["episode_id"]],
                "binding_inputs": inputs,
            }
        if day_eps:
            return {
                "status": "ambiguous",
                "episode_id": None,
                "method": "multiple_episodes_on_event_local_day",
                "candidates": [ep["episode_id"] for ep in day_eps],
                "binding_inputs": inputs,
            }

    return {
        "status": "unmatched",
        "episode_id": None,
        "method": "insufficient_deterministic_temporal_fields",
        "candidates": [],
        "binding_inputs": inputs,
    }


def extract_message_ids(row: dict[str, str]) -> list[str]:
    n = norm_row(row)
    vals = []
    for field in MESSAGE_ID_FIELDS:
        value = n.get(field)
        if value:
            vals.extend(re.findall(r"\d+", value))
    return list(dict.fromkeys(vals))


def telegram_index(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    idx: dict[str, list[dict[str, str]]] = {}
    for raw in rows:
        n = norm_row(raw)
        ids = []
        for field in MESSAGE_ID_FIELDS:
            value = n.get(field)
            if value:
                ids.extend(re.findall(r"\d+", value))
        for mid in dict.fromkeys(ids):
            idx.setdefault(mid, []).append(raw)
    return idx


def safe_subset(row: dict[str, str], fields: tuple[str, ...]) -> dict:
    n = norm_row(row)
    return {field: n[field] for field in fields if n.get(field)}


def legacy_fields(row: dict[str, str]) -> dict:
    out = {}
    for key, value in norm_row(row).items():
        if any(re.fullmatch(pattern, key) for pattern in LEGACY_FIELD_PATTERNS):
            out[key] = value
    return out


def nonlegacy_raw(row: dict[str, str]) -> dict:
    legacy = set(legacy_fields(row))
    return {
        key: value
        for key, value in row.items()
        if norm_key(key) not in legacy
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", required=True, type=Path)
    parser.add_argument("--evidence-zip", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    episodes = load_corpus(args.corpus)
    package_sha256 = hashlib.sha256(args.evidence_zip.read_bytes()).hexdigest()

    with zipfile.ZipFile(args.evidence_zip, "r") as zf:
        event_name, event_rows, event_fields = load_csv_from_zip(
            zf, EVENT_LEDGER_BASENAME
        )
        tg_name, tg_rows, tg_fields = load_csv_from_zip(zf, TELEGRAM_BASENAME)
        package_files = sorted(zf.namelist())

    tg_idx = telegram_index(tg_rows)
    bound = []
    for i, raw in enumerate(event_rows):
        binding = bind_row(raw, episodes)
        ids = extract_message_ids(raw)
        tg_matches = []
        for mid in ids:
            for tg in tg_idx.get(mid, []):
                n = norm_row(tg)
                tg_matches.append(
                    {
                        "message_id": mid,
                        "timestamp": first_value(n, MESSAGE_TIME_FIELDS)[1],
                        "text": first_value(n, MESSAGE_TEXT_FIELDS)[1],
                        "raw_nonlegacy": nonlegacy_raw(tg),
                    }
                )
        n = norm_row(raw)
        bound.append(
            {
                "event_row_index": i,
                "binding": binding,
                "source_url": first_value(n, SOURCE_URL_FIELDS)[1],
                "temporal_evidence": safe_subset(raw, TEMPORAL_FIELDS),
                "notes": safe_subset(raw, NOTES_FIELDS),
                "telegram_message_ids": ids,
                "telegram_matches": tg_matches,
                "raw_nonlegacy": nonlegacy_raw(raw),
                "legacy_fields_present_but_ignored": legacy_fields(raw),
            }
        )

    status_counts = Counter(x["binding"]["status"] for x in bound)
    method_counts = Counter(x["binding"]["method"] for x in bound)
    matched_ids = [
        x["binding"]["episode_id"]
        for x in bound
        if x["binding"]["episode_id"]
    ]
    episode_counts = Counter(matched_ids)

    artifact = {
        "schema_version": 1,
        "city_key": CITY_KEY,
        "purpose": (
            "Bind raw historical Lviv explosion evidence to canonical alert "
            "episodes without classification."
        ),
        "classification_performed": False,
        "legacy_classification_fields_used_for_binding": False,
        "inputs": {
            "canonical_corpus": str(args.corpus),
            "evidence_zip": str(args.evidence_zip),
            "evidence_zip_sha256": package_sha256,
            "event_ledger_member": event_name,
            "telegram_member": tg_name,
            "package_files": package_files,
            "event_ledger_fields": event_fields,
            "telegram_fields": tg_fields,
        },
        "summary": {
            "canonical_episode_count": len(episodes),
            "event_rows": len(event_rows),
            "telegram_rows": len(tg_rows),
            "binding_status_counts": dict(sorted(status_counts.items())),
            "binding_method_counts": dict(sorted(method_counts.items())),
            "distinct_matched_episode_ids": len(set(matched_ids)),
            "episodes_with_multiple_event_rows": {
                key: value
                for key, value in sorted(episode_counts.items())
                if value > 1
            },
            "event_rows_with_telegram_ids": sum(
                bool(x["telegram_message_ids"]) for x in bound
            ),
            "event_rows_with_raw_telegram_match": sum(
                bool(x["telegram_matches"]) for x in bound
            ),
        },
        "rows": bound,
    }
    artifact["verdict"] = (
        "LVIV HISTORICAL EVIDENCE BINDING CLEAN — READY FOR MANUAL QA OF AMBIGUOUS/UNMATCHED"
        if status_counts.get("unmatched", 0) == 0
        and status_counts.get("ambiguous", 0) == 0
        else "LVIV HISTORICAL EVIDENCE BINDING COMPLETE — MANUAL QA REQUIRED"
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(artifact["summary"], ensure_ascii=False, indent=2))
    print(artifact["verdict"])


if __name__ == "__main__":
    main()
