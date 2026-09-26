#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


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


def strip_basis(text: str | None) -> str:
    value = str(text or "").strip()
    return value.split(" — ", 1)[0].strip()


def locate_final_evidence_row(
    final_evidence: dict,
    qa_case: dict,
    audit_case: dict,
) -> tuple[str, int, dict]:
    best = audit_case.get("best_candidate") or {}
    target_url = str(best.get("url") or "")
    episode_id = str(qa_case.get("episode_id") or qa_case.get("case_id") or "")

    evidence_rows = [
        row
        for row in (qa_case.get("evidence") or [])
        if str(row.get("source_url") or "") == target_url
    ]
    if not evidence_rows:
        raise ValueError(
            f"{episode_id}: no QA evidence row matches audited source URL {target_url}"
        )

    preferred = [
        row for row in evidence_rows
        if str((row.get("binding") or {}).get("episode_id") or "") == episode_id
    ]
    qa_ev = preferred[0] if preferred else evidence_rows[0]
    bucket = str(qa_ev.get("bucket") or "")
    if bucket not in {"strict_events", "sensitivity_only_events", "review_events"}:
        raise ValueError(f"{episode_id}: unsupported evidence bucket {bucket!r}")

    rows = final_evidence.get(bucket)
    if not isinstance(rows, list):
        raise ValueError(f"{episode_id}: final evidence bucket {bucket!r} missing")

    qa_base = strip_basis(qa_ev.get("evidence"))
    candidates = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        if str(row.get("source_url") or "") != target_url:
            continue

        row_ids = {
            str(row.get("matched_episode_id") or ""),
            str(row.get("alert_episode_id") or ""),
            str(row.get("episode_id") or ""),
        }
        id_match = bool(episode_id and episode_id in row_ids)
        evidence_match = bool(
            qa_base and strip_basis(row.get("evidence")) == qa_base
        )
        candidates.append((id_match, evidence_match, index, row))

    if not candidates:
        raise ValueError(
            f"{episode_id}: no final evidence row matches source URL {target_url}"
        )

    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    best_match = candidates[0]
    tied = [
        item for item in candidates
        if (item[0], item[1]) == (best_match[0], best_match[1])
    ]
    if len(tied) != 1:
        raise ValueError(
            f"{episode_id}: ambiguous final evidence row match for {target_url}; "
            f"{len(tied)} equally ranked rows"
        )
    if not best_match[0] and not best_match[1] and len(candidates) > 1:
        raise ValueError(
            f"{episode_id}: source URL is not enough to bind a unique evidence row"
        )
    return bucket, best_match[2], best_match[3]


def changed_map(replay: dict) -> dict[str, dict]:
    return {
        str(row.get("episode_id") or ""): row
        for row in (replay.get("changed_episodes") or [])
        if str(row.get("episode_id") or "")
    }


def case_signature(row: dict) -> str:
    keep = {
        "episode_id": row.get("episode_id"),
        "category": row.get("category"),
        "frozen_old_status": row.get("frozen_old_status"),
        "replayed_status": row.get("replayed_status"),
        "reason_codes": row.get("reason_codes") or [],
        "candidate_contributor_ids": row.get("candidate_contributor_ids") or [],
        "ppo_related": bool(row.get("ppo_related")),
    }
    return canonical_hash(keep)


def run_replay(
    repo_root: Path,
    city: str,
    through: str,
    input_head: str,
    output: Path,
) -> dict:
    cmd = [
        sys.executable,
        str(repo_root / "scripts" / "replay_explosion_history.py"),
        "--repo-root",
        str(repo_root),
        "--city",
        city,
        "--through",
        through,
        "--input-head",
        input_head,
        "--read-only",
        "--output",
        str(output),
    ]
    proc = subprocess.run(cmd, text=True, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(
            "Replay failed\nSTDOUT:\n"
            + proc.stdout[-5000:]
            + "\nSTDERR:\n"
            + proc.stderr[-5000:]
        )
    return load_json(output)


def preflight(
    repo_root: Path,
    qa_path: Path,
    audit_path: Path,
    through: str,
    input_head: str,
    output: Path,
) -> None:
    qa = load_json(qa_path)
    audit = load_json(audit_path)
    city = str(qa.get("city_key") or "")
    if not city or audit.get("city_key") != city:
        raise ValueError("QA/audit city mismatch")
    if int(audit.get("schema_version") or 0) < 2:
        raise ValueError("Source-retention audit schema_version >=2 required")

    qa_cases = {
        str(case.get("case_id") or ""): case
        for case in (qa.get("cases") or [])
        if str(case.get("case_id") or "")
    }
    safe_cases = [
        case
        for case in (audit.get("cases") or [])
        if case.get("triage") == "SAFE_SOURCE_RETENTION_CANDIDATE"
    ]

    final_path = (
        repo_root
        / "data"
        / "explosion_research"
        / city
        / "final_evidence.json"
    )
    if not final_path.exists():
        raise ValueError(f"Missing {final_path}")

    original_text = final_path.read_text(encoding="utf-8")
    original_payload = json.loads(original_text)

    before_path = output.parent / f"before-{city}.json"
    after_path = output.parent / f"after-{city}.json"

    before = run_replay(
        repo_root, city, through, input_head, before_path
    )
    before_changed = changed_map(before)

    qa_ids = set(qa_cases)
    before_ids = set(before_changed)
    if before_ids != qa_ids:
        raise ValueError(
            "Preflight input drift: current replay changed episode IDs do not "
            f"match persistent QA bundle. qa={sorted(qa_ids)} "
            f"replay={sorted(before_ids)}"
        )

    patch_plan = []
    patched_payload = copy.deepcopy(original_payload)

    for audit_case in safe_cases:
        case_id = str(audit_case.get("case_id") or "")
        qa_case = qa_cases.get(case_id)
        if not qa_case:
            raise ValueError(f"Safe audit case {case_id} absent from QA bundle")
        best = audit_case.get("best_candidate") or {}
        if (
            best.get("required_roles_satisfied") is not True
            or best.get("time_anchored") is not True
            or best.get("event_local_safe") is not True
            or not (best.get("shared_time_tokens") or [])
        ):
            raise ValueError(f"{case_id}: safe candidate contract not satisfied")

        bucket, index, old_row = locate_final_evidence_row(
            original_payload, qa_case, audit_case
        )
        new_excerpt = str(best.get("excerpt") or best.get("text") or "").strip()
        if not new_excerpt:
            raise ValueError(f"{case_id}: empty audited source excerpt")

        patched_row = patched_payload[bucket][index]
        old_evidence = str(patched_row.get("evidence") or "")
        patched_row["evidence"] = new_excerpt
        patched_row["source_retention_repair_candidate"] = {
            "schema_version": 1,
            "case_id": case_id,
            "case_fingerprint": qa_case.get("case_fingerprint"),
            "source_url": best.get("url"),
            "source_content_sha256": next(
                (
                    row.get("content_sha256")
                    for row in (audit_case.get("source_fetches") or [])
                    if row.get("url") == best.get("url")
                ),
                None,
            ),
            "shared_time_tokens": best.get("shared_time_tokens") or [],
            "audit_schema_version": audit.get("schema_version"),
        }
        patch_plan.append({
            "case_id": case_id,
            "episode_id": qa_case.get("episode_id"),
            "case_fingerprint": qa_case.get("case_fingerprint"),
            "bucket": bucket,
            "row_index": index,
            "source_url": best.get("url"),
            "old_evidence": old_evidence,
            "new_evidence": new_excerpt,
            "old_row_hash": canonical_hash(old_row),
            "new_row_hash": canonical_hash(patched_row),
        })

    try:
        final_path.write_text(
            json.dumps(
                patched_payload,
                ensure_ascii=False,
                indent=2,
                sort_keys=False,
            )
            + "\n",
            encoding="utf-8",
        )
        after = run_replay(
            repo_root, city, through, input_head, after_path
        )
    finally:
        final_path.write_text(original_text, encoding="utf-8")

    after_changed = changed_map(after)
    after_ids = set(after_changed)
    safe_ids = {row["case_id"] for row in patch_plan}

    resolved = sorted(safe_ids - after_ids)
    unresolved = sorted(safe_ids & after_ids)
    new_regressions = sorted(after_ids - before_ids)

    non_target_drift = []
    for case_id in sorted((before_ids & after_ids) - safe_ids):
        if case_signature(before_changed[case_id]) != case_signature(
            after_changed[case_id]
        ):
            non_target_drift.append(case_id)

    eligible = (
        sorted(safe_ids)
        if not unresolved and not new_regressions and not non_target_drift
        else resolved
        if not new_regressions and not non_target_drift
        else []
    )

    if new_regressions or non_target_drift:
        status = "REGRESSION_BLOCKED"
    elif unresolved:
        status = "PARTIAL_CLEAN"
    else:
        status = "CLEAN_ELIGIBLE"

    payload = {
        "schema_version": 1,
        "kind": "historical_replay_source_retention_repair_preflight",
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace(
            "+00:00", "Z"
        ),
        "city_key": city,
        "input_head": input_head,
        "through": through,
        "status": status,
        "safe_candidate_count": len(safe_ids),
        "resolved_candidate_count": len(resolved),
        "unresolved_candidate_count": len(unresolved),
        "eligible_to_apply_count": len(eligible),
        "safe_candidate_ids": sorted(safe_ids),
        "resolved_candidate_ids": resolved,
        "unresolved_candidate_ids": unresolved,
        "eligible_to_apply_ids": sorted(eligible),
        "new_regression_episode_ids": new_regressions,
        "non_target_drift_episode_ids": non_target_drift,
        "before_changed_count": len(before_ids),
        "after_changed_count": len(after_ids),
        "before_replay_verdict": before.get("verdict"),
        "after_replay_verdict": after.get("verdict"),
        "patch_plan": patch_plan,
        "protected_source_restored": (
            final_path.read_text(encoding="utf-8") == original_text
        ),
        "mutation_performed": False,
        "verdict": (
            "SOURCE RETENTION REPAIR PREFLIGHT CLEAN — ELIGIBLE FOR ATOMIC APPLY"
            if status == "CLEAN_ELIGIBLE"
            else "SOURCE RETENTION REPAIR PREFLIGHT PARTIAL — APPLY ONLY ELIGIBLE CASES"
            if status == "PARTIAL_CLEAN"
            else "SOURCE RETENTION REPAIR PREFLIGHT BLOCKED — REGRESSION DETECTED"
        ),
    }
    dump_json(output, payload)


def self_test() -> None:
    assert strip_basis("abc — strict: reason") == "abc"
    assert strip_basis("abc") == "abc"
    row = {"episode_id": "x", "category": "A", "reason_codes": ["B"]}
    assert case_signature(row) == case_signature(dict(row))
    print("Historical source-retention repair preflight self-test OK")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path)
    parser.add_argument("--qa", type=Path)
    parser.add_argument("--audit", type=Path)
    parser.add_argument("--through", required=False, default="2026-09-17")
    parser.add_argument("--input-head", required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return
    if not args.repo_root or not args.qa or not args.audit or not args.output:
        parser.error("--repo-root, --qa, --audit and --output are required")

    preflight(
        args.repo_root.resolve(),
        args.qa.resolve(),
        args.audit.resolve(),
        args.through,
        args.input_head,
        args.output.resolve(),
    )


if __name__ == "__main__":
    main()
