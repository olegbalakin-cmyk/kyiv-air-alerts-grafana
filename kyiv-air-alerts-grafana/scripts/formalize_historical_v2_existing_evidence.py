#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import monitor_explosion_candidates as monitor
import replay_explosion_history as replay

ROOT = Path(__file__).resolve().parents[1]
CHECKOUT_ROOT = ROOT.parent
UTC = timezone.utc

BASE_HEAD = "fb563dc410fe6614263bdc8d4eb55025a987e950"
BRANCH = "historical-v2-formalization-kropyvnytskyi-mykolaiv-proof-2026-10-02"
MODE = "REBIND_EXISTING_EVIDENCE"
METHODOLOGY = "historical-attack-event-air-defense-action-v2"
NORMALIZATION = "retained-final-evidence-via-replay_explosion_history-current"
CITY_SPECS = {
    "kropyvnytskyi": 1161,
    "mykolaiv": 1648,
}
BUCKETS = ("strict_events", "sensitivity_only_events", "review_events")
TARGET_STATES = (
    "STRICT_EVENT_POSITIVE",
    "SENSITIVITY_EVENT_POSITIVE",
    "NO_CONFIRMED_EVENT",
    "NEEDS_REVIEW",
)


def git(*args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=CHECKOUT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def git_blob(path: Path) -> str:
    rel = path.resolve().relative_to(CHECKOUT_ROOT.resolve())
    return git("hash-object", str(rel))


def canonical_json_sha(payload) -> str:
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def source_identifier(row: dict, fallback: str) -> str:
    for key in ("source_url", "url", "telegram_url"):
        value = str(row.get(key) or "").strip()
        if value:
            return value
    return fallback


def compact_unresolved(
    *,
    city: str,
    bucket: str,
    index: int,
    observation: dict,
) -> dict:
    row = observation.get("row") or {}
    binding = observation.get("binding") or {}
    stable = str(
        observation.get("observation_id")
        or observation.get("parent_record_id")
        or hashlib.sha256(
            f"{city}|{bucket}|{index}|{row.get('source_url')}|{replay.evidence_text(row)}".encode("utf-8")
        ).hexdigest()[:24]
    )
    event_time = (
        observation.get("event_time_utc")
        or row.get("event_time")
        or row.get("event_timestamp")
        or None
    )
    return {
        "evidence_id": stable,
        "stable_source_identifier": source_identifier(row, stable),
        "event_time": event_time,
        "reason": str(binding.get("method") or binding.get("status") or "unresolved_binding"),
        "candidate_episode_ids": sorted(
            {str(x) for x in (binding.get("candidates") or []) if str(x)}
        ),
    }


def authoritative_inputs(city: str, source_files: list[str]) -> list[Path]:
    paths = [ROOT / "data" / "explosion_research" / city / "final_evidence.json"]
    paths.extend(ROOT / rel for rel in source_files)
    return sorted({p.resolve() for p in paths})


def hash_inputs(paths: list[Path]) -> dict:
    out = {}
    for path in paths:
        rel = str(path.relative_to(CHECKOUT_ROOT.resolve())).replace(os.sep, "/")
        out[rel] = {
            "git_blob_sha": git_blob(path),
            "sha256": sha256_file(path),
        }
    return out


def classify_bound_observation(
    *,
    city: str,
    bucket: str,
    observation: dict,
    episodes: list[dict],
    ep_by_id: dict[str, dict],
) -> tuple[dict, dict]:
    binding = observation.get("binding") or {}
    target_id = str(binding.get("episode_id") or "")
    row = observation.get("row") or {}
    candidate = replay.candidate_from_history(
        city,
        row,
        bucket,
        target_id,
        monitor,
        ep_by_id.get(target_id),
    )
    matching = replay.manual_matching(target_id)
    decision = monitor.classify_candidate(candidate, city, episodes, matching)
    monitor.apply_classification_decision(candidate, decision, matching)
    return candidate, decision


def formalize_city(city: str, expected_count: int) -> dict:
    blockers: list[str] = []
    evidence_path = ROOT / "data" / "explosion_research" / city / "final_evidence.json"
    if not evidence_path.exists():
        return {
            "city_key": city,
            "verdict": "CITY V2 FORMALIZATION BLOCKED",
            "blocker": "MISSING_FINAL_EVIDENCE",
            "blockers": ["MISSING_FINAL_EVIDENCE"],
        }

    evidence = load_json(evidence_path)
    if str(evidence.get("city_key") or "") != city:
        blockers.append("FINAL_EVIDENCE_CITY_MISMATCH")

    evidence_expected = int(
        evidence.get("frozen_denominator")
        or (evidence.get("final_counts") or {}).get("alerts_total")
        or 0
    )
    final_counts_expected = int((evidence.get("final_counts") or {}).get("alerts_total") or 0)
    if evidence_expected != expected_count or final_counts_expected != expected_count:
        blockers.append(
            f"EXPECTED_CANONICAL_COUNT_MISMATCH:evidence={evidence_expected},final_counts={final_counts_expected},contract={expected_count}"
        )

    episodes_all, source_files = replay.load_historical_episodes(ROOT, city, monitor)
    coverage_start = str(evidence.get("coverage_start") or "")
    coverage_end = str(evidence.get("coverage_end") or "")
    if not coverage_start or not coverage_end:
        blockers.append("MISSING_EVIDENCE_COVERAGE")
        episodes = []
    else:
        episodes = replay.filter_window(
            episodes_all, coverage_start, coverage_end, monitor
        )

    canonical_ids = [str(ep.get("episode_id") or "") for ep in episodes]
    duplicate_canonical_ids = sorted(
        eid for eid, count in Counter(canonical_ids).items() if eid and count > 1
    )
    blank_canonical_ids = sum(not eid for eid in canonical_ids)
    if len(episodes) != expected_count:
        blockers.append(
            f"CANONICAL_EPISODE_COUNT_MISMATCH:{len(episodes)}!={expected_count}"
        )
    if duplicate_canonical_ids:
        blockers.append(f"CANONICAL_DUPLICATE_IDS:{len(duplicate_canonical_ids)}")
    if blank_canonical_ids:
        blockers.append(f"CANONICAL_BLANK_IDS:{blank_canonical_ids}")

    canonical_set = {eid for eid in canonical_ids if eid}
    ep_by_id = {
        str(ep.get("episode_id") or ""): ep
        for ep in episodes
        if str(ep.get("episode_id") or "")
    }

    input_paths = authoritative_inputs(city, source_files)
    input_hashes_before = hash_inputs(input_paths)

    evidence_records_read = sum(
        len(evidence.get(bucket) or []) for bucket in BUCKETS
    )
    malformed_provenance = 0
    normalized_observations = 0
    bound_observations = 0
    unbound_observations = 0
    non_event_split_observations = 0
    zero_observation_parents = 0
    unresolved: list[dict] = []
    review_candidates: set[str] = set()
    candidates_by_episode: dict[str, list[dict]] = defaultdict(list)
    seen_candidates: set[tuple[str, str]] = set()
    normalized_digest_rows: list[dict] = []
    classifier_exceptions: list[str] = []

    for bucket in BUCKETS:
        allow_split = bucket in {"strict_events", "sensitivity_only_events"}
        for index, parent in enumerate(evidence.get(bucket) or []):
            if not str(parent.get("source_url") or "").strip():
                malformed_provenance += 1
            try:
                observations = replay.expand_historical_evidence_observations(
                    city,
                    bucket,
                    index,
                    parent,
                    episodes,
                    monitor,
                    allow_new_temporal_fallback=allow_split,
                )
            except Exception as exc:
                classifier_exceptions.append(
                    f"NORMALIZATION_EXCEPTION:{bucket}:{index}:{type(exc).__name__}:{exc}"
                )
                continue

            if not observations:
                zero_observation_parents += 1
                classifier_exceptions.append(
                    f"ZERO_NORMALIZED_OBSERVATIONS:{bucket}:{index}"
                )
                continue

            for observation in observations:
                normalized_observations += 1
                row = observation.get("row") or parent
                binding = observation.get("binding") or {}
                stable_id = str(
                    observation.get("observation_id")
                    or observation.get("parent_record_id")
                    or hashlib.sha256(
                        f"{city}|{bucket}|{index}|{parent.get('source_url')}".encode("utf-8")
                    ).hexdigest()[:24]
                )

                if (
                    observation.get("is_split_child")
                    and observation.get("event_fact_present") is False
                ):
                    non_event_split_observations += 1
                    normalized_digest_rows.append(
                        {
                            "observation_id": stable_id,
                            "bucket": bucket,
                            "binding": "NON_EVENT_SPLIT_CHILD",
                            "episode_id": binding.get("episode_id"),
                        }
                    )
                    continue

                target_id = str(binding.get("episode_id") or "")
                if not target_id:
                    unbound_observations += 1
                    item = compact_unresolved(
                        city=city,
                        bucket=bucket,
                        index=index,
                        observation=observation,
                    )
                    unresolved.append(item)
                    for candidate_id in item["candidate_episode_ids"]:
                        if candidate_id in canonical_set:
                            review_candidates.add(candidate_id)
                    normalized_digest_rows.append(
                        {
                            "observation_id": stable_id,
                            "bucket": bucket,
                            "binding": item["reason"],
                            "episode_id": None,
                            "candidate_episode_ids": item["candidate_episode_ids"],
                        }
                    )
                    continue

                bound_observations += 1
                if target_id not in canonical_set:
                    classifier_exceptions.append(
                        f"BOUND_TO_NONCANONICAL_EPISODE:{stable_id}:{target_id}"
                    )
                    continue

                try:
                    candidate, decision = classify_bound_observation(
                        city=city,
                        bucket=bucket,
                        observation=observation,
                        episodes=episodes,
                        ep_by_id=ep_by_id,
                    )
                except Exception as exc:
                    classifier_exceptions.append(
                        f"CLASSIFIER_EXCEPTION:{stable_id}:{type(exc).__name__}:{exc}"
                    )
                    continue

                candidate_key = (target_id, str(candidate.get("candidate_id") or ""))
                if candidate_key not in seen_candidates:
                    seen_candidates.add(candidate_key)
                    candidates_by_episode[target_id].append(candidate)

                normalized_digest_rows.append(
                    {
                        "observation_id": stable_id,
                        "bucket": bucket,
                        "binding": str(binding.get("method") or "bound"),
                        "episode_id": target_id,
                        "classification_outcome": decision.get("proposed_outcome"),
                        "reason_codes": sorted(
                            str(x) for x in (decision.get("reason_codes") or [])
                        ),
                    }
                )

    if classifier_exceptions:
        blockers.append(f"CLASSIFIER_OR_PIPELINE_EXCEPTIONS:{len(classifier_exceptions)}")
    if zero_observation_parents:
        blockers.append(f"ZERO_OBSERVATION_PARENTS:{zero_observation_parents}")
    if malformed_provenance:
        blockers.append(f"MALFORMED_PROVENANCE:{malformed_provenance}")

    target_rows = []
    for ep in episodes:
        eid = str(ep.get("episode_id") or "")
        rows = candidates_by_episode.get(eid, [])
        statuses = {str(row.get("status") or "") for row in rows}
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
            elif "needs_review" in statuses or eid in review_candidates:
                state = "NEEDS_REVIEW"
            else:
                state = "NO_CONFIRMED_EVENT"
        target_rows.append(
            {
                "episode_id": eid,
                "alert_start": ep.get("alert_start"),
                "alert_end": ep.get("alert_end"),
                "state": state,
            }
        )

    target_ids = [row["episode_id"] for row in target_rows]
    target_counter = Counter(target_ids)
    missing_targets = sorted(canonical_set - set(target_ids))
    duplicate_targets = sorted(
        eid for eid, count in target_counter.items() if eid and count > 1
    )
    extra_targets = sorted(set(target_ids) - canonical_set)
    if missing_targets:
        blockers.append(f"MISSING_TARGETS:{len(missing_targets)}")
    if duplicate_targets:
        blockers.append(f"DUPLICATE_TARGETS:{len(duplicate_targets)}")
    if extra_targets:
        blockers.append(f"EXTRA_TARGETS:{len(extra_targets)}")

    state_counts = Counter(row["state"] for row in target_rows)
    unknown_states = sorted(set(state_counts) - set(TARGET_STATES))
    if unknown_states:
        blockers.append("UNKNOWN_TARGET_STATES:" + ",".join(unknown_states))
    if sum(state_counts.values()) != len(episodes):
        blockers.append("TARGET_STATE_COUNT_ACCOUNTING_FAILURE")

    accounted_observations = (
        bound_observations + unbound_observations + non_event_split_observations
    )
    if accounted_observations != normalized_observations:
        blockers.append(
            f"NORMALIZATION_ACCOUNTING_FAILURE:{accounted_observations}!={normalized_observations}"
        )

    input_hashes_after = hash_inputs(input_paths)
    authoritative_inputs_unchanged = input_hashes_before == input_hashes_after
    if not authoritative_inputs_unchanged:
        blockers.append("AUTHORITATIVE_INPUT_HASH_DRIFT")

    target_rows_for_hash = sorted(
        target_rows,
        key=lambda row: (
            str(row.get("alert_start") or ""),
            str(row.get("episode_id") or ""),
        ),
    )
    target_state_sha = canonical_json_sha(target_rows_for_hash)
    normalized_observation_sha = canonical_json_sha(
        sorted(
            normalized_digest_rows,
            key=lambda row: (
                str(row.get("observation_id") or ""),
                str(row.get("bucket") or ""),
                str(row.get("episode_id") or ""),
            ),
        )
    )

    unresolved = sorted(
        unresolved,
        key=lambda row: (
            str(row.get("event_time") or ""),
            str(row.get("evidence_id") or ""),
        ),
    )

    blocker = blockers[0] if blockers else None
    return {
        "city_key": city,
        "verdict": (
            "CITY V2 FORMALIZATION BLOCKED"
            if blockers
            else "CITY V2 FORMALIZATION PROVEN"
        ),
        "blocker": blocker,
        "blockers": blockers,
        "counts": {
            "canonical_episodes": len(episodes),
            "evidence_records_read": evidence_records_read,
            "normalized_observations": normalized_observations,
            "bound_observations": bound_observations,
            "unbound_observations": unbound_observations,
            "non_event_split_observations": non_event_split_observations,
            "malformed_provenance": malformed_provenance,
            "strict_positives": int(state_counts.get("STRICT_EVENT_POSITIVE", 0)),
            "sensitivity_positives": int(state_counts.get("SENSITIVITY_EVENT_POSITIVE", 0)),
            "no_confirmed_event": int(state_counts.get("NO_CONFIRMED_EVENT", 0)),
            "needs_review": int(state_counts.get("NEEDS_REVIEW", 0)),
            "missing_targets": len(missing_targets),
            "duplicate_targets": len(duplicate_targets),
            "extra_targets": len(extra_targets),
            "unresolved_evidence_bindings": len(unresolved),
        },
        "unresolved_items": unresolved,
        "target_state_sha256": target_state_sha,
        "normalized_observation_sha256": normalized_observation_sha,
        "input_hashes": input_hashes_before,
        "guards": {
            "expected_canonical_count": expected_count,
            "evidence_contract_count": evidence_expected,
            "coverage_start": coverage_start,
            "coverage_end": coverage_end,
            "canonical_ids_unique": not duplicate_canonical_ids and not blank_canonical_ids,
            "every_canonical_episode_represented_once": (
                not missing_targets and not duplicate_targets and not extra_targets
            ),
            "normalization_accounting_pass": (
                accounted_observations == normalized_observations
            ),
            "authoritative_inputs_unchanged": authoritative_inputs_unchanged,
            "classifier_pipeline_exceptions": len(classifier_exceptions),
            "processed_other_cities": False,
            "public_web_research": False,
            "source_discovery": False,
            "db_neon_touched": False,
            "production_dashboard_mutated": False,
            "incorporation": False,
        },
        "diagnostic_hashes": {
            "classifier_git_blob": git_blob(ROOT / "scripts" / "monitor_explosion_candidates.py"),
            "replay_helper_git_blob": git_blob(ROOT / "scripts" / "replay_explosion_history.py"),
        },
    }


def compact_for_determinism(row: dict) -> dict:
    return {
        "city_key": row.get("city_key"),
        "verdict": row.get("verdict"),
        "blockers": row.get("blockers"),
        "counts": row.get("counts"),
        "unresolved_items": row.get("unresolved_items"),
        "target_state_sha256": row.get("target_state_sha256"),
        "normalized_observation_sha256": row.get("normalized_observation_sha256"),
        "input_hashes": row.get("input_hashes"),
        "guards": row.get("guards"),
        "diagnostic_hashes": row.get("diagnostic_hashes"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    tested_head = git("rev-parse", "HEAD")
    if not git("merge-base", "--is-ancestor", BASE_HEAD, tested_head) == "":
        pass

    results = {}
    repeat_results = {}
    with replay.network_blocked():
        for city, expected in CITY_SPECS.items():
            try:
                results[city] = formalize_city(city, expected)
            except Exception as exc:
                results[city] = {
                    "city_key": city,
                    "verdict": "CITY V2 FORMALIZATION BLOCKED",
                    "blocker": f"UNHANDLED_EXCEPTION:{type(exc).__name__}:{exc}",
                    "blockers": [f"UNHANDLED_EXCEPTION:{type(exc).__name__}:{exc}"],
                    "counts": {
                        "canonical_episodes": 0,
                        "evidence_records_read": 0,
                        "normalized_observations": 0,
                        "bound_observations": 0,
                        "unbound_observations": 0,
                        "non_event_split_observations": 0,
                        "malformed_provenance": 0,
                        "strict_positives": 0,
                        "sensitivity_positives": 0,
                        "no_confirmed_event": 0,
                        "needs_review": 0,
                        "missing_targets": expected,
                        "duplicate_targets": 0,
                        "extra_targets": 0,
                        "unresolved_evidence_bindings": 0,
                    },
                    "unresolved_items": [],
                    "target_state_sha256": None,
                    "normalized_observation_sha256": None,
                    "input_hashes": {},
                    "guards": {
                        "expected_canonical_count": expected,
                        "authoritative_inputs_unchanged": False,
                        "processed_other_cities": False,
                        "public_web_research": False,
                        "source_discovery": False,
                        "db_neon_touched": False,
                        "production_dashboard_mutated": False,
                        "incorporation": False,
                    },
                    "diagnostic_hashes": {},
                }

        for city, expected in CITY_SPECS.items():
            if results[city].get("blocker", "").startswith("UNHANDLED_EXCEPTION"):
                repeat_results[city] = results[city]
                continue
            repeat_results[city] = formalize_city(city, expected)

    determinism = {}
    for city in CITY_SPECS:
        first = compact_for_determinism(results[city])
        second = compact_for_determinism(repeat_results[city])
        passed = first == second
        determinism[city] = {
            "pass": passed,
            "target_state_sha256_first": results[city].get("target_state_sha256"),
            "target_state_sha256_second": repeat_results[city].get("target_state_sha256"),
        }
        if not passed:
            results[city].setdefault("blockers", []).append("NONDETERMINISTIC_FORMALIZATION")
            results[city]["blocker"] = results[city].get("blocker") or "NONDETERMINISTIC_FORMALIZATION"
            results[city]["verdict"] = "CITY V2 FORMALIZATION BLOCKED"

    artifact = {
        "schema_version": 1,
        "kind": "historical_v2_existing_evidence_formalization_proof",
        "mode": MODE,
        "methodology": METHODOLOGY,
        "normalization": NORMALIZATION,
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "proof_branch": BRANCH,
        "base_head": BASE_HEAD,
        "tested_head": tested_head,
        "github_run_id": os.getenv("GITHUB_RUN_ID"),
        "city_set": list(CITY_SPECS),
        "expected_canonical_counts": CITY_SPECS,
        "cities": results,
        "determinism": determinism,
        "mutation_guards": {
            "public_web_research": "NO",
            "source_discovery": "NO",
            "authoritative_evidence_mutations": 0,
            "db_neon_mutations": 0,
            "production_dashboard_mutations": 0,
            "incorporation": "NO",
            "processed_city_set_exact": list(CITY_SPECS),
        },
        "overall_verdict": (
            "PROVEN"
            if all(
                results[city].get("verdict") == "CITY V2 FORMALIZATION PROVEN"
                and determinism[city]["pass"]
                for city in CITY_SPECS
            )
            else "BLOCKED"
        ),
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(json.dumps({
        "overall_verdict": artifact["overall_verdict"],
        "cities": {
            city: {
                "verdict": results[city].get("verdict"),
                "counts": results[city].get("counts"),
                "target_state_sha256": results[city].get("target_state_sha256"),
                "blocker": results[city].get("blocker"),
            }
            for city in CITY_SPECS
        },
        "determinism": determinism,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
