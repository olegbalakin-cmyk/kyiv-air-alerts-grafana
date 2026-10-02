#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import replay_explosion_history as replay

COMMON_BASE = "fb563dc410fe6614263bdc8d4eb55025a987e950"
PROOF_NAME = "historical-v2-formalization-kharkiv-kherson-proof-2026-10-02"
MODE = "REBIND_EXISTING_EVIDENCE"
METHODOLOGY = "historical-attack-event-air-defense-action-v2"
CITY_CONFIG = {"kharkiv": 3565, "kherson": 1412}
BUCKETS = ("strict_events", "sensitivity_only_events", "review_events")
COUNTED_BUCKETS = {"strict_events", "sensitivity_only_events"}
PERSISTED_ID_FIELDS = ("episode_id", "matched_episode_id", "alert_episode_id")

ROOT = Path(__file__).resolve().parents[1]
CHECKOUT = ROOT.parent
ARTIFACT_REL = Path("research/historical_v2_formalization_kharkiv_kherson_proof_2026-10-02.json")
ARTIFACT = CHECKOUT / ARTIFACT_REL
WORKFLOW_REL = ".github/workflows/historical-v2-formalization-kharkiv-kherson-proof.yml"
SCRIPT_REL = "kyiv-air-alerts-grafana/scripts/historical_v2_formalization_existing_evidence.py"
ALLOWED_TESTED_DIFF = {WORKFLOW_REL, SCRIPT_REL}


def dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def git(*args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(CHECKOUT), *args],
        text=True,
    ).strip()


def git_blob(ref: str, rel: str) -> str | None:
    try:
        return git("rev-parse", f"{ref}:{rel}")
    except subprocess.CalledProcessError:
        return None


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def aggregate_files(paths: list[Path]) -> str:
    rows = []
    for path in sorted(paths):
        rel = path.relative_to(CHECKOUT).as_posix()
        rows.append(f"{rel}\0{sha256_file(path)}")
    return hashlib.sha256("\n".join(rows).encode("utf-8")).hexdigest()


def aggregate_git_blobs(ref: str, rels: list[str]) -> str:
    rows = []
    for rel in sorted(rels):
        rows.append(f"{rel}\0{git_blob(ref, rel)}")
    return hashlib.sha256("\n".join(rows).encode("utf-8")).hexdigest()


def base_slice_paths(city: str) -> list[str]:
    prefix = "kyiv-air-alerts-grafana/data/explosion_metric_handoff/source_slices"
    out = git("ls-tree", "-r", "--name-only", COMMON_BASE, "--", prefix).splitlines()
    return sorted(
        rel for rel in out
        if Path(rel).name.startswith(f"{city}-") and rel.endswith("_alerts.json")
    )


def stable_source_id(city: str, bucket: str, index: int, row: dict[str, Any]) -> str:
    for key in ("evidence_id", "event_id", "record_id", "id", "source_url"):
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return replay.historical_record_id(city, bucket, index, row)


def event_time_for_unresolved(row: dict[str, Any], binding: dict[str, Any]) -> str | None:
    times = binding.get("event_times_utc") or []
    if times:
        return str(times[0])
    for field in replay.EVENT_TIME_FIELDS:
        if row.get(field):
            return str(row.get(field))
    for field in replay.START_FIELDS + replay.LEGACY_START_FIELDS + replay.RECORDED_DATE_FIELDS:
        if row.get(field):
            return str(row.get(field))
    return None


def malformed_provenance(row: dict[str, Any]) -> bool:
    for key in ("review_provenance", "provenance", "raw_record"):
        if key in row and row.get(key) is not None and not isinstance(row.get(key), dict):
            return True
    if "source_url" in row and row.get("source_url") is not None and not isinstance(row.get("source_url"), str):
        return True
    return False


def strip_persisted_binding(row: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(row)
    for field in PERSISTED_ID_FIELDS:
        out.pop(field, None)
    return out


def compact_unresolved(
    city: str,
    bucket: str,
    index: int,
    row: dict[str, Any],
    binding: dict[str, Any],
    canonical_ids: set[str],
) -> dict[str, Any]:
    return {
        "evidence_id": stable_source_id(city, bucket, index, row),
        "event_time": event_time_for_unresolved(row, binding),
        "reason": str(binding.get("method") or "missing_episode_binding"),
        "candidate_episode_ids": [
            str(eid) for eid in (binding.get("candidates") or [])
            if str(eid) in canonical_ids
        ],
    }


def canonical_state_sha(city: str, states: list[dict[str, str]]) -> str:
    payload = {
        "city_key": city,
        "methodology": METHODOLOGY,
        "targets": states,
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def city_input_guard(city: str, expected_head: str) -> dict[str, Any]:
    evidence = ROOT / "data" / "explosion_research" / city / "final_evidence.json"
    slices = sorted(
        (ROOT / "data" / "explosion_metric_handoff" / "source_slices").glob(f"{city}-*_alerts.json")
    )
    evidence_rel = evidence.relative_to(CHECKOUT).as_posix()
    slice_rels = [p.relative_to(CHECKOUT).as_posix() for p in slices]
    base_rels = base_slice_paths(city)
    return {
        "evidence_path": evidence_rel,
        "evidence_base_blob": git_blob(COMMON_BASE, evidence_rel),
        "evidence_tested_blob": git_blob(expected_head, evidence_rel),
        "evidence_runtime_sha_before": sha256_file(evidence),
        "source_slice_count": len(slices),
        "source_slice_paths_match_base": slice_rels == base_rels,
        "source_slices_base_git_aggregate_sha256": aggregate_git_blobs(COMMON_BASE, base_rels),
        "source_slices_tested_git_aggregate_sha256": aggregate_git_blobs(expected_head, slice_rels),
        "source_slices_runtime_aggregate_sha256_before": aggregate_files(slices),
    }


def finalize_input_guard(city: str, guard: dict[str, Any]) -> dict[str, Any]:
    evidence = CHECKOUT / guard["evidence_path"]
    slices = sorted(
        (ROOT / "data" / "explosion_metric_handoff" / "source_slices").glob(f"{city}-*_alerts.json")
    )
    guard = dict(guard)
    guard["evidence_runtime_sha_after"] = sha256_file(evidence)
    guard["source_slices_runtime_aggregate_sha256_after"] = aggregate_files(slices)
    guard["evidence_unchanged"] = (
        guard["evidence_base_blob"]
        == guard["evidence_tested_blob"]
        and guard["evidence_runtime_sha_before"] == guard["evidence_runtime_sha_after"]
    )
    guard["source_slices_unchanged"] = (
        guard["source_slice_paths_match_base"]
        and guard["source_slices_base_git_aggregate_sha256"]
        == guard["source_slices_tested_git_aggregate_sha256"]
        and guard["source_slices_runtime_aggregate_sha256_before"]
        == guard["source_slices_runtime_aggregate_sha256_after"]
    )
    return guard


def formalize_city(city: str, expected_count: int, monitor, expected_head: str) -> dict[str, Any]:
    blockers: list[str] = []
    unresolved: list[dict[str, Any]] = []
    review_unresolved_candidates: set[str] = set()
    evidence_records_read = 0
    normalized_observations = 0
    bound_observations = 0
    unbound_observations = 0
    malformed = 0
    ignored_nonqualifying_split_children = 0
    duplicate_candidate_observations = 0
    classified_candidate_observations = 0
    parent_rows_accounted = 0

    guard = city_input_guard(city, expected_head)
    if not guard["evidence_base_blob"] or guard["evidence_base_blob"] != guard["evidence_tested_blob"]:
        blockers.append("AUTHORITATIVE_EVIDENCE_DRIFT_FROM_COMMON_BASE")
    if (
        not guard["source_slice_paths_match_base"]
        or guard["source_slices_base_git_aggregate_sha256"]
        != guard["source_slices_tested_git_aggregate_sha256"]
    ):
        blockers.append("CANONICAL_SOURCE_SLICE_DRIFT_FROM_COMMON_BASE")

    evidence_path = ROOT / "data" / "explosion_research" / city / "final_evidence.json"
    try:
        episodes, source_files = replay.load_historical_episodes(ROOT, city, monitor)
        canonical_episode_ids = [str(ep.get("episode_id") or "") for ep in episodes]
        canonical_set = set(canonical_episode_ids)
        if any(not eid for eid in canonical_episode_ids):
            blockers.append("CANONICAL_EPISODE_WITHOUT_ID")
        if len(canonical_set) != len(canonical_episode_ids):
            blockers.append("DUPLICATE_CANONICAL_EPISODE_IDS")
        if len(episodes) != expected_count:
            blockers.append(f"CANONICAL_COUNT_MISMATCH:{len(episodes)}!={expected_count}")

        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        if not isinstance(evidence, dict):
            raise RuntimeError("final_evidence.json is not an object")
        if evidence.get("city_key") not in (None, city):
            blockers.append("EVIDENCE_CITY_KEY_MISMATCH")

        ep_by_id = {str(ep["episode_id"]): ep for ep in episodes}
        candidates_by_episode: dict[str, list[dict[str, Any]]] = defaultdict(list)
        seen_candidate_keys: set[tuple[str, str]] = set()

        for bucket in BUCKETS:
            rows = evidence.get(bucket) or []
            if not isinstance(rows, list):
                blockers.append(f"MALFORMED_EVIDENCE_BUCKET:{bucket}")
                continue
            allow_split = bucket in COUNTED_BUCKETS
            for index, original_row in enumerate(rows):
                evidence_records_read += 1
                if not isinstance(original_row, dict):
                    malformed += 1
                    parent_rows_accounted += 1
                    blockers.append(f"MALFORMED_EVIDENCE_RECORD:{bucket}:{index}")
                    unresolved.append({
                        "evidence_id": f"{city}:{bucket}:{index}",
                        "event_time": None,
                        "reason": "malformed_evidence_record",
                        "candidate_episode_ids": [],
                    })
                    continue

                if malformed_provenance(original_row):
                    malformed += 1
                    blockers.append(f"MALFORMED_PROVENANCE:{bucket}:{index}")

                rebound_row = strip_persisted_binding(original_row)
                observations = replay.expand_historical_evidence_observations(
                    city,
                    bucket,
                    index,
                    rebound_row,
                    episodes,
                    monitor,
                    allow_new_temporal_fallback=allow_split,
                )
                if not observations:
                    blockers.append(f"NO_NORMALIZED_OBSERVATION:{bucket}:{index}")
                    unresolved.append({
                        "evidence_id": stable_source_id(city, bucket, index, original_row),
                        "event_time": None,
                        "reason": "no_normalized_observation",
                        "candidate_episode_ids": [],
                    })
                    parent_rows_accounted += 1
                    continue

                parent_rows_accounted += 1
                for observation in observations:
                    normalized_observations += 1
                    binding = dict(observation.get("binding") or {})
                    target_id = str(binding.get("episode_id") or "")
                    nonqualifying_child = (
                        observation.get("is_split_child")
                        and observation.get("event_fact_present") is False
                    )

                    if target_id and target_id in canonical_set:
                        bound_observations += 1
                    else:
                        unbound_observations += 1

                    if nonqualifying_child:
                        ignored_nonqualifying_split_children += 1
                        continue

                    if not target_id or target_id not in canonical_set:
                        item = compact_unresolved(
                            city, bucket, index, original_row, binding, canonical_set
                        )
                        unresolved.append(item)
                        if bucket in COUNTED_BUCKETS:
                            blockers.append(
                                f"UNRESOLVED_COUNTED_EVIDENCE:{bucket}:{item['evidence_id']}"
                            )
                        else:
                            review_unresolved_candidates.update(item["candidate_episode_ids"])
                        continue

                    candidate = replay.candidate_from_history(
                        city,
                        observation["row"],
                        bucket,
                        target_id,
                        monitor,
                        ep_by_id.get(target_id),
                    )
                    key = (target_id, str(candidate.get("candidate_id") or ""))
                    if key in seen_candidate_keys:
                        duplicate_candidate_observations += 1
                        continue
                    seen_candidate_keys.add(key)

                    matching = replay.manual_matching(target_id)
                    decision = monitor.classify_candidate(candidate, city, episodes, matching)
                    monitor.apply_classification_decision(candidate, decision, matching)
                    candidates_by_episode[target_id].append(candidate)
                    classified_candidate_observations += 1

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

        for eid in review_unresolved_candidates:
            if target_states.get(eid) == "NO_CONFIRMED_EVENT":
                target_states[eid] = "NEEDS_REVIEW"

        state_rows = [
            {"episode_id": eid, "state": target_states[eid]}
            for eid in sorted(target_states)
        ]
        output_ids = [row["episode_id"] for row in state_rows]
        missing_targets = len(canonical_set - set(output_ids))
        duplicate_targets = len(output_ids) - len(set(output_ids))
        extra_targets = len(set(output_ids) - canonical_set)
        counts = Counter(row["state"] for row in state_rows)

        if missing_targets:
            blockers.append(f"MISSING_TARGETS:{missing_targets}")
        if duplicate_targets:
            blockers.append(f"DUPLICATE_TARGETS:{duplicate_targets}")
        if extra_targets:
            blockers.append(f"EXTRA_TARGETS:{extra_targets}")
        if parent_rows_accounted != evidence_records_read:
            blockers.append(
                f"EVIDENCE_ACCOUNTING_MISMATCH:{parent_rows_accounted}!={evidence_records_read}"
            )
        if sum(counts.values()) != len(episodes):
            blockers.append("TARGET_STATE_COUNT_MISMATCH")

        guard = finalize_input_guard(city, guard)
        if not guard["evidence_unchanged"]:
            blockers.append("AUTHORITATIVE_EVIDENCE_RUNTIME_MUTATION")
        if not guard["source_slices_unchanged"]:
            blockers.append("CANONICAL_SOURCE_SLICE_RUNTIME_MUTATION")

        blocker_codes = sorted(set(blockers))
        verdict = (
            "CITY V2 FORMALIZATION PROVEN"
            if not blocker_codes
            else "CITY V2 FORMALIZATION BLOCKED"
        )
        return {
            "city_key": city,
            "verdict": verdict,
            "canonical_episodes": len(episodes),
            "expected_canonical_episodes": expected_count,
            "evidence_records_read": evidence_records_read,
            "normalized_observations": normalized_observations,
            "bound_observations": bound_observations,
            "unbound_observations": unbound_observations,
            "malformed_provenance": malformed,
            "strict_positives": counts["STRICT_EVENT_POSITIVE"],
            "sensitivity_positives": counts["SENSITIVITY_EVENT_POSITIVE"],
            "no_confirmed_event": counts["NO_CONFIRMED_EVENT"],
            "needs_review": counts["NEEDS_REVIEW"],
            "missing_targets": missing_targets,
            "duplicate_targets": duplicate_targets,
            "extra_targets": extra_targets,
            "unresolved_evidence_bindings": len(unresolved),
            "unresolved_items": unresolved,
            "target_state_sha256": canonical_state_sha(city, state_rows),
            "blockers": blocker_codes,
            "source_files_count": len(source_files),
            "evidence_accounting": {
                "parent_rows_accounted": parent_rows_accounted,
                "ignored_nonqualifying_split_children": ignored_nonqualifying_split_children,
                "duplicate_candidate_observations": duplicate_candidate_observations,
                "classified_candidate_observations": classified_candidate_observations,
                "no_silent_evidence_loss": parent_rows_accounted == evidence_records_read,
            },
            "input_guards": guard,
        }
    except Exception as exc:
        guard = finalize_input_guard(city, guard)
        return {
            "city_key": city,
            "verdict": "CITY V2 FORMALIZATION BLOCKED",
            "canonical_episodes": 0,
            "expected_canonical_episodes": expected_count,
            "evidence_records_read": evidence_records_read,
            "normalized_observations": normalized_observations,
            "bound_observations": bound_observations,
            "unbound_observations": unbound_observations,
            "malformed_provenance": malformed,
            "strict_positives": 0,
            "sensitivity_positives": 0,
            "no_confirmed_event": 0,
            "needs_review": 0,
            "missing_targets": expected_count,
            "duplicate_targets": 0,
            "extra_targets": 0,
            "unresolved_evidence_bindings": len(unresolved),
            "unresolved_items": unresolved,
            "target_state_sha256": None,
            "blockers": sorted(set(blockers + [f"PIPELINE_EXCEPTION:{type(exc).__name__}:{exc}"])),
            "evidence_accounting": {
                "parent_rows_accounted": parent_rows_accounted,
                "ignored_nonqualifying_split_children": ignored_nonqualifying_split_children,
                "duplicate_candidate_observations": duplicate_candidate_observations,
                "classified_candidate_observations": classified_candidate_observations,
                "no_silent_evidence_loss": parent_rows_accounted == evidence_records_read,
            },
            "input_guards": guard,
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-head", required=True)
    args = parser.parse_args()

    actual_head = git("rev-parse", "HEAD")
    if actual_head != args.expected_head:
        raise SystemExit(f"HEAD mismatch: expected {args.expected_head}, got {actual_head}")

    diff_files = sorted(
        x for x in git("diff", "--name-only", f"{COMMON_BASE}..{actual_head}").splitlines() if x
    )
    scope_ok = set(diff_files) == ALLOWED_TESTED_DIFF

    replay_before = git_blob(COMMON_BASE, "kyiv-air-alerts-grafana/scripts/replay_explosion_history.py")
    replay_tested = git_blob(actual_head, "kyiv-air-alerts-grafana/scripts/replay_explosion_history.py")
    monitor_before = git_blob(COMMON_BASE, "kyiv-air-alerts-grafana/scripts/monitor_explosion_candidates.py")
    monitor_tested = git_blob(actual_head, "kyiv-air-alerts-grafana/scripts/monitor_explosion_candidates.py")

    with replay.network_blocked():
        monitor = replay.import_monitor(ROOT)
        monitor.self_test()
        cities = {
            city: formalize_city(city, expected, monitor, actual_head)
            for city, expected in CITY_CONFIG.items()
        }

    all_city_proven = all(
        row["verdict"] == "CITY V2 FORMALIZATION PROVEN"
        for row in cities.values()
    )
    all_input_guards = all(
        row["input_guards"]["evidence_unchanged"]
        and row["input_guards"]["source_slices_unchanged"]
        for row in cities.values()
    )
    methodology_impl_unchanged = (
        replay_before == replay_tested
        and monitor_before == monitor_tested
    )

    if not scope_ok:
        for row in cities.values():
            if "PROOF_SCOPE_DIFF_GUARD_FAILED" not in row["blockers"]:
                row["blockers"].append("PROOF_SCOPE_DIFF_GUARD_FAILED")
                row["blockers"].sort()
                row["verdict"] = "CITY V2 FORMALIZATION BLOCKED"
        all_city_proven = False

    if not methodology_impl_unchanged:
        for row in cities.values():
            if "METHODOLOGY_IMPLEMENTATION_DRIFT" not in row["blockers"]:
                row["blockers"].append("METHODOLOGY_IMPLEMENTATION_DRIFT")
                row["blockers"].sort()
                row["verdict"] = "CITY V2 FORMALIZATION BLOCKED"
        all_city_proven = False

    artifact = {
        "schema_version": 1,
        "proof": PROOF_NAME,
        "common_base": COMMON_BASE,
        "tested_head": actual_head,
        "city_set": list(CITY_CONFIG),
        "mode": MODE,
        "methodology": METHODOLOGY,
        "github_actions": {
            "run_id": os.environ.get("GITHUB_RUN_ID"),
            "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
            "job": os.environ.get("GITHUB_JOB"),
        },
        "cities": cities,
        "unresolved_total": sum(
            row["unresolved_evidence_bindings"] for row in cities.values()
        ),
        "guards": {
            "tested_diff_files": diff_files,
            "scope_allowlist": "PASS" if scope_ok else "FAIL",
            "methodology_implementation_from_common_base": (
                "UNCHANGED" if methodology_impl_unchanged else "CHANGED"
            ),
            "historical_inputs_unchanged": "PASS" if all_input_guards else "FAIL",
            "network_policy": "socket and requests network calls blocked during proof processing",
            "public_web_research": "NO",
            "source_discovery": "NO",
            "db_neon": "UNTOUCHED",
            "deploy": "NO",
            "dashboard_and_production_state": "UNCHANGED",
            "authoritative_evidence_mutations": 0 if all_input_guards else None,
            "incorporation": "NO",
        },
        "final_verdict": (
            "KHARKIV-KHERSON V2 FORMALIZATION PROVEN"
            if all_city_proven and scope_ok and methodology_impl_unchanged and all_input_guards
            else "KHARKIV-KHERSON V2 FORMALIZATION BLOCKED"
        ),
    }
    dump_json(ARTIFACT, artifact)
    print(json.dumps({
        "artifact": ARTIFACT_REL.as_posix(),
        "final_verdict": artifact["final_verdict"],
        "cities": {
            city: {
                "verdict": row["verdict"],
                "canonical_episodes": row["canonical_episodes"],
                "unresolved": row["unresolved_evidence_bindings"],
                "target_state_sha256": row["target_state_sha256"],
                "blockers": row["blockers"],
            }
            for city, row in cities.items()
        },
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
