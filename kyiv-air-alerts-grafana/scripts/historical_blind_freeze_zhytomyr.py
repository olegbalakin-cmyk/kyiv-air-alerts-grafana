#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path
from typing import Any

SOURCE_HEAD = "a8eeaf13d51d3e16582212c85cd69a9e6c09685d"
CITY = "zhytomyr"
SEED = "20261002-23city-blind-v1"
EXPECTED_CANONICAL = 685
EXPECTED_NO_CONFIRMED = 665
EXPECTED_TARGET_SHA256 = "224a286578fba06c6ca5853bb0eee8c8b54c901836b5b77a54f5786c4bbe7546"
CASE_START = 151
SELECT_N = 5

FORMALIZER_REL = Path("kyiv-air-alerts-grafana/scripts/historical_v2_formalize_stream09.py")
CANONICAL_REL = Path("kyiv-air-alerts-grafana/data/explosion_metric_handoff/source_slices/zhytomyr-historical-recovery_alerts.json")
EVIDENCE_REL = Path("kyiv-air-alerts-grafana/data/explosion_research/zhytomyr/final_evidence.json")
ACCEPTED_ARTIFACT_REL = Path("research/historical_v2_formalization_vinnytsia_zhytomyr_proof_2026-10-02.json")

PRECEDENCE = {
    "NO_CONFIRMED_EVENT": 0,
    "NEEDS_REVIEW": 1,
    "SENSITIVITY_EVENT_POSITIVE": 2,
    "STRICT_EVENT_POSITIVE": 3,
}
BUCKET_STATE = {
    "strict": "STRICT_EVENT_POSITIVE",
    "sensitivity": "SENSITIVITY_EVENT_POSITIVE",
    "review": "NEEDS_REVIEW",
}

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def load_formalizer(source_root: Path):
    path = source_root / FORMALIZER_REL
    spec = importlib.util.spec_from_file_location("accepted_stream09_formalizer", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import accepted formalization implementation")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-root", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    source_root = Path(args.source_root).resolve()
    output = Path(args.output).resolve()

    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=source_root, text=True
    ).strip()
    if head != SOURCE_HEAD:
        raise RuntimeError(f"source checkout mismatch: {head} != {SOURCE_HEAD}")

    accepted_artifact = json.loads((source_root / ACCEPTED_ARTIFACT_REL).read_text(encoding="utf-8"))
    accepted_city = accepted_artifact["cities"][CITY]
    if accepted_city["counts"]["no_confirmed_event"] != EXPECTED_NO_CONFIRMED:
        raise RuntimeError("accepted compact artifact NO_CONFIRMED mismatch")
    if accepted_city["target_state_sha256"] != EXPECTED_TARGET_SHA256:
        raise RuntimeError("accepted compact artifact target-state SHA mismatch")

    canonical_path = source_root / CANONICAL_REL
    evidence_path = source_root / EVIDENCE_REL
    canonical_sha_before = sha256_file(canonical_path)
    evidence_sha_before = sha256_file(evidence_path)

    formalizer = load_formalizer(source_root)

    canonical_doc = json.loads(canonical_path.read_text(encoding="utf-8"))
    episodes = canonical_doc.get("episodes")
    if not isinstance(episodes, list):
        raise RuntimeError("canonical episodes missing")
    canonical: dict[str, dict[str, Any]] = {}
    for row in episodes:
        if not isinstance(row, dict):
            raise RuntimeError("non-object canonical row")
        eid = formalizer.stable_id(row)
        if not eid:
            raise RuntimeError("canonical row missing stable episode id")
        if eid in canonical:
            raise RuntimeError(f"duplicate canonical episode: {eid}")
        canonical[eid] = row
    if len(canonical) != EXPECTED_CANONICAL:
        raise RuntimeError(f"canonical count mismatch: {len(canonical)} != {EXPECTED_CANONICAL}")

    evdoc = json.loads(evidence_path.read_text(encoding="utf-8"))
    buckets = {
        "strict": list(evdoc.get("strict_events") or []),
        "sensitivity": list(evdoc.get("sensitivity_only_events") or []),
        "review": list(evdoc.get("review_events") or []),
    }

    states = {eid: "NO_CONFIRMED_EVENT" for eid in sorted(canonical)}
    observation_counts = {eid: 0 for eid in canonical}
    unresolved = 0

    for bucket, events in buckets.items():
        for ev0 in events:
            ev = ev0 if isinstance(ev0, dict) else {"raw_value": ev0}
            eid = formalizer.episode_ref(ev)
            if eid and eid in canonical:
                bind = eid
            else:
                bind, _ = formalizer.canonical_time_match(ev, canonical)
            if bind:
                observation_counts[bind] += 1
                state = BUCKET_STATE[bucket]
                if PRECEDENCE[state] > PRECEDENCE[states[bind]]:
                    states[bind] = state
            else:
                unresolved += 1

    target_rows = [{"episode_id": eid, "state": states[eid]} for eid in sorted(states)]
    target_state_sha = hashlib.sha256(
        json.dumps(
            target_rows,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    if target_state_sha != EXPECTED_TARGET_SHA256:
        raise RuntimeError(
            f"reconstructed target-state SHA mismatch: {target_state_sha} != {EXPECTED_TARGET_SHA256}"
        )

    counts = {
        "STRICT_EVENT_POSITIVE": sum(v == "STRICT_EVENT_POSITIVE" for v in states.values()),
        "SENSITIVITY_EVENT_POSITIVE": sum(v == "SENSITIVITY_EVENT_POSITIVE" for v in states.values()),
        "NO_CONFIRMED_EVENT": sum(v == "NO_CONFIRMED_EVENT" for v in states.values()),
        "NEEDS_REVIEW": sum(v == "NEEDS_REVIEW" for v in states.values()),
    }
    expected_counts = {
        "STRICT_EVENT_POSITIVE": 19,
        "SENSITIVITY_EVENT_POSITIVE": 1,
        "NO_CONFIRMED_EVENT": 665,
        "NEEDS_REVIEW": 0,
    }
    if counts != expected_counts:
        raise RuntimeError(f"formalized count mismatch: {counts} != {expected_counts}")

    eligible = [eid for eid, state in states.items() if state == "NO_CONFIRMED_EVENT"]
    before_exclusions = len(eligible)
    prior_researched: set[str] = set()
    eligible = [eid for eid in eligible if eid not in prior_researched]
    after_exclusions = len(eligible)

    if before_exclusions != EXPECTED_NO_CONFIRMED:
        raise RuntimeError(
            f"CITY BLIND FREEZE BLOCKED — NO_CONFIRMED COUNT MISMATCH: {before_exclusions}"
        )

    ranked = []
    for eid in eligible:
        rank = hashlib.sha256(f"{SEED}|{CITY}|{eid}".encode("utf-8")).hexdigest()
        ranked.append((rank, eid))
    ranked.sort(key=lambda x: (x[0], x[1]))

    selected = []
    for offset, (rank, eid) in enumerate(ranked[:SELECT_N]):
        row = canonical[eid]
        record = {
            "case": CASE_START + offset,
            "city_key": CITY,
            "episode_id": eid,
            "alert_start": row.get("alert_start"),
            "alert_end": row.get("alert_end"),
            "final_outcome": states[eid],
            "observation_count": observation_counts[eid],
            "rank": rank,
        }
        if record["final_outcome"] != "NO_CONFIRMED_EVENT":
            raise RuntimeError("selected non-NO_CONFIRMED case")
        if not isinstance(record["alert_start"], str) or not isinstance(record["alert_end"], str):
            raise RuntimeError("selected case missing alert bounds")
        selected.append(record)

    canonical_selected = json.dumps(
        selected,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    city_sample_sha = hashlib.sha256(canonical_selected).hexdigest()

    canonical_sha_after = sha256_file(canonical_path)
    evidence_sha_after = sha256_file(evidence_path)
    if canonical_sha_before != canonical_sha_after or evidence_sha_before != evidence_sha_after:
        raise RuntimeError("authoritative input mutation detected")

    result = {
        "schema_version": 1,
        "verdict": "CITY BLIND SAMPLE FROZEN",
        "city": CITY,
        "source_accepted_head": SOURCE_HEAD,
        "selection_mode": "FORMALIZED_18CITY_STATE",
        "deterministic_seed": SEED,
        "reconstructed_target_state_sha256": target_state_sha,
        "eligible_count_before_exclusions": before_exclusions,
        "prior_episodes_excluded": len(prior_researched),
        "eligible_count_after_exclusions": after_exclusions,
        "selected_cases": selected,
        "CITY_SAMPLE_SHA256": city_sample_sha,
        "reconstruction_guards": {
            "canonical_episode_count": len(canonical),
            "state_counts": counts,
            "unresolved_evidence_bindings": unresolved,
            "canonical_input_sha256": canonical_sha_before,
            "evidence_input_sha256": evidence_sha_before,
            "authoritative_inputs_unchanged": True,
        },
        "mutation_guards": {
            "research_performed": "NO",
            "public_web": "NO",
            "source_discovery": "NO",
            "db_neon": "UNTOUCHED",
            "deploy": "NO",
            "mutations_to_authoritative_data": 0,
        },
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
