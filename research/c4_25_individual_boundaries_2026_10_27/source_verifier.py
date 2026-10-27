#!/usr/bin/env python3
"""Read-only 25-case source verification. No DB access, no persistent writes."""
import csv
import hashlib
import io
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = Path(__file__).with_name("registry.json")
OUT = Path(os.environ.get("C4_OUTPUT_PATH", "/tmp/c4_source_result.json"))
PRODUCTION_SHA = "634fc6beffbcdf76026d64b9866314fdb53ab0e4"
VADIMKIN_COMMIT = "0b243d3986da01e176ff2a3e7d7bc669652a1065"
VADIMKIN_BLOB = "71d70c0ca54968f530d596cf315616fa858800e1"
VADIMKIN_URL = ("https://raw.githubusercontent.com/Vadimkin/"
    "ukrainian-air-raid-sirens-dataset/" + VADIMKIN_COMMIT +
    "/datasets/official_data_uk.csv")
KYIV_URL = ("https://data.kyivcity.gov.ua/dataset/"
    "statystyka-povitrianykh-tryvoh-u-misti-kyievi-dep-municipal/"
    "resource/5e4fb8a8-f0c8-4a12-885f-192d1f0dba75/data/download")
KYIV_TZ = ZoneInfo("Europe/Kyiv")
UTC = timezone.utc
CONFIG = {
    "lviv": {"oblast": "Львівська область", "raion": "Львівський район",
             "coverage": "2025-09-01"},
    "sumy": {"oblast": "Сумська область", "raion": "Сумський район",
             "coverage": "2025-08-06"},
    "kharkiv": {"hromada": "м. Харків та Харківська територіальна громада",
                "valid_from": "2025-02-17T19:02:05+00:00"},
    "zaporizhzhia": {"hromada": "м. Запоріжжя та Запорізька територіальна громада",
                     "valid_from": "2025-03-19T14:25:36+00:00"},
}

def parse_dt(text, local_naive=False):
    d = datetime.fromisoformat(str(text).strip().replace("Z", "+00:00"))
    if d.tzinfo is None:
        if not local_naive:
            raise ValueError("No timezone: " + str(text))
        d = d.replace(tzinfo=KYIV_TZ)
    return d.astimezone(UTC)

def stamp(t):
    return t.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")

def precision(text):
    t = str(text).split("+")[0].split("Z")[0]
    return len(t.split(".", 1)[1]) if "." in t else 0

def fetch(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 C4-source-verification-readonly",
        "Accept": "application/json,text/csv,*/*"})
    with urllib.request.urlopen(req, timeout=150) as rsp:
        return rsp.read()

def sha_meta(raw, uri, **kwargs):
    return {"uri": uri, "sha256": hashlib.sha256(raw).hexdigest(),
            "byte_count": len(raw), "retrieved_utc": stamp(datetime.now(UTC)),
            **kwargs}

def episode(start, end, source, refs, levels=None, ps=None, pe=None):
    return {"s": start, "e": end, "source": source,
            "raw_rows": refs, "levels": levels or [],
            "timestamp_precision_start": ps, "timestamp_precision_end": pe}

def episode_out(ep):
    return {"start_utc": stamp(ep["s"]), "end_utc": stamp(ep["e"]),
            "source": ep["source"], "raw_rows": ep["raw_rows"][:12],
            "raw_row_count": len(ep["raw_rows"]), "levels": sorted(set(ep["levels"])),
            "source_precision_start": ep["timestamp_precision_start"],
            "source_precision_end": ep["timestamp_precision_end"]}

def from_vadimkin(raw):
    records = {k: [] for k in CONFIG}
    seen = {k: set() for k in CONFIG}
    text = raw.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    fieldnames = list(reader.fieldnames or [])
    diagnostics = {"input_rows": 0, "filtered": {k: 0 for k in CONFIG}}
    for ix, row in enumerate(reader, 2):
        diagnostics["input_rows"] += 1
        level = (row.get("level") or "").strip()
        oblast = (row.get("oblast") or "").strip()
        hromada = (row.get("hromada") or "").strip()
        raion = (row.get("raion") or "").strip()
        for city, cfg in CONFIG.items():
            if city in ("lviv", "sumy"):
                if oblast != cfg["oblast"] or not (
                    level == "oblast" or (level == "raion" and raion == cfg["raion"])):
                    continue
            elif level != "hromada" or hromada != cfg["hromada"]:
                continue
            a = (row.get("started_at") or "").strip()
            b = (row.get("finished_at") or "").strip()
            if not a or not b:
                continue
            key = (level, a, b) if city in ("lviv", "sumy") else (a, b)
            if key in seen[city]:
                continue
            try:
                st, en = parse_dt(a), parse_dt(b)
            except ValueError:
                continue
            if en <= st:
                continue
            if city in ("lviv", "sumy"):
                cutoff = parse_dt(cfg["coverage"] + "T00:00:00", local_naive=True)
                if en <= cutoff:
                    continue
                if st < cutoff:
                    st = cutoff
            elif st < parse_dt(cfg["valid_from"]):
                continue
            seen[city].add(key)
            records[city].append(episode(st, en, "vadimkin_official_data_uk",
                [ix], [level], precision(a), precision(b)))
            diagnostics["filtered"][city] += 1
    for city in ("kharkiv", "zaporizhzhia"):
        records[city].sort(key=lambda e: (e["s"], e["e"]))
    for city in ("lviv", "sumy"):
        merged = []
        for ep in sorted(records[city], key=lambda e: (e["s"], e["e"])):
            if merged and ep["s"] <= merged[-1]["e"]:
                prev = merged[-1]
                if ep["e"] > prev["e"]:
                    prev["e"] = ep["e"]
                    prev["timestamp_precision_end"] = ep["timestamp_precision_end"]
                prev["raw_rows"] += ep["raw_rows"]
                prev["levels"] += ep["levels"]
            else:
                merged.append(ep)
        records[city] = merged
    return records, fieldnames, diagnostics

def from_kyiv(raw):
    data = json.loads(raw.decode("utf-8-sig"))
    if not isinstance(data, list):
        raise ValueError("Expected Kyiv municipal JSON list")
    eps = []
    type_counts = {}
    for ix, row in enumerate(data):
        if not isinstance(row, dict):
            continue
        t = row.get("type")
        type_counts[str(t)] = type_counts.get(str(t), 0) + 1
        if t != "Повітряна тривога":
            continue
        a, b = row.get("dateTimeStart"), row.get("dateTimeEnd")
        if not a or not b:
            continue
        try:
            st, en = parse_dt(a, local_naive=True), parse_dt(b, local_naive=True)
        except ValueError:
            continue
        if en <= st:
            continue
        eps.append(episode(st, en, "kyiv_municipal_airAlerts",
            [ix], ["city_kyiv"], precision(a), precision(b)))
    eps.sort(key=lambda e: (e["s"], e["e"]))
    return eps, {"input_rows": len(data), "parsed_AIR": len(eps), "types": type_counts}

def verified_episodes_for_original(episodes, original, city):
    st = parse_dt(original["start_at"])
    en = parse_dt(original["end_at"])
    if city == "kyiv":
        # The original Kyiv crosswalk has minute-exact, not second-exact, times.
        matches = [i for i, ep in enumerate(episodes) if
                   st <= ep["s"] < st + timedelta(minutes=1) and
                   en <= ep["e"] < en + timedelta(minutes=1)]
        method = "MINUTE_BUCKET_ONLY_NOT_EXACT_IDENTITY"
    else:
        # Time proximity here is ONLY an investigative witness, NEVER a parent binding.
        matches = [i for i, ep in enumerate(episodes) if
                   abs((ep["s"] - st).total_seconds()) <= 120 and
                   abs((ep["e"] - en).total_seconds()) <= 120]
        method = "TIME_PROXIMITY_INVESTIGATIVE_ONLY_NOT_BINDING"
    if len(matches) == 1:
        ix = matches[0]
        return ix, method, [{
            "start_delta_seconds": round((episodes[ix]["s"]-st).total_seconds(), 6),
            "end_delta_seconds": round((episodes[ix]["e"]-en).total_seconds(), 6),
            "episode": episode_out(episodes[ix])}]
    return None, ("AMBIGUOUS" if matches else "NO_SOURCE_TIME_MATCH"), [
        episode_out(episodes[i]) for i in matches[:5]]

def compare_candidate(candidate, source_ep):
    if not candidate or source_ep is None:
        return "NOT_CHECKED"
    exact = (parse_dt(candidate["start_at"]) == source_ep["s"] and
             parse_dt(candidate["end_at"]) == source_ep["e"])
    return "SOURCE_EXACT_MATCH" if exact else "SOURCE_DIFFERENT_BOUNDARIES"

def main():
    original = json.loads(REGISTRY.read_text(encoding="utf-8"))
    sources = {}
    source_meta = {}
    failures = {}
    try:
        raw = fetch(VADIMKIN_URL)
        actual_blob = hashlib.sha1(
            ("blob " + str(len(raw)) + "\0").encode() + raw).hexdigest()
        if actual_blob != VADIMKIN_BLOB:
            raise RuntimeError("Pinned Vadimkin blob mismatch: " + actual_blob)
        vad, columns, diagnostics = from_vadimkin(raw)
        sources.update(vad)
        source_meta["vadimkin"] = sha_meta(raw, VADIMKIN_URL,
            github_blob=actual_blob, github_commit=VADIMKIN_COMMIT,
            csv_columns=columns, diagnostics=diagnostics,
            normalized_episodes_by_city={k: len(v) for k, v in vad.items()})
    except Exception as e:
        failures["vadimkin"] = type(e).__name__ + ": " + str(e)[:500]
    try:
        raw = fetch(KYIV_URL)
        kyiv, diag = from_kyiv(raw)
        if not kyiv:
            raise RuntimeError("Official Kyiv source returned zero AIR episodes")
        sources["kyiv"] = kyiv
        source_meta["kyiv"] = sha_meta(raw, KYIV_URL, diagnostics=diag,
            source_kind="MUNICIPAL_RAW_JSON")
    except Exception as e:
        failures["kyiv"] = type(e).__name__ + ": " + str(e)[:500]

    prod_path = (ROOT / "site-prod-snapshot/kyiv-air-alerts-grafana/data/"
                 "alerts_combined.json")
    production = []
    if prod_path.exists():
        production = json.loads(prod_path.read_text(encoding="utf-8"))
    records = []
    for case in original["records"]:
        n, city = case["ordinal"], case["city"]
        entry = {"ordinal": n, "city": city,
            "classification_uid": case["classification_uid"],
            "original_id": case["original"]["legacy_episode_id"],
            "original_start_utc": case["original"]["start_at"],
            "original_end_utc": case["original"]["end_at"],
            "source_available": city in sources,
            "source_authority": "kyiv" if city == "kyiv" else "vadimkin",
            "old_candidate_A_uid": case["candidate_A"]["episode_uid"],
            "old_candidate_B_uid": case["candidate_B"]["episode_uid"],
            "boundary_A": None, "boundary_B": None,
            "all_interior_source_episodes": [],
            "source_original_correspondence": None,
            "production_json_evidence": None,
            "neon_full_interval_rows": None,
            "attack_event_dependency_closure": None,
            "source_status": "SOURCE_UNAVAILABLE",
            "ready_for_repair": False,
            "source_blockers": []}
        eps = sources.get(city, [])
        if not eps:
            entry["source_blockers"].append("SOURCE_DOWNLOAD_OR_PARSE_FAILURE")
            records.append(entry)
            continue
        original_row = case["original"]
        idx, matching, candidate_matches = verified_episodes_for_original(eps, original_row, city)
        entry["source_original_correspondence"] = {
            "kind": matching, "candidate_source_episodes": candidate_matches}
        st, en = parse_dt(original_row["start_at"]), parse_dt(original_row["end_at"])
        if idx is not None:
            aidx, bidx = idx - 1, idx + 1
        else:
            left = [i for i, e in enumerate(eps) if e["e"] <= st]
            right = [i for i, e in enumerate(eps) if e["s"] >= en]
            aidx, bidx = (left[-1] if left else -1), (right[0] if right else len(eps))
        if aidx < 0 or bidx >= len(eps) or aidx >= bidx:
            entry["source_status"] = "BOUNDARY_UNVERIFIED"
            entry["source_blockers"].append("MISSING_FULL_SOURCE_A_OR_B")
            records.append(entry)
            continue
        a, b = eps[aidx], eps[bidx]
        entry["boundary_A"] = episode_out(a)
        entry["boundary_B"] = episode_out(b)
        entry["A_old_neon_candidate_comparison"] = compare_candidate(case["candidate_A"], a)
        entry["B_old_neon_candidate_comparison"] = compare_candidate(case["candidate_B"], b)
        inner = eps[aidx + 1:bidx]
        entry["all_interior_source_episodes"] = [episode_out(e) for e in inner]
        entry["interior_episode_count"] = len(inner)
        if not inner:
            entry["source_blockers"].append("NO_SOURCE_EPISODES_INSIDE_VERIFIED_BOUNDS")
        if idx is None:
            entry["source_blockers"].append("ORIGINAL_SOURCE_IDENTITY_NOT_EXACTLY_CORROBORATED")
        elif city != "kyiv":
            # Original parent old-precision identity is not source-verified.
            entry["source_blockers"].append("ORIGINAL_PARENT_ID_NOT_SOURCE_EXACT")
        if city == "kyiv":
            json_rows = []
            for x in production:
                try:
                    xs, xe = parse_dt(x["start"]), parse_dt(x["end"])
                except (KeyError, ValueError):
                    continue
                if a["s"] <= xs and xe <= b["e"]:
                    json_rows.append({"start_utc": stamp(xs),
                                     "end_utc": stamp(xe),
                                     "recorded_source": x.get("source")})
            entry["production_json_evidence"] = {
                "kind": "LITERAL_ALERTS_COMBINED_LIST",
                "rows_inclusive_AB": json_rows,
                "all_source_episodes_exactly_present": all(
                    any(j["start_utc"] == stamp(i["s"]) and
                        j["end_utc"] == stamp(i["e"]) for j in json_rows)
                    for i in eps[aidx:bidx+1])}
        else:
            entry["production_json_evidence"] = {
                "kind": "AGGREGATED_DASHBOARD_NOT_LITERAL_EPISODE_LIST",
                "expected_from_current_producer_method": "Vadimkin hromada or raion/oblast union",
                "literal_episode_comparison": "NOT_APPLICABLE"}
        entry["source_status"] = "SOURCE_BOUNDS_RECONSTRUCTED"
        # Canonical parent full Neon readback & dependent FK closure MUST precede owner-review repair.
        entry["source_blockers"].append("NEON_FULL_INTERVAL_AND_DEPENDENCY_READBACK_PENDING")
        if city in ("lviv", "sumy"):
            entry["source_blockers"].append("RAION_PROXY_GEOGRAPHY_AND_API_REFINEMENT_REVIEW")
        records.append(entry)
    result = {"schema_version": "c4-readonly-source-reconstruction-v1",
        "observed_at_utc": stamp(datetime.now(UTC)),
        "baseline_research_commit": "251cb2de011f1728cc9a6b02184271acd5f11dc8",
        "production_snapshot_commit": PRODUCTION_SHA,
        "source_metadata": source_meta, "source_failures": failures,
        "records": records,
        "counters": {"cases": len(records),
            "source_bounds_reconstructed": sum(
                r["source_status"] == "SOURCE_BOUNDS_RECONSTRUCTED" for r in records),
            "ready_for_repair": 0,
            "public_source_failures": sorted(failures)}}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("C4_SOURCE_META|" + json.dumps(
        {"sources": source_meta, "failures": failures, "counters": result["counters"]},
        ensure_ascii=False, separators=(",", ":")), flush=True)
    for record in records:
        print("C4_CASE|" + json.dumps(
            record, ensure_ascii=False, separators=(",", ":")), flush=True)
    print("C4_READONLY_VERIFICATION_COMPLETE", flush=True)
    if len(records) != 25:
        sys.exit(2)

if __name__ == "__main__":
    main()
