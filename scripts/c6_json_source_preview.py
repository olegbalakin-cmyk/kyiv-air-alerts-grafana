#!/usr/bin/env python3
"""Stage an isolated production-frontend preview. Never publish or collect data."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import zipfile

from scripts.c2_shadow_bundle import verify_archive

PROOF_RUN = 42487688608
PROOF_ARTIFACT = 13619973574
PROOF_MANIFEST_SHA256 = "588700a49a5af6d19df2784ce6ded8e143db9128661b2be30f6886dff6fb97f7"
SITE_SHA = "f60214c61de08cef677e90f158e2824d90bc324b"
C2_BUNDLE_SHA256 = "2e56e3af58b28ddb9450930f201c5a81f41a39327a0da57a1d6c913f0981c501"
FILES = ("dashboard_data.json", "site_derived.json", "alerts_combined.json",
         "historical-daily-kpi.json", "kyiv_threat_mix.json", "sevastopol_events.json")
RAW_BASE = 'const RAW_DATA_BASE = "https://raw.githubusercontent.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/site-prod/kyiv-air-alerts-grafana/data/";'
MARKER = "c6-preview-only.json"


class Blocked(ValueError):
    pass


def require(ok, reason):
    if not ok:
        raise Blocked(reason)


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True,
                               allow_nan=False) + "\n", encoding="utf-8")


def verify_proof(proof):
    require(proof is not None, "MISSING_NEON_PROOF_NO_GIT_FALLBACK")
    manifest = proof / "sha256_manifest.json"
    require(manifest.is_file() and digest(manifest) == PROOF_MANIFEST_SHA256,
            "UNACCEPTED_PROOF_MANIFEST")
    hashes = read(manifest)["files"]
    require(len(hashes) == 14, "PROOF_FILE_CONTRACT")
    for name, expected in hashes.items():
        path = proof / name
        require(path.resolve().is_relative_to(proof.resolve()) and path.is_file()
                and not path.is_symlink() and digest(path) == expected,
                "PROOF_FILE_MISSING_OR_CHANGED:" + name)
    verdict = read(proof / "verdict.json")
    require(verdict.get("status") == "PASS" and verdict.get("frontend_compatible") is True
            and verdict.get("physical_neon_readback_run") is True
            and verdict.get("city_count") == 23, "PHYSICAL_PROOF_NOT_PASS")
    require(set(verdict["candidate_files"]) == set(FILES), "SIX_FILE_CONTRACT")
    require(all(hashes["candidate/" + name] == verdict["candidate_files"][name]
                for name in FILES), "CANDIDATE_MANIFEST_MISMATCH")
    return verdict


def compatible(data, baseline):
    dashboard = data["dashboard_data.json"]
    keys = baseline["multicity_meta"]["production_city_keys"]
    require(len(keys) == len(set(keys)) == 23 and
            dashboard["multicity_meta"]["production_city_keys"] == keys and
            set(dashboard["cities"]) == set(keys), "CITY_BOUNDARY_CHANGED")
    for key in keys:
        city = dashboard["cities"][key]
        require(city["meta"]["timezone"] == "Europe/Kyiv", "TIMEZONE_CHANGED")
        require(all(isinstance(city.get(s), list) and city[s] for s in
                    ("kpis", "monthly", "weekly", "daily28", "rolling30", "rolling90")),
                "CITY_ROWS_MISSING:" + key)
        old = baseline["multicity_meta"]["cities"][key]
        new = dashboard["multicity_meta"]["cities"][key]
        require(all(new.get(f) == old.get(f) for f in ("source_type", "proxy_raion")),
                "EXACT_PROXY_SEMANTICS_CHANGED")
    require(all(dashboard.get(k) == baseline.get(k) for k in
                ("casualties", "casualties_by_city")), "CASUALTY_DATA_CHANGED")
    derived = data["site_derived.json"]
    require(set(derived["time_of_day_heatmap_test"]["cities"]) == set(keys) and
            set(derived["all_cities_table_test"]["cities"]) == set(keys),
            "DERIVED_CITIES_MISSING")
    history = data["historical-daily-kpi.json"]
    require(history == dashboard["historical_daily_kpi"] and
            history["meta"]["verified_count"] == 23, "HISTORICAL_INDEX_MISMATCH")
    require(isinstance(data["alerts_combined.json"], list) and
            bool(data["alerts_combined.json"]), "KYIV_INTERVALS_MISSING")


def verify_kyiv_membership(candidate, git_rows):
    def intervals(rows):
        result = []
        for row in rows:
            pair = tuple(datetime.fromisoformat(row[k].replace("Z", "+00:00"))
                         for k in ("start", "end"))
            require(all(t.tzinfo is not None for t in pair) and pair[0] < pair[1],
                    "INVALID_KYIV_INTERVAL")
            result.append(tuple(t.astimezone(timezone.utc) for t in pair))
        require(len(result) == len(set(result)), "DUPLICATE_KYIV_INTERVAL")
        return set(result)
    require(intervals(candidate) == intervals(git_rows), "KYIV_DISPLAY_MEMBERSHIP_CHANGED")


def history_release_blockers(proof, now=None):
    """The existing site needs completed history, not a new live-alert feature."""
    now = now or datetime.now(timezone.utc)
    verdict = read(proof / "verdict.json")
    gates = read(proof / "source_gates.json")
    blockers = ["OWNER_CUTOVER_NOT_AUTHORIZED"]
    for key, gate in gates.items():
        value = gate.get("source_captured_at_utc")
        captured = datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None
        # Recompute age; inherited dashboard 'fresh' flags and DB/build clocks
        # cannot certify a source capture. Match the current site's 36h ceiling.
        valid = (captured is not None and captured.tzinfo is not None and
                 0 <= (now - captured).total_seconds() <= 36 * 3600)
        if not (valid and gate.get("source_capture_verified") is True and
                gate.get("continuity_verified") is True):
            blockers.append("HISTORY_CAPTURE_OR_CONTINUITY:" + key)
    if verdict.get("dst_repair_certified") is not True:
        blockers.append("FOUR_DST_CASES_UNRESOLVED")
    return blockers


def stage(site, output, *, bundle, source="git", proof=None):
    """Only build a marked static preview; default OFF means Git, no DB access."""
    require(source in ("git", "neon"), "UNKNOWN_SOURCE")
    site, output = Path(site).resolve(), Path(output).absolute()
    proof = Path(proof).resolve() if proof is not None else None
    require(not output.is_symlink(), "OUTPUT_SYMLINK")
    output = output.resolve()
    bundle = Path(bundle).resolve()
    inputs = [site, bundle] + ([proof] if proof is not None else [])
    require(all(not output.is_relative_to(p) and not p.is_relative_to(output)
                for p in inputs), "OUTPUT_OVERLAPS_INPUT")
    if output.exists():
        require(output.is_dir() and (output / MARKER).is_file() and
                read(output / MARKER).get("kind") == "c6-isolated-static-preview-v1",
                "REFUSE_UNOWNED_OUTPUT")
    verify_archive(bundle, C2_BUNDLE_SHA256, run_id=42297035421, input_sha=SITE_SHA)
    with zipfile.ZipFile(bundle) as archive:
        git_raw = {name: archive.read("site_data/" + name) for name in FILES
                   if name != "historical-daily-kpi.json"}
    baseline = json.loads(git_raw["dashboard_data.json"])
    git_raw["historical-daily-kpi.json"] = (json.dumps(
        baseline["historical_daily_kpi"], ensure_ascii=False, sort_keys=True,
        indent=2, allow_nan=False) + "\n").encode("utf-8")
    verdict = verify_proof(proof) if source == "neon" else None
    raw = ({name: (proof / "candidate" / name).read_bytes() for name in FILES}
           if source == "neon" else git_raw)
    data = {name: json.loads(value) for name, value in raw.items()}
    compatible(data, baseline)
    verify_kyiv_membership(data["alerts_combined.json"], json.loads(git_raw["alerts_combined.json"]))
    for name in ("kyiv_threat_mix.json", "sevastopol_events.json"):
        require(raw[name] == git_raw[name], "GIT_AUXILIARY_CHANGED")
    frontend = site / "pages-preview"
    app = (frontend / "app.js").read_text(encoding="utf-8")
    require(app.count(RAW_BASE) == 1, "FRONTEND_DATA_ROUTE_DRIFT")
    require(read(frontend / "features.json").get("attack_events") is False,
            "WIP_FEATURE_ENABLED")
    html = (frontend / "index.html").read_text(encoding="utf-8")
    require(len(re.findall(r"<body\b[^>]*>", html)) == 1, "FRONTEND_BODY_DRIFT")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="c6-stage-", dir=output.parent) as td:
        build = Path(td) / "preview"
        shutil.copytree(frontend, build)
        (build / "data").mkdir()
        for name in FILES:
            (build / "data" / name).write_bytes(raw[name])
        shutil.copyfile(build / "data/historical-daily-kpi.json", build / "historical-daily-kpi.json")
        (build / "app.js").write_text(app.replace(RAW_BASE, 'const RAW_DATA_BASE = "data/";'), encoding="utf-8")
        banner = ('<aside style="padding:12px;background:#ffe69c;color:#222;text-align:center">'
                  'Статичний тест / Static preview · ' + source.upper() +
                  ' · Дані не оновлюються / Data is frozen</aside>')
        html = re.sub(r"(<body\b[^>]*>)", lambda m: m[1] + banner, html, count=1)
        (build / "index.html").write_text(html, encoding="utf-8")
        (build / "robots.txt").write_text("User-agent: *\nDisallow: /\n")
        (build / "_headers").write_text("/*\n  X-Robots-Tag: noindex, nofollow\n  Cache-Control: no-store\n")
        report = {"kind": "c6-isolated-static-preview-v1", "source": source,
                  "publication_allowed": False, "global_cutover": "NO",
                  "publication_blockers": history_release_blockers(proof) if verdict else
                      ["PREVIEW_ONLY_USE_EXISTING_GIT_PUBLICATION_FOR_PRODUCTION"],
                  "reason": "STATIC_PREVIEW_ONLY_NOT_A_RELEASE_CANDIDATE",
                  "proof_run": PROOF_RUN if verdict else None,
                  "proof_artifact": PROOF_ARTIFACT if verdict else None,
                  "git_bundle_sha256": C2_BUNDLE_SHA256,
                  "site_input_sha": SITE_SHA,
                  "input_files_sha256": {n: digest(build / "data" / n) for n in FILES},
                  "frontend_changes": ["local data base", "static preview banner"],
                  "kyiv_same_run_membership": "EXACT_INTERVAL_SET_MATCH",
                  "rollback": "Rebuild with --source git from the unchanged site input"}
        write(build / MARKER, report)
        # Preserve the old preview until the complete replacement has validated.
        previous = Path(td) / "previous"
        if output.exists():
            output.rename(previous)
        try:
            build.rename(output)
        except BaseException:
            if previous.exists():
                previous.rename(output)
            raise
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--proof", type=Path)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--source", choices=("git", "neon"),
                        default=os.environ.get("C6_JSON_SOURCE", "git"))
    args = parser.parse_args()
    try:
        result = stage(args.site, args.output, bundle=args.bundle, source=args.source, proof=args.proof)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, "C6 preview BLOCKED: " + (str(exc) if isinstance(exc, Blocked) else type(exc).__name__) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
