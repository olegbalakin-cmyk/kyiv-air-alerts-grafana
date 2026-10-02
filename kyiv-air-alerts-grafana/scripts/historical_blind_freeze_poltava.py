#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

SCRIPT_DIR = Path(__file__).resolve().parent
APP_ROOT = SCRIPT_DIR.parent
REPO_ROOT = APP_ROOT.parent
sys.path.insert(0, str(SCRIPT_DIR))

import historical_v2_formalize_poltava_rivne as formalizer

CITY = "poltava"
CASES = list(range(111, 116))
EXPECTED_NO_CONFIRMED = 1752
SEED = "20261002-23city-blind-v1"
ACCEPTED_HEAD = "c01f4b3d8f304a8024899f22eaa8a73a8975af05"
EXPECTED_TARGET_STATE_SHA256 = "617ee7003f79df6bc99422b57778d6f9c097f53c96b0166dc056c74ba5f27be9"
ARTIFACT_REL = Path("research/historical_blind_freeze_poltava_2026-10-02.json")
ARTIFACT_PATH = REPO_ROOT / ARTIFACT_REL
PROOF_SCRIPT_REL = Path("kyiv-air-alerts-grafana/scripts/historical_blind_freeze_poltava.py")
WORKFLOW_REL = Path(".github/workflows/historical-blind-freeze-poltava-proof.yml")
ALLOWED_BRANCH_DIFF = {str(PROOF_SCRIPT_REL), str(WORKFLOW_REL)}
PRIOR_RESEARCHED_EPISODES: set[str] = set()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def git_output(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=REPO_ROOT, text=True).strip()


def git_changed_paths() -> list[str]:
    out = subprocess.check_output(
        ["git", "status", "--porcelain"], cwd=REPO_ROOT, text=True
    )
    paths: list[str] = []
    for line in out.splitlines():
        if not line.strip():
            continue
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        paths.append(path)
    return paths


def capture_formalized_state() -> tuple[dict[str, Any], dict[str, str], list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    captured: dict[str, Any] = {}
    code = formalizer.formalize_city.__code__

    def tracer(frame, event, arg):
        if frame.f_code is code and event == "return":
            captured["target_states"] = dict(frame.f_locals.get("target_states") or {})
            captured["episodes"] = [dict(x) for x in (frame.f_locals.get("episodes") or [])]
            source = frame.f_locals.get("candidates_by_episode") or {}
            captured["candidates_by_episode"] = {
                str(k): list(v) for k, v in source.items()
            }
        return tracer

    old = sys.gettrace()
    sys.settrace(tracer)
    try:
        aggregate = formalizer.formalize_city(CITY)
    finally:
        sys.settrace(old)

    if not captured:
        raise RuntimeError("FORMALIZER_TARGET_STATE_CAPTURE_FAILED")
    return (
        aggregate,
        captured["target_states"],
        captured["episodes"],
        captured["candidates_by_episode"],
    )


def main() -> int:
    current_head = git_output("rev-parse", "HEAD")
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", ACCEPTED_HEAD, current_head],
        cwd=REPO_ROOT,
        check=True,
    )

    branch_diff = set(
        p for p in git_output("diff", "--name-only", f"{ACCEPTED_HEAD}...{current_head}").splitlines() if p
    )
    unexpected_branch_diff = branch_diff - ALLOWED_BRANCH_DIFF
    if unexpected_branch_diff:
        raise SystemExit(f"UNEXPECTED_BRANCH_DIFF:{sorted(unexpected_branch_diff)}")

    dirty_before = git_changed_paths()
    if dirty_before:
        raise SystemExit(f"DIRTY_CHECKOUT_BEFORE_PROCESSING:{dirty_before}")

    guarded_paths = [
        APP_ROOT / "data/explosion_metric_handoff/source_slices/poltava-historical-recovery_alerts.json",
        APP_ROOT / "data/explosion_research/poltava/final_evidence.json",
        APP_ROOT / "scripts/monitor_explosion_candidates.py",
        APP_ROOT / "scripts/replay_explosion_history.py",
        APP_ROOT / "scripts/historical_v2_formalize_poltava_rivne.py",
    ]
    guarded_before = {
        str(p.relative_to(REPO_ROOT)): sha256_file(p)
        for p in guarded_paths
    }

    formalizer.monitor.self_test()
    aggregate, target_states, episodes, candidates_by_episode = capture_formalized_state()

    if aggregate.get("verdict") != "CITY V2 FORMALIZATION PROVEN":
        raise SystemExit(f"CITY_FORMALIZATION_NOT_PROVEN:{aggregate.get('blocker')}")
    if aggregate.get("no_confirmed_event") != EXPECTED_NO_CONFIRMED:
        raise SystemExit(
            f"CITY BLIND FREEZE BLOCKED - NO_CONFIRMED COUNT MISMATCH:"
            f"{aggregate.get('no_confirmed_event')}!={EXPECTED_NO_CONFIRMED}"
        )

    target_rows = [
        {"episode_id": eid, "state": target_states[eid]}
        for eid in sorted(target_states)
    ]
    target_state_sha = sha256_bytes(
        formalizer.stable_json(target_rows).encode("utf-8")
    )
    if target_state_sha != EXPECTED_TARGET_STATE_SHA256:
        raise SystemExit(
            f"TARGET_STATE_SHA256_MISMATCH:{target_state_sha}!={EXPECTED_TARGET_STATE_SHA256}"
        )
    if aggregate.get("target_state_sha256") != EXPECTED_TARGET_STATE_SHA256:
        raise SystemExit(
            f"AGGREGATE_TARGET_STATE_SHA256_MISMATCH:{aggregate.get('target_state_sha256')}"
        )

    ep_by_id = {
        str(ep["episode_id"]): ep for ep in episodes if ep.get("episode_id")
    }
    eligible_before = sorted(
        eid for eid, state in target_states.items()
        if state == "NO_CONFIRMED_EVENT"
    )
    if len(eligible_before) != EXPECTED_NO_CONFIRMED:
        raise SystemExit(
            f"CITY BLIND FREEZE BLOCKED - NO_CONFIRMED COUNT MISMATCH:"
            f"{len(eligible_before)}!={EXPECTED_NO_CONFIRMED}"
        )

    excluded = sorted(set(eligible_before) & PRIOR_RESEARCHED_EPISODES)
    eligible = [eid for eid in eligible_before if eid not in PRIOR_RESEARCHED_EPISODES]

    ranked = sorted(
        (
            hashlib.sha256(f"{SEED}|{CITY}|{eid}".encode("utf-8")).hexdigest(),
            eid,
        )
        for eid in eligible
    )[:5]

    selected: list[dict[str, Any]] = []
    for case_number, (rank, eid) in zip(CASES, ranked, strict=True):
        ep = ep_by_id[eid]
        row = {
            "case": case_number,
            "city_key": CITY,
            "episode_id": eid,
            "alert_start": str(ep.get("alert_start") or ""),
            "alert_end": str(ep.get("alert_end") or ""),
            "final_outcome": target_states[eid],
            "observation_count": len(candidates_by_episode.get(eid, [])),
            "rank": rank,
        }
        if not row["alert_start"] or not row["alert_end"]:
            raise SystemExit(f"SELECTED_EPISODE_MISSING_ALERT_BOUNDS:{eid}")
        if row["final_outcome"] != "NO_CONFIRMED_EVENT":
            raise SystemExit(f"SELECTED_EPISODE_NOT_NO_CONFIRMED:{eid}")
        selected.append(row)

    canonical = json.dumps(
        selected,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    city_sample_sha256 = sha256_bytes(canonical)

    guarded_after = {
        str(p.relative_to(REPO_ROOT)): sha256_file(p)
        for p in guarded_paths
    }
    if guarded_before != guarded_after:
        raise SystemExit("AUTHORITATIVE_INPUT_MUTATION_GUARD_FAILED")

    artifact = {
        "schema_version": 1,
        "verdict": "CITY BLIND SAMPLE FROZEN",
        "city": CITY,
        "cases": "111-115",
        "selection_mode": "FORMALIZED_18CITY_STATE",
        "deterministic_seed": SEED,
        "source_accepted_head": ACCEPTED_HEAD,
        "formalization_target_state_sha256": target_state_sha,
        "eligible_count_before_exclusions": len(eligible_before),
        "prior_researched_episodes": sorted(PRIOR_RESEARCHED_EPISODES),
        "prior_episodes_excluded": len(excluded),
        "eligible_count_after_exclusions": len(eligible),
        "selected_cases": selected,
        "city_sample_sha256": city_sample_sha256,
        "research_performed": "NO",
        "public_web": "NO",
        "source_discovery": "NO",
        "mutations_to_authoritative_data": 0,
        "mutation_guards": {
            "accepted_head_is_ancestor": True,
            "proof_branch_diff_allowlist": sorted(branch_diff),
            "guarded_input_sha256_before": guarded_before,
            "guarded_input_sha256_after": guarded_after,
            "authoritative_inputs_unchanged": True,
            "db_neon": "UNTOUCHED",
            "deployment": "NO",
            "historical_evidence_mutations": 0,
            "production_state_mutations": 0,
        },
        "proof_execution_head": os.environ.get("GITHUB_SHA") or current_head,
    }

    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_PATH.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    changed_after = set(git_changed_paths())
    if changed_after != {str(ARTIFACT_REL)}:
        raise SystemExit(f"UNEXPECTED_MUTATIONS_AFTER_ARTIFACT:{sorted(changed_after)}")

    print(json.dumps({
        "verdict": artifact["verdict"],
        "city": CITY,
        "eligible_before": len(eligible_before),
        "excluded": len(excluded),
        "eligible_after": len(eligible),
        "selected_cases": selected,
        "city_sample_sha256": city_sample_sha256,
    }, ensure_ascii=False, sort_keys=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
