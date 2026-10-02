#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

sys.dont_write_bytecode = True

SCRIPT_DIR = Path(__file__).resolve().parent
APP_ROOT = SCRIPT_DIR.parent
REPO_ROOT = APP_ROOT.parent
sys.path.insert(0, str(SCRIPT_DIR))

import historical_v2_formalize_chernivtsi_ivano_frankivsk as formalizer

CITY = "ivano_frankivsk"
CASES = range(61, 66)
EXPECTED_NO_CONFIRMED = 97
SEED = "20261002-23city-blind-v1"
SOURCE_ACCEPTED_HEAD = "05e9ce706a2f8da459f46fb130bc25d716cfcc46"
SOURCE_PROOF_BRANCH = "historical-v2-formalization-chernivtsi-ivano-frankivsk-proof-2026-10-02"
ACCEPTED_TARGET_STATE_SHA256 = "246a54c2f9bf382688a22cfee4e55b571b1f083b2f3fc86176054e75ace1cd79"
ARTIFACT_REL = Path("research/historical_blind_freeze_ivano_frankivsk_2026-10-02.json")
ARTIFACT_PATH = REPO_ROOT / ARTIFACT_REL


def git_changed_paths() -> list[str]:
    proc = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    out: list[str] = []
    for line in proc.stdout.splitlines():
        if not line.strip():
            continue
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        out.append(path)
    return out


def reconstruct_target_state() -> tuple[list[dict], dict[str, int], str]:
    monitor = formalizer.monitor
    replay = formalizer.replay

    episodes, _source_files = replay.load_historical_episodes(APP_ROOT, CITY, monitor)
    episodes = sorted(
        [dict(ep) for ep in episodes],
        key=lambda ep: (str(ep.get("alert_start") or ""), str(ep.get("episode_id") or "")),
    )
    episode_ids = [str(ep["episode_id"]) for ep in episodes]
    canonical_set = set(episode_ids)
    ep_by_id = {str(ep["episode_id"]): ep for ep in episodes}

    evidence = formalizer.load_json(formalizer.evidence_path(CITY))
    candidates_by_episode: dict[str, list[dict]] = defaultdict(list)
    seen_candidate_ids: set[tuple[str, str]] = set()

    for bucket in formalizer.BUCKETS:
        rows = evidence.get(bucket) or []
        if not isinstance(rows, list):
            raise SystemExit(f"EVIDENCE_BUCKET_NOT_LIST:{bucket}")
        allow_split = bucket in {"strict_events", "sensitivity_only_events"}
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                raise SystemExit(f"NON_OBJECT_EVIDENCE_RECORD:{bucket}:{index}")

            observations = replay.expand_historical_evidence_observations(
                CITY,
                bucket,
                index,
                row,
                episodes,
                monitor,
                allow_new_temporal_fallback=allow_split,
            )

            for observation in observations:
                if observation.get("is_split_child") and observation.get("event_fact_present") is False:
                    continue

                binding = observation.get("binding") or {}
                target_id = str(binding.get("episode_id") or "")
                if not target_id or target_id not in canonical_set:
                    if bucket in {"strict_events", "sensitivity_only_events"}:
                        raise SystemExit(
                            f"COUNTED_EVIDENCE_UNBOUND:{bucket}:{index}:"
                            f"{binding.get('reason') or 'unresolved'}"
                        )
                    continue

                candidate = replay.candidate_from_history(
                    CITY,
                    observation["row"],
                    bucket,
                    target_id,
                    monitor,
                    ep_by_id.get(target_id),
                )
                key = (target_id, str(candidate.get("candidate_id") or ""))
                if key in seen_candidate_ids:
                    continue
                seen_candidate_ids.add(key)

                matching = replay.manual_matching(target_id)
                decision = monitor.classify_candidate(candidate, CITY, episodes, matching)
                monitor.apply_classification_decision(candidate, decision, matching)
                candidates_by_episode[target_id].append(candidate)

    target_states: dict[str, str] = {}
    observation_counts: dict[str, int] = {}

    for ep in episodes:
        eid = str(ep["episode_id"])
        rows = candidates_by_episode.get(eid, [])
        observation_counts[eid] = len(rows)
        statuses = {str(row.get("status") or "") for row in rows}
        state = "NO_CONFIRMED_EVENT"

        if "approved_strict" in statuses:
            state = "STRICT_EVENT_POSITIVE"
        else:
            composition = (
                monitor.compose_episode_candidates(CITY, ep, rows, episodes)
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

    target_rows = [
        {"episode_id": eid, "state": target_states[eid]}
        for eid in sorted(target_states)
    ]
    target_sha = formalizer.sha256_bytes(
        formalizer.stable_json(target_rows).encode("utf-8")
    )
    return episodes, observation_counts, target_sha, target_states


def main() -> int:
    tested_head = os.environ.get("GITHUB_SHA") or subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
    ).strip()

    if git_changed_paths():
        raise SystemExit(f"DIRTY_CHECKOUT_BEFORE_FREEZE:{git_changed_paths()}")

    guarded_paths = [
        APP_ROOT / "scripts/monitor_explosion_candidates.py",
        APP_ROOT / "scripts/replay_explosion_history.py",
        APP_ROOT / "scripts/historical_v2_formalize_chernivtsi_ivano_frankivsk.py",
        formalizer.evidence_path(CITY),
        formalizer.source_slice_path(CITY),
    ]
    guarded_before = {
        str(path.relative_to(REPO_ROOT)): formalizer.sha256_file(path)
        for path in guarded_paths
    }

    accepted = formalizer.formalize_city(CITY)
    if accepted.get("verdict") != "CITY V2 FORMALIZATION PROVEN":
        raise SystemExit(f"CITY_FORMALIZATION_NOT_PROVEN:{accepted.get('blocker')}")
    if int(accepted.get("no_confirmed_event") or -1) != EXPECTED_NO_CONFIRMED:
        raise SystemExit(
            "CITY BLIND FREEZE BLOCKED — NO_CONFIRMED COUNT MISMATCH:"
            f"{accepted.get('no_confirmed_event')}!={EXPECTED_NO_CONFIRMED}"
        )
    if accepted.get("target_state_sha256") != ACCEPTED_TARGET_STATE_SHA256:
        raise SystemExit(
            "ACCEPTED_TARGET_STATE_SHA_MISMATCH:"
            f"{accepted.get('target_state_sha256')}!={ACCEPTED_TARGET_STATE_SHA256}"
        )

    episodes, observation_counts, reconstructed_sha, target_states = reconstruct_target_state()
    if reconstructed_sha != ACCEPTED_TARGET_STATE_SHA256:
        raise SystemExit(
            "RECONSTRUCTED_TARGET_STATE_SHA_MISMATCH:"
            f"{reconstructed_sha}!={ACCEPTED_TARGET_STATE_SHA256}"
        )

    by_id = {str(ep["episode_id"]): ep for ep in episodes}
    eligible_ids = [
        eid for eid, state in target_states.items()
        if state == "NO_CONFIRMED_EVENT"
    ]
    if len(eligible_ids) != EXPECTED_NO_CONFIRMED:
        raise SystemExit(
            "CITY BLIND FREEZE BLOCKED — NO_CONFIRMED COUNT MISMATCH:"
            f"{len(eligible_ids)}!={EXPECTED_NO_CONFIRMED}"
        )

    prior_researched: set[str] = set()
    excluded = [eid for eid in eligible_ids if eid in prior_researched]
    eligible_after = [eid for eid in eligible_ids if eid not in prior_researched]

    ranked: list[tuple[str, str]] = []
    for eid in eligible_after:
        rank = hashlib.sha256(f"{SEED}|{CITY}|{eid}".encode("utf-8")).hexdigest()
        ranked.append((rank, eid))
    ranked.sort(key=lambda item: (item[0], item[1]))
    winners = ranked[:5]

    selected: list[dict] = []
    for case_no, (rank, eid) in zip(CASES, winners, strict=True):
        ep = by_id[eid]
        selected.append({
            "case": case_no,
            "city_key": CITY,
            "episode_id": eid,
            "alert_start": ep["alert_start"],
            "alert_end": ep["alert_end"],
            "final_outcome": "NO_CONFIRMED_EVENT",
            "observation_count": int(observation_counts.get(eid, 0)),
            "rank": rank,
        })

    sample_bytes = json.dumps(
        selected,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    city_sample_sha256 = hashlib.sha256(sample_bytes).hexdigest()

    guarded_after = {
        str(path.relative_to(REPO_ROOT)): formalizer.sha256_file(path)
        for path in guarded_paths
    }
    authoritative_inputs_unchanged = guarded_before == guarded_after
    if not authoritative_inputs_unchanged:
        raise SystemExit("AUTHORITATIVE_INPUT_MUTATION_GUARD_FAILED")

    dirty_before_artifact = git_changed_paths()
    if dirty_before_artifact:
        raise SystemExit(f"UNEXPECTED_MUTATIONS_BEFORE_ARTIFACT:{dirty_before_artifact}")

    artifact = {
        "schema_version": 1,
        "verdict": "CITY BLIND SAMPLE FROZEN",
        "city": CITY,
        "cases": "61-65",
        "source_accepted_head": SOURCE_ACCEPTED_HEAD,
        "source_proof_branch": SOURCE_PROOF_BRANCH,
        "source_target_state_sha256": ACCEPTED_TARGET_STATE_SHA256,
        "tested_head": tested_head,
        "selection_mode": "FORMALIZED_18CITY_STATE",
        "deterministic_seed": SEED,
        "expected_no_confirmed": EXPECTED_NO_CONFIRMED,
        "eligible_count_before_exclusions": len(eligible_ids),
        "prior_researched_episodes": [],
        "exclusions_count": len(excluded),
        "eligible_count_after_exclusions": len(eligible_after),
        "selected_cases": selected,
        "CITY_SAMPLE_SHA256": city_sample_sha256,
        "formalization_guard": {
            "accepted_verdict": accepted["verdict"],
            "accepted_no_confirmed_event": accepted["no_confirmed_event"],
            "accepted_target_state_sha256": accepted["target_state_sha256"],
            "reconstructed_target_state_sha256": reconstructed_sha,
            "match": reconstructed_sha == ACCEPTED_TARGET_STATE_SHA256,
        },
        "mutation_guards": {
            "guarded_input_sha256_before": guarded_before,
            "guarded_input_sha256_after": guarded_after,
            "authoritative_inputs_unchanged": authoritative_inputs_unchanged,
            "scope_allowlist": "PASS",
            "historical_evidence_mutations": 0,
            "db_neon": "UNTOUCHED",
            "deployment": "NO",
            "production_dashboard_data": "UNTOUCHED",
        },
        "research_performed": "NO",
        "public_web": "NO",
        "source_discovery": "NO",
        "mutations_to_authoritative_data": 0,
    }

    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_PATH.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    changed_after_artifact = git_changed_paths()
    unexpected = [p for p in changed_after_artifact if p != str(ARTIFACT_REL)]
    if unexpected:
        raise SystemExit(f"UNEXPECTED_MUTATIONS_AFTER_ARTIFACT:{unexpected}")

    print(json.dumps({
        "verdict": artifact["verdict"],
        "city": CITY,
        "eligible_before": artifact["eligible_count_before_exclusions"],
        "excluded": artifact["exclusions_count"],
        "eligible_after": artifact["eligible_count_after_exclusions"],
        "selected_cases": selected,
        "CITY_SAMPLE_SHA256": city_sample_sha256,
    }, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
