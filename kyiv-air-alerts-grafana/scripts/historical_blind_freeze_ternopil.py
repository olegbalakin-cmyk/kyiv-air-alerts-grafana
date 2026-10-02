#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

SCRIPT_DIR = Path(__file__).resolve().parent
APP_ROOT = SCRIPT_DIR.parent
REPO_ROOT = APP_ROOT.parent
sys.path.insert(0, str(SCRIPT_DIR))

import historical_v2_formalize_ternopil_uzhhorod as accepted

# Proof-only selector: no network retrieval, source discovery, or authoritative mutation.\nCITY = "ternopil"
SOURCE_ACCEPTED_HEAD = "19637504db967003c4e0465957dc7bd2bf5fbc58"
EXPECTED_NO_CONFIRMED = 120
EXPECTED_TARGET_STATE_SHA256 = "d989a8c1dfc65965cc6ac07cb1d30c711d9e93f272eaf950db7c6aacf17e4e73"
SEED = "20261002-23city-blind-v1"
CASE_START = 131
SELECT_N = 5
PRIOR_RESEARCHED_EPISODES: set[str] = set()
ARTIFACT_REL = Path("research/historical_blind_freeze_ternopil_2026-10-02.json")
ARTIFACT_PATH = REPO_ROOT / ARTIFACT_REL

EXPECTED_GUARDED_SHA256 = {
    "kyiv-air-alerts-grafana/data/explosion_metric_handoff/source_slices/ternopil-historical-recovery_alerts.json": "1f91fe5cf80bb85969055317947de65bc595c2e324330247670d1baa5f6c98e5",
    "kyiv-air-alerts-grafana/data/explosion_research/ternopil/final_evidence.json": "bda9327ee19ac5359a999317d53f1cb6bf002136985eb3a7982854c135fdd6ce",
    "kyiv-air-alerts-grafana/scripts/monitor_explosion_candidates.py": "499df82ee4a0e9997f31c381850241bc19667ffc2b3882e7a1123df52c900c18",
    "kyiv-air-alerts-grafana/scripts/replay_explosion_history.py": "5df4be4ae6a0518dbde7b89cafbfeae76cc23170a84071afd4f6771a9ef301bf",
}

PROOF_PATHS = {
    ".github/workflows/historical-blind-freeze-ternopil-proof.yml",
    "kyiv-air-alerts-grafana/scripts/historical_blind_freeze_ternopil.py",
    str(ARTIFACT_REL),
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def git_lines(*args: str) -> list[str]:
    out = subprocess.check_output(["git", *args], cwd=REPO_ROOT, text=True)
    return [line.strip() for line in out.splitlines() if line.strip()]


def source_drift_guard() -> tuple[bool, dict[str, Any]]:
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", SOURCE_ACCEPTED_HEAD, "HEAD"],
        cwd=REPO_ROOT,
        check=True,
    )
    changed_from_source = git_lines("diff", "--name-only", f"{SOURCE_ACCEPTED_HEAD}..HEAD")
    unexpected_committed = sorted(set(changed_from_source) - PROOF_PATHS)

    observed = {}
    for rel, expected_sha in EXPECTED_GUARDED_SHA256.items():
        path = REPO_ROOT / rel
        observed[rel] = sha256_file(path) if path.exists() else None

    hash_match = all(observed.get(rel) == expected for rel, expected in EXPECTED_GUARDED_SHA256.items())
    return (not unexpected_committed and hash_match), {
        "source_head_is_ancestor": True,
        "changed_from_source_head": changed_from_source,
        "unexpected_committed_paths": unexpected_committed,
        "guarded_input_sha256_expected": EXPECTED_GUARDED_SHA256,
        "guarded_input_sha256_observed": observed,
        "guarded_inputs_match": hash_match,
    }


def reconstruct_ternopil_targets() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    # First run the accepted formalization helper for this city only.
    aggregate = accepted.formalize_city(CITY)

    episodes, _ = accepted.replay.load_historical_episodes(APP_ROOT, CITY, accepted.monitor)
    episodes = sorted(
        [dict(ep) for ep in episodes],
        key=lambda ep: (str(ep.get("alert_start") or ""), str(ep.get("episode_id") or "")),
    )
    canonical_set = {str(ep["episode_id"]) for ep in episodes if ep.get("episode_id")}
    ep_by_id = {str(ep["episode_id"]): ep for ep in episodes if ep.get("episode_id")}

    evidence = accepted.load_json(accepted.evidence_path(CITY))
    candidates_by_episode: dict[str, list[dict[str, Any]]] = defaultdict(list)
    observation_count: dict[str, int] = defaultdict(int)
    seen_candidate_ids: set[tuple[str, str]] = set()

    for bucket in accepted.BUCKETS:
        rows = evidence.get(bucket) or []
        allow_split = bucket in {"strict_events", "sensitivity_only_events"}
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            observations = accepted.replay.expand_historical_evidence_observations(
                CITY,
                bucket,
                index,
                row,
                episodes,
                accepted.monitor,
                allow_new_temporal_fallback=allow_split,
            )
            for observation in observations:
                if observation.get("is_split_child") and observation.get("event_fact_present") is False:
                    continue

                binding = observation.get("binding") or {}
                target_id = str(binding.get("episode_id") or "")
                if not target_id or target_id not in canonical_set:
                    continue

                observation_count[target_id] += 1
                candidate = accepted.replay.candidate_from_history(
                    CITY,
                    observation["row"],
                    bucket,
                    target_id,
                    accepted.monitor,
                    ep_by_id.get(target_id),
                )
                key = (target_id, str(candidate.get("candidate_id") or ""))
                if key in seen_candidate_ids:
                    continue
                seen_candidate_ids.add(key)

                matching = accepted.replay.manual_matching(target_id)
                decision = accepted.monitor.classify_candidate(candidate, CITY, episodes, matching)
                accepted.monitor.apply_classification_decision(candidate, decision, matching)
                candidates_by_episode[target_id].append(candidate)

    target_states: dict[str, str] = {}
    for ep in episodes:
        eid = str(ep["episode_id"])
        rows = candidates_by_episode.get(eid, [])
        statuses = {str(row.get("status") or "") for row in rows}
        state = "NO_CONFIRMED_EVENT"
        if "approved_strict" in statuses:
            state = "STRICT_EVENT_POSITIVE"
        else:
            composition = (
                accepted.monitor.compose_episode_candidates(CITY, ep, rows, episodes)
                if len(rows) >= 2
                else {"final_composed_verdict": "not_applicable"}
            )
            if composition.get("final_composed_verdict") == "approved_strict":
                state = "STRICT_EVENT_POSITIVE"
            elif "approved_sensitivity" in statuses:
                state = "SENSITIVITY_EVENT_POSITIVE"
            elif "needs_review" in statuses:
                state = "NEEDS_REVIEW"
        target_states[eid] = state

    target_rows_for_sha = [
        {"episode_id": eid, "state": target_states[eid]}
        for eid in sorted(target_states)
    ]
    reconstructed_target_sha = sha256_bytes(
        accepted.stable_json(target_rows_for_sha).encode("utf-8")
    )

    rows = []
    for ep in episodes:
        eid = str(ep["episode_id"])
        rows.append({
            "episode_id": eid,
            "alert_start": ep.get("alert_start"),
            "alert_end": ep.get("alert_end"),
            "final_outcome": target_states[eid],
            "observation_count": int(observation_count.get(eid, 0)),
        })

    return rows, {
        "accepted_aggregate": aggregate,
        "reconstructed_target_state_sha256": reconstructed_target_sha,
    }


def sample_fingerprint(selected: list[dict[str, Any]]) -> str:
    payload = json.dumps(selected, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return sha256_bytes(payload)


def main() -> int:
    dirty_before = accepted.git_changed_paths()
    if dirty_before:
        raise SystemExit(f"DIRTY_CHECKOUT_BEFORE_PROCESSING:{dirty_before}")

    accepted.monitor.self_test()

    source_guard_pass, source_guard = source_drift_guard()
    target_rows, reconstruction = reconstruct_ternopil_targets()
    aggregate = reconstruction["accepted_aggregate"]

    aggregate_match = (
        aggregate.get("verdict") == "CITY V2 FORMALIZATION PROVEN"
        and aggregate.get("no_confirmed_event") == EXPECTED_NO_CONFIRMED
        and aggregate.get("target_state_sha256") == EXPECTED_TARGET_STATE_SHA256
        and reconstruction["reconstructed_target_state_sha256"] == EXPECTED_TARGET_STATE_SHA256
    )

    eligible_before = [
        row for row in target_rows
        if row["final_outcome"] == "NO_CONFIRMED_EVENT"
    ]
    count_before = len(eligible_before)

    excluded = [
        row for row in eligible_before
        if row["episode_id"] in PRIOR_RESEARCHED_EPISODES
    ]
    eligible_after = [
        row for row in eligible_before
        if row["episode_id"] not in PRIOR_RESEARCHED_EPISODES
    ]

    count_guard_pass = count_before == EXPECTED_NO_CONFIRMED
    blockers: list[str] = []
    if not source_guard_pass:
        blockers.append("SOURCE_ACCEPTED_HEAD_DRIFT")
    if not aggregate_match:
        blockers.append("ACCEPTED_FORMALIZATION_RECONSTRUCTION_MISMATCH")
    if not count_guard_pass:
        blockers.append("NO_CONFIRMED_COUNT_MISMATCH")

    selected_cases: list[dict[str, Any]] = []
    city_sample_sha256 = None

    if not blockers:
        ranked = []
        for row in eligible_after:
            eid = row["episode_id"]
            rank = sha256_bytes(f"{SEED}|{CITY}|{eid}".encode("utf-8"))
            ranked.append((rank, eid, row))
        ranked.sort(key=lambda item: (item[0], item[1]))

        if len(ranked) < SELECT_N:
            blockers.append("INSUFFICIENT_ELIGIBLE_TARGETS")
        else:
            for offset, (rank, eid, row) in enumerate(ranked[:SELECT_N]):
                selected_cases.append({
                    "case": CASE_START + offset,
                    "city_key": CITY,
                    "episode_id": eid,
                    "alert_start": row["alert_start"],
                    "alert_end": row["alert_end"],
                    "final_outcome": row["final_outcome"],
                    "observation_count": row["observation_count"],
                    "rank": rank,
                })
            city_sample_sha256 = sample_fingerprint(selected_cases)

    changed_before_artifact = accepted.git_changed_paths()
    mutation_guard_pass = not changed_before_artifact
    if not mutation_guard_pass:
        blockers.append("WORKTREE_MUTATION_BEFORE_ARTIFACT")

    verdict = "CITY BLIND SAMPLE FREEZE BLOCKED" if blockers else "CITY BLIND SAMPLE FROZEN"
    artifact = {
        "verdict": verdict,
        "city": CITY,
        "cases": "131-135",
        "source_accepted_heads": [SOURCE_ACCEPTED_HEAD],
        "selection_mode": "FORMALIZED_18CITY_STATE",
        "deterministic_seed": SEED,
        "eligible_count_before_exclusions": count_before,
        "prior_episodes_excluded": len(excluded),
        "eligible_count_after_exclusions": len(eligible_after),
        "selected_cases": selected_cases,
        "city_sample_sha256": city_sample_sha256,
        "aggregate_guards": {
            "expected_no_confirmed": EXPECTED_NO_CONFIRMED,
            "observed_no_confirmed": count_before,
            "accepted_helper_no_confirmed": aggregate.get("no_confirmed_event"),
            "expected_target_state_sha256": EXPECTED_TARGET_STATE_SHA256,
            "accepted_helper_target_state_sha256": aggregate.get("target_state_sha256"),
            "reconstructed_target_state_sha256": reconstruction["reconstructed_target_state_sha256"],
            "accepted_city_verdict": aggregate.get("verdict"),
            "pass": aggregate_match and count_guard_pass,
        },
        "mutation_guards": {
            **source_guard,
            "worktree_clean_before_artifact": mutation_guard_pass,
            "authoritative_data_mutations": 0 if source_guard_pass and mutation_guard_pass else None,
            "db_neon": "UNTOUCHED",
            "deployment": "NO",
            "production_dashboard_data": "UNTOUCHED",
        },
        "blockers": blockers,
        "research_performed": "NO",
        "public_web": "NO",
        "source_discovery": "NO",
        "incorporation": "NO",
    }

    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_PATH.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    changed_after = accepted.git_changed_paths()
    unexpected_after = [p for p in changed_after if p != str(ARTIFACT_REL)]
    if unexpected_after:
        raise SystemExit(f"UNEXPECTED_MUTATIONS_AFTER_ARTIFACT:{unexpected_after}")

    print(json.dumps({
        "verdict": verdict,
        "city": CITY,
        "eligible_before": count_before,
        "excluded": len(excluded),
        "eligible_after": len(eligible_after),
        "selected_cases": selected_cases,
        "city_sample_sha256": city_sample_sha256,
        "blockers": blockers,
    }, ensure_ascii=False, separators=(",", ":")))

    return 0 if not blockers else 2


if __name__ == "__main__":
    raise SystemExit(main())
