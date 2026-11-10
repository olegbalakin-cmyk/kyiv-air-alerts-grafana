#!/usr/bin/env python3
"""Manual-only, snapshot-guarded casualty review operator.

No production file paths are implicit. This module never pushes Git refs,
runs discovery or aggregation, or publishes dashboard totals. The workflow
owns explicit authority-branch transport and fast-forward-only commits.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import shutil
import tempfile
from datetime import date
from pathlib import Path

from review_casualty_candidates import (
    _validate_confirmation, _validated_confirmed_disposition,
    hold_candidate, load_queue, load_revision_rows, promote_reviewed,
    reopen_held_candidate, review_candidate,
)

# Accepted current production city set. Unknown city identifiers fail closed.
ALLOWED_CITY_KEYS = frozenset({
    "kyiv", "kharkiv", "zaporizhzhia", "cherkasy", "zhytomyr", "dnipro",
    "khmelnytskyi", "poltava", "rivne", "sumy", "vinnytsia",
    "kropyvnytskyi", "lviv", "chernihiv", "odesa",
    "sevastopol", "kherson", "mykolaiv", "lutsk",
    "uzhhorod", "ivano-frankivsk", "ternopil", "chernivtsi",
})
STATES = ("wip_head", "site_prod_head", "queue_blob_sha", "revisions_blob_sha")
REVIEW_DECISIONS = ("CONFIRM", "REJECT", "HOLD", "REOPEN")


class RefStaleError(RuntimeError):
    """No mutation is permitted from a stale approval preview."""


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def digest_json(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def verify_inputs(queue_path: Path, revisions_path: Path, state: dict) -> None:
    if not all(isinstance(state.get(k), str) and state[k] for k in STATES):
        raise ValueError("Both branch identities and blob SHAs are mandatory")
    if git_blob_sha(queue_path) != state["queue_blob_sha"]:
        raise RefStaleError("Queue content does not match claimed blob SHA")
    if git_blob_sha(revisions_path) != state["revisions_blob_sha"]:
        raise RefStaleError("Revision content does not match claimed blob SHA")


def candidate_by_id(queue: list, candidate_id: str) -> dict:
    matches = [row for row in queue if isinstance(row, dict)
               and row.get("candidate_id") == candidate_id]
    if len(matches) != 1:
        raise ValueError("Candidate ID must match exactly one row")
    return matches[0]


def allowed_city(city_key: str) -> str:
    if city_key not in ALLOWED_CITY_KEYS:
        raise ValueError("Unknown production city_key")
    return city_key


def _revision_effect(revisions: list[dict], reviewed: dict) -> dict:
    """Preview of the exact canonical invariant check used by production."""
    record_id = reviewed["record_id"]
    existing = next((row for row in revisions if row["record_id"] == record_id), None)
    invariant = {
        "city_key": reviewed["city_key"],
        "attack_date": reviewed["attack_date"],
        "deaths_delta": str(reviewed["deaths_delta"]),
        "status": "confirmed",
    }
    if existing:
        conflict = {field: (existing.get(field), value) for field, value
                    in invariant.items() if str(existing.get(field) or "") != value}
        if conflict:
            raise ValueError("Conflicting canonical record_id: " + repr(conflict))
    month = reviewed["attack_date"][:7]
    current = sum(int(row["deaths_delta"]) for row in revisions
                  if row["city_key"] == reviewed["city_key"]
                  and row["attack_date"].startswith(month)
                  and row["status"] == "confirmed")
    increment = 0 if existing else reviewed["deaths_delta"]
    return {
        "canonical_id_exists": bool(existing),
        "projected_revision_increment": increment,
        "month": month,
        "existing_monthly_revision_deaths": current,
        "projected_monthly_revision_deaths": current + increment,
        "existing_source_preserved": bool(existing),
    }


def _warnings(queue: list, candidate: dict, revisions: list[dict],
              reviewed: dict | None) -> list[str]:
    warnings = []
    candidate_id, city = candidate["candidate_id"], candidate["city_key"]
    title = str(candidate.get("title") or "").strip().casefold()
    url = str(candidate.get("url") or "")
    for other in queue:
        if not isinstance(other, dict) or other.get("candidate_id") == candidate_id:
            continue
        if other.get("city_key") != city:
            continue
        same_url = bool(url and other.get("url") == url)
        same_title = bool(title and str(other.get("title") or "").strip().casefold() == title)
        if same_url or same_title:
            warnings.append("Possible media duplicate candidate: " +
                            str(other.get("candidate_id", "")))
    if reviewed:
        for row in revisions:
            if row["city_key"] == city and row["attack_date"] == reviewed["attack_date"] \
                    and row["record_id"] != reviewed["record_id"]:
                warnings.append("Same city and date, DIFFERENT canonical ID: " +
                                row["record_id"] + "; manual verification required")
    return warnings


def _evidence(candidate: dict) -> dict:
    keys = (
        "candidate_id", "city_key", "city", "status", "source", "publisher",
        "publisher_url", "url", "title", "snippet", "published_at",
        "first_discovered_at", "last_seen_at", "alert_trigger_scope",
        "trigger_check_labels", "trigger_episode_ids", "review_disposition",
        "review_history",
    )
    return {key: candidate.get(key) for key in keys if key in candidate}


def build_preview(*, mode: str, candidate_id: str, decision: str,
                  payload: dict, queue_path: Path, revisions_path: Path,
                  state: dict) -> dict:
    verify_inputs(queue_path, revisions_path, state)
    mode, decision = mode.upper(), decision.upper()
    if mode not in {"INSPECT", "REVIEW", "PROMOTE"}:
        raise ValueError("Unknown operator mode")
    if not isinstance(payload, dict):
        raise ValueError("Review payload must be a JSON object")
    queue, revisions = load_queue(queue_path), load_revision_rows(revisions_path)
    candidate = candidate_by_id(queue, candidate_id) if candidate_id else None
    if mode != "INSPECT" and candidate is None:
        raise ValueError("REVIEW and PROMOTE require candidate_id")

    preview = {
        "format_version": 1,
        "mode": mode, "decision": decision if mode == "REVIEW" else "",
        "candidate_id": candidate_id,
        "state": {key: state[key] for key in STATES},
        "candidate_status": candidate.get("status") if candidate else None,
        "candidate_disposition_fingerprint": digest_json(candidate.get("review_disposition"))
                                              if candidate else None,
        "evidence": _evidence(candidate) if candidate else None,
        "inbox": ([{"candidate_id": c.get("candidate_id"), "city_key": c.get("city_key"),
                   "status": c.get("status")}
                  for c in queue if isinstance(c, dict) and c.get("status") == "needs_review"][:30]
                  if candidate is None else None),
        "pending_count": sum(c.get("status") == "needs_review"
                             for c in queue if isinstance(c, dict)),
        "payload": {},
        "effect": None,
        "warnings": [],
    }
    if mode == "INSPECT":
        if candidate:
            preview["warnings"] = _warnings(queue, candidate, revisions, None)
        return preview

    assert candidate is not None
    city = allowed_city(str(candidate.get("city_key") or ""))
    if mode == "REVIEW":
        if decision not in REVIEW_DECISIONS:
            raise ValueError("REVIEW requires an explicit allowed decision")
        if payload.get("city_key") != city:
            raise ValueError("Submitted city does not equal candidate city")
        status = candidate.get("status")
        if decision == "REOPEN":
            disposition = candidate.get("review_disposition")
            if status != "hold" or not isinstance(disposition, dict) \
                    or disposition.get("status") != "hold":
                raise ValueError("Explicit HOLD required before REOPEN")
        elif status != "needs_review":
            raise ValueError("Only needs_review candidates can be reviewed")
        note = payload.get("note", "")
        if not isinstance(note, str):
            raise ValueError("Review note must be text")
        if decision in {"REJECT", "HOLD", "REOPEN"} and not note.strip():
            raise ValueError("REJECT/HOLD/REOPEN require a reason")
        clean = {"city_key": city, "note": note}
        if decision == "CONFIRM":
            value = payload.get("deaths_delta")
            if isinstance(value, bool) or not re.fullmatch(r"[1-9][0-9]*", str(value or "")):
                raise ValueError("deaths_delta must be a positive whole number")
            confirmed = _validate_confirmation(
                payload.get("record_id"), payload.get("attack_date"),
                value, payload.get("source_name"), payload.get("source_url"))
            clean.update(confirmed)
            reviewed = {**confirmed, "city_key": city}
            preview["effect"] = _revision_effect(revisions, reviewed)
            preview["warnings"] = _warnings(queue, candidate, revisions, reviewed)
        else:
            preview["effect"] = {"projected_revision_increment": 0,
                                 "revision_ledger_unchanged": True}
            preview["warnings"] = _warnings(queue, candidate, revisions, None)
        preview["payload"] = clean
    else:
        if payload:
            raise ValueError("PROMOTE accepts no new review overrides")
        reviewed = _validated_confirmed_disposition(candidate)
        allowed_city(reviewed["city_key"])
        preview["payload"] = reviewed
        preview["effect"] = _revision_effect(revisions, reviewed)
        preview["warnings"] = _warnings(queue, candidate, revisions, reviewed)
    return preview


def verify_preview(preview: dict, *, queue_path: Path,
                   revisions_path: Path, current_state: dict) -> None:
    if preview.get("format_version") != 1 or preview.get("mode") == "INSPECT":
        raise ValueError("Only reviewed non-INSPECT previews can be applied")
    verify_inputs(queue_path, revisions_path, current_state)
    for field in STATES:
        if current_state[field] != preview["state"][field]:
            raise RefStaleError("Stale approved preview: " + field)
    selected = candidate_by_id(load_queue(queue_path), preview["candidate_id"])
    if selected.get("status") != preview["candidate_status"]:
        raise RefStaleError("Candidate status changed since preview")
    if digest_json(selected.get("review_disposition")) != preview["candidate_disposition_fingerprint"]:
        raise RefStaleError("Candidate disposition changed since preview")
    # Revalidate the exact approved payload against the just-reloaded ledger.
    fresh = build_preview(
        mode=preview["mode"], candidate_id=preview["candidate_id"],
        decision=preview.get("decision", ""), payload=preview["payload"]
                if preview["mode"] == "REVIEW" else {},
        queue_path=queue_path, revisions_path=revisions_path,
        state=current_state)
    if fresh["effect"] != preview["effect"]:
        raise RefStaleError("Expected canonical effect changed")


def apply_preview(preview: dict, *, queue_path: Path, revisions_path: Path,
                  current_state: dict, reviewed_by: str,
                  workflow_run_id: str) -> dict:
    actor = str(reviewed_by or "").strip()
    run_id = str(workflow_run_id or "").strip()
    if not actor or actor.endswith("[bot]") or not run_id:
        raise PermissionError("A named human GitHub actor and run ID are mandatory")
    verify_preview(preview, queue_path=queue_path, revisions_path=revisions_path,
                   current_state=current_state)
    mode, candidate_id = preview["mode"], preview["candidate_id"]
    if mode == "REVIEW":
        payload = preview["payload"]
        common = {
            "candidate_id": candidate_id, "city_key": payload["city_key"],
            "note": payload["note"], "reviewed_by": actor,
            "workflow_run_id": run_id,
        }
        decision = preview["decision"]
        if decision in {"CONFIRM", "REJECT"}:
            result = review_candidate(
                queue_path, status=("confirmed" if decision == "CONFIRM" else "rejected"),
                **common,
                **({key: payload[key] for key in (
                    "record_id", "attack_date", "deaths_delta", "source_name",
                    "source_url")} if decision == "CONFIRM" else {}))
        elif decision == "HOLD":
            result = hold_candidate(queue_path, **common)
        elif decision == "REOPEN":
            result = reopen_held_candidate(queue_path, **common)
        else:
            raise ValueError("Unknown decision")
        return {"mode": "REVIEW", "decision": decision, "disposition": result,
                "target": "WIP_REVIEW_QUEUE", "revisions_changed": False}

    if mode != "PROMOTE":
        raise ValueError("Unsupported mutation mode")
    selected = candidate_by_id(load_queue(queue_path), candidate_id)
    _validated_confirmed_disposition(selected)
    # Exact accepted production function, bounded to ONE selected candidate.
    # Both inputs are synthetic/scratch copies; review queue is never written.
    with tempfile.TemporaryDirectory(prefix="casualty-promote-") as scratch:
        tmp_queue = Path(scratch) / "selected_candidate.json"
        tmp_revisions = Path(scratch) / "revisions.csv"
        tmp_queue.write_text(json.dumps([selected], ensure_ascii=False), encoding="utf-8")
        shutil.copyfile(revisions_path, tmp_revisions)
        result = promote_reviewed(tmp_queue, tmp_revisions,
                                  allowed_city_keys=set(ALLOWED_CITY_KEYS))
        if result["ledger_changed"]:
            staged = revisions_path.with_name(revisions_path.name + ".operator.tmp")
            shutil.copyfile(tmp_revisions, staged)
            os.replace(staged, revisions_path)
    return {"mode": "PROMOTE", "target": "REVISION_LEDGER",
            "review_state_changed": False, **result}


def render_summary(preview: dict) -> str:
    """Untrusted media text is HTML escaped and never passed to a shell."""
    sections = ["## Casualty operator: " + html.escape(preview["mode"])]
    for key in ("decision", "candidate_id", "pending_count", "candidate_status"):
        sections.append("<p><b>" + key + "</b>: " +
                        html.escape(str(preview.get(key, "")), quote=True) + "</p>")
    for key in ("state", "evidence", "payload", "effect", "warnings", "inbox"):
        value = json.dumps(preview.get(key), ensure_ascii=False, indent=2)
        sections.append("<h3>" + key + "</h3><pre>" +
                        html.escape(value, quote=True) + "</pre>")
    sections.append("<p><b>Human must inspect the actual source; possible duplicates are warnings only.</b></p>")
    return "\n".join(sections) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preview", "apply"))
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--revisions", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--wip-head", required=True)
    parser.add_argument("--site-prod-head", required=True)
    parser.add_argument("--queue-blob-sha", required=True)
    parser.add_argument("--revisions-blob-sha", required=True)
    parser.add_argument("--mode", default=os.environ.get("CASUALTY_MODE", "INSPECT"))
    parser.add_argument("--decision", default=os.environ.get("CASUALTY_DECISION", ""))
    parser.add_argument("--candidate-id", default=os.environ.get("CASUALTY_CANDIDATE_ID", ""))
    parser.add_argument("--reviewed-by", default=os.environ.get("GITHUB_ACTOR", ""))
    parser.add_argument("--workflow-run-id", default=os.environ.get("GITHUB_RUN_ID", ""))
    args = parser.parse_args()
    state = {
        "wip_head": args.wip_head, "site_prod_head": args.site_prod_head,
        "queue_blob_sha": args.queue_blob_sha,
        "revisions_blob_sha": args.revisions_blob_sha,
    }
    if args.action == "preview":
        payload = json.loads(os.environ.get("CASUALTY_REVIEW_PAYLOAD_JSON", "{}") or "{}")
        preview = build_preview(
            mode=args.mode, candidate_id=args.candidate_id,
            decision=args.decision, payload=payload,
            queue_path=args.queue, revisions_path=args.revisions, state=state)
        args.snapshot.write_text(json.dumps(preview, indent=2, ensure_ascii=False)
                                 + "\n", encoding="utf-8")
        if os.environ.get("GITHUB_STEP_SUMMARY"):
            with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as out:
                out.write(render_summary(preview))
        print(json.dumps({"mode": preview["mode"], "warnings": preview["warnings"],
                          "effect": preview["effect"]}, ensure_ascii=False))
    else:
        preview = json.loads(args.snapshot.read_text(encoding="utf-8"))
        result = apply_preview(preview, queue_path=args.queue,
                               revisions_path=args.revisions, current_state=state,
                               reviewed_by=args.reviewed_by,
                               workflow_run_id=args.workflow_run_id)
        print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
