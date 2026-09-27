#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from collections import Counter
from datetime import timezone
from pathlib import Path
from typing import Any

APP_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = APP_ROOT.parent
SCRIPTS = APP_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import build_explosion_source_slices as builder
import replay_explosion_history as replay

UTC = timezone.utc
EXPECTED = {
    "chernihiv": 1676,
    "chernivtsi": 113,
    "dnipro": 2259,
    "ivano_frankivsk": 103,
    "kharkiv": 3565,
    "kherson": 1412,
    "khmelnytskyi": 248,
    "kropyvnytskyi": 1161,
    "lutsk": 135,
    "mykolaiv": 1648,
    "odesa": 1465,
    "poltava": 1805,
    "rivne": 232,
    "ternopil": 125,
    "uzhhorod": 92,
    "vinnytsia": 362,
    "zhytomyr": 685,
}
EXPECTED_TOTAL = 17086
KHARKIV_BOUNDARY_ID = "30e0080db2e490337f98d277"
UPSTREAM_REPO = "Vadimkin/ukrainian-air-raid-sirens-dataset"
UPSTREAM_PATH = "datasets/official_data_uk.csv"
UPSTREAM_BLOB = "71d70c0ca54968f530d596cf315616fa858800e1"
CORRECTED_ARTIFACT_COMMIT = "89f3304e91ae5bbf1bdeb7fd13f1a18b480e4e99"
CORRECTED_CONTRACT_COMMIT = "68f716be027d3a614bbee02878ecf23f6c80c993"
RECOVERY_SUFFIX = "-historical-recovery_alerts.json"


def load_recon():
    path = SCRIPTS / "_historical_17_city_corrected_recon_tmp.py"
    spec = importlib.util.spec_from_file_location("_corrected_recon", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import corrected reconciliation helper from {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def overlap(a_start, a_end, b_start, b_end) -> bool:
    return a_start < b_end and b_start < a_end


def clean_final(city: str, start, end) -> dict[str, Any]:
    return {
        "episode_id": builder.event_id(city, start, end),
        "alert_start": builder.utc_z(start),
        "alert_end": builder.utc_z(end),
        "alert_start_date_kyiv": start.astimezone(builder.TZ).date().isoformat(),
    }


def filtered_current(city: str, cutoff: str) -> tuple[list[dict[str, Any]], list[str]]:
    episodes, sources = replay.load_historical_episodes(APP_ROOT, city, None)
    out = []
    for ep in episodes:
        day = str(ep.get("alert_start_date_kyiv") or "")
        if not day:
            day = ep["alert_start"][:10]
        if day <= cutoff:
            out.append(dict(ep))
    out.sort(key=lambda x: (x.get("alert_start") or "", x.get("episode_id") or ""))
    return out, sources


def source_slice_duplicate_count(city: str, cutoff: str) -> tuple[int, list[str]]:
    ids = []
    files = []
    root = APP_ROOT / "data" / "explosion_metric_handoff" / "source_slices"
    for path in sorted(root.glob(f"{city}-*_alerts.json")):
        files.append(str(path.relative_to(APP_ROOT)))
        payload = json.loads(path.read_text(encoding="utf-8"))
        for ep in payload.get("episodes") or []:
            day = str(ep.get("alert_start_date_kyiv") or "")
            if day and day > cutoff:
                continue
            eid = str(ep.get("episode_id") or "")
            if eid:
                ids.append(eid)
    counts = Counter(ids)
    dups = sorted(k for k, v in counts.items() if v > 1)
    return sum(v - 1 for v in counts.values() if v > 1), dups


def provenance_for_episode(
    city: str,
    row: dict[str, Any],
    upstream_intervals,
    retained_intervals,
    retained_blocks,
) -> tuple[dict[str, Any], str]:
    start = row["_start"]
    end = row["_end"]
    upstream_matches = [
        {
            "source_type": "verified_public_upstream",
            "repository": UPSTREAM_REPO,
            "path": UPSTREAM_PATH,
            "git_blob_sha": UPSTREAM_BLOB,
            "parsed_observation_start": builder.utc_z(s),
            "parsed_observation_end": builder.utc_z(e),
        }
        for s, e in upstream_intervals
        if overlap(start, end, s, e)
    ]
    retained_matches = [
        {
            "source_type": "retained_primary",
            "source_start": builder.utc_z(s),
            "source_end": builder.utc_z(e),
        }
        for s, e in retained_intervals
        if overlap(start, end, s, e)
    ]
    block_refs = []
    for block in retained_blocks:
        raw_range = block.get("raw_time_range") or []
        if len(raw_range) < 2:
            continue
        try:
            lo = recon.parse_dt(raw_range[0])
            hi = recon.parse_dt(raw_range[1])
        except Exception:
            continue
        if overlap(start, end, lo, hi):
            block_refs.append({
                "source_path": block.get("source_path"),
                "source_kind": block.get("source_kind"),
                "raw_time_range": raw_range,
            })

    has_u = bool(upstream_matches)
    has_r = bool(retained_matches)
    if not (has_u or has_r):
        raise RuntimeError(f"missing approved source support for {city} {row['episode_id']}")
    if has_u and has_r:
        bucket = "retained_and_upstream"
    elif has_r:
        bucket = "retained_primary_only"
    else:
        bucket = "verified_public_upstream_only"

    return {
        "recovery_bucket": bucket,
        "canonical_city": city,
        "canonical_start": row["alert_start"],
        "canonical_end": row["alert_end"],
        "canonical_episode_id": row["episode_id"],
        "canonicalization": {
            "builder": "scripts/build_explosion_source_slices.py",
            "transition_boundary_reconciliation": True,
            "corrected_contract_commit": CORRECTED_CONTRACT_COMMIT,
            "corrected_reconciliation_artifact_commit": CORRECTED_ARTIFACT_COMMIT,
        },
        "verified_public_upstream_observations": upstream_matches,
        "retained_primary_observations": retained_matches,
        "retained_primary_source_blocks": block_refs,
    }, bucket


def update_audited_baseline() -> dict[str, Any]:
    path = APP_ROOT / "data" / "explosion_audited_baseline.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    before = {}
    changed = False
    for city, expected in EXPECTED.items():
        row = data["cities"][city]
        old = int(row.get("total_alerts") or 0)
        before[city] = old
        if city == "chernihiv":
            if old not in {1677, 1676}:
                raise RuntimeError(f"unexpected Chernihiv audited total_alerts={old}")
            if old != 1676:
                row["total_alerts"] = 1676
                changed = True
        elif old != expected:
            raise RuntimeError(f"audited baseline drift for {city}: {old}!={expected}")
    if changed:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"before": before, "chernihiv_after": int(data["cities"]["chernihiv"]["total_alerts"]), "changed": changed}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["apply", "verify"], required=True)
    parser.add_argument("--upstream", type=Path, required=True)
    parser.add_argument("--forensic", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-pre-head")
    args = parser.parse_args()

    global recon
    recon = load_recon()

    source_bytes = args.upstream.read_bytes()
    if recon.git_blob_sha(source_bytes) != UPSTREAM_BLOB:
        raise RuntimeError("verified upstream blob bytes drifted")

    forensic = json.loads(args.forensic.read_text(encoding="utf-8"))
    status = json.loads((REPO_ROOT / "research" / "historical_replay_status_current.json").read_text(encoding="utf-8"))
    cutoff = str(status.get("through") or "")
    if cutoff != str(forensic.get("replay_through") or ""):
        raise RuntimeError(f"cutoff drift: {cutoff} vs {forensic.get('replay_through')}")

    status_expected = {c: int(status["cities"][c]["expected_alert_episodes"]) for c in EXPECTED}
    if status_expected != EXPECTED:
        raise RuntimeError(f"corrected expected contract not materialized: {status_expected}")

    upstream_base, upstream_meta = recon.upstream_base_episodes(source_bytes, set(EXPECTED))
    full_by_city, full_meta = builder.production_episodes_from_bytes(source_bytes, set(EXPECTED))
    subslices = [r for r in builder.load_subslices() if r.get("city_key") in EXPECTED]
    boundary_exclusions = builder.reconcile_parent_boundaries(full_by_city, full_meta, subslices)

    city_data = {}
    pre_total = 0
    final_total = 0
    added_total = 0
    removed_total = 0
    unchanged_total = 0
    support_counts = Counter()
    written_files = []

    for city, expected in EXPECTED.items():
        final_pairs = []
        for start, end in full_by_city[city]:
            s = start.astimezone(UTC)
            e = end.astimezone(UTC)
            if s.astimezone(builder.TZ).date().isoformat() <= cutoff:
                final_pairs.append((s, e))
        final_pairs = recon.dedup_tuples(final_pairs)
        final_rows = []
        for s, e in final_pairs:
            r = clean_final(city, s, e)
            r["_start"] = s
            r["_end"] = e
            final_rows.append(r)
        final_rows.sort(key=lambda x: (x["_start"], x["_end"], x["episode_id"]))
        final_ids_list = [r["episode_id"] for r in final_rows]
        final_ids = set(final_ids_list)
        if len(final_ids_list) != len(final_ids):
            raise RuntimeError(f"target duplicate canonical IDs in {city}")
        if len(final_rows) != expected:
            raise RuntimeError(f"target count mismatch {city}: {len(final_rows)}!={expected}")

        current, current_sources = filtered_current(city, cutoff)
        current_ids = {str(r.get("episode_id") or "") for r in current}
        if len(current_ids) != len(current):
            raise RuntimeError(f"loaded current duplicate IDs in {city}")
        extra = sorted(current_ids - final_ids)
        if extra:
            raise RuntimeError(f"current corpus has unexplained excess IDs in {city}: {extra[:10]}")
        pre_count = len(current)
        missing_rows = [r for r in final_rows if r["episode_id"] not in current_ids]

        retained_intervals, retained_diag = recon.load_retained_blocks(city, forensic["cities"][city])
        bad_retained = [d for d in retained_diag if not d.get("match")]
        if bad_retained:
            raise RuntimeError(f"retained extraction mismatch {city}: {bad_retained}")
        upstream_intervals = recon.filter_alerts_to_cutoff(upstream_base[city], cutoff)

        payload_eps = []
        for r in missing_rows:
            prov, bucket = provenance_for_episode(
                city, r, upstream_intervals, retained_intervals,
                forensic["cities"][city].get("recoverable_raw_blocks") or [],
            )
            support_counts[bucket] += 1
            payload_eps.append({
                "episode_id": r["episode_id"],
                "alert_start": r["alert_start"],
                "alert_end": r["alert_end"],
                "alert_start_date_kyiv": r["alert_start_date_kyiv"],
                "recovery_provenance": prov,
            })

        if args.mode == "apply" and payload_eps:
            path = APP_ROOT / "data" / "explosion_metric_handoff" / "source_slices" / f"{city}{RECOVERY_SUFFIX}"
            if path.exists():
                raise RuntimeError(f"recovery slice unexpectedly already exists: {path}")
            payload = {
                "schema_version": 2,
                "kind": "historical_alert_corpus_recovery_slice",
                "city_key": city,
                "assignment_rule": "alert start date in Europe/Kyiv",
                "historical_cutoff": cutoff,
                "corrected_expected_count": expected,
                "pre_repair_reconstructed_count": pre_count,
                "episode_count": len(payload_eps),
                "source": {
                    "corrected_reconciliation_artifact": "research/historical_17_city_corrected_baseline_reconciliation_2026-09-27.json",
                    "corrected_reconciliation_artifact_commit": CORRECTED_ARTIFACT_COMMIT,
                    "verified_public_upstream_repository": UPSTREAM_REPO,
                    "verified_public_upstream_path": UPSTREAM_PATH,
                    "verified_public_upstream_git_blob_sha": UPSTREAM_BLOB,
                    "production_adapter": full_meta[city],
                },
                "episodes": payload_eps,
            }
            path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
            written_files.append(str(path.relative_to(REPO_ROOT)).replace("\\", "/"))

        pre_total += pre_count
        final_total += len(final_rows)
        added_total += len(missing_rows)
        unchanged_total += pre_count
        city_data[city] = {
            "expected": expected,
            "pre_repair": pre_count,
            "planned_additions" if args.mode == "apply" else "remaining_missing": len(missing_rows),
            "planned_removals": 0,
            "target_count": len(final_rows),
            "current_source_files": current_sources,
            "target_ids": final_ids,
        }

    if final_total != EXPECTED_TOTAL:
        raise RuntimeError(f"aggregate target mismatch {final_total}!={EXPECTED_TOTAL}")

    baseline_change = {"changed": False}
    if args.mode == "apply":
        baseline_change = update_audited_baseline()

    post_city = {}
    post_total = 0
    duplicates_total = 0
    missing_all = {}
    excess_all = {}
    for city, expected in EXPECTED.items():
        loaded, _ = filtered_current(city, cutoff)
        ids = [str(x.get("episode_id") or "") for x in loaded]
        idset = set(ids)
        target_ids = city_data[city].pop("target_ids")
        missing = sorted(target_ids - idset)
        excess = sorted(idset - target_ids)
        dup_count, dup_ids = source_slice_duplicate_count(city, cutoff)
        if missing:
            missing_all[city] = missing
        if excess:
            excess_all[city] = excess
        duplicates_total += dup_count
        post_city[city] = {
            "expected": expected,
            "pre_repair": city_data[city]["pre_repair"],
            "episodes_added": city_data[city].get("planned_additions", 0),
            "reconstructed": len(idset),
            "missing": len(missing),
            "excess": len(excess),
            "duplicate_source_slice_ids": dup_count,
            "duplicate_ids": dup_ids,
        }
        post_total += len(idset)

    if args.mode == "apply":
        if pre_total + added_total - removed_total != EXPECTED_TOTAL:
            raise RuntimeError("repair arithmetic mismatch")
        if post_total != EXPECTED_TOTAL or missing_all or excess_all or duplicates_total:
            raise RuntimeError(
                f"post repair mismatch total={post_total} missing={len(missing_all)} excess={len(excess_all)} dup={duplicates_total}"
            )
    else:
        if added_total != 0 or post_total != EXPECTED_TOTAL or missing_all or excess_all or duplicates_total:
            raise RuntimeError(
                f"idempotence failed additions={added_total} total={post_total} missing={len(missing_all)} excess={len(excess_all)} dup={duplicates_total}"
            )

    kh_exclusions = [x for x in boundary_exclusions if x.get("city_key") == "kharkiv"]
    if not any(x.get("alert_start") == "2025-02-17T19:02:05Z" for x in kh_exclusions):
        raise RuntimeError("required Kharkiv transition-boundary exclusion not observed")
    kh_loaded, _ = filtered_current("kharkiv", cutoff)
    if KHARKIV_BOUNDARY_ID in {x["episode_id"] for x in kh_loaded}:
        raise RuntimeError("rejected Kharkiv boundary episode is present")

    result = {
        "schema_version": 1,
        "mode": args.mode,
        "historical_cutoff": cutoff,
        "expected_total": EXPECTED_TOTAL,
        "pre_repair_total": pre_total,
        "episodes_added": added_total,
        "episodes_removed": removed_total,
        "episodes_unchanged": unchanged_total,
        "post_repair_total": post_total,
        "cities_reconciled": sum(
            1 for c, row in post_city.items()
            if row["reconstructed"] == row["expected"] and row["missing"] == 0 and row["excess"] == 0 and row["duplicate_source_slice_ids"] == 0
        ),
        "missing_canonical_ids": missing_all,
        "unexplained_excess_ids": excess_all,
        "duplicate_canonical_ids": duplicates_total,
        "provenance_breakdown": dict(support_counts),
        "written_files": written_files,
        "per_city": post_city,
        "kharkiv_boundary_exclusions": kh_exclusions,
        "kharkiv_boundary_episode_present": False,
        "chernihiv_final_count": post_city["chernihiv"]["reconstructed"],
        "synthetic_chernihiv_episode_added": False,
        "audited_baseline_update": baseline_change,
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
