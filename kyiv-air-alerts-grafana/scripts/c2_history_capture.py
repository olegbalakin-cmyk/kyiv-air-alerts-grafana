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
    if not payload_path:
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
    obj.setdefault("historical_source_receipts", {})[city] = receipt
    path.write_text(json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    if pages:
        checkpoints[city] = {"source_key": source_key, "source_identity": source_identity,
            "last_checked_at": checked, "source_sha256": receipt["source_sha256"], **identity(env)}
        checkpoints_path.parent.mkdir(parents=True, exist_ok=True)
        checkpoints_path.write_text(json.dumps(checkpoints, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    return receipt


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
    for page in pages:
        raw = base64.b64decode(page["body_base64"], validate=True)
        require(hashlib.sha256(raw).hexdigest() == page["body_sha256"], "CAPTURE_BODY_SHA")
        require(utc(page["started_at"]) <= utc(page["captured_at"]) <= utc(read_at), "CAPTURE_CLOCK")
    require(utc(row["last_checked_at"]) == min(utc(p["captured_at"]) for p in pages), "CAPTURE_CLOCK")
    completed = row.get("completed_air", [])
    require(fingerprint(completed) == row.get("completed_air_sha256"), "CAPTURE_COMPLETED_SHA")
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
