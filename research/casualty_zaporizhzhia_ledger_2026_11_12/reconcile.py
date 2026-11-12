#!/usr/bin/env python3
"""Reconcile a frozen site-prod Zaporizhzhia casualty ledger without mutations or news HTTP.

All git reads use immutable commit SHAs. Optional HTTP reads only the production
site's static JS and the public GitHub JSON, never any publisher/article.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import subprocess
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

REPO = "olegbalakin-cmyk/kyiv-air-alerts-grafana"
PROD_SHA = "fc7261660bdee75ee59296ee94cc1189be6b1a22"
WIP_SHA = "c66c242a852d7647b6183425228cb3db2d1d088b"
ATTACK_DATE = "2026-10-10"
CANDIDATE_ID = "e0fba98b19473874e9a1d8f1"
CONFIRMED_TOTAL = 23
ROOT = "kyiv-air-alerts-grafana/"
CAS = ROOT + "data/casualties/"
CITY = CAS + "cities/zaporizhzhia/"
DATA_PATH = ROOT + "data/dashboard_data.json"
APP_PATH = ROOT + "pages-preview/app.js"
REVISIONS_PATH = CAS + "revisions.csv"
ZMONTH_PATH = CITY + "zaporizhzhia_air_attack_deaths_monthly.csv"
ZMANIFEST_PATH = CITY + "manifest.json"
WIP_QUEUE_PATH = CAS + "multicity_review_queue.json"
NETLIFY_JS_URL = "https://ukraine-air-alerts.netlify.app/app.js"
PUBLIC_JSON_URL = (
    "https://raw.githubusercontent.com/" + REPO
    + "/site-prod/" + DATA_PATH
)
OUT = Path("research/casualty_zaporizhzhia_ledger_2026_11_12/proof")


def git_read(commit: str, path: str) -> bytes:
    return subprocess.run(
        ["git", "show", commit + ":" + path],
        check=True, capture_output=True
    ).stdout


def digest(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def csv_records(blob: bytes) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(blob.decode("utf-8-sig"))))


def http_read(url: str) -> dict:
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (CasualtyLedgerReadOnly/1.0)",
        "Accept": "application/json, text/javascript, */*"
    })
    try:
        with urllib.request.urlopen(req, timeout=50) as response:
            content = response.read()
            return {
                "ok": response.status == 200,
                "status": response.status,
                "byte_count": len(content),
                "sha256": digest(content),
                "content": content,
            }
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
        return {"ok": False, "status": None, "error": str(exc), "content": b""}


def github_line_link(commit: str, path: str, data: bytes, needle: str) -> str:
    decoded = data.decode("utf-8")
    idx = decoded.find(needle)
    base = "https://github.com/" + REPO + "/blob/" + commit + "/" + path
    if idx < 0:
        return base
    return base + "#L" + str(decoded.count("\n", 0, idx) + 1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true",
                        help="Skip site and public JSON HTTP; decision stays BLOCKED")
    args = parser.parse_args()

    paths = {
        "dashboard_data_json": (PROD_SHA, DATA_PATH),
        "zaporizhzhia_manifest": (PROD_SHA, ZMANIFEST_PATH),
        "zaporizhzhia_monthly": (PROD_SHA, ZMONTH_PATH),
        "production_revisions": (PROD_SHA, REVISIONS_PATH),
        "master_20cities_manifest": (PROD_SHA, CAS + "master_20cities_manifest.json"),
        "master_20cities_wide": (PROD_SHA, CAS + "master_20cities_monthly_wide.csv"),
        "kyiv_baseline": (PROD_SHA, CAS + "baseline_monthly.csv"),
        "casualty_generator": (PROD_SHA, ROOT + "scripts/update_casualties.py"),
        "production_app_js": (PROD_SHA, APP_PATH),
        "production_review_queue": (PROD_SHA, CAS + "review_queue.json"),
        "wip_multicity_review_queue": (WIP_SHA, WIP_QUEUE_PATH),
    }
    payload = {}
    receipts = {}
    links = {}
    for label, (sha, path) in paths.items():
        content = git_read(sha, path)
        payload[label] = content
        receipts[label] = {"git_commit": sha, "path": path,
                           "bytes": len(content), "sha256": digest(content)}
        links[label] = "https://github.com/" + REPO + "/blob/" + sha + "/" + path

    data = json.loads(payload["dashboard_data_json"])
    zmanifest = json.loads(payload["zaporizhzhia_manifest"])
    zcsv = csv_records(payload["zaporizhzhia_monthly"])
    rev = csv_records(payload["production_revisions"])
    wide = csv_records(payload["master_20cities_wide"])
    master = json.loads(payload["master_20cities_manifest"])
    prod_queue = json.loads(payload["production_review_queue"])
    wip_queue = json.loads(payload["wip_multicity_review_queue"])
    z = data["casualties_by_city"]["zaporizhzhia"]
    monthly = z["monthly"]

    # Explicit routing/provenance checks: the city is NOT the Kyiv baseline
    # and is NOT one of the 20 cities in the master monthly table.
    assert "zaporizhzhia" not in wide[0]
    assert "zaporizhzhia" not in {city["slug"] for city in master["cities"]}
    assert z["meta"] == zmanifest
    assert zmanifest["city_slug"] == "zaporizhzhia"
    assert zmanifest["validated_through"] == "2026-09-18"
    assert date.fromisoformat(zmanifest["validated_through"]) < date.fromisoformat(ATTACK_DATE)
    assert len(monthly) == len(zcsv)
    for csv_item, json_item in zip(zcsv, monthly):
        assert csv_item["month"] == json_item["month"]
        assert int(csv_item["deaths_confirmed"]) == json_item["deaths"]
        assert int(csv_item["event_count"]) == json_item["event_count"]
        assert int(csv_item["late_deaths_included"]) == json_item["late_deaths_included"]
    assert sum(int(item["deaths"]) for item in monthly) == 316
    assert monthly[-1]["month"] == "2026-09"
    assert not any(item["month"] >= "2026-10" for item in monthly)
    assert not any(item["month"] >= "2026-10" for item in zcsv)
    assert not any(r.get("city_key") == "zaporizhzhia" and r.get("status") == "confirmed" for r in rev)
    assert all(item.get("city_key") != "zaporizhzhia" for item in rev)
    assert len(rev) == 1 and rev[0]["city_key"] == "sumy"
    assert all(row.get("status") != "confirmed" for row in prod_queue)
    app_js = payload["production_app_js"]
    expected_root = (
        "https://raw.githubusercontent.com/" + REPO
        + "/site-prod/kyiv-air-alerts-grafana/data/"
    )
    assert expected_root.encode() in app_js
    assert b'const DATA_URL = RAW_DATA_BASE + "dashboard_data.json"' in app_js
    assert data["casualties_by_city"]["zaporizhzhia"]["meta"]["confirmed_deaths"] == 316

    target = [r for r in wip_queue if r.get("candidate_id") == CANDIDATE_ID]
    assert len(target) == 1
    assert target[0].get("city_key") == "zaporizhzhia"
    assert target[0].get("status") == "needs_review"
    matched = []
    for r in wip_queue:
        title = r.get("title", "")
        if r.get("city_key") != "zaporizhzhia":
            continue
        if any(s in title.lower() for s in (
            "10 жовтня", "10-го жовтня", "20 загиблих", "18 загиблих",
            "23 загиблих", "до двадцяти", "двадцяти трьох"
        )):
            matched.append({
                "candidate_id": r.get("candidate_id"),
                "title": title,
                "status": r.get("status"),
                "record": github_line_link(WIP_SHA, WIP_QUEUE_PATH,
                     payload["wip_multicity_review_queue"],
                     '"candidate_id": "' + str(r.get("candidate_id")) + '"')
            })
    # WIP objects are candidates, never accounting entries.
    matched.sort(key=lambda x: (x["candidate_id"] != CANDIDATE_ID, x["title"]))
    event_links = {
        "target_candidate": github_line_link(WIP_SHA, WIP_QUEUE_PATH,
            payload["wip_multicity_review_queue"],
            '"candidate_id": "' + CANDIDATE_ID + '"'),
        "zap_2026_09_last_month": github_line_link(PROD_SHA, ZMONTH_PATH,
            payload["zaporizhzhia_monthly"], "2026-09,4,3,1"),
        "sumy_only_revision": github_line_link(PROD_SHA, REVISIONS_PATH,
            payload["production_revisions"], "casualty:sumy:"),
        "zap_validated_through": github_line_link(PROD_SHA, ZMANIFEST_PATH,
            payload["zaporizhzhia_manifest"], '"validated_through":'),
        "generator_route": github_line_link(PROD_SHA, ROOT + "scripts/update_casualties.py",
            payload["casualty_generator"], "def city_baseline_routes"),
        "generator_overlay": github_line_link(PROD_SHA, ROOT + "scripts/update_casualties.py",
            payload["casualty_generator"], "def apply_city_revision_overlay"),
        "json_zap": github_line_link(PROD_SHA, DATA_PATH,
            payload["dashboard_data_json"], '"zaporizhzhia": {'),
        "app_raw_source": github_line_link(PROD_SHA, APP_PATH, app_js,
            "const RAW_DATA_BASE")
    }

    public_js = {"ok": False, "status": None, "error": "offline"}
    public_data = {"ok": False, "status": None, "error": "offline"}
    if not args.offline:
        public_js = http_read(NETLIFY_JS_URL)
        public_data = http_read(PUBLIC_JSON_URL)
    http_proof = {
        "netlify_app_url": NETLIFY_JS_URL,
        "netlify_app": {k: v for k, v in public_js.items() if k != "content"},
        "netlify_app_matches_pinned_git": bool(
            public_js["ok"] and public_js["sha256"] == receipts["production_app_js"]["sha256"]
        ),
        "raw_public_json_url": PUBLIC_JSON_URL,
        "raw_public_json": {k: v for k, v in public_data.items() if k != "content"},
        "raw_json_matches_pinned_git": bool(
            public_data["ok"] and public_data["sha256"] == receipts["dashboard_data_json"]["sha256"]
        )
    }
    if public_data["ok"]:
        try:
            published = json.loads(public_data["content"])
            public_z = published["casualties_by_city"]["zaporizhzhia"]
            http_proof["raw_json_zap_months"] = len(public_z["monthly"])
            http_proof["raw_json_zap_last_month"] = public_z["monthly"][-1]["month"]
            http_proof["raw_json_zap_october_row"] = any(
                item["month"] == "2026-10" for item in public_z["monthly"]
            )
        except (ValueError, KeyError, TypeError) as exc:
            http_proof["raw_json_parse_error"] = str(exc)
    if public_js["ok"]:
        http_proof["netlify_app_points_to_site_prod_dashboard"] = bool(
            expected_root.encode() in public_js["content"]
            and b'const DATA_URL = RAW_DATA_BASE + "dashboard_data.json"' in public_js["content"]
        )

    physical_pass = bool(
        http_proof["netlify_app_matches_pinned_git"]
        and http_proof["raw_json_matches_pinned_git"]
        and http_proof.get("netlify_app_points_to_site_prod_dashboard")
        and http_proof.get("raw_json_zap_last_month") == "2026-09"
        and not http_proof.get("raw_json_zap_october_row", True)
    )
    decision = "RECONCILED_DELTA_FOR_REVIEW" if physical_pass else "BLOCKED_INSUFFICIENT_LEDGER_PROVENANCE"
    already_accounted = 0 if physical_pass else None
    delta = CONFIRMED_TOTAL if physical_pass else None

    result = {
        "check": "CASUALTY-ZAPORIZHZHIA-CURRENT-LEDGER-2026-11-12",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "freeze": {"site_prod": PROD_SHA, "wip": WIP_SHA},
        "attack": {"city_key": "zaporizhzhia", "attack_date": ATTACK_DATE,
                   "official_cumulative_deaths": CONFIRMED_TOTAL,
                   "candidate_id": CANDIDATE_ID},
        "ledger": {"route": "validated_city+confirmed_revision_overlay",
                   "validated_through": zmanifest["validated_through"],
                   "last_month": monthly[-1]["month"], "monthly_rows": len(monthly),
                   "baseline_total": sum(item["deaths"] for item in monthly),
                   "october_row_present": False,
                   "zaporizhzhia_confirmed_revisions": 0,
                   "all_production_confirmed_revisions": len(rev),
                   "dashboard_generated_at": data["casualties"]["meta"]["generated_at"],
                   "wip_target_status": target[0]["status"],
                   "matching_wip_candidate_records": matched,
                   "wip_is_not_published_ledger": True},
        "physical_http": http_proof,
        "file_sha256": receipts,
        "links": {**links, **event_links},
        "already_accounted": already_accounted,
        "delta_for_human_review": delta,
        "decision": decision,
        "publication_allowed": False,
        "notes": [
            "18, 20, 23 are cumulative reports on the same candidate, never additive.",
            "WIP status needs_review does not add deaths to production.",
            "The validated city baseline ends before the 10 October attack.",
            "No Zaporizhzhia confirmed revision exists in site-prod revisions.csv.",
            "A monthly aggregate alone cannot establish event identity.",
            "The independent HTTP check must match pinned app.js and JSON bytes.",
            "Research-only: no media HTTP, Neon, production writes, merge, or deploy."
        ]
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "reconciliation.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    table_rows = [
        ("Current source", "site-prod / dashboard_data.json / casualties_by_city.zaporizhzhia"),
        ("Pinned site-prod SHA", PROD_SHA),
        ("Dashboard casualty generated", result["ledger"]["dashboard_generated_at"]),
        ("Official cumulative", str(CONFIRMED_TOTAL)),
        ("Accounted for this attack", str(already_accounted) if physical_pass else "not independently proven"),
        ("Delta for review", str(delta) if physical_pass else "not computed"),
        ("Duplicates", str(len(matched)) + " possible WIP title matches, all unposted / not incident-deduplicated"),
        ("Conflicts", "18 -> 20 -> 23 cumulative updates; do not sum"),
        ("Enough evidence", "yes, immutable ledger + HTTP exact bytes" if physical_pass else "no HTTP exact-match proof"),
        ("Decision", decision),
    ]
    md = [
        "# Zaporizhzhia 10 October 2026 — pinned casualty-ledger reconciliation",
        "",
        "**Research-only; do not publish or merge.**",
        "",
        "| Metric | Value |", "| --- | --- |",
    ]
    for label, value in table_rows:
        md.append("| " + label + " | " + value.replace("|", "\\|") + " |")
    md += [
        "",
        "## Evidence boundary",
        "",
        "This check reads Git objects from two immutable SHAs, never the research "
        "already_accounted=0 snapshot. Zaporizhzhia validated-city monthly "
        "data are complete only through 18 September 2026. The only "
        "confirmed production revision is for Sumy, not Zaporizhzhia. "
        "WIP candidates are separate and cannot be counted as production changes.",
        "",
        "If and only if the public app.js and public raw JSON match the frozen "
        "Git bytes, no October entry plus the pre-attack baseline cutoff and "
        "empty Zaporizhzhia revision overlay identify zero credited deaths "
        "in the public series. The 23-death delta remains a review proposal, "
        "not a publication approval.",
        "",
        "## Exact records",
        "",
    ]
    for key, url in event_links.items():
        md.append("- " + key + ": " + url)
    md += ["", "## SHA-256 (exact bytes)", "", "| File | SHA-256 |", "| --- | --- |"]
    for name, item in receipts.items():
        md.append("| " + name + " | " + item["sha256"] + " |")
    md += [
        "", "## Public HTTP proof", "",
        "Netlify JS exact pinned match: " + str(http_proof["netlify_app_matches_pinned_git"]),
        "",
        "Public raw JSON exact pinned match: " + str(http_proof["raw_json_matches_pinned_git"]),
        "",
        "Netlify app points to site-prod data: " +
        str(http_proof.get("netlify_app_points_to_site_prod_dashboard")),
        "",
        "## WIP possible same-day candidates (not confirmed ledger entries)", ""
    ]
    for item in matched[:30]:
        md.append("- " + str(item["candidate_id"]) + " — " + item["title"] +
                  " — " + str(item["status"]) + " — " + item["record"])
    md += ["", "**Decision: " + decision + ". No statistics changed.**", ""]
    (OUT / "FINAL_REPORT.md").write_text("\n".join(md), encoding="utf-8")
    print("RESULT_JSON_START")
    print(json.dumps({k: result[k] for k in (
        "freeze", "attack", "ledger", "physical_http", "already_accounted",
        "delta_for_human_review", "decision", "publication_allowed")},
        ensure_ascii=False))
    print("RESULT_JSON_END")
    print("SHA256_FILE_REPORT_START")
    for label, item in receipts.items():
        print(label, item["sha256"])
    print("SHA256_FILE_REPORT_END")


if __name__ == "__main__":
    main()
