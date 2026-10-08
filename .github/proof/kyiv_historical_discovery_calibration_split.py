#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

SNAP_COMMIT = "efefa399e69eadd3d7fc8393ac1553cfde35f138"
SNAP_PATH = "research/attack_event_23city_persistence_snapshot_v2_2026-10-04.json"
SNAP_BLOB = "8a2f6bd33f879be9db978da59c12c34e61f6f843"
EXPECTED_POS = {"STRICT_EVENT_POSITIVE": 141, "SENSITIVITY_EVENT_POSITIVE": 4}
EXPECTED_HOLDS = 57
DEV_POS = 48
DEV_HOLDS = 19
UTC = timezone.utc

def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()

def git_bytes(ref: str, path: str) -> bytes:
    return subprocess.check_output(["git", "show", f"{ref}:{path}"])

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def iso_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")

def evenly_spaced_indices(total: int, count: int) -> list[int]:
    if count < 0 or count > total:
        raise ValueError((total, count))
    if count == 0:
        return []
    # Midpoint systematic selection distributes membership across the full time range.
    out = [min(total - 1, math.floor((i + 0.5) * total / count)) for i in range(count)]
    if len(set(out)) != count:
        raise RuntimeError("SYSTEMATIC_INDEX_COLLISION")
    return out

def year_of(row: dict) -> str:
    return str(row["alert_start_utc_microseconds"])[:4]

def compact(row: dict, cohort: str, truth: str) -> dict:
    return {
        "episode_id": str(row["historical_episode_id"]),
        "city_key": "kyiv",
        "alert_start": str(row["alert_start_utc_microseconds"]),
        "alert_end": str(row["alert_end_utc_microseconds"]),
        "cohort": cohort,
        "truth_label": truth,
    }

def ensure_sensitivity_both(selected: set[int], rows: list[dict]) -> set[int]:
    sens = [i for i, r in enumerate(rows) if str(r.get("verdict")) == "SENSITIVITY_EVENT_POSITIVE"]
    if not sens:
        raise RuntimeError("NO_SENSITIVITY_ROWS")
    sel_sens = [i for i in sens if i in selected]
    blind_sens = [i for i in sens if i not in selected]

    def nearest_strict(pool: set[int], target: int) -> int:
        candidates = [i for i in pool if str(rows[i].get("verdict")) == "STRICT_EVENT_POSITIVE"]
        if not candidates:
            raise RuntimeError("NO_STRICT_SWAP_CANDIDATE")
        return min(candidates, key=lambda i: (abs(i - target), i))

    if not sel_sens:
        target = sens[len(sens) // 2]
        victim = nearest_strict(selected, target)
        selected.remove(victim)
        selected.add(target)
    if not [i for i in sens if i not in selected]:
        target = sens[-1]
        selected.remove(target)
        replacement = nearest_strict(set(range(len(rows))) - selected - {target}, target)
        selected.add(replacement)
    return selected

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--run-id", default="")
    args = ap.parse_args()

    # Pin the accepted frozen snapshot; labels are used only here for splitting/evaluation.
    subprocess.run(["git", "fetch", "--no-tags", "origin", SNAP_COMMIT], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    actual_blob = git("rev-parse", f"{SNAP_COMMIT}:{SNAP_PATH}")
    if actual_blob != SNAP_BLOB:
        raise RuntimeError(f"SNAPSHOT_BLOB_MISMATCH:{actual_blob}")
    raw = git_bytes(SNAP_COMMIT, SNAP_PATH)
    doc = json.loads(raw)
    rows = list(doc.get("classifications") or [])
    links = list(doc.get("source_links") or [])

    kyiv = [r for r in rows if str(r.get("city_key") or "") == "kyiv"]
    if len(kyiv) != 2456:
        raise RuntimeError(f"KYIV_EPISODE_COUNT_MISMATCH:{len(kyiv)}")

    pos = [r for r in kyiv if str(r.get("verdict")) in EXPECTED_POS]
    dist = Counter(str(r.get("verdict")) for r in pos)
    if dict(dist) != EXPECTED_POS:
        raise RuntimeError(f"KYIV_POSITIVE_DISTRIBUTION_MISMATCH:{dict(dist)}")

    by_key = {str(r.get("classification_key") or ""): r for r in kyiv}
    evidence_link_counts = Counter()
    for link in links:
        key = str(link.get("classification_key_v2") or link.get("classification_key") or "")
        if key in by_key:
            evidence_link_counts[key] += 1

    # Accepted 57 safety controls are the frozen PRE_CUTOFF_REVIEW cohort
    # established by kyiv_review_transferability_audit.py: evidence-backed
    # NEEDS_REVIEW rows with alert date <= 2025-02-12. In this snapshot all
    # 266 Kyiv NEEDS_REVIEW rows have retained source links; the historical
    # cutoff is what distinguishes the accepted 57 controls from the later
    # 209 review-transfer cases.
    holds = [
        r for r in kyiv
        if str(r.get("verdict")) == "NEEDS_REVIEW"
        and evidence_link_counts[str(r.get("classification_key") or "")] > 0
        and str(r.get("alert_start_utc_microseconds") or "")[:10] <= "2025-02-12"
    ]
    if len(holds) != EXPECTED_HOLDS:
        raise RuntimeError(f"EVIDENCE_BACKED_HOLD_COUNT_MISMATCH:{len(holds)}")

    pos.sort(key=lambda r: (str(r["alert_start_utc_microseconds"]), str(r["historical_episode_id"])))
    holds.sort(key=lambda r: (str(r["alert_start_utc_microseconds"]), str(r["historical_episode_id"])))

    dev_pos_idx = set(evenly_spaced_indices(len(pos), DEV_POS))
    dev_pos_idx = ensure_sensitivity_both(dev_pos_idx, pos)
    if len(dev_pos_idx) != DEV_POS:
        raise RuntimeError("DEV_POS_COUNT_DRIFT")
    dev_hold_idx = set(evenly_spaced_indices(len(holds), DEV_HOLDS))

    records = []
    for i, row in enumerate(pos):
        cohort = "development" if i in dev_pos_idx else "blind"
        records.append(compact(row, cohort, str(row["verdict"])))
    for i, row in enumerate(holds):
        cohort = "development" if i in dev_hold_idx else "blind"
        records.append(compact(row, cohort, "HOLD_CONTROL"))
    records.sort(key=lambda r: (r["cohort"], r["alert_start"], r["episode_id"]))

    counts = Counter((r["cohort"], r["truth_label"]) for r in records)
    dev_pos_n = sum(v for (c,t),v in counts.items() if c == "development" and t in EXPECTED_POS)
    blind_pos_n = sum(v for (c,t),v in counts.items() if c == "blind" and t in EXPECTED_POS)
    dev_hold_n = counts[("development","HOLD_CONTROL")]
    blind_hold_n = counts[("blind","HOLD_CONTROL")]
    if (dev_pos_n, blind_pos_n, dev_hold_n, blind_hold_n) != (48,97,19,38):
        raise RuntimeError(f"SPLIT_COUNT_MISMATCH:{dev_pos_n},{blind_pos_n},{dev_hold_n},{blind_hold_n}")

    dev_sens = counts[("development","SENSITIVITY_EVENT_POSITIVE")]
    blind_sens = counts[("blind","SENSITIVITY_EVENT_POSITIVE")]
    if dev_sens < 1 or blind_sens < 1:
        raise RuntimeError(f"SENSITIVITY_SPLIT_INVALID:{dev_sens},{blind_sens}")

    years = defaultdict(lambda: Counter())
    for r in records:
        years[year_of(r)][r["cohort"] + ":" + r["truth_label"]] += 1

    discovery_projection_fields = ["episode_id", "city_key", "alert_start", "alert_end"]
    forbidden_discovery_fields = [
        "truth_label", "old_evidence_urls", "old_candidate_urls", "telegram_message_ids",
        "publisher_urls", "review_provenance", "review_notes", "recovered_fulltext",
        "historical_candidate_text", "attack_event_text", "known_attack_timestamps",
        "truth_source_identity", "truth_source_mapping"
    ]
    identity_payload = "\n".join(
        f'{r["cohort"]}|{r["episode_id"]}|{r["alert_start"]}|{r["alert_end"]}|{r["truth_label"]}'
        for r in records
    ) + "\n"

    artifact = {
        "schema_version": 1,
        "kind": "kyiv_historical_discovery_calibration_split",
        "generated_at": iso_now(),
        "workflow_run_id": str(args.run_id or ""),
        "source_snapshot": {
            "commit": SNAP_COMMIT,
            "path": SNAP_PATH,
            "blob": actual_blob,
            "sha256": sha256_bytes(raw),
        },
        "ground_truth_reconciliation": {
            "kyiv_total": len(kyiv),
            "strict": dist["STRICT_EVENT_POSITIVE"],
            "sensitivity": dist["SENSITIVITY_EVENT_POSITIVE"],
            "positive_total": len(pos),
            "evidence_backed_holds": len(holds),
            "hold_definition": "accepted PRE_CUTOFF_REVIEW cohort: frozen NEEDS_REVIEW with retained evidence and alert date <= 2025-02-12, matching the accepted 57-control transferability audit; source-link content is never projected into discovery",
        },
        "split_method": {
            "name": "deterministic_evenly_spaced_time_systematic_v1",
            "ordering": ["alert_start_utc_microseconds", "historical_episode_id"],
            "development_positive_target": DEV_POS,
            "development_hold_target": DEV_HOLDS,
            "time_stratification": "systematic midpoint ranks across the full sorted time range",
            "sensitivity_constraint": "deterministic nearest-rank STRICT swap only if needed to place >=1 SENSITIVITY in each cohort",
            "truth_features_used_for_membership": ["positive_vs_hold", "STRICT_vs_SENSITIVITY only for required representation"],
            "truth_features_not_used": ["evidence source", "wording", "attack type", "publisher", "URL", "review notes"],
        },
        "counts": {
            "development_positives": dev_pos_n,
            "development_holds": dev_hold_n,
            "development_strict": counts[("development","STRICT_EVENT_POSITIVE")],
            "development_sensitivity": dev_sens,
            "blind_positives": blind_pos_n,
            "blind_holds": blind_hold_n,
            "blind_strict": counts[("blind","STRICT_EVENT_POSITIVE")],
            "blind_sensitivity": blind_sens,
        },
        "period_distribution": {year: dict(counter) for year,counter in sorted(years.items())},
        "blindness_contract": {
            "discovery_projection_fields": discovery_projection_fields,
            "forbidden_discovery_fields": forbidden_discovery_fields,
            "discovery_must_construct_sanitized_episode_objects": True,
            "old_truth_urls_allowed_as_discovery_input": False,
            "split_frozen_before_discovery": True,
        },
        "ordered_split_identity_sha256": sha256_bytes(identity_payload.encode("utf-8")),
        "episodes": records,
        "verdict": "KYIV HISTORICAL DISCOVERY SPLIT = FROZEN",
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "verdict": artifact["verdict"],
        "counts": artifact["counts"],
        "hold_definition": artifact["ground_truth_reconciliation"]["hold_definition"],
        "ordered_split_identity_sha256": artifact["ordered_split_identity_sha256"],
    }, ensure_ascii=False, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())