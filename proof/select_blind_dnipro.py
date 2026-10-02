#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

ACCEPTED_HEAD = "1998919036b4832fc3555b54c9854e6cfe24a696"
CITY = "dnipro"
SEED = "20261002-23city-blind-v1"
EXPECTED_NO_CONFIRMED = 2068
EXPECTED_TARGET_STATE_SHA256 = "7cf081a6d55340d7431e8eff57051a09de1de5a1ded84c73d4ca31f3d177dea6"
CASE_START = 56
SELECT_N = 5
OUT_REL = Path("research/historical_blind_freeze_dnipro_2026-10-02.json")


def git(checkout: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(checkout), *args],
        text=True,
    ).strip()


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: select_blind_dnipro.py <accepted-checkout>")
    checkout = Path(sys.argv[1]).resolve()

    head = git(checkout, "rev-parse", "HEAD")
    if head != ACCEPTED_HEAD:
        raise RuntimeError(f"ACCEPTED_HEAD_MISMATCH:{head}")

    dirty_before = git(checkout, "status", "--porcelain", "--untracked-files=all")
    if dirty_before:
        raise RuntimeError("ACCEPTED_CHECKOUT_DIRTY_BEFORE")

    formalize_path = checkout / "kyiv-air-alerts-grafana" / "scripts" / "formalize_historical_v2_chernihiv_dnipro.py"
    spec = importlib.util.spec_from_file_location("accepted_formalize_dnipro", formalize_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("FORMALIZATION_IMPORT_SPEC_FAILED")
    formalize = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(formalize)

    accepted_artifact_path = checkout / "research" / "historical_v2_formalization_chernihiv_dnipro_proof_2026-10-02.json"
    accepted_artifact = json.loads(accepted_artifact_path.read_text(encoding="utf-8"))
    accepted_city = accepted_artifact["cities"][CITY]
    if accepted_city["no_confirmed_event"] != EXPECTED_NO_CONFIRMED:
        raise RuntimeError("ACCEPTED_ARTIFACT_NO_CONFIRMED_MISMATCH")
    if accepted_city["target_state_sha256"] != EXPECTED_TARGET_STATE_SHA256:
        raise RuntimeError("ACCEPTED_ARTIFACT_TARGET_HASH_MISMATCH")
    if accepted_city["verdict"] != "CITY V2 FORMALIZATION PROVEN":
        raise RuntimeError("ACCEPTED_ARTIFACT_CITY_NOT_PROVEN")

    captured_target_rows: list[tuple[str, str]] = []
    observation_counts: Counter[str] = Counter()

    original_target_state_sha = formalize.target_state_sha
    original_expand = formalize.replay.expand_historical_evidence_observations

    def capture_target_state_sha(rows):
        captured_target_rows[:] = list(rows)
        return original_target_state_sha(rows)

    def capture_expand(*args, **kwargs):
        observations = original_expand(*args, **kwargs)
        for observation in observations:
            if (
                observation.get("is_split_child")
                and observation.get("event_fact_present") is False
            ):
                continue
            binding = dict(observation.get("binding") or {})
            target_id = str(binding.get("episode_id") or "")
            if target_id:
                observation_counts[target_id] += 1
        return observations

    formalize.target_state_sha = capture_target_state_sha
    formalize.replay.expand_historical_evidence_observations = capture_expand

    try:
        monitor = formalize.replay.import_monitor(formalize.ROOT)
        with formalize.replay.network_blocked():
            episodes, _source_files = formalize.replay.load_historical_episodes(
                formalize.ROOT, CITY, monitor
            )
            summary = formalize.process_city(CITY, monitor)
    finally:
        formalize.target_state_sha = original_target_state_sha
        formalize.replay.expand_historical_evidence_observations = original_expand

    if summary["verdict"] != "CITY V2 FORMALIZATION PROVEN":
        raise RuntimeError(f"CITY_FORMALIZATION_NOT_PROVEN:{summary['blockers']}")
    if summary["no_confirmed_event"] != EXPECTED_NO_CONFIRMED:
        raise RuntimeError(
            f"NO_CONFIRMED_COUNT_MISMATCH:{summary['no_confirmed_event']}!={EXPECTED_NO_CONFIRMED}"
        )
    if summary["target_state_sha256"] != EXPECTED_TARGET_STATE_SHA256:
        raise RuntimeError("TARGET_STATE_SHA256_MISMATCH")
    if not captured_target_rows:
        raise RuntimeError("TARGET_ROWS_NOT_CAPTURED")

    episode_by_id = {
        str(ep.get("episode_id") or ""): dict(ep)
        for ep in episodes
        if ep.get("episode_id")
    }
    canonical_set = set(episode_by_id)
    bound_count_from_capture = sum(
        observation_counts[eid] for eid in canonical_set
    )
    if bound_count_from_capture != summary["bound_observations"]:
        raise RuntimeError(
            f"OBSERVATION_COUNT_CAPTURE_MISMATCH:{bound_count_from_capture}!={summary['bound_observations']}"
        )

    eligible = [
        eid
        for eid, state in captured_target_rows
        if state == "NO_CONFIRMED_EVENT"
    ]
    before_exclusions = len(eligible)
    if before_exclusions != EXPECTED_NO_CONFIRMED:
        raise RuntimeError(
            f"CITY BLIND FREEZE BLOCKED — NO_CONFIRMED COUNT MISMATCH:{before_exclusions}"
        )

    prior_researched: set[str] = set()
    excluded = sum(1 for eid in eligible if eid in prior_researched)
    eligible_after = [eid for eid in eligible if eid not in prior_researched]

    ranked = []
    for eid in eligible_after:
        rank = hashlib.sha256(f"{SEED}|{CITY}|{eid}".encode("utf-8")).hexdigest()
        ranked.append((rank, eid))
    ranked.sort(key=lambda row: (row[0], row[1]))
    picked = ranked[:SELECT_N]
    if len(picked) != SELECT_N:
        raise RuntimeError("INSUFFICIENT_ELIGIBLE_ROWS")

    selected = []
    for offset, (rank, eid) in enumerate(picked):
        ep = episode_by_id[eid]
        selected.append({
            "case": CASE_START + offset,
            "city_key": CITY,
            "episode_id": eid,
            "alert_start": str(ep.get("alert_start") or ""),
            "alert_end": str(ep.get("alert_end") or ""),
            "final_outcome": "NO_CONFIRMED_EVENT",
            "observation_count": int(observation_counts.get(eid, 0)),
            "rank": rank,
        })

    canonical = json.dumps(
        selected,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    city_sample_sha256 = hashlib.sha256(canonical).hexdigest()

    dirty_after = git(checkout, "status", "--porcelain", "--untracked-files=all")
    if dirty_after:
        raise RuntimeError("ACCEPTED_CHECKOUT_DIRTY_AFTER")

    artifact = {
        "schema_version": 1,
        "verdict": "CITY BLIND SAMPLE FROZEN",
        "city": CITY,
        "cases": "56-60",
        "selection_mode": "FORMALIZED_18CITY_STATE",
        "source_accepted_head": ACCEPTED_HEAD,
        "source_compact_artifact": "research/historical_v2_formalization_chernihiv_dnipro_proof_2026-10-02.json",
        "seed": SEED,
        "eligible_count_before_exclusions": before_exclusions,
        "prior_episodes_excluded": excluded,
        "eligible_count_after_exclusions": len(eligible_after),
        "selected_cases": selected,
        "CITY_SAMPLE_SHA256": city_sample_sha256,
        "accepted_state_guards": {
            "accepted_city_verdict": accepted_city["verdict"],
            "target_state_sha256": summary["target_state_sha256"],
            "target_state_sha256_matches_accepted": True,
            "bound_observations": summary["bound_observations"],
            "captured_bound_observations": bound_count_from_capture,
            "accepted_checkout_clean_before": True,
            "accepted_checkout_clean_after": True,
        },
        "mutation_guards": {
            "research_performed": "NO",
            "public_web": "NO",
            "source_discovery": "NO",
            "authoritative_evidence_mutations": 0,
            "historical_source_slice_mutations": 0,
            "canonical_data_mutations": 0,
            "production_dashboard_mutations": 0,
            "db_neon": "UNTOUCHED",
            "deploy": "NO",
            "incorporation": "NO",
        },
    }

    out = Path.cwd() / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print("__CITY_FREEZE_JSON_BEGIN__")
    print(json.dumps(artifact, ensure_ascii=False, separators=(",", ":")))
    print("__CITY_FREEZE_JSON_END__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
