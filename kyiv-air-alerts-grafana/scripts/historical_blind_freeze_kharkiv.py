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

REPO_ROOT = Path(os.environ.get("GITHUB_WORKSPACE", ".")).resolve()
APP_ROOT = REPO_ROOT / "kyiv-air-alerts-grafana"
SCRIPT_DIR = APP_ROOT / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import historical_v2_formalization_existing_evidence as formalizer

CITY = "kharkiv"
CASES = range(66, 71)
EXPECTED_CANONICAL = 3565
EXPECTED_NO_CONFIRMED = 3250
SEED = "20261002-23city-blind-v1"
SOURCE_ACCEPTED_HEAD = "79397290b0d51ca49bf15d6e5890ffc3ce631ce3"
SOURCE_PROOF_BRANCH = "historical-v2-formalization-kharkiv-kherson-proof-2026-10-02"
ACCEPTED_TARGET_STATE_SHA256 = "2400891dd85dbebdfdf347f88c178f43780d7ccfe814701b069b4593e06f491b"
PROOF_BRANCH = "historical-blind-freeze-kharkiv-proof-2026-10-02"
SCRIPT_REL = "kyiv-air-alerts-grafana/scripts/historical_blind_freeze_kharkiv.py"
WORKFLOW_REL = ".github/workflows/historical-blind-freeze-kharkiv-proof.yml"
ARTIFACT_REL = Path("research/historical_blind_freeze_kharkiv_2026-10-02.json")
ARTIFACT_PATH = REPO_ROOT / ARTIFACT_REL
ACCEPTED_ARTIFACT = REPO_ROOT / "research/historical_v2_formalization_kharkiv_kherson_proof_2026-10-02.json"


def git(*args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(REPO_ROOT), *args],
        text=True,
    ).strip()


def git_changed_paths() -> list[str]:
    rows = subprocess.check_output(
        ["git", "-C", str(REPO_ROOT), "status", "--porcelain", "--untracked-files=all"],
        text=True,
    ).splitlines()
    out: list[str] = []
    for row in rows:
        if not row.strip():
            continue
        path = row[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        out.append(path)
    return out


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def guarded_paths() -> list[Path]:
    paths = [
        APP_ROOT / "scripts/monitor_explosion_candidates.py",
        APP_ROOT / "scripts/replay_explosion_history.py",
        APP_ROOT / "scripts/historical_v2_formalization_existing_evidence.py",
        APP_ROOT / "data/explosion_research/kharkiv/final_evidence.json",
    ]
    paths.extend(sorted(
        (APP_ROOT / "data/explosion_metric_handoff/source_slices").glob("kharkiv-*_alerts.json")
    ))
    return paths


def reconstruct_target_state(monitor) -> tuple[list[dict], dict[str, int], str, dict[str, str]]:
    replay = formalizer.replay

    episodes, _source_files = replay.load_historical_episodes(APP_ROOT, CITY, monitor)
    episodes = sorted(
        [dict(ep) for ep in episodes],
        key=lambda ep: (str(ep.get("alert_start") or ""), str(ep.get("episode_id") or "")),
    )
    if len(episodes) != EXPECTED_CANONICAL:
        raise SystemExit(f"CANONICAL_COUNT_MISMATCH:{len(episodes)}!={EXPECTED_CANONICAL}")

    episode_ids = [str(ep.get("episode_id") or "") for ep in episodes]
    if any(not eid for eid in episode_ids):
        raise SystemExit("CANONICAL_EPISODE_WITHOUT_ID")
    if len(set(episode_ids)) != len(episode_ids):
        raise SystemExit("DUPLICATE_CANONICAL_EPISODE_IDS")

    canonical_set = set(episode_ids)
    ep_by_id = {str(ep["episode_id"]): ep for ep in episodes}

    evidence_path = APP_ROOT / "data/explosion_research" / CITY / "final_evidence.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    if not isinstance(evidence, dict):
        raise SystemExit("EVIDENCE_NOT_OBJECT")

    candidates_by_episode: dict[str, list[dict]] = defaultdict(list)
    seen_candidate_keys: set[tuple[str, str]] = set()
    review_unresolved_candidates: set[str] = set()

    for bucket in formalizer.BUCKETS:
        rows = evidence.get(bucket) or []
        if not isinstance(rows, list):
            raise SystemExit(f"EVIDENCE_BUCKET_NOT_LIST:{bucket}")

        allow_split = bucket in formalizer.COUNTED_BUCKETS
        for index, original_row in enumerate(rows):
            if not isinstance(original_row, dict):
                raise SystemExit(f"NON_OBJECT_EVIDENCE_RECORD:{bucket}:{index}")

            rebound_row = formalizer.strip_persisted_binding(original_row)
            observations = replay.expand_historical_evidence_observations(
                CITY,
                bucket,
                index,
                rebound_row,
                episodes,
                monitor,
                allow_new_temporal_fallback=allow_split,
            )
            if not observations:
                raise SystemExit(f"NO_NORMALIZED_OBSERVATION:{bucket}:{index}")

            for observation in observations:
                if (
                    observation.get("is_split_child")
                    and observation.get("event_fact_present") is False
                ):
                    continue

                binding = dict(observation.get("binding") or {})
                target_id = str(binding.get("episode_id") or "")

                if not target_id or target_id not in canonical_set:
                    if bucket in formalizer.COUNTED_BUCKETS:
                        raise SystemExit(
                            f"COUNTED_EVIDENCE_UNBOUND:{bucket}:{index}:"
                            f"{binding.get('method') or 'unresolved'}"
                        )
                    review_unresolved_candidates.update(
                        str(eid)
                        for eid in (binding.get("candidates") or [])
                        if str(eid) in canonical_set
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
                if key in seen_candidate_keys:
                    continue
                seen_candidate_keys.add(key)

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

    for eid in review_unresolved_candidates:
        if target_states.get(eid) == "NO_CONFIRMED_EVENT":
            target_states[eid] = "NEEDS_REVIEW"

    target_rows = [
        {"episode_id": eid, "state": target_states[eid]}
        for eid in sorted(target_states)
    ]
    target_sha = formalizer.canonical_state_sha(CITY, target_rows)
    return episodes, observation_counts, target_sha, target_states


def main() -> int:
    actual_checkout_head = git("rev-parse", "HEAD")
    if actual_checkout_head != SOURCE_ACCEPTED_HEAD:
        raise SystemExit(
            f"EXACT_ACCEPTED_HEAD_REQUIRED:{actual_checkout_head}!={SOURCE_ACCEPTED_HEAD}"
        )

    proof_execution_head = os.environ.get("GITHUB_SHA") or SOURCE_ACCEPTED_HEAD
    proof_diff = sorted(
        p for p in git("diff", "--name-only", f"{SOURCE_ACCEPTED_HEAD}..{proof_execution_head}").splitlines()
        if p
    )
    allowed_proof_diff = sorted([SCRIPT_REL, WORKFLOW_REL])
    if proof_diff != allowed_proof_diff:
        raise SystemExit(
            f"PROOF_SCOPE_DIFF_GUARD_FAILED:{proof_diff}!={allowed_proof_diff}"
        )

    if git_changed_paths():
        raise SystemExit(f"DIRTY_CHECKOUT_BEFORE_FREEZE:{git_changed_paths()}")

    accepted_doc = json.loads(ACCEPTED_ARTIFACT.read_text(encoding="utf-8"))
    accepted_city = (accepted_doc.get("cities") or {}).get(CITY) or {}
    if accepted_city.get("verdict") != "CITY V2 FORMALIZATION PROVEN":
        raise SystemExit("ACCEPTED_CITY_FORMALIZATION_NOT_PROVEN")
    if int(accepted_city.get("no_confirmed_event") or -1) != EXPECTED_NO_CONFIRMED:
        raise SystemExit(
            "CITY BLIND FREEZE BLOCKED — NO_CONFIRMED COUNT MISMATCH:"
            f"{accepted_city.get('no_confirmed_event')}!={EXPECTED_NO_CONFIRMED}"
        )
    if accepted_city.get("target_state_sha256") != ACCEPTED_TARGET_STATE_SHA256:
        raise SystemExit(
            "ACCEPTED_TARGET_STATE_SHA_MISMATCH:"
            f"{accepted_city.get('target_state_sha256')}!={ACCEPTED_TARGET_STATE_SHA256}"
        )

    guard_files = guarded_paths()
    guarded_before = {
        str(path.relative_to(REPO_ROOT)): sha256_file(path)
        for path in guard_files
    }

    with formalizer.replay.network_blocked():
        monitor = formalizer.replay.import_monitor(APP_ROOT)
        monitor.self_test()

        accepted = formalizer.formalize_city(
            CITY,
            EXPECTED_CANONICAL,
            monitor,
            SOURCE_ACCEPTED_HEAD,
        )
        if accepted.get("verdict") != "CITY V2 FORMALIZATION PROVEN":
            raise SystemExit(f"CITY_FORMALIZATION_NOT_PROVEN:{accepted.get('blockers')}")
        if int(accepted.get("no_confirmed_event") or -1) != EXPECTED_NO_CONFIRMED:
            raise SystemExit(
                "CITY BLIND FREEZE BLOCKED — NO_CONFIRMED COUNT MISMATCH:"
                f"{accepted.get('no_confirmed_event')}!={EXPECTED_NO_CONFIRMED}"
            )
        if accepted.get("target_state_sha256") != ACCEPTED_TARGET_STATE_SHA256:
            raise SystemExit(
                "FORMALIZER_TARGET_STATE_SHA_MISMATCH:"
                f"{accepted.get('target_state_sha256')}!={ACCEPTED_TARGET_STATE_SHA256}"
            )

        episodes, observation_counts, reconstructed_sha, target_states = reconstruct_target_state(monitor)

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
    if len(winners) != 5:
        raise SystemExit(f"INSUFFICIENT_ELIGIBLE_EPISODES:{len(winners)}")

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
        str(path.relative_to(REPO_ROOT)): sha256_file(path)
        for path in guard_files
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
        "cases": "66-70",
        "source_accepted_head": SOURCE_ACCEPTED_HEAD,
        "source_proof_branch": SOURCE_PROOF_BRANCH,
        "source_target_state_sha256": ACCEPTED_TARGET_STATE_SHA256,
        "proof_branch": PROOF_BRANCH,
        "proof_execution_head": proof_execution_head,
        "reconstruction_checkout_head": actual_checkout_head,
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
            "accepted_artifact_verdict": accepted_city["verdict"],
            "accepted_artifact_no_confirmed_event": accepted_city["no_confirmed_event"],
            "accepted_artifact_target_state_sha256": accepted_city["target_state_sha256"],
            "runtime_formalizer_verdict": accepted["verdict"],
            "runtime_formalizer_no_confirmed_event": accepted["no_confirmed_event"],
            "runtime_formalizer_target_state_sha256": accepted["target_state_sha256"],
            "reconstructed_target_state_sha256": reconstructed_sha,
            "match": (
                accepted["target_state_sha256"]
                == reconstructed_sha
                == ACCEPTED_TARGET_STATE_SHA256
            ),
        },
        "mutation_guards": {
            "proof_diff_files": proof_diff,
            "proof_scope_allowlist": "PASS",
            "guarded_input_sha256_before": guarded_before,
            "guarded_input_sha256_after": guarded_after,
            "authoritative_inputs_unchanged": authoritative_inputs_unchanged,
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
    if changed_after_artifact != [str(ARTIFACT_REL)]:
        raise SystemExit(f"UNEXPECTED_MUTATIONS_AFTER_ARTIFACT:{changed_after_artifact}")

    print(json.dumps({
        "verdict": artifact["verdict"],
        "city": CITY,
        "source_accepted_head": SOURCE_ACCEPTED_HEAD,
        "reconstruction_checkout_head": actual_checkout_head,
        "eligible_before": artifact["eligible_count_before_exclusions"],
        "excluded": artifact["exclusions_count"],
        "eligible_after": artifact["eligible_count_after_exclusions"],
        "selected_cases": selected,
        "CITY_SAMPLE_SHA256": city_sample_sha256,
        "formalization_match": artifact["formalization_guard"]["match"],
    }, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
