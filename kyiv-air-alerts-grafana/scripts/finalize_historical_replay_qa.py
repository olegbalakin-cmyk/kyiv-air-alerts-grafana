#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ALLOWED_DECISIONS = {
    "ACCEPT_REPLAY",
    "KEEP_BASELINE",
    "SET_STRICT",
    "SET_SENSITIVITY",
    "EXCLUDE",
    "NEED_MORE_EVIDENCE",
}
COUNTED_SENSITIVITY = {"STRICT", "SENSITIVITY"}


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def index_cases(bundle: dict) -> dict[str, dict]:
    result = {}
    for case in bundle.get("cases") or []:
        cid = str(case.get("case_id") or "")
        if not cid:
            raise ValueError("QA case without case_id")
        if cid in result:
            raise ValueError(f"Duplicate QA case_id: {cid}")
        result[cid] = case
    return result


def resolve_final_status(case: dict, decision: str) -> str | None:
    if case.get("case_type") != "EPISODE_CHANGE":
        return None
    if decision == "ACCEPT_REPLAY":
        return str(case.get("replayed_status") or "NON_STRICT")
    if decision == "KEEP_BASELINE":
        return str(case.get("frozen_old_status") or "NON_STRICT")
    if decision == "SET_STRICT":
        return "STRICT"
    if decision == "SET_SENSITIVITY":
        return "SENSITIVITY"
    if decision == "EXCLUDE":
        return "NON_STRICT"
    return None


def metric_member(status: str | None, metric: str) -> bool:
    if metric == "strict":
        return status == "STRICT"
    if metric == "sensitivity":
        return status in COUNTED_SENSITIVITY
    raise ValueError(metric)


def finalize(persistent: dict, fresh: dict, decisions: dict) -> dict:
    city = str(fresh.get("city_key") or "")
    if not city:
        raise ValueError("Fresh QA bundle missing city_key")
    for name, payload in (
        ("persistent bundle", persistent),
        ("decision file", decisions),
    ):
        if payload.get("city_key") != city:
            raise ValueError(
                f"{name} city mismatch: {payload.get('city_key')!r} != {city!r}"
            )

    persistent_cases = index_cases(persistent)
    fresh_cases = index_cases(fresh)
    persistent_ids = set(persistent_cases)
    fresh_ids = set(fresh_cases)

    drift = []
    if persistent_ids != fresh_ids:
        drift.append({
            "code": "CASE_SET_DRIFT",
            "persistent_only": sorted(persistent_ids - fresh_ids),
            "fresh_only": sorted(fresh_ids - persistent_ids),
        })
    for cid in sorted(persistent_ids & fresh_ids):
        old_fp = persistent_cases[cid].get("case_fingerprint")
        new_fp = fresh_cases[cid].get("case_fingerprint")
        if old_fp != new_fp:
            drift.append({
                "code": "CASE_FINGERPRINT_DRIFT",
                "case_id": cid,
                "persistent_fingerprint": old_fp,
                "fresh_fingerprint": new_fp,
            })

    decision_rows = {}
    duplicate_decisions = []
    for row in decisions.get("decisions") or []:
        cid = str(row.get("case_id") or "")
        if not cid:
            continue
        if cid in decision_rows:
            duplicate_decisions.append(cid)
        decision_rows[cid] = row

    invalid = []
    if duplicate_decisions:
        invalid.append({
            "code": "DUPLICATE_DECISION_CASE_ID",
            "case_ids": sorted(set(duplicate_decisions)),
        })
    unknown_ids = sorted(set(decision_rows) - fresh_ids)
    if unknown_ids:
        invalid.append({
            "code": "DECISIONS_FOR_UNKNOWN_CASES",
            "case_ids": unknown_ids,
        })

    resolved_rows = []
    unresolved_rows = []
    strict_delta = 0
    sensitivity_delta = 0

    for cid in sorted(fresh_ids):
        case = fresh_cases[cid]
        decision_row = decision_rows.get(cid)
        if decision_row is None:
            unresolved_rows.append({
                "case_id": cid,
                "reason": "MISSING_DECISION",
                "case_fingerprint": case.get("case_fingerprint"),
            })
            continue

        expected_fp = case.get("case_fingerprint")
        supplied_fp = decision_row.get("case_fingerprint")
        if supplied_fp != expected_fp:
            invalid.append({
                "code": "DECISION_FINGERPRINT_MISMATCH",
                "case_id": cid,
                "expected": expected_fp,
                "supplied": supplied_fp,
            })
            continue

        decision = decision_row.get("decision")
        if decision in (None, ""):
            unresolved_rows.append({
                "case_id": cid,
                "reason": "DECISION_NOT_SET",
                "case_fingerprint": expected_fp,
            })
            continue
        if decision not in ALLOWED_DECISIONS:
            invalid.append({
                "code": "INVALID_DECISION",
                "case_id": cid,
                "decision": decision,
            })
            continue
        if decision == "NEED_MORE_EVIDENCE":
            unresolved_rows.append({
                "case_id": cid,
                "reason": "NEED_MORE_EVIDENCE",
                "case_fingerprint": expected_fp,
                "review_note": decision_row.get("review_note"),
            })
            continue

        if case.get("case_type") != "EPISODE_CHANGE":
            invalid.append({
                "code": "NON_EPISODE_CASE_CANNOT_BE_FINALIZED",
                "case_id": cid,
                "decision": decision,
            })
            continue

        old_status = str(case.get("frozen_old_status") or "NON_STRICT")
        replayed_status = str(case.get("replayed_status") or "NON_STRICT")
        final_status = resolve_final_status(case, decision)
        strict_delta += int(metric_member(final_status, "strict")) - int(
            metric_member(old_status, "strict")
        )
        sensitivity_delta += int(metric_member(final_status, "sensitivity")) - int(
            metric_member(old_status, "sensitivity")
        )
        resolved_rows.append({
            "case_id": cid,
            "episode_id": case.get("episode_id"),
            "case_fingerprint": expected_fp,
            "decision": decision,
            "review_note": decision_row.get("review_note"),
            "frozen_old_status": old_status,
            "replayed_status": replayed_status,
            "final_status": final_status,
            "category": case.get("category"),
        })

    baseline_strict = int(
        (fresh.get("replay_summary") or {}).get("baseline_strict_episodes") or 0
    )
    baseline_sensitivity = int(
        (fresh.get("replay_summary") or {}).get("baseline_sensitivity_episodes") or 0
    )

    if drift:
        status = "STALE_QA_BUNDLE"
    elif invalid:
        status = "INVALID_DECISIONS"
    elif unresolved_rows:
        status = "DECISIONS_REQUIRED"
    else:
        status = "READY_TO_APPLY"

    return {
        "schema_version": 1,
        "kind": "historical_replay_qa_finalization",
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "city_key": city,
        "through": fresh.get("through"),
        "status": status,
        "persistent_bundle_replay_input_head": persistent.get("replay_input_head"),
        "fresh_bundle_replay_input_head": fresh.get("replay_input_head"),
        "case_count": len(fresh_ids),
        "resolved_count": len(resolved_rows),
        "unresolved_count": len(unresolved_rows),
        "invalid_count": len(invalid),
        "drift_count": len(drift),
        "drift": drift,
        "invalid": invalid,
        "unresolved": unresolved_rows,
        "resolved": resolved_rows,
        "projected_metric": {
            "baseline_strict_episodes": baseline_strict,
            "projected_strict_episodes": baseline_strict + strict_delta,
            "strict_delta": strict_delta,
            "baseline_sensitivity_episodes": baseline_sensitivity,
            "projected_sensitivity_episodes": baseline_sensitivity + sensitivity_delta,
            "sensitivity_delta": sensitivity_delta,
        },
        "protected_files_unchanged_required_for_apply": True,
        "verdict": (
            "QA FINALIZATION CLEAN — READY TO APPLY ATOMICALLY"
            if status == "READY_TO_APPLY"
            else f"QA FINALIZATION {status}"
        ),
    }


def self_test() -> None:
    case = {
        "case_type": "EPISODE_CHANGE",
        "case_id": "x",
        "episode_id": "x",
        "case_fingerprint": "fp",
        "frozen_old_status": "SENSITIVITY",
        "replayed_status": "AMBIGUOUS",
        "category": "NEW_AMBIGUOUS",
    }
    bundle = {
        "city_key": "test",
        "through": "2026-09-17",
        "replay_input_head": "h",
        "replay_summary": {
            "baseline_strict_episodes": 1,
            "baseline_sensitivity_episodes": 2,
        },
        "cases": [case],
    }
    decisions = {
        "city_key": "test",
        "decisions": [
            {
                "case_id": "x",
                "case_fingerprint": "fp",
                "decision": "KEEP_BASELINE",
                "review_note": "test",
            }
        ],
    }
    out = finalize(bundle, bundle, decisions)
    assert out["status"] == "READY_TO_APPLY"
    assert out["projected_metric"]["projected_sensitivity_episodes"] == 2
    decisions["decisions"][0]["decision"] = "ACCEPT_REPLAY"
    out = finalize(bundle, bundle, decisions)
    assert out["projected_metric"]["projected_sensitivity_episodes"] == 1
    print("Historical replay QA finalizer self-test OK")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate historical replay QA decisions against a fresh replay."
    )
    parser.add_argument("--persistent-bundle", type=Path)
    parser.add_argument("--fresh-bundle", type=Path)
    parser.add_argument("--decisions", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return
    if not all(
        (
            args.persistent_bundle,
            args.fresh_bundle,
            args.decisions,
            args.output,
        )
    ):
        parser.error(
            "--persistent-bundle, --fresh-bundle, --decisions and --output are required"
        )

    out = finalize(
        load_json(args.persistent_bundle),
        load_json(args.fresh_bundle),
        load_json(args.decisions),
    )
    dump_json(args.output, out)
    print(
        json.dumps(
            {
                "city": out["city_key"],
                "status": out["status"],
                "resolved": out["resolved_count"],
                "unresolved": out["unresolved_count"],
                "projected_metric": out["projected_metric"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
