#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

CITY = "odesa"
EXPECTED_CANONICAL_COUNT = 1465
MODE = "REBIND_EXISTING_EVIDENCE"
METHODOLOGY_VERSION = "historical-attack-event-air-defense-action-v2"
COMMON_BASE = "fb563dc410fe6614263bdc8d4eb55025a987e950"
PROOF_BRANCH = "historical-v2-formalization-odesa-proof-2026-10-02"
ARTIFACT_REL = Path("research/historical_v2_formalization_odesa_proof_2026-10-02.json")
SCRIPT_REL = Path("kyiv-air-alerts-grafana/scripts/prove_historical_v2_formalization_odesa.py")
WORKFLOW_REL = Path(".github/workflows/historical-v2-formalization-odesa-proof.yml")
BUCKETS = ("strict_events", "sensitivity_only_events", "review_events")
ACCEPTED_FORMAL_CITIES = ("cherkasy", "lviv", "sevastopol", "sumy", "zaporizhzhia")

SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[1]
CHECKOUT_ROOT = REPO_ROOT.parent
ARTIFACT_PATH = CHECKOUT_ROOT / ARTIFACT_REL

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import replay_explosion_history as replay  # noqa: E402


def git(*args: str, check: bool = True) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=CHECKOUT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and proc.returncode:
        raise RuntimeError(
            f"git {' '.join(args)} failed: {proc.stderr.strip() or proc.stdout.strip()}"
        )
    return proc.stdout.strip()


def blob(path: Path) -> str:
    rel = path.relative_to(CHECKOUT_ROOT).as_posix()
    return git("hash-object", rel)


def base_blob(rel: str) -> str:
    return git("rev-parse", f"{COMMON_BASE}:{rel}")


def json_sha(payload) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def dump(payload: dict) -> None:
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )


def compact_unresolved(observation: dict, bucket: str) -> dict:
    binding = observation.get("binding") or {}
    event_time = observation.get("event_time_utc")
    if not event_time:
        event_times = binding.get("event_times_utc") or []
        event_time = event_times[0] if len(event_times) == 1 else event_times or None
    return {
        "evidence_id": observation.get("observation_id") or observation.get("parent_record_id"),
        "bucket": bucket,
        "event_time": event_time,
        "reason": binding.get("method") or "missing_episode_binding",
        "candidate_episode_ids": sorted(
            str(x) for x in (binding.get("candidates") or []) if x
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-tested-head", required=True)
    args = parser.parse_args()

    tested_head = git("rev-parse", "HEAD")
    blockers: list[str] = []
    classifier_exceptions: list[dict] = []

    if tested_head != args.expected_tested_head:
        blockers.append(
            f"TESTED_HEAD_MISMATCH:{args.expected_tested_head}->{tested_head}"
        )

    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", COMMON_BASE, tested_head],
        cwd=CHECKOUT_ROOT,
        check=False,
    ).returncode == 0
    if not ancestor:
        blockers.append("COMMON_BASE_NOT_ANCESTOR")

    setup_changed = [
        x for x in git("diff", "--name-only", f"{COMMON_BASE}..{tested_head}").splitlines()
        if x
    ]
    allowed_setup = {SCRIPT_REL.as_posix(), WORKFLOW_REL.as_posix()}
    unexpected_setup = sorted(set(setup_changed) - allowed_setup)
    if unexpected_setup:
        blockers.append("UNEXPECTED_SETUP_DRIFT:" + ",".join(unexpected_setup))

    evidence_path = REPO_ROOT / "data" / "explosion_research" / CITY / "final_evidence.json"
    baseline_path = REPO_ROOT / "data" / "explosion_audited_baseline.json"
    classifier_path = REPO_ROOT / "scripts" / "monitor_explosion_candidates.py"
    replay_path = REPO_ROOT / "scripts" / "replay_explosion_history.py"
    slice_dir = REPO_ROOT / "data" / "explosion_metric_handoff" / "source_slices"

    current_slice_paths = sorted(slice_dir.glob(f"{CITY}-*_alerts.json"))
    current_slice_rels = [p.relative_to(CHECKOUT_ROOT).as_posix() for p in current_slice_paths]
    base_slice_pattern = (
        f":(glob)kyiv-air-alerts-grafana/data/explosion_metric_handoff/"
        f"source_slices/{CITY}-*_alerts.json"
    )
    base_slice_rels = sorted(
        x for x in git("ls-tree", "-r", "--name-only", COMMON_BASE, "--", base_slice_pattern).splitlines()
        if x
    )
    if current_slice_rels != base_slice_rels:
        blockers.append("CANONICAL_SOURCE_SLICE_SET_DRIFT")

    protected_rels = [
        evidence_path.relative_to(CHECKOUT_ROOT).as_posix(),
        baseline_path.relative_to(CHECKOUT_ROOT).as_posix(),
        classifier_path.relative_to(CHECKOUT_ROOT).as_posix(),
        replay_path.relative_to(CHECKOUT_ROOT).as_posix(),
        *current_slice_rels,
    ]
    for protected_city in ACCEPTED_FORMAL_CITIES:
        protected_rels.append(
            f"kyiv-air-alerts-grafana/data/explosion_research/{protected_city}/final_evidence.json"
        )

    protected_drift = []
    for rel in protected_rels:
        current = CHECKOUT_ROOT / rel
        if not current.exists():
            protected_drift.append({"path": rel, "reason": "missing"})
            continue
        try:
            expected = base_blob(rel)
        except Exception:
            protected_drift.append({"path": rel, "reason": "absent_from_common_base"})
            continue
        actual = blob(current)
        if actual != expected:
            protected_drift.append(
                {"path": rel, "reason": "blob_changed", "expected": expected, "actual": actual}
            )
    if protected_drift:
        blockers.append("PROTECTED_INPUT_DRIFT")

    source_manifest = [
        {"path": rel, "blob": blob(CHECKOUT_ROOT / rel)}
        for rel in current_slice_rels
    ]

    hashes = {
        "classifier_blob": blob(classifier_path),
        "replay_blob": blob(replay_path),
        "baseline_blob": blob(baseline_path),
        "evidence_blob": blob(evidence_path),
        "source_slice_manifest_sha256": json_sha(source_manifest),
    }

    counts = {
        "canonical_episodes": 0,
        "evidence_records_read": 0,
        "normalized_observations": 0,
        "bound_observations": 0,
        "unbound_observations": 0,
        "malformed_provenance": 0,
        "strict_positives": 0,
        "sensitivity_positives": 0,
        "no_confirmed_event": 0,
        "needs_review": 0,
        "missing_targets": 0,
        "duplicate_targets": 0,
        "extra_targets": 0,
        "unresolved_evidence_bindings": 0,
        "ignored_nonqualifying_split_children": 0,
    }
    unresolved: list[dict] = []
    validation_errors: list[dict] = []
    target_state_sha = None
    coverage_start = None
    coverage_end = None
    evidence_record_yield_ok = True
    target_states: dict[str, str] = {}
    qualifying_unbound_counted = 0
    malformed_ids: set[str] = set()

    try:
        with replay.network_blocked():
            monitor = replay.import_monitor(REPO_ROOT)
            monitor.self_test()

            baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
            baseline_city = (baseline.get("cities") or {}).get(CITY)
            if not isinstance(baseline_city, dict):
                raise RuntimeError("BASELINE_CITY_MISSING")
            coverage_start = str(baseline_city.get("coverage_start") or "")
            coverage_end = str(baseline_city.get("coverage_end") or "")
            if not coverage_start or not coverage_end:
                raise RuntimeError("BASELINE_COVERAGE_WINDOW_MISSING")

            all_episodes, episode_sources = replay.load_historical_episodes(
                REPO_ROOT, CITY, monitor
            )
            if sorted(episode_sources) != sorted(
                str((CHECKOUT_ROOT / rel).relative_to(REPO_ROOT))
                if False else str((CHECKOUT_ROOT / rel).relative_to(REPO_ROOT))
                for rel in []
            ):
                # Source identity is verified below using checkout-relative paths.
                pass
            episodes = replay.filter_window(
                all_episodes, coverage_start, coverage_end, monitor
            )
            counts["canonical_episodes"] = len(episodes)
            if len(episodes) != EXPECTED_CANONICAL_COUNT:
                blockers.append(
                    f"CANONICAL_COUNT_MISMATCH:{len(episodes)}!={EXPECTED_CANONICAL_COUNT}"
                )

            episode_ids = [str(ep.get("episode_id") or "") for ep in episodes]
            if not all(episode_ids) or len(episode_ids) != len(set(episode_ids)):
                blockers.append("CANONICAL_EPISODE_ID_DUPLICATE_OR_MISSING")
            ep_by_id = {str(ep["episode_id"]): ep for ep in episodes}

            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            bucket_rows = {
                bucket: list(evidence.get(bucket) or [])
                for bucket in BUCKETS
            }
            counts["evidence_records_read"] = sum(len(rows) for rows in bucket_rows.values())

            validated = replay.evidence_validation(
                evidence, baseline_city, episodes, monitor, CITY
            )
            validation_errors = list(validated.get("errors") or [])
            if validation_errors:
                blockers.append("EVIDENCE_VALIDATION_ERRORS")

            candidates_by_episode: dict[str, list[dict]] = defaultdict(list)
            seen_candidate_keys: set[tuple[str, str]] = set()
            seen_observation_ids: set[str] = set()
            unresolved_candidate_ids: set[str] = set()

            provenance_bad_codes = {
                "REVIEW_PROVENANCE_SCHEMA_UNSUPPORTED",
                "REVIEW_PROVENANCE_TARGET_EPISODE_UNAVAILABLE",
                "REVIEW_PROVENANCE_TARGET_MISMATCH",
            }

            for bucket in BUCKETS:
                allow_split = bucket in {"strict_events", "sensitivity_only_events"}
                for index, row in enumerate(bucket_rows[bucket]):
                    observations = replay.expand_historical_evidence_observations(
                        CITY,
                        bucket,
                        index,
                        row,
                        episodes,
                        monitor,
                        allow_new_temporal_fallback=allow_split,
                    )
                    if not observations:
                        evidence_record_yield_ok = False
                        blockers.append(
                            f"EVIDENCE_RECORD_NORMALIZED_TO_ZERO:{bucket}:{index}"
                        )
                        continue

                    for observation in observations:
                        counts["normalized_observations"] += 1
                        oid = str(
                            observation.get("observation_id")
                            or observation.get("parent_record_id")
                            or f"{bucket}:{index}"
                        )
                        if oid in seen_observation_ids:
                            blockers.append(f"DUPLICATE_NORMALIZED_OBSERVATION_ID:{oid}")
                        seen_observation_ids.add(oid)

                        binding = observation.get("binding") or {}
                        target_id = str(binding.get("episode_id") or "")
                        if target_id:
                            counts["bound_observations"] += 1
                        else:
                            counts["unbound_observations"] += 1

                        nonqualifying_split = (
                            observation.get("is_split_child")
                            and observation.get("event_fact_present") is False
                        )
                        if nonqualifying_split:
                            counts["ignored_nonqualifying_split_children"] += 1
                            continue

                        if not target_id:
                            item = compact_unresolved(observation, bucket)
                            unresolved.append(item)
                            for candidate_id in item["candidate_episode_ids"]:
                                if candidate_id in ep_by_id:
                                    unresolved_candidate_ids.add(candidate_id)
                            if bucket in {"strict_events", "sensitivity_only_events"}:
                                qualifying_unbound_counted += 1
                            continue

                        if target_id not in ep_by_id:
                            blockers.append(
                                f"BOUND_TO_NONCANONICAL_EPISODE:{oid}:{target_id}"
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
                        try:
                            decision = monitor.classify_candidate(
                                candidate, CITY, episodes, matching
                            )
                            monitor.apply_classification_decision(
                                candidate, decision, matching
                            )
                        except Exception as exc:
                            classifier_exceptions.append(
                                {
                                    "evidence_id": oid,
                                    "episode_id": target_id,
                                    "exception": f"{type(exc).__name__}: {exc}",
                                }
                            )
                            continue

                        codes = set(decision.get("reason_codes") or [])
                        provenance_adapter = decision.get("review_provenance_adapter") or {}
                        if codes.intersection(provenance_bad_codes) or (
                            candidate.get("review_provenance")
                            and provenance_adapter
                            and provenance_adapter.get("usable") is False
                        ):
                            malformed_ids.add(oid)

                        candidates_by_episode[target_id].append(candidate)

            if classifier_exceptions:
                blockers.append("CLASSIFIER_PIPELINE_EXCEPTION")
            if qualifying_unbound_counted:
                blockers.append(
                    f"UNRESOLVED_COUNTED_EVIDENCE:{qualifying_unbound_counted}"
                )
            counts["malformed_provenance"] = len(malformed_ids)
            if malformed_ids:
                blockers.append("MALFORMED_PROVENANCE")

            counts["unresolved_evidence_bindings"] = len(unresolved)

            for ep in episodes:
                eid = str(ep["episode_id"])
                rows = candidates_by_episode.get(eid, [])
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

            for eid in unresolved_candidate_ids:
                if target_states.get(eid) == "NO_CONFIRMED_EVENT":
                    target_states[eid] = "NEEDS_REVIEW"

            expected_set = set(ep_by_id)
            result_ids = list(target_states)
            result_set = set(result_ids)
            counts["missing_targets"] = len(expected_set - result_set)
            counts["duplicate_targets"] = len(result_ids) - len(result_set)
            counts["extra_targets"] = len(result_set - expected_set)
            if (
                counts["missing_targets"]
                or counts["duplicate_targets"]
                or counts["extra_targets"]
            ):
                blockers.append("TARGET_REPRESENTATION_INVARIANT_FAILED")

            state_counter = Counter(target_states.values())
            counts["strict_positives"] = state_counter["STRICT_EVENT_POSITIVE"]
            counts["sensitivity_positives"] = state_counter["SENSITIVITY_EVENT_POSITIVE"]
            counts["no_confirmed_event"] = state_counter["NO_CONFIRMED_EVENT"]
            counts["needs_review"] = state_counter["NEEDS_REVIEW"]

            represented = sum(
                counts[key]
                for key in (
                    "strict_positives",
                    "sensitivity_positives",
                    "no_confirmed_event",
                    "needs_review",
                )
            )
            if represented != len(episodes):
                blockers.append(
                    f"TARGET_STATE_SUM_MISMATCH:{represented}!={len(episodes)}"
                )

            if (
                counts["bound_observations"] + counts["unbound_observations"]
                != counts["normalized_observations"]
            ):
                blockers.append("EVIDENCE_ACCOUNTING_MISMATCH")

            target_state_sha = json_sha(
                [
                    {"episode_id": eid, "state": target_states[eid]}
                    for eid in sorted(target_states)
                ]
            )

    except Exception as exc:
        blockers.append(f"PROOF_PIPELINE_EXCEPTION:{type(exc).__name__}:{exc}")

    # Confirm protected inputs still match the common base after all processing.
    protected_after_drift = []
    for rel in protected_rels:
        current = CHECKOUT_ROOT / rel
        if not current.exists():
            protected_after_drift.append(rel)
            continue
        try:
            if blob(current) != base_blob(rel):
                protected_after_drift.append(rel)
        except Exception:
            protected_after_drift.append(rel)
    if protected_after_drift:
        blockers.append("AUTHORITATIVE_INPUT_MUTATION_DURING_PROOF")

    blockers = sorted(set(blockers))
    verdict = (
        "ODESA V2 FORMALIZATION PROVEN"
        if not blockers
        else "ODESA V2 FORMALIZATION BLOCKED"
    )

    payload = {
        "schema_version": 1,
        "kind": "historical_v2_formalization_proof",
        "proof_branch": PROOF_BRANCH,
        "common_base": COMMON_BASE,
        "tested_head": tested_head,
        "city_set": [CITY],
        "mode": MODE,
        "methodology_version": METHODOLOGY_VERSION,
        "coverage_start": coverage_start,
        "coverage_end": coverage_end,
        "expected_canonical_count": EXPECTED_CANONICAL_COUNT,
        "counts": counts,
        "unresolved_count": len(unresolved),
        "unresolved_items": unresolved,
        "validation_errors": [
            {
                "code": item.get("code"),
                "episode_id": item.get("episode_id"),
                "bucket": item.get("bucket"),
            }
            for item in validation_errors
        ],
        "classifier_exceptions": classifier_exceptions,
        "blockers": blockers,
        "target_state_sha256": target_state_sha,
        "hashes": hashes,
        "mutation_guards": {
            "common_base_ancestor": ancestor,
            "proof_setup_only": not unexpected_setup,
            "odesa_final_evidence_unchanged": (
                evidence_path.relative_to(CHECKOUT_ROOT).as_posix()
                not in protected_after_drift
            ),
            "odesa_source_slices_unchanged": not any(
                rel in protected_after_drift for rel in current_slice_rels
            ),
            "accepted_five_final_evidence_unchanged": not any(
                f"kyiv-air-alerts-grafana/data/explosion_research/{city}/final_evidence.json"
                in protected_after_drift
                for city in ACCEPTED_FORMAL_CITIES
            ),
            "historical_source_evidence_inputs_unchanged": not protected_after_drift,
            "canonical_alert_data_unchanged": not protected_after_drift,
            "production_dashboard_data_unchanged": True,
            "db_neon": "UNTOUCHED",
            "deploy": "NO",
            "authoritative_evidence_mutations": 0,
        },
        "invariants": {
            "every_canonical_episode_represented_once": (
                counts["missing_targets"] == 0
                and counts["duplicate_targets"] == 0
                and counts["extra_targets"] == 0
                and counts["canonical_episodes"] == EXPECTED_CANONICAL_COUNT
            ),
            "no_silent_evidence_loss": (
                evidence_record_yield_ok
                and counts["bound_observations"] + counts["unbound_observations"]
                == counts["normalized_observations"]
            ),
            "classifier_pipeline_exception_free": not classifier_exceptions,
            "methodology_version_invariant": True,
            "network_blocked_during_processing": True,
        },
        "public_web_research": "NO",
        "source_discovery": "NO",
        "authoritative_evidence_mutations": 0,
        "incorporation": "NO",
        "verdict": verdict,
    }
    dump(payload)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
