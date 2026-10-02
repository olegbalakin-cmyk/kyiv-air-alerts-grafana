#!/usr/bin/env python3
from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
CHECKOUT_ROOT = ROOT.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import replay_explosion_history as replay

COMMON_BASE = "fb563dc410fe6614263bdc8d4eb55025a987e950"
PROOF_NAME = "historical-v2-formalization-chernihiv-dnipro-proof-2026-10-02"
MODE = "REBIND_EXISTING_EVIDENCE"
METHODOLOGY_VERSION = "historical-attack-event-air-defense-action-v2"
OUTPUT_REL = Path("research/historical_v2_formalization_chernihiv_dnipro_proof_2026-10-02.json")
CITY_SET = ("chernihiv", "dnipro")
EXPECTED_CANONICAL_COUNTS = {
    "chernihiv": 1676,
    "dnipro": 2259,
}
EXPECTED_FIXED_BLOBS = {
    "kyiv-air-alerts-grafana/scripts/monitor_explosion_candidates.py": "89b1be41909c6622339ce8a82d9ac2d982b82481",
    "kyiv-air-alerts-grafana/scripts/replay_explosion_history.py": "e1a6c793d680196724fbf70f09ed09a821912aca",
    "kyiv-air-alerts-grafana/data/explosion_research/chernihiv/final_evidence.json": "708644ea2cf5673d56f8cc73104c2fa17c72fd93",
    "kyiv-air-alerts-grafana/data/explosion_research/dnipro/final_evidence.json": "99758ae2a7d888593ffd863cc53cd9f48bf34f5a",
}
EVIDENCE_BUCKETS = ("strict_events", "sensitivity_only_events", "review_events")
COUNTED_BUCKETS = {"strict_events", "sensitivity_only_events"}
PRIOR_BINDING_FIELDS = ("episode_id", "matched_episode_id", "alert_episode_id")
TARGET_STATES = (
    "STRICT_EVENT_POSITIVE",
    "SENSITIVITY_EVENT_POSITIVE",
    "NO_CONFIRMED_EVENT",
    "NEEDS_REVIEW",
)


def git(*args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(CHECKOUT_ROOT), *args],
        text=True,
    ).strip()


def git_blob_worktree(rel: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(CHECKOUT_ROOT), "hash-object", rel],
        text=True,
    ).strip()


def sha256_json(value) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def target_state_sha(rows: list[tuple[str, str]]) -> str:
    payload = "".join(
        f"{episode_id}\t{state}\n"
        for episode_id, state in sorted(rows)
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def source_set_snapshot(source_files: list[str]) -> dict:
    rows = []
    for rel in sorted(set(source_files)):
        checkout_rel = f"kyiv-air-alerts-grafana/{rel}"
        rows.append({
            "path": checkout_rel,
            "blob": git_blob_worktree(checkout_rel),
        })
    return {
        "count": len(rows),
        "sha256": sha256_json(rows),
        "rows": rows,
    }


def compact_source_snapshot(snapshot: dict) -> dict:
    return {
        "source_slice_count": int(snapshot["count"]),
        "source_slice_set_sha256": snapshot["sha256"],
    }


def prior_episode_id(row: dict) -> str | None:
    for field in PRIOR_BINDING_FIELDS:
        value = row.get(field)
        if value:
            return str(value)
    return None


def rebinding_row(row: dict) -> dict:
    out = copy.deepcopy(row)
    for field in PRIOR_BINDING_FIELDS:
        out.pop(field, None)
    return out


def known_event_times(row: dict, monitor) -> list[str]:
    values = []
    try:
        for dt in replay.retained_event_datetimes(row, monitor):
            value = dt.astimezone(monitor.UTC).isoformat().replace("+00:00", "Z")
            if value not in values:
                values.append(value)
    except Exception:
        pass
    return values


def unresolved_record(
    *,
    evidence_id: str,
    event_times: list[str],
    reason: str,
    candidates: list[str],
) -> dict:
    return {
        "evidence_id": evidence_id,
        "event_time": event_times or None,
        "reason": reason,
        "candidate_episode_ids": sorted({str(x) for x in candidates if x}),
    }


def block(summary: dict, reason: str) -> None:
    if reason not in summary["blockers"]:
        summary["blockers"].append(reason)


def process_city(city: str, monitor) -> dict:
    expected = EXPECTED_CANONICAL_COUNTS[city]
    evidence_rel = f"kyiv-air-alerts-grafana/data/explosion_research/{city}/final_evidence.json"
    evidence_path = CHECKOUT_ROOT / evidence_rel

    summary = {
        "verdict": "CITY V2 FORMALIZATION BLOCKED",
        "canonical_episodes": 0,
        "expected_canonical_episodes": expected,
        "evidence_records_read": 0,
        "evidence_record_buckets": {bucket: 0 for bucket in EVIDENCE_BUCKETS},
        "normalized_observations": 0,
        "bound_observations": 0,
        "unbound_observations": 0,
        "nonqualifying_split_children": 0,
        "normalization_failures": 0,
        "classification_failures": 0,
        "deduplicated_candidate_occurrences": 0,
        "malformed_provenance": 0,
        "strict_positives": 0,
        "sensitivity_positives": 0,
        "no_confirmed_event": 0,
        "needs_review": 0,
        "missing_targets": 0,
        "duplicate_targets": 0,
        "extra_targets": 0,
        "unresolved_evidence_bindings": 0,
        "unbound_counted_evidence": 0,
        "rebound_from_prior_episode_id": 0,
        "target_state_sha256": None,
        "target_state_hash_semantics": "sha256 of episode_id<TAB>state<LF>, sorted by episode_id",
        "input_hashes": {},
        "unresolved_items": [],
        "blockers": [],
    }

    try:
        episodes, source_files = replay.load_historical_episodes(ROOT, city, monitor)
        episodes = sorted(
            [dict(ep) for ep in episodes],
            key=lambda ep: (
                str(ep.get("alert_start") or ""),
                str(ep.get("episode_id") or ""),
            ),
        )
        canonical_ids = [str(ep.get("episode_id") or "") for ep in episodes]
        canonical_set = set(canonical_ids)
        summary["canonical_episodes"] = len(episodes)

        if len(episodes) != expected:
            block(summary, f"CANONICAL_COUNT_MISMATCH:{len(episodes)}!={expected}")
        if any(not eid for eid in canonical_ids):
            block(summary, "CANONICAL_EPISODE_ID_MISSING")
        if len(canonical_ids) != len(canonical_set):
            block(summary, "CANONICAL_EPISODE_ID_DUPLICATE")

        source_before = source_set_snapshot(source_files)
        evidence_blob_before = git_blob_worktree(evidence_rel)
        summary["input_hashes"] = {
            "final_evidence_blob": evidence_blob_before,
            **compact_source_snapshot(source_before),
        }

        evidence = replay.load_json(evidence_path)
        if not isinstance(evidence, dict):
            raise RuntimeError("FINAL_EVIDENCE_NOT_OBJECT")

        ep_by_id = {
            str(ep["episode_id"]): ep
            for ep in episodes
            if ep.get("episode_id")
        }
        candidates_by_episode: dict[str, list[dict]] = defaultdict(list)
        seen_candidate_ids: set[tuple[str, str]] = set()
        forced_review_targets: set[str] = set()

        for bucket in EVIDENCE_BUCKETS:
            rows = evidence.get(bucket) or []
            if not isinstance(rows, list):
                block(summary, f"MALFORMED_EVIDENCE_BUCKET:{bucket}")
                continue
            summary["evidence_record_buckets"][bucket] = len(rows)
            summary["evidence_records_read"] += len(rows)

            for index, original in enumerate(rows):
                fallback_id = f"{city}:{bucket}:{index}"
                if not isinstance(original, dict):
                    summary["normalization_failures"] += 1
                    summary["unbound_observations"] += 1
                    summary["unresolved_items"].append(
                        unresolved_record(
                            evidence_id=fallback_id,
                            event_times=[],
                            reason="NON_OBJECT_EVIDENCE_RECORD",
                            candidates=[],
                        )
                    )
                    block(summary, f"UNREPRESENTABLE_EVIDENCE_RECORD:{bucket}:{index}")
                    continue

                record_id = replay.historical_record_id(city, bucket, index, original)
                old_episode_id = prior_episode_id(original)
                bind_row = rebinding_row(original)

                try:
                    observations = replay.expand_historical_evidence_observations(
                        city,
                        bucket,
                        index,
                        bind_row,
                        episodes,
                        monitor,
                        allow_new_temporal_fallback=bucket in COUNTED_BUCKETS,
                    )
                except Exception as exc:
                    summary["normalization_failures"] += 1
                    summary["unbound_observations"] += 1
                    summary["unresolved_items"].append(
                        unresolved_record(
                            evidence_id=record_id,
                            event_times=known_event_times(original, monitor),
                            reason=f"NORMALIZATION_EXCEPTION:{type(exc).__name__}",
                            candidates=[],
                        )
                    )
                    block(summary, f"NORMALIZATION_EXCEPTION:{bucket}:{index}:{type(exc).__name__}")
                    continue

                if not observations:
                    summary["normalization_failures"] += 1
                    summary["unbound_observations"] += 1
                    summary["unresolved_items"].append(
                        unresolved_record(
                            evidence_id=record_id,
                            event_times=known_event_times(original, monitor),
                            reason="NORMALIZATION_RETURNED_NO_OBSERVATIONS",
                            candidates=[],
                        )
                    )
                    block(summary, f"NORMALIZATION_EMPTY:{bucket}:{index}")
                    continue

                summary["normalized_observations"] += len(observations)

                for ordinal, observation in enumerate(observations):
                    if (
                        observation.get("is_split_child")
                        and observation.get("event_fact_present") is False
                    ):
                        summary["nonqualifying_split_children"] += 1
                        continue

                    obs_id = str(observation.get("observation_id") or record_id)
                    if len(observations) > 1 and not observation.get("observation_id"):
                        obs_id = f"{record_id}:{ordinal}"

                    binding = dict(observation.get("binding") or {})
                    target_id = str(binding.get("episode_id") or "")
                    candidates = [str(x) for x in (binding.get("candidates") or []) if x]
                    event_times = []
                    if observation.get("event_time_utc"):
                        event_times.append(str(observation["event_time_utc"]).replace("+00:00", "Z"))
                    if not event_times:
                        event_times = known_event_times(original, monitor)

                    if not target_id or target_id not in canonical_set:
                        summary["unbound_observations"] += 1
                        reason = str(binding.get("method") or "MISSING_BINDING")
                        if target_id and target_id not in canonical_set:
                            reason = f"BINDING_OUTSIDE_CANONICAL_UNIVERSE:{target_id}"
                            candidates = sorted(set(candidates + [target_id]))
                        prefix = (
                            "UNBOUND_COUNTED_EVIDENCE"
                            if bucket in COUNTED_BUCKETS
                            else "UNBOUND_REVIEW_EVIDENCE"
                        )
                        summary["unresolved_items"].append(
                            unresolved_record(
                                evidence_id=obs_id,
                                event_times=event_times,
                                reason=f"{prefix}:{reason}",
                                candidates=candidates,
                            )
                        )
                        if bucket in COUNTED_BUCKETS:
                            summary["unbound_counted_evidence"] += 1
                        continue

                    summary["bound_observations"] += 1
                    if old_episode_id and old_episode_id != target_id:
                        summary["rebound_from_prior_episode_id"] += 1

                    normalized_row = observation.get("row")
                    if not isinstance(normalized_row, dict):
                        summary["classification_failures"] += 1
                        forced_review_targets.add(target_id)
                        block(summary, f"CLASSIFICATION_ROW_INVALID:{obs_id}")
                        continue

                    normalized_row["_historical_parent_record"] = copy.deepcopy(original)
                    try:
                        candidate = replay.candidate_from_history(
                            city,
                            normalized_row,
                            bucket,
                            target_id,
                            monitor,
                            ep_by_id.get(target_id),
                        )
                        matching = replay.manual_matching(target_id)
                        decision = monitor.classify_candidate(
                            candidate,
                            city,
                            episodes,
                            matching,
                        )
                        monitor.apply_classification_decision(
                            candidate,
                            decision,
                            matching,
                        )
                    except Exception as exc:
                        summary["classification_failures"] += 1
                        forced_review_targets.add(target_id)
                        block(summary, f"CLASSIFIER_EXCEPTION:{obs_id}:{type(exc).__name__}")
                        continue

                    reviewed_adapter = decision.get("review_provenance_adapter") or {}
                    if (
                        reviewed_adapter.get("present") is True
                        and reviewed_adapter.get("usable") is not True
                    ):
                        summary["malformed_provenance"] += 1

                    candidate_key = (target_id, str(candidate.get("candidate_id") or ""))
                    if candidate_key in seen_candidate_ids:
                        summary["deduplicated_candidate_occurrences"] += 1
                        continue
                    seen_candidate_ids.add(candidate_key)
                    candidates_by_episode[target_id].append(candidate)

        if summary["unbound_counted_evidence"]:
            block(
                summary,
                f"UNRESOLVED_COUNTED_EVIDENCE:{summary['unbound_counted_evidence']}",
            )
        if summary["normalization_failures"]:
            block(
                summary,
                f"NORMALIZATION_FAILURES:{summary['normalization_failures']}",
            )
        if summary["classification_failures"]:
            block(
                summary,
                f"CLASSIFICATION_FAILURES:{summary['classification_failures']}",
            )

        target_rows: list[tuple[str, str]] = []
        for ep in episodes:
            eid = str(ep.get("episode_id") or "")
            rows = candidates_by_episode.get(eid, [])
            statuses = {str(row.get("status") or "") for row in rows}
            state = "NO_CONFIRMED_EVENT"

            if "approved_strict" in statuses:
                state = "STRICT_EVENT_POSITIVE"
            else:
                composition = {"final_composed_verdict": "not_applicable"}
                if len(rows) >= 2:
                    try:
                        composition = monitor.compose_episode_candidates(
                            city,
                            ep,
                            rows,
                            episodes,
                        )
                    except Exception as exc:
                        forced_review_targets.add(eid)
                        block(summary, f"COMPOSITION_EXCEPTION:{eid}:{type(exc).__name__}")
                if composition.get("final_composed_verdict") == "approved_strict":
                    state = "STRICT_EVENT_POSITIVE"
                elif "approved_sensitivity" in statuses:
                    state = "SENSITIVITY_EVENT_POSITIVE"
                elif "needs_review" in statuses or eid in forced_review_targets:
                    state = "NEEDS_REVIEW"

            if state not in TARGET_STATES:
                block(summary, f"INVALID_TARGET_STATE:{eid}:{state}")
                state = "NEEDS_REVIEW"
            target_rows.append((eid, state))

        counts = Counter(state for _, state in target_rows)
        summary["strict_positives"] = counts["STRICT_EVENT_POSITIVE"]
        summary["sensitivity_positives"] = counts["SENSITIVITY_EVENT_POSITIVE"]
        summary["no_confirmed_event"] = counts["NO_CONFIRMED_EVENT"]
        summary["needs_review"] = counts["NEEDS_REVIEW"]

        target_ids = [eid for eid, _ in target_rows]
        target_counter = Counter(target_ids)
        summary["missing_targets"] = len(canonical_set - set(target_ids))
        summary["duplicate_targets"] = sum(
            count - 1 for count in target_counter.values() if count > 1
        )
        summary["extra_targets"] = len(set(target_ids) - canonical_set)
        summary["unresolved_evidence_bindings"] = len(summary["unresolved_items"])
        summary["target_state_sha256"] = target_state_sha(target_rows)

        if summary["missing_targets"]:
            block(summary, f"MISSING_TARGETS:{summary['missing_targets']}")
        if summary["duplicate_targets"]:
            block(summary, f"DUPLICATE_TARGETS:{summary['duplicate_targets']}")
        if summary["extra_targets"]:
            block(summary, f"EXTRA_TARGETS:{summary['extra_targets']}")
        if len(target_rows) != expected:
            block(summary, f"TARGET_ROW_COUNT_MISMATCH:{len(target_rows)}!={expected}")
        if sum(counts.values()) != len(target_rows):
            block(summary, "TARGET_STATE_COUNT_SUM_MISMATCH")

        source_after = source_set_snapshot(source_files)
        evidence_blob_after = git_blob_worktree(evidence_rel)
        summary["input_hashes"]["final_evidence_blob_after"] = evidence_blob_after
        summary["input_hashes"]["source_slice_set_sha256_after"] = source_after["sha256"]

        if evidence_blob_before != evidence_blob_after:
            block(summary, "FINAL_EVIDENCE_MUTATED_DURING_RUN")
        if source_before["sha256"] != source_after["sha256"]:
            block(summary, "CANONICAL_SOURCE_SLICES_MUTATED_DURING_RUN")

        if not summary["blockers"]:
            summary["verdict"] = "CITY V2 FORMALIZATION PROVEN"

    except Exception as exc:
        block(summary, f"PIPELINE_EXCEPTION:{type(exc).__name__}:{str(exc)[:240]}")

    summary["unresolved_evidence_bindings"] = len(summary["unresolved_items"])
    return summary


def main() -> int:
    tested_head = git("rev-parse", "HEAD")
    fixed_actual = {
        path: git_blob_worktree(path)
        for path in EXPECTED_FIXED_BLOBS
    }
    global_blockers = [
        f"COMMON_BASE_BLOB_DRIFT:{path}:{fixed_actual[path]}!={expected}"
        for path, expected in EXPECTED_FIXED_BLOBS.items()
        if fixed_actual[path] != expected
    ]

    monitor = replay.import_monitor(ROOT)
    cities = {}
    with replay.network_blocked():
        for city in CITY_SET:
            cities[city] = process_city(city, monitor)

    pre_artifact_status = git("status", "--porcelain", "--untracked-files=all")
    if pre_artifact_status:
        global_blockers.append(
            "UNEXPECTED_PRE_ARTIFACT_WORKTREE_MUTATION:"
            + "|".join(line.strip() for line in pre_artifact_status.splitlines())
        )

    if global_blockers:
        for row in cities.values():
            for reason in global_blockers:
                block(row, f"GLOBAL_GUARD:{reason}")
            row["verdict"] = "CITY V2 FORMALIZATION BLOCKED"

    all_proven = all(
        row["verdict"] == "CITY V2 FORMALIZATION PROVEN"
        for row in cities.values()
    )
    evidence_unchanged = all(
        row.get("input_hashes", {}).get("final_evidence_blob")
        == row.get("input_hashes", {}).get("final_evidence_blob_after")
        for row in cities.values()
    )
    source_slices_unchanged = all(
        row.get("input_hashes", {}).get("source_slice_set_sha256")
        == row.get("input_hashes", {}).get("source_slice_set_sha256_after")
        for row in cities.values()
    )

    artifact = {
        "schema_version": 1,
        "proof": PROOF_NAME,
        "mode": MODE,
        "city_set": list(CITY_SET),
        "common_base": COMMON_BASE,
        "tested_head": tested_head,
        "methodology_version": METHODOLOGY_VERSION,
        "overall_verdict": (
            "HISTORICAL V2 FORMALIZATION PROVEN"
            if all_proven
            else "HISTORICAL V2 FORMALIZATION BLOCKED"
        ),
        "cities": cities,
        "global_blockers": global_blockers,
        "mutation_guards": {
            "common_base_implementation_blobs_match": not global_blockers
            or not any(x.startswith("COMMON_BASE_BLOB_DRIFT:") for x in global_blockers),
            "pre_artifact_worktree_clean": not pre_artifact_status,
            "authoritative_evidence_inputs_unchanged": evidence_unchanged,
            "historical_source_slices_unchanged": source_slices_unchanged,
            "authoritative_evidence_mutations": 0 if evidence_unchanged else None,
            "historical_source_slice_mutations": 0 if source_slices_unchanged else None,
            "accepted_five_formal_campaign_cities_untouched": True,
            "canonical_data_mutations": 0,
            "production_dashboard_mutations": 0,
            "db_neon": "UNTOUCHED",
            "deploy": "NO",
            "network_during_formalization": "BLOCKED",
            "public_web_research": "NO",
            "source_discovery": "NO",
            "incorporation": "NO",
        },
    }

    out = CHECKOUT_ROOT / OUTPUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )

    print(json.dumps({
        "proof": PROOF_NAME,
        "tested_head": tested_head,
        "overall_verdict": artifact["overall_verdict"],
        "cities": {
            city: {
                "verdict": row["verdict"],
                "canonical_episodes": row["canonical_episodes"],
                "evidence_records_read": row["evidence_records_read"],
                "normalized_observations": row["normalized_observations"],
                "bound_observations": row["bound_observations"],
                "unbound_observations": row["unbound_observations"],
                "malformed_provenance": row["malformed_provenance"],
                "strict_positives": row["strict_positives"],
                "sensitivity_positives": row["sensitivity_positives"],
                "no_confirmed_event": row["no_confirmed_event"],
                "needs_review": row["needs_review"],
                "missing_targets": row["missing_targets"],
                "duplicate_targets": row["duplicate_targets"],
                "extra_targets": row["extra_targets"],
                "unresolved_evidence_bindings": row["unresolved_evidence_bindings"],
                "target_state_sha256": row["target_state_sha256"],
                "blockers": row["blockers"],
            }
            for city, row in cities.items()
        },
        "artifact": str(OUTPUT_REL),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
