#!/usr/bin/env python3
"""Extend accepted shadow-02 with explicit cutoff and pure, offline derivation.

Uses the accepted adapter, B2 reader and existing site builders. All writes are
to a separate research output directory. A DST preview is a proposed projection,
never a physical Neon repair. A selection manifest is never a source receipt.
"""
from __future__ import annotations

import argparse
import collections
import copy
import hashlib
import importlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

UTC = timezone.utc


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def aware(value):
    d = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if d.tzinfo is None:
        raise ValueError("Naive timestamp")
    return d.astimezone(UTC)


def token(row, start="start_at", end="end_at"):
    return aware(row[start]), aware(row[end])


def apply_dst_preview(rows, plan):
    """Apply exact accepted replacement tuples in memory, checking preconditions."""
    result = copy.deepcopy(rows)
    operations = []
    for item in plan["candidate_records"]:
        old = item["existing_incorrect_physical_record"]
        if old:
            found = [r for r in result if r["uid"] == old["episode_uid"]]
            if len(found) != 1 or found[0]["city_key"] != item["city_key"] or token(found[0]) != token(old, "start_utc", "end_utc"):
                raise ValueError("DST exact precondition drift")
            result.remove(found[0])
        for new in item["new_candidate_utc_intervals"]:
            if any(r["city_key"] == item["city_key"] and token(r) == token(new, "start_utc", "end_utc") for r in result):
                raise ValueError("DST corrected tuple already present")
            # Deliberately not a UUID: never pass a simulated row off as physical.
            result.append({"uid": "PROPOSED:" + new["legacy_episode_id"],
                           "episode_uid": "PROPOSED:" + new["legacy_episode_id"],
                           "city_key": item["city_key"], "start_at": new["start_utc"],
                           "end_at": new["end_utc"], "legacy_episode_id": new["legacy_episode_id"],
                           "projection_origin": "ACCEPTED_DST_SOURCE_REPLAY_NOT_DB_WRITE"})
        operations.append({"city": item["city_key"], "old": old,
                           "proposed": item["new_candidate_utc_intervals"]})
    if len(result) != len(rows) + 4:
        raise ValueError("Unexpected DST delta")
    return result, operations


def completed_month_comparison(payload, bridge):
    # Production builds monthly comparison before rolling adds partial month.
    # Retain that contract while calculating every value from generated rows.
    complete = copy.deepcopy(payload["cities"])
    for city in complete.values():
        city["monthly"] = [r for r in city["monthly"] if not r.get("is_partial_period")]
    keys = payload["multicity_meta"]["production_city_keys"]
    payload["comparison"]["monthly"] = bridge.generic_comparison(complete, keys, "monthly")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", type=Path, required=True)
    ap.add_argument("--accepted-adapter", type=Path, required=True)
    ap.add_argument("--research", type=Path, required=True)
    ap.add_argument("--rows", type=Path, required=True)
    ap.add_argument("--receipt", type=Path, required=True)
    ap.add_argument("--classifications", type=Path, required=True)
    ap.add_argument("--cutoff", required=True)
    ap.add_argument("--reference-sha", default="09192a36dae49bd71e1042942481384a5e763086")
    ap.add_argument("--dst-plan", type=Path)
    ap.add_argument("--corroborating-http", type=Path)
    ap.add_argument("--http-evidence", type=Path)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    if args.output.resolve().is_relative_to(args.site.resolve()):
        raise ValueError("Output must be outside pinned production checkout")
    args.output.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(args.accepted_adapter.resolve()))
    import adapter
    import derived
    sys.path.insert(0, str((args.research / "c6_oct184_b1_source_priority_2026_10_29").resolve()))
    import source_priority_reader as b2
    receipt = load(args.receipt)
    if receipt["recovery"] is not True or receipt["read_only"] != "on":
        raise ValueError("Replica read-only evidence missing")
    cutoff = aware(args.cutoff)
    rows = load(args.rows)
    if len(rows) != receipt["rows"] or aware(receipt["cutoff"]) != cutoff:
        raise ValueError("Physical input/cutoff mismatch")
    if len({r["uid"] for r in rows}) != len(rows) or len({r["city_key"] for r in rows}) != 23:
        raise ValueError("Physical identity/city contract mismatch")
    if any(token(r)[1] <= token(r)[0] or aware(r["created_at"]) > cutoff for r in rows):
        raise ValueError("Invalid or future physical input")
    if args.reference_sha == "09192a36dae49bd71e1042942481384a5e763086":
        pin = adapter.verify_reference(args.site)
    else:
        actual = subprocess.check_output(["git", "-C", str(args.site), "rev-parse", "HEAD"], text=True).strip()
        if actual != args.reference_sha:
            raise ValueError("Explicit current reference SHA mismatch")
        pin = {"site_prod_commit": actual, "verified_blob": {}}
        for relative, accepted in adapter.PINNED_SOURCE_BLOBS.items():
            blob = adapter.git_blob_sha(args.site / relative)
            if relative.startswith("scripts/") and blob != accepted:
                raise ValueError("Current generator code differs from accepted source")
            expected = subprocess.check_output(["git", "-C", str(args.site), "rev-parse", f"HEAD:kyiv-air-alerts-grafana/{relative}"], text=True).strip()
            if blob != expected:
                raise ValueError("Current reference worktree drift")
            pin["verified_blob"][relative] = blob
        for name in ("dashboard_data.json", "site_derived.json"):
            relative = "data/" + name
            blob = adapter.git_blob_sha(args.site / relative)
            expected = subprocess.check_output(["git", "-C", str(args.site), "rev-parse", f"HEAD:kyiv-air-alerts-grafana/{relative}"], text=True).strip()
            if blob != expected:
                raise ValueError("Current reference data drift")
            pin["verified_blob"][relative] = blob
    original = load(args.site / "data/dashboard_data.json")
    original_derived = load(args.site / "data/site_derived.json")
    source_rows = rows
    operations = []
    if args.dst_plan:
        rows, operations = apply_dst_preview(rows, load(args.dst_plan))
    non_kyiv = [r for r in rows if r["city_key"] != "kyiv"]
    payload, diagnostics, alerts = adapter.build_projection_from_site(non_kyiv, original, cutoff, args.site)
    mods = adapter.import_site_modules(args.site)
    update = mods["update_data"]
    rolling = mods["apply_site_rolling_7d"]
    bridge = mods["apply_ukrainealarm_bridge"]
    complete_before = copy.deepcopy(payload)
    completed_month_comparison(complete_before, bridge)
    direct_diff = adapter.diff_rows(original, complete_before, max_details=20000)
    save(args.output / "22city_diff.json", direct_diff)
    frozen_bytes = (args.research / "c6_oct184_b1_source_priority_2026_10_29/frozen_october_382_198_bundle.json").read_bytes()
    bundle = b2.verify_approved_frozen_bundle(frozen_bytes, frozen_bytes)
    frozen_uids = {r["uid"] for r in bundle["source_rows"]}
    classes = load(args.classifications)
    if classes["recovery"] is not True or classes["read_only"] != "on":
        raise ValueError("Classification read-only evidence missing")
    physical = [dict(r, start_at=aware(r["start_at"]), end_at=aware(r["end_at"])) for r in source_rows if r["uid"] in frozen_uids]
    snapshot = {"episodes": physical, "classifications": classes["classifications"] or [],
                "source_links": classes["source_links"] or [], "events": classes["events"] or []}
    selected = b2.run_bundle(bundle, snapshot)
    if selected["counts"]["raw"] != 382 or selected["counts"]["display"] != 198 or selected["enrichment"]["rebinds"] != 0:
        raise ValueError("Approved frozen B2 contract drift")
    save(args.output / "kyiv_b2_selection.json", selected)
    original_kyiv = load(args.site / "data/alerts_combined.json")
    index = collections.defaultdict(list)
    for row in source_rows:
        if row["city_key"] == "kyiv":
            index[token(row)].append(row)
    boundary = aware("2026-09-30T21:00:00Z")
    prior = [r for r in original_kyiv if aware(r["start"]) < boundary]
    mapping = []
    for row in prior:
        matches = index[token(row, "start", "end")]
        mapping.append({"start": row["start"], "end": row["end"], "source_kind": row.get("source"),
                        "physical_uids": [r["uid"] for r in matches],
                        "status": "UNIQUE_EXACT_INTERVAL" if len(matches) == 1 else "UNRESOLVED",
                        "primary_source_receipt": "NOT_ASSERTED"})
        if len(matches) == 1:
            # Read interval values from Neon; the frozen Git row governs only
            # the historical display-selection/source-priority decision.
            row["start"] = aware(matches[0]["start_at"]).astimezone(update.TZ).isoformat()
            row["end"] = aware(matches[0]["end_at"]).astimezone(update.TZ).isoformat()
        else:
            raise ValueError("Historical Kyiv exact selection is unresolved")
    current = [{"start": r["start_utc"], "end": r["end_utc"], "source": r["source_kind"]}
               for r in selected["display_alerts"]]
    selected_tokens = {token(r, "start", "end") for r in current}
    extra = [r for r in original_kyiv if aware(r["start"]) >= boundary and token(r, "start", "end") not in selected_tokens]
    corroboration = []
    if args.corroborating_http:
        http = load(args.http_evidence)
        raw = args.corroborating_http.read_bytes()
        if http["http_status"] != 200 or hashlib.sha256(raw).hexdigest() != http["entity_sha256"]:
            raise ValueError("HTTP capture digest/status mismatch")
        parsed, _ = update.parse_live_history(raw.decode("utf-8"))
        published_tokens = {(a.start.astimezone(UTC), a.end.astimezone(UTC)) for a in parsed}
        for row in extra:
            key = token(row, "start", "end")
            matches = index[key]
            ok = key in published_tokens and len(matches) == 1 and key[1] <= cutoff
            corroboration.append({"start": row["start"], "end": row["end"],
                                  "physical_uids": [r["uid"] for r in matches],
                                  "publisher_present_at_capture": key in published_tokens,
                                  "exact_unique_candidate": ok,
                                  "capture_at": http["received_at_utc"],
                                  "original_ingestion_receipt": "NOT_PROVEN",
                                  "policy": "PREVIEW_ONLY_OWNER_ACCEPTANCE_REQUIRED"})
            if ok:
                current.append(row)
    candidate_kyiv = sorted(prior + current, key=lambda r: aware(r["start"]))
    alerts["kyiv"] = update.parse_committed_alerts(candidate_kyiv)
    raw_kyiv = update.build_outputs(alerts["kyiv"], cutoff.astimezone(update.TZ), dict(original["cities"]["kyiv"]["meta"]))
    kyiv = copy.deepcopy(raw_kyiv)
    mods["add_duration_unit_switch"].trim_first_partial_periods(kyiv, min(a.start.astimezone(update.TZ).date() for a in alerts["kyiv"]))
    rolling.update_city_rolling(kyiv, alerts["kyiv"])
    payload["cities"]["kyiv"] = kyiv
    for section in ("kpis", "monthly", "weekly", "daily28", "rolling30", "rolling90"):
        if section in payload or section in ("kpis", "monthly", "weekly", "daily28"):
            payload[section] = kyiv[section] if section == "weekly" else raw_kyiv[section]
    keys = payload["multicity_meta"]["production_city_keys"]
    payload["comparison"]["weekly"] = bridge.generic_comparison(payload["cities"], keys, "weekly")
    completed_month_comparison(payload, bridge)
    # Existing rolling profile functions; use physical history for every city.
    coverage = {key: rolling.first_coverage_day(payload["cities"][key], alerts[key]) for key in keys}
    ends = {key: rolling.analysis_end(payload["cities"][key]) for key in keys}
    common_start = datetime.fromisoformat(original["all_cities_table"]["meta"]["common_start"]).date()
    common_end = min(ends.values())
    for key in keys:
        payload["time_of_day_profile"]["cities"][key] = {
            "coverage_start": coverage[key].isoformat(), "analysis_end": ends[key].isoformat(),
            "source_type": payload["multicity_meta"]["cities"][key].get("source_type"),
            "periods": {p: rolling.time_profile(alerts[key], coverage[key], ends[key], n) for p, n in rolling.PROFILE_PERIODS.items()}}
        from datetime import timedelta
        payload["all_cities_table"]["cities"][key] = {"periods": {
            label: rolling.period_summary(alerts[key], common_start if length is None else max(common_start, common_end-timedelta(days=length-1)), common_end)
            for label, length in (("7d",7),("30d",30),("90d",90),("year",365),("common",None))}}
    # Reuse the accepted pure derived builder for all 23 cities. The successor
    # supports explicit Kyiv input and does not call an HTTP-fetching main().
    successor = importlib.import_module("derived_successor")
    derived_payload = successor.create_derived(payload, original_derived, alerts, cutoff, args.site, mods)
    historical = mods["build_preview_historical_daily"]
    payload["historical_daily_kpi"] = historical.produce(args.site, None, generated_at=cutoff.isoformat(),
                                                        source_override=payload, sources_override=alerts)
    payload["meta"]["generated_at"] = cutoff.astimezone(update.TZ).isoformat()
    save(args.output / "site/dashboard_data.json", payload)
    save(args.output / "site/site_derived.json", derived_payload)
    save(args.output / "site/alerts_combined.json", candidate_kyiv)
    save(args.output / "kyiv_historical_exact_selection.json", mapping)
    save(args.output / "kyiv_current_corroboration.json", corroboration)
    save(args.output / "dst_projection_plan.json", operations)
    save(args.output / "22city_union_diagnostics.json", diagnostics)
    sys.path.insert(0, str((args.research / "c6_23city_integrated_shadow_2026_10_30").resolve()))
    old_integration = importlib.import_module("integration")
    old_integration.diffs.clear()
    old_integration.diff_tree(payload, original)
    old_integration.diff_tree(derived_payload, original_derived, "$.site_derived")
    save(args.output / "full_diff.json", old_integration.diffs)
    verdict = {"status": "PARTIAL_RESEARCH", "production_cutover_allowed": False,
               "physical_receipt": receipt, "classifications_snapshot": classes["snapshot"],
               "pins": pin, "cutoff": cutoff.isoformat(), "physical_rows": len(source_rows),
               "projected_rows": len(rows), "dst_simulation": bool(operations),
               "direct_22city_diff": direct_diff["total_diff_items"],
               "full_json_path_differences": len(old_integration.diffs),
               "kyiv_historical_selection": dict(collections.Counter(r["status"] for r in mapping)),
               "kyiv_current_corroborated": sum(r["exact_unique_candidate"] for r in corroboration),
               "kyiv_current_site_only": len(extra), "suppressed_parent_rebinds": 0,
               "remaining_git_dependencies": ["historical_Kyiv_display_selection", "kyiv_threat_mix.json", "sevastopol_metadata", "casualty_track"],
               "neon_mutations": 0, "production_mutations": 0}
    save(args.output / "machine_verdict.json", verdict)
    print(json.dumps({k:v for k,v in verdict.items() if k not in ("pins",)}, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
