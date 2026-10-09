#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
CASUALTY_DIR = ROOT / "data" / "casualties"
DEFAULT_QUEUE_FILE = CASUALTY_DIR / "multicity_review_queue.json"
DEFAULT_REVISIONS_FILE = CASUALTY_DIR / "revisions.csv"
TZ = ZoneInfo("Europe/Kyiv")

REVISION_FIELDS = [
    "record_id",
    "city_key",
    "observed_at",
    "attack_date",
    "deaths_delta",
    "status",
    "source_name",
    "source_url",
    "note",
    "candidate_ids",
]


def atomic_write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def atomic_write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=REVISION_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in REVISION_FIELDS})
    tmp.replace(path)


def load_queue(path: Path) -> list[dict]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Unable to read review queue {path}: {exc}") from exc
    if not isinstance(value, list):
        raise RuntimeError(f"Review queue must be a JSON list: {path}")
    return value


def load_revision_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    seen = set()
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for raw in reader:
            record_id = (raw.get("record_id") or "").strip()
            if not record_id:
                continue
            if record_id in seen:
                raise RuntimeError(f"Duplicate casualty revision record_id: {record_id}")
            seen.add(record_id)
            row = {field: (raw.get(field) or "").strip() for field in REVISION_FIELDS}
            rows.append(row)
    return rows


def _validate_source(source_name: str | None, source_url: str | None) -> tuple[str, str]:
    name = (source_name or "").strip()
    url = (source_url or "").strip()
    parsed = urlparse(url)
    if not name:
        raise ValueError("confirmed disposition requires source_name")
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("confirmed disposition requires an http(s) source_url")
    return name, url


def _validate_confirmation(
    record_id: str | None,
    attack_date: str | None,
    deaths_delta: int | str | None,
    source_name: str | None,
    source_url: str | None,
) -> dict:
    canonical_id = (record_id or "").strip()
    if not canonical_id:
        raise ValueError("confirmed disposition requires canonical record_id")
    attack_text = (attack_date or "").strip()
    try:
        attack_day = date.fromisoformat(attack_text)
    except ValueError as exc:
        raise ValueError("confirmed disposition requires ISO attack_date") from exc
    try:
        delta = int(deaths_delta)
    except (TypeError, ValueError) as exc:
        raise ValueError("confirmed disposition requires integer deaths_delta") from exc
    if delta <= 0:
        raise ValueError("confirmed candidate deaths_delta must be positive")
    source, url = _validate_source(source_name, source_url)
    return {
        "record_id": canonical_id,
        "attack_date": attack_day.isoformat(),
        "deaths_delta": delta,
        "source_name": source,
        "source_url": url,
    }


def review_candidate(
    queue_path: Path,
    *,
    candidate_id: str,
    city_key: str,
    status: str,
    record_id: str | None = None,
    attack_date: str | None = None,
    deaths_delta: int | str | None = None,
    source_name: str | None = None,
    source_url: str | None = None,
    note: str | None = None,
    reviewed_at: str | None = None,
    reviewed_by: str | None = None,
    workflow_run_id: str | None = None,
) -> dict:
    candidate_id = (candidate_id or "").strip()
    city_key = (city_key or "").strip()
    target_status = (status or "").strip().lower()
    if not candidate_id or not city_key:
        raise ValueError("candidate_id and city_key are required")
    if target_status not in {"confirmed", "rejected"}:
        raise ValueError("status must be confirmed or rejected")

    queue = load_queue(queue_path)
    matches = [
        item
        for item in queue
        if isinstance(item, dict) and str(item.get("candidate_id") or "") == candidate_id
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected exactly one candidate_id={candidate_id}, found {len(matches)}"
        )
    candidate = matches[0]
    if str(candidate.get("city_key") or "") != city_key:
        raise RuntimeError(
            f"Candidate {candidate_id} city mismatch: "
            f"{candidate.get('city_key')!r} != {city_key!r}"
        )
    if str(candidate.get("status") or "") != "needs_review":
        raise RuntimeError(
            f"Candidate {candidate_id} is not needs_review: {candidate.get('status')!r}"
        )

    reviewed_at = reviewed_at or datetime.now(TZ).isoformat()
    disposition = {
        "status": target_status,
        "candidate_id": candidate_id,
        "city_key": city_key,
        "reviewed_at": reviewed_at,
        "note": (note or "").strip(),
    }
    if target_status == "confirmed":
        disposition.update(
            _validate_confirmation(
                record_id,
                attack_date,
                deaths_delta,
                source_name,
                source_url,
            )
        )

    if reviewed_by is not None:
        disposition["reviewed_by"] = str(reviewed_by).strip()
    if workflow_run_id is not None:
        disposition["workflow_run_id"] = str(workflow_run_id).strip()
    previous = candidate.get("review_disposition")
    if isinstance(previous, dict):
        history = candidate.setdefault("review_history", [])
        if not isinstance(history, list):
            raise RuntimeError("review_history must be a list")
        history.append(previous)
    candidate["status"] = target_status
    candidate["review_disposition"] = disposition
    atomic_write_json(queue_path, queue)
    return disposition



def _hold_transition(
    queue_path: Path,
    *,
    candidate_id: str,
    city_key: str,
    action: str,
    note: str,
    reviewed_by: str,
    workflow_run_id: str,
    reviewed_at: str | None = None,
) -> dict:
    """Durable HOLD and explicit REOPEN; original CONFIRM/REJECT/PROMOTE remain intact."""
    if action not in {"hold", "reopen"}:
        raise ValueError("Unknown hold transition")
    if not candidate_id or not city_key or not str(note or "").strip():
        raise ValueError("candidate_id, city_key and reason are required")
    if not str(reviewed_by or "").strip() or not str(workflow_run_id or "").strip():
        raise ValueError("reviewer and workflow_run_id are required")

    queue = load_queue(queue_path)
    matches = [item for item in queue if isinstance(item, dict)
               and item.get("candidate_id") == candidate_id]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one candidate_id={candidate_id}, found {len(matches)}")
    candidate = matches[0]
    if candidate.get("city_key") != city_key:
        raise RuntimeError("Candidate city mismatch")
    previous = candidate.get("review_disposition")
    if action == "hold":
        if candidate.get("status") != "needs_review":
            raise RuntimeError("HOLD requires needs_review")
        target = "hold"
    else:
        if candidate.get("status") != "hold" or not isinstance(previous, dict) or previous.get("status") != "hold":
            raise RuntimeError("REOPEN requires an explicit durable HOLD")
        target = "needs_review"

    if isinstance(previous, dict):
        history = candidate.setdefault("review_history", [])
        if not isinstance(history, list):
            raise RuntimeError("review_history must be a list")
        history.append(previous)
    disposition = {
        "status": "hold" if action == "hold" else "reopened",
        "candidate_id": candidate_id,
        "city_key": city_key,
        "reviewed_at": reviewed_at or datetime.now(TZ).isoformat(),
        "reviewed_by": reviewed_by.strip(),
        "workflow_run_id": str(workflow_run_id).strip(),
        "note": note.strip(),
    }
    candidate["status"] = target
    candidate["review_disposition"] = disposition
    atomic_write_json(queue_path, queue)
    return disposition


def hold_candidate(queue_path: Path, **kwargs) -> dict:
    return _hold_transition(queue_path, action="hold", **kwargs)


def reopen_held_candidate(queue_path: Path, **kwargs) -> dict:
    return _hold_transition(queue_path, action="reopen", **kwargs)


def _validated_confirmed_disposition(candidate: dict) -> dict:
    if candidate.get("status") != "confirmed":
        raise ValueError("candidate is not explicitly confirmed")
    disposition = candidate.get("review_disposition")
    if not isinstance(disposition, dict) or disposition.get("status") != "confirmed":
        raise ValueError("confirmed candidate lacks explicit confirmed review_disposition")
    candidate_id = str(candidate.get("candidate_id") or "").strip()
    city_key = str(candidate.get("city_key") or "").strip()
    if disposition.get("candidate_id") != candidate_id:
        raise ValueError("review_disposition candidate_id does not match candidate")
    if disposition.get("city_key") != city_key:
        raise ValueError("review_disposition city_key does not match candidate")
    validated = _validate_confirmation(
        disposition.get("record_id"),
        disposition.get("attack_date"),
        disposition.get("deaths_delta"),
        disposition.get("source_name"),
        disposition.get("source_url"),
    )
    validated["candidate_id"] = candidate_id
    validated["city_key"] = city_key
    validated["reviewed_at"] = str(disposition.get("reviewed_at") or "").strip()
    validated["note"] = str(disposition.get("note") or "").strip()
    if not validated["reviewed_at"]:
        raise ValueError("confirmed disposition requires reviewed_at")
    return validated


def _candidate_id_set(value: str) -> set[str]:
    return {item.strip() for item in (value or "").split("|") if item.strip()}


def promote_reviewed(
    queue_path: Path,
    revisions_path: Path,
    *,
    allowed_city_keys: set[str] | None = None,
) -> dict:
    queue = load_queue(queue_path)
    rows = load_revision_rows(revisions_path)
    by_record = {row["record_id"]: row for row in rows}
    changed = False
    added_records = 0
    linked_candidates = 0
    confirmed_candidates = 0

    for candidate in queue:
        if not isinstance(candidate, dict):
            continue
        status = str(candidate.get("status") or "")
        if status != "confirmed":
            continue

        confirmed_candidates += 1
        reviewed = _validated_confirmed_disposition(candidate)
        city_key = reviewed["city_key"]
        if allowed_city_keys is not None and city_key not in allowed_city_keys:
            raise RuntimeError(f"Confirmed candidate targets unknown city_key: {city_key}")

        record_id = reviewed["record_id"]
        existing = by_record.get(record_id)
        if existing is None:
            row = {
                "record_id": record_id,
                "city_key": city_key,
                "observed_at": reviewed["reviewed_at"],
                "attack_date": reviewed["attack_date"],
                "deaths_delta": str(reviewed["deaths_delta"]),
                "status": "confirmed",
                "source_name": reviewed["source_name"],
                "source_url": reviewed["source_url"],
                "note": reviewed["note"],
                "candidate_ids": reviewed["candidate_id"],
            }
            rows.append(row)
            by_record[record_id] = row
            added_records += 1
            linked_candidates += 1
            changed = True
            continue

        invariant_fields = {
            "city_key": city_key,
            "attack_date": reviewed["attack_date"],
            "deaths_delta": str(reviewed["deaths_delta"]),
            "status": "confirmed",
        }
        conflicts = {
            field: (existing.get(field), expected)
            for field, expected in invariant_fields.items()
            if str(existing.get(field) or "") != expected
        }
        if conflicts:
            raise RuntimeError(
                f"Unsafe duplicate canonical record_id {record_id}: {conflicts}"
            )

        candidate_ids = _candidate_id_set(existing.get("candidate_ids") or "")
        if reviewed["candidate_id"] not in candidate_ids:
            candidate_ids.add(reviewed["candidate_id"])
            existing["candidate_ids"] = "|".join(sorted(candidate_ids))
            linked_candidates += 1
            changed = True

    if changed:
        atomic_write_csv(revisions_path, rows)

    return {
        "confirmed_candidates_seen": confirmed_candidates,
        "canonical_records_added": added_records,
        "candidate_links_added": linked_candidates,
        "revision_rows": len(rows),
        "ledger_changed": changed,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Explicit human review and isolated promotion for multicity casualty candidates"
    )
    parser.add_argument("--queue", type=Path, default=DEFAULT_QUEUE_FILE)
    parser.add_argument("--revisions", type=Path, default=DEFAULT_REVISIONS_FILE)
    sub = parser.add_subparsers(dest="command", required=True)

    review = sub.add_parser("review", help="Change exactly one needs_review candidate")
    review.add_argument("--candidate-id", required=True)
    review.add_argument("--city-key", required=True)
    review.add_argument("--status", required=True, choices=("confirmed", "rejected"))
    review.add_argument("--record-id")
    review.add_argument("--attack-date")
    review.add_argument("--deaths-delta", type=int)
    review.add_argument("--source-name")
    review.add_argument("--source-url")
    review.add_argument("--note")

    sub.add_parser(
        "promote",
        help="Persist explicitly confirmed dispositions to the canonical revision ledger",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "review":
        result = review_candidate(
            args.queue,
            candidate_id=args.candidate_id,
            city_key=args.city_key,
            status=args.status,
            record_id=args.record_id,
            attack_date=args.attack_date,
            deaths_delta=args.deaths_delta,
            source_name=args.source_name,
            source_url=args.source_url,
            note=args.note,
        )
    else:
        result = promote_reviewed(args.queue, args.revisions)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
