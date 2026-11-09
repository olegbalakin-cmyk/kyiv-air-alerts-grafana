"""Receipts for responses the regular collectors already fetched. No HTTP or SQL."""
from __future__ import annotations

import base64
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "c2-history-capture-v1"
CHECKPOINTS = Path(__file__).resolve().parents[1] / "data/c2_history_capture_checkpoints.json"


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def utc(value):
    dt = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("CAPTURE_NAIVE_TIMESTAMP")
    return dt.astimezone(timezone.utc)


def identity(env=None):
    env = os.environ if env is None else env
    return {"github_run_id": int(env.get("GITHUB_RUN_ID") or 0),
        "github_run_attempt": int(env.get("GITHUB_RUN_ATTEMPT") or 0),
        "workflow_sha": env.get("GITHUB_SHA"), "input_sha": env.get("PHASE1_INPUT_SHA")}


def response_page(response, *, url, started_at):
    """Call immediately after the existing successful response, before parsing."""
    raw = response.content
    return {"url": url, "started_at": utc(started_at).isoformat(),
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "body_sha256": hashlib.sha256(raw).hexdigest(),
        "body_base64": base64.b64encode(raw).decode("ascii")}


def record(city, source_key, source_identity, pages, completed, *, previous=None,
           continuity=True, checkpoint_path=None, env=None):
    """Save response evidence in the existing ephemeral canonical payload.

    The small persistent checkpoint contains capture clocks, never event clocks.
    An initial capture bootstraps it but cannot certify historical continuity.
    No payload environment means OFF, like multicity_shadow_payload itself.
    """
    env = os.environ if env is None else env
    payload_path = env.get("MULTICITY_CANONICAL_PAYLOAD_PATH")
    if not payload_path or env.get("C2_HISTORY_CAPTURE_ENABLED") != "true":
        return None
    checkpoints_path = Path(checkpoint_path or CHECKPOINTS)
    checkpoints = json.loads(checkpoints_path.read_text()) if checkpoints_path.exists() else {}
    previous = previous if previous is not None else checkpoints.get(city)
    rows = sorted({(utc(r["start"]).isoformat(), utc(r["end"]).isoformat()) for r in completed})
    completed = [{"start": s, "end": e} for s, e in rows if utc(s) < utc(e)]
    captures = [utc(p["captured_at"]) for p in pages]
    checked = min(captures).isoformat() if captures else None  # oldest page is the conservative clock
    overlap = bool(previous and completed and checked and
        previous.get("source_key") == source_key and previous.get("source_identity") == source_identity and
        utc(completed[0]["start"]) <= utc(previous["last_checked_at"]) <= utc(checked))
    receipt = {"schema": SCHEMA, "city_key": city, "source_key": source_key,
        "source_identity": source_identity, **identity(env), "pages": pages,
        "source_payload_kind": "captured-response-pages-v1", "source_sha256": fingerprint(pages),
        "completed_air": completed, "completed_air_sha256": fingerprint(completed),
        "previous_checkpoint": previous, "previous_checkpoint_sha256": fingerprint(previous),
        "previous_checked_at": previous.get("last_checked_at") if previous else None,
        "last_checked_at": checked, "last_error": None,
        "oldest_fetched_completed_air_start": completed[0]["start"] if completed else None,
        "continuity_verified": bool(continuity and overlap),
        "continuity_reason": "history_reaches_previous_poll" if continuity and overlap else
            "missing_checkpoint_or_history_overlap", "publication_allowed": False}
    path = Path(payload_path)
    obj = json.loads(path.read_text())
    obj["history_capture_contract"] = SCHEMA
    obj.setdefault("historical_source_receipts", {})[city] = receipt
    path.write_text(json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    if pages and (previous is None or receipt["continuity_verified"]):
        checkpoints[city] = {"source_key": source_key, "source_identity": source_identity,
            "last_checked_at": checked, "source_sha256": receipt["source_sha256"], **identity(env)}
        checkpoints_path.parent.mkdir(parents=True, exist_ok=True)
        checkpoints_path.write_text(json.dumps(checkpoints, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    return receipt


def replay(row):
    """Reuse source parsers; raw retained responses must yield the claimed pairs."""
    raw_pages = [base64.b64decode(p["body_base64"], validate=True) for p in row["pages"]]
    source = row["source_key"]
    if source == "ukrainealarm_region_history":
        pairs = []
        for raw in raw_pages:
            payload = json.loads(raw)
            groups = [payload] if isinstance(payload, dict) else payload
            for group in groups:
                for alarm in group.get("alarms") or []:
                    if str(alarm.get("alertType") or "").upper() != "AIR":
                        continue
                    start, end = alarm.get("startDate"), alarm.get("endDate")
                    if start and end and utc(start) < utc(end):
                        pairs.append({"start": start, "end": end})
    elif source == "kyiv_digital":
        from update_data import parse_live_history
        alerts, _ = parse_live_history(raw_pages[0].decode("utf-8"))
        pairs = [{"start": a.start, "end": a.end} for a in alerts]
    elif source == "sevastopol_history":
        from add_sevastopol_exact import parse_page, pair_recent
        found = {m["id"]: m for raw in raw_pages for m in parse_page(raw.decode("utf-8"))}
        pairs, _ = pair_recent(sorted(found.values(), key=lambda m: (m["at"], m["id"])))
    else:
        raise ValueError("CAPTURE_UNKNOWN_SOURCE")
    return [{"start": s, "end": e} for s, e in sorted({
        (utc(p["start"]).isoformat(), utc(p["end"]).isoformat()) for p in pairs})]


def verify(row, *, city, source_key, run_identity, read_at):
    """Rehash retained source bytes and recompute overlap; cached booleans do not suffice."""
    def require(ok, reason):
        if not ok:
            raise ValueError(reason + ":" + city)
    require(row.get("schema") == SCHEMA and row.get("city_key") == city and
        row.get("source_key") == source_key and row.get("publication_allowed") is False,
        "CAPTURE_SCHEMA")
    require(all(row.get(k) == v for k, v in run_identity.items()), "CAPTURE_RUN_MISMATCH")
    pages = row.get("pages", [])
    require(bool(pages) and fingerprint(pages) == row.get("source_sha256"), "CAPTURE_SOURCE_SHA")
    require(row.get("source_payload_kind") == "captured-response-pages-v1", "CAPTURE_PAYLOAD_KIND")
    for page in pages:
        raw = base64.b64decode(page["body_base64"], validate=True)
        require(hashlib.sha256(raw).hexdigest() == page["body_sha256"], "CAPTURE_BODY_SHA")
        require(utc(page["started_at"]) <= utc(page["captured_at"]) <= utc(read_at), "CAPTURE_CLOCK")
    source_identity = row.get("source_identity", {})
    if source_key == "ukrainealarm_region_history":
        require(source_identity.get("url") == "https://api.ukrainealarm.com/api/v3/alerts/regionHistory" and
            bool(source_identity.get("region_id")) and all(p["url"] == source_identity["url"] +
                "?regionId=" + source_identity["region_id"] for p in pages), "CAPTURE_SOURCE_IDENTITY")
    elif source_key == "kyiv_digital":
        require(source_identity == {"url": "https://kyiv.digital/storage/air-alert/stats.html"} and
            len(pages) == 1 and pages[0]["url"] == source_identity["url"], "CAPTURE_SOURCE_IDENTITY")
    elif source_key == "sevastopol_history":
        require(source_identity == {"url": "https://t.me/s/razvozhaev", "channel": "razvozhaev"} and
            all(p["url"] == source_identity["url"] or p["url"].startswith(source_identity["url"] +
                "?before=") for p in pages), "CAPTURE_SOURCE_IDENTITY")
    require(utc(row["last_checked_at"]) == min(utc(p["captured_at"]) for p in pages), "CAPTURE_CLOCK")
    completed = row.get("completed_air", [])
    require(fingerprint(completed) == row.get("completed_air_sha256"), "CAPTURE_COMPLETED_SHA")
    require(completed == replay(row), "CAPTURE_REPLAY_MISMATCH")
    require(row.get("oldest_fetched_completed_air_start") == (completed[0]["start"] if completed else None),
        "CAPTURE_OLDEST_COMPLETED")
    require(all(utc(r["start"]) < utc(r["end"]) for r in completed), "CAPTURE_COMPLETED_INTERVAL")
    previous = row.get("previous_checkpoint")
    require(fingerprint(previous) == row.get("previous_checkpoint_sha256"), "CAPTURE_CHECKPOINT_SHA")
    # Missing continuity is a per-city BLOCKED result, never a fabricated PASS.
    overlap = bool(previous and completed and previous.get("source_key") == source_key and
        previous.get("source_identity") == row.get("source_identity") and
        utc(min(completed, key=lambda r: utc(r["start"]))["start"]) <=
        utc(previous["last_checked_at"]) <= utc(row["last_checked_at"]))
    require(row.get("previous_checked_at") == (previous.get("last_checked_at") if previous else None),
        "CAPTURE_CHECKPOINT_CLOCK")
    require(not row.get("continuity_verified") or overlap, "CAPTURE_FALSE_CONTINUITY")
    return overlap and row.get("continuity_verified") is True and row.get("last_error") is None
