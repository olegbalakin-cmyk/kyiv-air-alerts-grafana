#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ALLOWED_DECISIONS = (
    "ACCEPT_REPLAY",
    "KEEP_BASELINE",
    "SET_STRICT",
    "SET_SENSITIVITY",
    "EXCLUDE",
    "NEED_MORE_EVIDENCE",
)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def canonical_hash(value) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def episode_case(row: dict) -> dict:
    episode_id = str(row.get("episode_id") or "")
    if not episode_id:
        raise ValueError("Changed episode is missing episode_id")
    reviewed = {
        "episode_id": episode_id,
        "local_date": row.get("local_date"),
        "alert_start": row.get("alert_start"),
        "alert_end": row.get("alert_end"),
        "category": row.get("category"),
        "frozen_old_status": row.get("frozen_old_status"),
        "replayed_status": row.get("replayed_status"),
        "ppo_related": bool(row.get("ppo_related")),
        "reason_codes": row.get("reason_codes") or [],
        "candidate_contributor_ids": row.get("candidate_contributor_ids") or [],
        "evidence": row.get("evidence") or [],
        "matching_result": row.get("matching_result") or [],
        "temporal_basis": row.get("temporal_basis") or [],
        "composition_basis": row.get("composition_basis"),
        "provenance_basis": row.get("provenance_basis") or [],
    }
    fingerprint = canonical_hash(reviewed)
    return {
        "case_type": "EPISODE_CHANGE",
        "case_id": episode_id,
        "episode_id": episode_id,
        "case_fingerprint": fingerprint,
        **reviewed,
        "decision_template": {
            "case_fingerprint": fingerprint,
            "decision": None,
            "allowed_decisions": list(ALLOWED_DECISIONS),
            "review_note": None,
        },
    }


def error_case(row: dict, index: int) -> dict:
    fingerprint = canonical_hash(row)
    return {
        "case_type": "REPLAY_ERROR",
        "case_id": f"error-{index + 1}-{fingerprint[:12]}",
        "case_fingerprint": fingerprint,
        "error": row,
        "decision_template": {
            "case_fingerprint": fingerprint,
            "decision": None,
            "allowed_decisions": ["NEED_MORE_EVIDENCE"],
            "review_note": None,
        },
    }


def build_bundle(replay: dict, status: dict, city: str) -> dict:
    city_status = (status.get("cities") or {}).get(city)
    if not isinstance(city_status, dict):
        raise ValueError(f"City {city} is absent from historical replay status")
    if city_status.get("status") != "QA_REQUIRED":
        raise ValueError(
            f"City {city} status is {city_status.get('status')!r}, expected QA_REQUIRED"
        )
    if replay.get("city_key") != city:
        raise ValueError(
            f"Replay city mismatch: {replay.get('city_key')!r} != {city!r}"
        )
    if replay.get("status") != "COMPLETE":
        raise ValueError(f"Replay is not COMPLETE: {replay.get('status')!r}")
    if replay.get("protected_files_unchanged") is not True:
        raise ValueError("Replay did not prove protected_files_unchanged=true")

    changed = replay.get("changed_episodes") or []
    errors = replay.get("errors") or []
    episode_cases = [episode_case(row) for row in changed]
    error_cases = [error_case(row, i) for i, row in enumerate(errors)]
    cases = episode_cases + error_cases

    replay_ids = [case["episode_id"] for case in episode_cases]
    expected_ids = [str(x) for x in (city_status.get("qa_episode_ids") or [])]
    if sorted(replay_ids) != sorted(expected_ids):
        raise ValueError(
            "QA episode ID drift between persistent status and fresh replay: "
            f"status={sorted(expected_ids)} replay={sorted(replay_ids)}"
        )

    expected_manual = city_status.get("manual_qa_count")
    if expected_manual is not None and int(expected_manual) != len(cases):
        raise ValueError(
            "Manual QA count drift between persistent status and fresh replay: "
            f"status={expected_manual} replay={len(cases)}"
        )

    category_counts = Counter(
        case.get("category") for case in episode_cases if case.get("category")
    )
    ppo_count = sum(1 for case in episode_cases if case.get("ppo_related"))
    fingerprints = {
        case["case_id"]: case["case_fingerprint"]
        for case in cases
    }

    return {
        "schema_version": 1,
        "kind": "historical_replay_manual_qa_bundle",
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "city_key": city,
        "through": replay.get("replay_end") or city_status.get("through") or status.get("through"),
        "replay_input_head": replay.get("input_head"),
        "status_basis_input_head": city_status.get("input_head") or status.get("input_head"),
        "status_source": "research/historical_replay_status_current.json",
        "source_status": city_status.get("source_status"),
        "status": "READY_FOR_MANUAL_QA",
        "qa_count": len(cases),
        "episode_change_count": len(episode_cases),
        "error_count": len(error_cases),
        "ppo_related_change_count": ppo_count,
        "category_counts": dict(sorted(category_counts.items())),
        "qa_episode_ids": sorted(replay_ids),
        "case_fingerprints": dict(sorted(fingerprints.items())),
        "decision_contract": {
            "schema_version": 1,
            "allowed_episode_decisions": list(ALLOWED_DECISIONS),
            "rule": (
                "A decision is valid only for the exact case_fingerprint in this bundle. "
                "If evidence or classifier output changes, regenerate QA before applying it."
            ),
        },
        "replay_summary": {
            "episodes_checked": replay.get("episodes_checked"),
            "baseline_strict_episodes": replay.get("baseline_strict_episodes"),
            "replayed_strict_episodes": replay.get("replayed_strict_episodes"),
            "baseline_sensitivity_episodes": replay.get("baseline_sensitivity_episodes"),
            "replayed_sensitivity_episodes": replay.get("replayed_sensitivity_episodes"),
            "reconciliation_counts": replay.get("reconciliation_counts") or {},
            "protected_files_unchanged": replay.get("protected_files_unchanged"),
            "verdict": replay.get("verdict"),
        },
        "cases": cases,
    }


def self_test() -> None:
    row = {
        "episode_id": "abc",
        "category": "STRICT_DOWNGRADE",
        "frozen_old_status": "STRICT",
        "replayed_status": "NON_STRICT",
        "ppo_related": True,
        "reason_codes": ["X"],
        "evidence": [{"evidence": "test"}],
    }
    a = episode_case(row)
    b = episode_case(dict(row))
    assert a["case_fingerprint"] == b["case_fingerprint"]
    assert a["decision_template"]["decision"] is None
    assert "KEEP_BASELINE" in a["decision_template"]["allowed_decisions"]
    print("Historical replay QA helper self-test OK")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a persistent manual-QA bundle from a fresh read-only historical replay."
    )
    parser.add_argument("--replay", type=Path)
    parser.add_argument("--status", type=Path)
    parser.add_argument("--city")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return
    if not all((args.replay, args.status, args.city, args.output)):
        parser.error("--replay, --status, --city and --output are required")

    replay = load_json(args.replay)
    status = load_json(args.status)
    bundle = build_bundle(replay, status, args.city)
    dump_json(args.output, bundle)
    print(
        json.dumps(
            {
                "city": args.city,
                "qa_count": bundle["qa_count"],
                "category_counts": bundle["category_counts"],
                "ppo_related_change_count": bundle["ppo_related_change_count"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
