#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

sys.dont_write_bytecode = True

SCRIPT_DIR = Path(__file__).resolve().parent
APP_ROOT = SCRIPT_DIR.parent
REPO_ROOT = APP_ROOT.parent
sys.path.insert(0, str(SCRIPT_DIR))

import historical_v2_formalize_kyiv as formalizer

CITY = "kyiv"
CASES = range(86, 91)
EXPECTED_NO_CONFIRMED = 2045
SEED = "20261002-23city-blind-v1"
SOURCE_ACCEPTED_HEAD = "778fb57908f64c684d3ee7df5d9a7e3f7731559b"
EXPECTED_TARGET_STATE_SHA256 = "ab008e7acedb04f1a15f64558e4470ace5167be925fa5b60fb4d30ec3292e332"
ARTIFACT_REL = Path("research/historical_blind_freeze_kyiv_2026-10-02.json")
ARTIFACT_PATH = REPO_ROOT / ARTIFACT_REL
PROOF_PATHS = {
    "kyiv-air-alerts-grafana/scripts/historical_blind_freeze_kyiv.py",
    ".github/workflows/historical-blind-freeze-kyiv-proof.yml",
}


def compact_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def git_changed_paths() -> list[str]:
    rows = subprocess.check_output(
        ["git", "status", "--porcelain"],
        cwd=REPO_ROOT,
        text=True,
    ).splitlines()
    out: list[str] = []
    for line in rows:
        if not line.strip():
            continue
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        out.append(path)
    return out


def proof_diff_paths() -> set[str]:
    out = subprocess.check_output(
        ["git", "diff", "--name-only", f"{SOURCE_ACCEPTED_HEAD}...HEAD"],
        cwd=REPO_ROOT,
        text=True,
    )
    return {line.strip() for line in out.splitlines() if line.strip()}


def reconstruct_target_rows() -> tuple[list[dict], dict]:
    city_summary = formalizer.formalize_city(CITY)
    if city_summary["verdict"] != "CITY V2 FORMALIZATION PROVEN":
        raise SystemExit(f"FORMALIZATION_BLOCKED:{city_summary.get('blocker')}")
    if city_summary["no_confirmed_event"] != EXPECTED_NO_CONFIRMED:
        raise SystemExit(
            f"CITY BLIND FREEZE BLOCKED — NO_CONFIRMED COUNT MISMATCH:"
            f"{city_summary['no_confirmed_event']}!={EXPECTED_NO_CONFIRMED}"
        )
    if city_summary["target_state_sha256"] != EXPECTED_TARGET_STATE_SHA256:
        raise SystemExit(
            "ACCEPTED_TARGET_STATE_SHA_MISMATCH:"
            f"{city_summary['target_state_sha256']}!={EXPECTED_TARGET_STATE_SHA256}"
        )

    episodes, _ = formalizer.replay.load_historical_episodes(
        formalizer.APP_ROOT, CITY, formalizer.monitor
    )
    episodes = sorted(
        [dict(ep) for ep in episodes],
        key=lambda ep: (str(ep.get("alert_start") or ""), str(ep.get("episode_id") or "")),
    )
    ep_by_id = {str(ep["episode_id"]): ep for ep in episodes}
    canonical_set = set(ep_by_id)

    evidence = formalizer.load_json(formalizer.evidence_path(CITY))
    candidates_by_episode: dict[str, list[dict]] = defaultdict(list)
    observation_count: dict[str, int] = defaultdict(int)
    seen_candidate_ids: set[tuple[str, str]] = set()

    for bucket in formalizer.BUCKETS:
        rows = evidence.get(bucket) or []
        allow_split = bucket in {"strict_events", "sensitivity_only_events"}
        for index, row in enumerate(rows):
            observations = formalizer.replay.expand_historical_evidence_observations(
                CITY,
                bucket,
                index,
                row,
                episodes,
                formalizer.monitor,
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
                candidate = formalizer.replay.candidate_from_history(
                    CITY,
                    observation["row"],
                    bucket,
                    target_id,
                    formalizer.monitor,
                    ep_by_id.get(target_id),
                )
                key = (target_id, str(candidate.get("candidate_id") or ""))
                if key in seen_candidate_ids:
                    continue
                seen_candidate_ids.add(key)
                matching = formalizer.replay.manual_matching(target_id)
                decision = formalizer.monitor.classify_candidate(
                    candidate, CITY, episodes, matching
                )
                formalizer.monitor.apply_classification_decision(
                    candidate, decision, matching
                )
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
                formalizer.monitor.compose_episode_candidates(CITY, ep, rows, episodes)
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

    state_rows = [
        {"episode_id": eid, "state": target_states[eid]}
        for eid in sorted(target_states)
    ]
    reconstructed_sha = sha256_bytes(
        formalizer.stable_json(state_rows).encode("utf-8")
    )
    if reconstructed_sha != city_summary["target_state_sha256"]:
        raise SystemExit(
            f"RECONSTRUCTED_TARGET_STATE_SHA_MISMATCH:"
            f"{reconstructed_sha}!={city_summary['target_state_sha256']}"
        )

    rows = []
    for ep in episodes:
        eid = str(ep["episode_id"])
        rows.append(
            {
                "episode_id": eid,
                "alert_start": ep.get("alert_start"),
                "alert_end": ep.get("alert_end"),
                "final_outcome": target_states[eid],
                "observation_count": int(observation_count.get(eid, 0)),
            }
        )
    return rows, city_summary


def main() -> int:
    if git_changed_paths():
        raise SystemExit(f"DIRTY_CHECKOUT_BEFORE_PROCESSING:{git_changed_paths()}")

    proof_changes = proof_diff_paths()
    if not proof_changes <= PROOF_PATHS:
        raise SystemExit(f"NON_PROOF_DRIFT_SINCE_ACCEPTED_HEAD:{sorted(proof_changes - PROOF_PATHS)}")

    formalizer.monitor.self_test()

    guarded_paths = [
        formalizer.evidence_path(CITY),
        formalizer.APP_ROOT / "data/alerts_combined.json",
        formalizer.APP_ROOT / "scripts/monitor_explosion_candidates.py",
        formalizer.APP_ROOT / "scripts/replay_explosion_history.py",
        formalizer.APP_ROOT / "scripts/historical_v2_formalize_kyiv.py",
    ]
    guarded_before = {
        str(path.relative_to(REPO_ROOT)): sha256_file(path)
        for path in guarded_paths
    }

    target_rows, city_summary = reconstruct_target_rows()

    eligible_before = [
        row for row in target_rows
        if row["final_outcome"] == "NO_CONFIRMED_EVENT"
    ]
    if len(eligible_before) != EXPECTED_NO_CONFIRMED:
        raise SystemExit(
            f"CITY BLIND FREEZE BLOCKED — NO_CONFIRMED COUNT MISMATCH:"
            f"{len(eligible_before)}!={EXPECTED_NO_CONFIRMED}"
        )

    prior_researched_episodes: set[str] = set()
    eligible = [
        row for row in eligible_before
        if row["episode_id"] not in prior_researched_episodes
    ]
    exclusions_count = len(eligible_before) - len(eligible)

    ranked = []
    for row in eligible:
        rank = hashlib.sha256(
            f"{SEED}|{CITY}|{row['episode_id']}".encode("utf-8")
        ).hexdigest()
        ranked.append((rank, row["episode_id"], row))
    ranked.sort(key=lambda item: (item[0], item[1]))

    selected = []
    for case_no, (rank, _, row) in zip(CASES, ranked[:5]):
        selected.append(
            {
                "case": case_no,
                "city_key": CITY,
                "episode_id": row["episode_id"],
                "alert_start": row["alert_start"],
                "alert_end": row["alert_end"],
                "final_outcome": row["final_outcome"],
                "observation_count": row["observation_count"],
                "rank": rank,
            }
        )

    if len(selected) != 5:
        raise SystemExit(f"SELECTION_COUNT_MISMATCH:{len(selected)}")
    if any(row["final_outcome"] != "NO_CONFIRMED_EVENT" for row in selected):
        raise SystemExit("SELECTED_NON_NO_CONFIRMED_CASE")

    city_sample_sha256 = sha256_bytes(compact_json(selected).encode("utf-8"))

    guarded_after = {
        str(path.relative_to(REPO_ROOT)): sha256_file(path)
        for path in guarded_paths
    }
    if guarded_before != guarded_after:
        raise SystemExit("AUTHORITATIVE_INPUT_MUTATION_GUARD_FAILED")

    changed_before_artifact = git_changed_paths()
    if changed_before_artifact:
        raise SystemExit(f"UNEXPECTED_MUTATIONS_BEFORE_ARTIFACT:{changed_before_artifact}")

    tested_head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        text=True,
    ).strip()

    artifact = {
        "verdict": "CITY BLIND SAMPLE FROZEN",
        "city": CITY,
        "cases": "86–90",
        "selection_mode": "FORMALIZED_18CITY_STATE",
        "deterministic_seed": SEED,
        "source_accepted_head": SOURCE_ACCEPTED_HEAD,
        "source_target_state_sha256": city_summary["target_state_sha256"],
        "eligible_count_before_exclusions": len(eligible_before),
        "exclusions_count": exclusions_count,
        "eligible_count_after_exclusions": len(eligible),
        "selected_cases": selected,
        "CITY_SAMPLE_SHA256": city_sample_sha256,
        "mutation_guards": {
            "proof_only_changed_paths_since_source_head": sorted(proof_changes),
            "authoritative_inputs_unchanged": True,
            "authoritative_evidence_mutations": 0,
            "db_neon": "UNTOUCHED",
            "deployment": "NO",
            "incorporation": "NO",
        },
        "research_performed": "NO",
        "public_web": "NO",
        "source_discovery": "NO",
        "tested_proof_head": tested_head,
    }

    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_PATH.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    changed_after = git_changed_paths()
    if changed_after != [str(ARTIFACT_REL)]:
        raise SystemExit(f"MUTATION_ALLOWLIST_FAILED:{changed_after}")

    print(compact_json({
        "verdict": artifact["verdict"],
        "city": CITY,
        "before": len(eligible_before),
        "excluded": exclusions_count,
        "after": len(eligible),
        "selected_cases": selected,
        "CITY_SAMPLE_SHA256": city_sample_sha256,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
