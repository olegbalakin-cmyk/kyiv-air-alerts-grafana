#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
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

import monitor_explosion_candidates as monitor
import replay_explosion_history as replay

CITY_SET = ("ternopil", "uzhhorod")
EXPECTED_CANONICAL_COUNTS = {"ternopil": 125, "uzhhorod": 92}
METHODOLOGY_VERSION = "historical-attack-event-air-defense-action-v2"
NORMALIZATION_VERSION = "historical-attack-event-observation-v2"
COMMON_BASE = "fb563dc410fe6614263bdc8d4eb55025a987e950"
ARTIFACT_REL = Path("research/historical_v2_formalization_ternopil_uzhhorod_proof_2026-10-02.json")
ARTIFACT_PATH = REPO_ROOT / ARTIFACT_REL
BUCKETS = ("strict_events", "sensitivity_only_events", "review_events")


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def git_changed_paths() -> list[str]:
    proc = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    out = []
    for line in proc.stdout.splitlines():
        if not line.strip():
            continue
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        out.append(path)
    return out


def source_slice_path(city: str) -> Path:
    return APP_ROOT / "data/explosion_metric_handoff/source_slices" / f"{city}-historical-recovery_alerts.json"


def evidence_path(city: str) -> Path:
    return APP_ROOT / "data/explosion_research" / city / "final_evidence.json"


def compact_unresolved(
    *,
    row: dict,
    observation: dict,
    reason: str,
    candidates: list[str] | None = None,
) -> dict:
    evidence_id = (
        observation.get("observation_id")
        or observation.get("parent_record_id")
        or row.get("evidence_id")
        or row.get("id")
        or row.get("source_url")
        or sha256_bytes(stable_json(row).encode("utf-8"))[:24]
    )
    event_time = (
        observation.get("event_time_utc")
        or row.get("event_time")
        or row.get("event_time_kyiv")
        or row.get("event_time_local")
    )
    return {
        "evidence_id": str(evidence_id),
        "event_time": event_time,
        "reason": reason,
        "candidate_episode_ids": sorted({str(x) for x in (candidates or []) if x}),
    }


def provenance_is_malformed(candidate: dict, row: dict) -> bool:
    provenance = candidate.get("review_provenance")
    if isinstance(provenance, dict) and provenance:
        return False
    if any(str(candidate.get(k) or "").strip() for k in ("url", "resolved_url", "source", "publisher")):
        return False
    if any(str(row.get(k) or "").strip() for k in ("source_url", "source", "publisher", "url")):
        return False
    return True


def formalize_city(city: str) -> dict:
    ev_path = evidence_path(city)
    canonical_path = source_slice_path(city)
    blockers: list[str] = []

    if not ev_path.exists():
        blockers.append("FINAL_EVIDENCE_MISSING")
    if not canonical_path.exists():
        blockers.append("CANONICAL_SOURCE_SLICE_MISSING")
    if blockers:
        return {
            "city_key": city,
            "verdict": "CITY V2 FORMALIZATION BLOCKED",
            "blocker": ";".join(blockers),
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
            "unresolved_items": [],
            "target_state_sha256": None,
            "canonical_source_files": [],
        }

    # Resolve the canonical alert universe exactly the same way as the accepted
    # historical replay path: committed source slices only, no network.
    episodes, source_files = replay.load_historical_episodes(APP_ROOT, city, monitor)
    episodes = sorted(
        [dict(ep) for ep in episodes],
        key=lambda ep: (str(ep.get("alert_start") or ""), str(ep.get("episode_id") or "")),
    )
    episode_ids = [str(ep.get("episode_id") or "") for ep in episodes if ep.get("episode_id")]
    canonical_set = set(episode_ids)
    ep_by_id = {str(ep["episode_id"]): ep for ep in episodes}
    if len(episodes) != EXPECTED_CANONICAL_COUNTS[city]:
        blockers.append(f"CANONICAL_COUNT_MISMATCH:{len(episodes)}!={EXPECTED_CANONICAL_COUNTS[city]}")
    if len(episode_ids) != len(canonical_set):
        blockers.append("CANONICAL_EPISODE_ID_DUPLICATE")

    evidence = load_json(ev_path)
    if not isinstance(evidence, dict):
        blockers.append("FINAL_EVIDENCE_SCHEMA_NOT_OBJECT")
        evidence = {}

    evidence_records_read = sum(
        len(evidence.get(bucket) or [])
        for bucket in BUCKETS
        if isinstance(evidence.get(bucket) or [], list)
    )
    if evidence_records_read == 0:
        blockers.append("NO_EVIDENCE_RECORDS_EXTRACTED")

    candidates_by_episode: dict[str, list[dict]] = defaultdict(list)
    unresolved: list[dict] = []
    normalized_observations = 0
    bound_observations = 0
    unbound_observations = 0
    malformed_provenance = 0
    classifier_exceptions = 0
    counted_evidence_unbound = 0
    silently_unhandled = 0
    seen_candidate_ids: set[tuple[str, str]] = set()

    for bucket in BUCKETS:
        rows = evidence.get(bucket) or []
        if not isinstance(rows, list):
            blockers.append(f"EVIDENCE_BUCKET_NOT_LIST:{bucket}")
            continue
        allow_split = bucket in {"strict_events", "sensitivity_only_events"}
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                silently_unhandled += 1
                unresolved.append({
                    "evidence_id": f"{bucket}:{index}",
                    "event_time": None,
                    "reason": "non_object_evidence_record",
                    "candidate_episode_ids": [],
                })
                continue
            try:
                observations = replay.expand_historical_evidence_observations(
                    city,
                    bucket,
                    index,
                    row,
                    episodes,
                    monitor,
                    allow_new_temporal_fallback=allow_split,
                )
            except Exception as exc:
                classifier_exceptions += 1
                unresolved.append({
                    "evidence_id": str(row.get("id") or row.get("source_url") or f"{bucket}:{index}"),
                    "event_time": row.get("event_time"),
                    "reason": f"normalization_exception:{type(exc).__name__}",
                    "candidate_episode_ids": [],
                })
                continue

            if not observations:
                silently_unhandled += 1
                unresolved.append({
                    "evidence_id": str(row.get("id") or row.get("source_url") or f"{bucket}:{index}"),
                    "event_time": row.get("event_time"),
                    "reason": "zero_normalized_observations",
                    "candidate_episode_ids": [],
                })
                continue

            for observation in observations:
                normalized_observations += 1
                binding = observation.get("binding") or {}
                candidate_ids = [str(x) for x in (binding.get("candidates") or []) if x]

                # Split children explicitly marked as not containing an event are
                # mechanically preserved but do not classify any target.
                if observation.get("is_split_child") and observation.get("event_fact_present") is False:
                    continue

                target_id = str(binding.get("episode_id") or "")
                if not target_id or target_id not in canonical_set:
                    unbound_observations += 1
                    if bucket in {"strict_events", "sensitivity_only_events"}:
                        counted_evidence_unbound += 1
                    unresolved.append(
                        compact_unresolved(
                            row=row,
                            observation=observation,
                            reason=str(binding.get("reason") or "unresolved_evidence_binding"),
                            candidates=candidate_ids,
                        )
                    )
                    continue

                bound_observations += 1
                try:
                    candidate = replay.candidate_from_history(
                        city,
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
                    if provenance_is_malformed(candidate, row):
                        malformed_provenance += 1
                    matching = replay.manual_matching(target_id)
                    decision = monitor.classify_candidate(candidate, city, episodes, matching)
                    monitor.apply_classification_decision(candidate, decision, matching)
                    candidates_by_episode[target_id].append(candidate)
                except Exception as exc:
                    classifier_exceptions += 1
                    unresolved.append(
                        compact_unresolved(
                            row=row,
                            observation=observation,
                            reason=f"classifier_exception:{type(exc).__name__}",
                            candidates=[target_id],
                        )
                    )

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
                monitor.compose_episode_candidates(city, ep, rows, episodes)
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

    missing_targets = len(canonical_set - set(target_states))
    extra_targets = len(set(target_states) - canonical_set)
    duplicate_targets = len(target_states) - len(set(target_states))

    if counted_evidence_unbound:
        blockers.append(f"UNBOUND_COUNTED_EVIDENCE:{counted_evidence_unbound}")
    if silently_unhandled:
        blockers.append(f"MECHANICALLY_UNREPRESENTABLE_EVIDENCE:{silently_unhandled}")
    if classifier_exceptions:
        blockers.append(f"CLASSIFIER_PIPELINE_EXCEPTIONS:{classifier_exceptions}")
    if missing_targets or duplicate_targets or extra_targets:
        blockers.append("TARGET_COVERAGE_INVARIANT_FAILED")

    counts = {
        state: sum(1 for value in target_states.values() if value == state)
        for state in (
            "STRICT_EVENT_POSITIVE",
            "SENSITIVITY_EVENT_POSITIVE",
            "NO_CONFIRMED_EVENT",
            "NEEDS_REVIEW",
        )
    }
    target_rows = [
        {"episode_id": eid, "state": target_states[eid]}
        for eid in sorted(target_states)
    ]
    target_sha = sha256_bytes(stable_json(target_rows).encode("utf-8"))

    # Unresolved review evidence may remain as bounded follow-up items; counted
    # evidence that cannot be represented is a blocker above.
    return {
        "city_key": city,
        "verdict": "CITY V2 FORMALIZATION BLOCKED" if blockers else "CITY V2 FORMALIZATION PROVEN",
        "blocker": ";".join(blockers) if blockers else None,
        "canonical_episodes": len(episodes),
        "evidence_records_read": evidence_records_read,
        "normalized_observations": normalized_observations,
        "bound_observations": bound_observations,
        "unbound_observations": unbound_observations,
        "malformed_provenance": malformed_provenance,
        "strict_positives": counts["STRICT_EVENT_POSITIVE"],
        "sensitivity_positives": counts["SENSITIVITY_EVENT_POSITIVE"],
        "no_confirmed_event": counts["NO_CONFIRMED_EVENT"],
        "needs_review": counts["NEEDS_REVIEW"],
        "missing_targets": missing_targets,
        "duplicate_targets": duplicate_targets,
        "extra_targets": extra_targets,
        "unresolved_evidence_bindings": len(unresolved),
        "unresolved_items": unresolved,
        "target_state_sha256": target_sha,
        "canonical_source_files": source_files,
        "counted_evidence_unbound": counted_evidence_unbound,
        "classifier_pipeline_exceptions": classifier_exceptions,
        "mechanically_unrepresentable": silently_unhandled,
    }


def main() -> int:
    tested_head = os.environ.get("GITHUB_SHA") or subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
    ).strip()

    # The Actions checkout must be clean before processing. The previously
    # committed proof artifact is allowed because it is tracked and clean.
    dirty_before = git_changed_paths()
    if dirty_before:
        raise SystemExit(f"DIRTY_CHECKOUT_BEFORE_PROCESSING:{dirty_before}")

    monitor.self_test()

    guarded_paths = [
        APP_ROOT / "scripts/monitor_explosion_candidates.py",
        APP_ROOT / "scripts/replay_explosion_history.py",
    ]
    for city in CITY_SET:
        guarded_paths.extend([evidence_path(city), source_slice_path(city)])
    guarded_before = {
        str(path.relative_to(REPO_ROOT)): sha256_file(path)
        for path in guarded_paths
        if path.exists()
    }

    city_results = [formalize_city(city) for city in CITY_SET]

    guarded_after = {
        str(path.relative_to(REPO_ROOT)): sha256_file(path)
        for path in guarded_paths
        if path.exists()
    }
    authoritative_inputs_unchanged = guarded_before == guarded_after

    changed_before_artifact = git_changed_paths()
    unexpected = [p for p in changed_before_artifact if p != str(ARTIFACT_REL)]
    mutation_guard_pass = authoritative_inputs_unchanged and not unexpected

    overall_blockers = []
    if not mutation_guard_pass:
        overall_blockers.append("AUTHORITATIVE_INPUT_MUTATION_GUARD_FAILED")
    if any(row["verdict"].endswith("BLOCKED") for row in city_results):
        overall_blockers.append("ONE_OR_MORE_CITIES_BLOCKED")

    artifact = {
        "schema_version": 2,
        "proof": "historical-v2-formalization-ternopil-uzhhorod-proof-2026-10-02",
        "mode": "FREEZE_EXISTING_EVIDENCE",
        "city_set": list(CITY_SET),
        "common_base": COMMON_BASE,
        "tested_head": tested_head,
        "methodology_version": METHODOLOGY_VERSION,
        "normalization_version": NORMALIZATION_VERSION,
        "overall_verdict": "BLOCKED" if overall_blockers else "PROVEN",
        "overall_blocker": ";".join(overall_blockers) if overall_blockers else None,
        "cities": {row["city_key"]: row for row in city_results},
        "mutation_guards": {
            "guarded_input_sha256_before": guarded_before,
            "guarded_input_sha256_after": guarded_after,
            "authoritative_inputs_unchanged": authoritative_inputs_unchanged,
            "unexpected_changed_paths_before_artifact": unexpected,
            "scope_allowlist": "PASS" if mutation_guard_pass else "FAIL",
            "db_neon": "UNTOUCHED",
            "deployment": "NO",
            "production_dashboard_data": "UNTOUCHED",
            "historical_evidence_mutations": 0 if mutation_guard_pass else None,
        },
        "public_web_research": "NO",
        "source_discovery": "NO",
        "authoritative_evidence_mutations": 0 if mutation_guard_pass else None,
        "incorporation": "NO",
    }

    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_PATH.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    changed_after = git_changed_paths()
    unexpected_after = [p for p in changed_after if p != str(ARTIFACT_REL)]
    if unexpected_after:
        raise SystemExit(f"UNEXPECTED_MUTATIONS_AFTER_ARTIFACT:{unexpected_after}")

    compact = {
        city: {
            "verdict": row["verdict"],
            "canonical": row["canonical_episodes"],
            "evidence": row["evidence_records_read"],
            "normalized": row["normalized_observations"],
            "bound": row["bound_observations"],
            "unbound": row["unbound_observations"],
            "strict": row["strict_positives"],
            "sensitivity": row["sensitivity_positives"],
            "no_confirmed": row["no_confirmed_event"],
            "needs_review": row["needs_review"],
            "unresolved": row["unresolved_evidence_bindings"],
            "sha": row["target_state_sha256"],
            "blocker": row["blocker"],
        }
        for city, row in artifact["cities"].items()
    }
    print(json.dumps({"overall": artifact["overall_verdict"], "cities": compact}, ensure_ascii=False, sort_keys=True))
    return 0 if artifact["overall_verdict"] == "PROVEN" else 2


if __name__ == "__main__":
    raise SystemExit(main())
