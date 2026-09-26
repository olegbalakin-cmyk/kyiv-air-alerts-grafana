#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
import tempfile


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


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def changed_map(replay: dict) -> dict[str, dict]:
    return {
        str(row.get("episode_id") or ""): row
        for row in (replay.get("changed_episodes") or [])
        if str(row.get("episode_id") or "")
    }


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


def apply(
    repo_root: Path,
    preflight_path: Path,
    audit_path: Path,
    qa_path: Path,
    request_path: Path,
    input_head: str,
    output_path: Path,
) -> None:
    preflight = load_json(preflight_path)
    audit = load_json(audit_path)
    qa = load_json(qa_path)
    request = load_json(request_path)

    city = str(request.get("city_key") or "")
    if not city:
        raise ValueError("Apply request missing city_key")
    for label, payload in (
        ("preflight", preflight),
        ("audit", audit),
        ("qa", qa),
    ):
        if payload.get("city_key") != city:
            raise ValueError(
                f"{label} city mismatch: {payload.get('city_key')!r} != {city!r}"
            )

    expected_blob = str(request.get("preflight_blob_sha") or "")
    actual_blob = git_blob_sha(preflight_path)
    if expected_blob and actual_blob != expected_blob:
        raise ValueError(
            f"Preflight blob mismatch: expected {expected_blob}, got {actual_blob}"
        )

    if preflight.get("status") not in {"CLEAN_ELIGIBLE", "PARTIAL_CLEAN"}:
        raise ValueError(
            f"Preflight status is not applyable: {preflight.get('status')!r}"
        )
    if preflight.get("new_regression_episode_ids"):
        raise ValueError("Preflight contains new regression episode IDs")
    if preflight.get("non_target_drift_episode_ids"):
        raise ValueError("Preflight contains non-target drift")

    requested_ids = [str(x) for x in (request.get("case_ids") or [])]
    if not requested_ids:
        raise ValueError("Apply request contains no case_ids")
    if len(set(requested_ids)) != len(requested_ids):
        raise ValueError("Apply request contains duplicate case_ids")

    eligible = {
        str(x) for x in (preflight.get("eligible_to_apply_ids") or [])
    }
    if not set(requested_ids).issubset(eligible):
        raise ValueError(
            "Request includes non-eligible cases: "
            + repr(sorted(set(requested_ids) - eligible))
        )

    plans = {
        str(row.get("case_id") or ""): row
        for row in (preflight.get("patch_plan") or [])
        if str(row.get("case_id") or "")
    }
    audit_cases = {
        str(row.get("case_id") or ""): row
        for row in (audit.get("cases") or [])
        if str(row.get("case_id") or "")
    }
    qa_cases = {
        str(row.get("case_id") or ""): row
        for row in (qa.get("cases") or [])
        if str(row.get("case_id") or "")
    }

    final_path = (
        repo_root
        / "data"
        / "explosion_research"
        / city
        / "final_evidence.json"
    )
    payload = load_json(final_path)
    applied_rows = []

    for case_id in requested_ids:
        plan = plans.get(case_id)
        audit_case = audit_cases.get(case_id)
        qa_case = qa_cases.get(case_id)
        if not plan or not audit_case or not qa_case:
            raise ValueError(f"{case_id}: missing plan/audit/QA record")

        if qa_case.get("case_fingerprint") != plan.get("case_fingerprint"):
            raise ValueError(f"{case_id}: QA/preflight fingerprint mismatch")
        if audit_case.get("case_fingerprint") != plan.get("case_fingerprint"):
            raise ValueError(f"{case_id}: audit/preflight fingerprint mismatch")
        if audit_case.get("triage") != "SAFE_SOURCE_RETENTION_CANDIDATE":
            raise ValueError(f"{case_id}: source audit is no longer SAFE")

        bucket = str(plan.get("bucket") or "")
        index = int(plan.get("row_index"))
        rows = payload.get(bucket)
        if not isinstance(rows, list) or not (0 <= index < len(rows)):
            raise ValueError(f"{case_id}: target row unavailable")
        row = rows[index]

        old_hash = canonical_hash(row)
        if old_hash != plan.get("old_row_hash"):
            raise ValueError(
                f"{case_id}: old row hash drift: {old_hash} != "
                f"{plan.get('old_row_hash')}"
            )
        if str(row.get("evidence") or "") != str(plan.get("old_evidence") or ""):
            raise ValueError(f"{case_id}: old evidence text drift")

        best = audit_case.get("best_candidate") or {}
        source_url = str(plan.get("source_url") or "")
        if source_url != str(best.get("url") or ""):
            raise ValueError(f"{case_id}: source URL drift")
        source_content_sha = next(
            (
                item.get("content_sha256")
                for item in (audit_case.get("source_fetches") or [])
                if item.get("url") == source_url
            ),
            None,
        )

        row["evidence"] = str(plan.get("new_evidence") or "")
        row["source_retention_repair_candidate"] = {
            "schema_version": 1,
            "case_id": case_id,
            "case_fingerprint": plan.get("case_fingerprint"),
            "source_url": source_url,
            "source_content_sha256": source_content_sha,
            "shared_time_tokens": best.get("shared_time_tokens") or [],
            "audit_schema_version": audit.get("schema_version"),
        }

        new_hash = canonical_hash(row)
        if new_hash != plan.get("new_row_hash"):
            raise ValueError(
                f"{case_id}: applied row hash does not match dry-run plan: "
                f"{new_hash} != {plan.get('new_row_hash')}"
            )

        applied_rows.append({
            "case_id": case_id,
            "episode_id": plan.get("episode_id"),
            "bucket": bucket,
            "row_index": index,
            "old_row_hash": old_hash,
            "new_row_hash": new_hash,
            "source_url": source_url,
            "case_fingerprint": plan.get("case_fingerprint"),
        })

    final_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    through = str(preflight.get("through") or qa.get("through") or "2026-09-17")
    replay_path = Path(tempfile.gettempdir()) / f"post-apply-replay-{city}.json"
    replay = run_replay(
        repo_root,
        city,
        through,
        input_head,
        replay_path,
    )

    before_ids = {
        str(row.get("case_id") or "")
        for row in (qa.get("cases") or [])
        if str(row.get("case_id") or "")
    }
    expected_after = before_ids - set(requested_ids)
    after_ids = set(changed_map(replay))

    if after_ids != expected_after:
        raise ValueError(
            "Post-apply replay changed-set mismatch: "
            f"expected={sorted(expected_after)} actual={sorted(after_ids)}"
        )
    if replay.get("errors"):
        raise ValueError(
            f"Post-apply replay produced errors: {replay.get('errors')!r}"
        )
    if replay.get("protected_files_unchanged") is not True:
        raise ValueError(
            "Post-apply replay did not prove protected_files_unchanged=true"
        )

    report = {
        "schema_version": 1,
        "kind": "historical_replay_source_retention_atomic_apply",
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace(
            "+00:00", "Z"
        ),
        "city_key": city,
        "input_head": input_head,
        "preflight_blob_sha": actual_blob,
        "requested_case_ids": requested_ids,
        "applied_count": len(applied_rows),
        "applied_rows": applied_rows,
        "post_apply_changed_count": len(after_ids),
        "post_apply_changed_episode_ids": sorted(after_ids),
        "post_apply_replay_verdict": replay.get("verdict"),
        "protected_files_unchanged": replay.get("protected_files_unchanged"),
        "status": "APPLIED_WORKTREE_VALIDATED",
        "verdict": "SOURCE RETENTION REPAIRS APPLIED IN WORKTREE — READY TO COMMIT",
    }
    dump_json(output_path, report)


def self_test() -> None:
    row = {"a": 1, "b": ["x"]}
    assert canonical_hash(row) == canonical_hash({"b": ["x"], "a": 1})
    print("Historical source-retention atomic apply self-test OK")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path)
    parser.add_argument("--preflight", type=Path)
    parser.add_argument("--audit", type=Path)
    parser.add_argument("--qa", type=Path)
    parser.add_argument("--request", type=Path)
    parser.add_argument("--input-head")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return
    required = (
        args.repo_root,
        args.preflight,
        args.audit,
        args.qa,
        args.request,
        args.input_head,
        args.output,
    )
    if not all(required):
        parser.error(
            "--repo-root, --preflight, --audit, --qa, --request, "
            "--input-head and --output are required"
        )

    apply(
        args.repo_root.resolve(),
        args.preflight.resolve(),
        args.audit.resolve(),
        args.qa.resolve(),
        args.request.resolve(),
        args.input_head,
        args.output.resolve(),
    )


if __name__ == "__main__":
    main()
