#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
ROOT = REPO_ROOT / "kyiv-air-alerts-grafana"
CITY = "vinnytsia"
CASE_START = 141
SELECT_N = 5
SEED = "20261002-23city-blind-v1"
EXPECTED_NO_CONFIRMED = 355
ACCEPTED_HEAD = "a8eeaf13d51d3e16582212c85cd69a9e6c09685d"
ACCEPTED_TARGET_STATE_SHA256 = "2c7f096b5041b6efae48c95db36bfb445dfdc598898d83d35cc8c253360d8d7a"
FORMALIZER = ROOT / "scripts" / "historical_v2_formalize_stream09.py"
EVIDENCE_PATH = ROOT / "data" / "explosion_research" / CITY / "final_evidence.json"
ARTIFACT = REPO_ROOT / "research" / "historical_blind_freeze_vinnytsia_2026-10-02.json"
PRIOR_RESEARCHED_EPISODES: tuple[str, ...] = ()

def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=REPO_ROOT, text=True).strip()

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def load_formalizer():
    spec = importlib.util.spec_from_file_location("historical_v2_formalize_stream09_freeze", FORMALIZER)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import accepted formalization implementation")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # Context-bound reconstruction: make the accepted helper scan only Vinnytsia.
    mod.CITY_SET = (CITY,)
    mod.EXPECTED = {CITY: 362}
    return mod

def main() -> int:
    git("merge-base", "--is-ancestor", ACCEPTED_HEAD, "HEAD")
    mod = load_formalizer()

    evidence_sha_before = sha256_file(EVIDENCE_PATH)
    canonical, diagnostics = mod.discover_canonical(CITY)
    if len(canonical) != 362:
        raise RuntimeError(f"CITY BLIND FREEZE BLOCKED — canonical count {len(canonical)} != 362")

    evdoc = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
    buckets = {
        "strict": list(evdoc.get("strict_events") or []),
        "sensitivity": list(evdoc.get("sensitivity_only_events") or []),
        "review": list(evdoc.get("review_events") or []),
    }
    states = {eid: "NO_CONFIRMED_EVENT" for eid in sorted(canonical)}
    observation_counts = {eid: 0 for eid in states}
    precedence = {
        "NO_CONFIRMED_EVENT": 0,
        "NEEDS_REVIEW": 1,
        "SENSITIVITY_EVENT_POSITIVE": 2,
        "STRICT_EVENT_POSITIVE": 3,
    }
    bucket_state = {
        "strict": "STRICT_EVENT_POSITIVE",
        "sensitivity": "SENSITIVITY_EVENT_POSITIVE",
        "review": "NEEDS_REVIEW",
    }

    for bucket, events in buckets.items():
        for ev0 in events:
            ev: dict[str, Any] = ev0 if isinstance(ev0, dict) else {"raw_value": ev0}
            eid = mod.episode_ref(ev)
            if eid and eid in canonical:
                bind = eid
            else:
                bind, _ = mod.canonical_time_match(ev, canonical)
            if bind:
                observation_counts[bind] += 1
                candidate_state = bucket_state[bucket]
                if precedence[candidate_state] > precedence[states[bind]]:
                    states[bind] = candidate_state

    target_rows = [{"episode_id": eid, "state": states[eid]} for eid in sorted(states)]
    target_state_sha256 = hashlib.sha256(
        json.dumps(target_rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if target_state_sha256 != ACCEPTED_TARGET_STATE_SHA256:
        raise RuntimeError(
            "CITY BLIND FREEZE BLOCKED — accepted target-state fingerprint mismatch: "
            f"{target_state_sha256} != {ACCEPTED_TARGET_STATE_SHA256}"
        )

    eligible_before = [eid for eid, state in states.items() if state == "NO_CONFIRMED_EVENT"]
    if len(eligible_before) != EXPECTED_NO_CONFIRMED:
        raise RuntimeError(
            "CITY BLIND FREEZE BLOCKED — NO_CONFIRMED COUNT MISMATCH: "
            f"{len(eligible_before)} != {EXPECTED_NO_CONFIRMED}"
        )

    prior = set(PRIOR_RESEARCHED_EPISODES)
    eligible = [eid for eid in eligible_before if eid not in prior]
    exclusions_count = len(eligible_before) - len(eligible)

    ranked = []
    for eid in eligible:
        rank = hashlib.sha256(f"{SEED}|{CITY}|{eid}".encode("utf-8")).hexdigest()
        ranked.append((rank, eid))
    ranked.sort(key=lambda x: (x[0], x[1]))
    selected = ranked[:SELECT_N]
    if len(selected) != SELECT_N:
        raise RuntimeError("CITY BLIND FREEZE BLOCKED — fewer than five eligible episodes")

    cases = []
    for offset, (rank, eid) in enumerate(selected):
        row = canonical[eid]
        alert_start = mod.first_str(row, mod.START_KEYS)
        alert_end = mod.first_str(row, mod.END_KEYS)
        if not alert_start or not alert_end:
            raise RuntimeError(f"CITY BLIND FREEZE BLOCKED — missing alert bounds for {eid}")
        cases.append({
            "case": CASE_START + offset,
            "city_key": CITY,
            "episode_id": eid,
            "alert_start": alert_start,
            "alert_end": alert_end,
            "final_outcome": "NO_CONFIRMED_EVENT",
            "observation_count": observation_counts[eid],
            "rank": rank,
        })

    canonical_serialization = json.dumps(
        cases,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    city_sample_sha256 = hashlib.sha256(canonical_serialization).hexdigest()

    evidence_sha_after = sha256_file(EVIDENCE_PATH)
    artifact = {
        "schema_version": 1,
        "proof": "historical-blind-freeze-vinnytsia-proof-2026-10-02",
        "source_accepted_head": ACCEPTED_HEAD,
        "accepted_formalization_artifact": "research/historical_v2_formalization_vinnytsia_zhytomyr_proof_2026-10-02.json",
        "city": CITY,
        "cases": "141-145",
        "selection_mode": "FORMALIZED_18CITY_STATE",
        "seed": SEED,
        "expected_no_confirmed": EXPECTED_NO_CONFIRMED,
        "reconstructed_target_state_sha256": target_state_sha256,
        "eligible_count_before_exclusions": len(eligible_before),
        "prior_episodes_excluded": exclusions_count,
        "eligible_count_after_exclusions": len(eligible),
        "selected_cases": cases,
        "city_sample_sha256": city_sample_sha256,
        "canonical_discovery": {
            "candidate_sources": diagnostics,
            "selected_episode_count": len(canonical),
        },
        "mutation_guards": {
            "evidence_sha256_before": evidence_sha_before,
            "evidence_sha256_after": evidence_sha_after,
            "evidence_unchanged": evidence_sha_before == evidence_sha_after,
            "research_performed": "NO",
            "public_web": "NO",
            "source_discovery": "NO",
            "db_neon": "UNTOUCHED",
            "incorporation": "NO",
            "deploy": "NO",
            "authoritative_data_mutations": 0,
        },
        "proof_runtime": {
            "branch": os.environ.get("GITHUB_REF_NAME"),
            "run_id": os.environ.get("GITHUB_RUN_ID"),
            "head_before_artifact_commit": git("rev-parse", "HEAD"),
        },
        "verdict": "CITY BLIND SAMPLE FROZEN",
    }
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({
        "verdict": artifact["verdict"],
        "city": CITY,
        "eligible_before": len(eligible_before),
        "excluded": exclusions_count,
        "eligible_after": len(eligible),
        "city_sample_sha256": city_sample_sha256,
    }, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
