#!/usr/bin/env python3
"""Read-only monthly publication readiness check for verified static SEO archives.

Does not fetch sources, call Neon, write Git, or deploy Netlify. Feed it the
exact Git-only historical KPI and the LAST PUBLISHED archive manifest.
The site-prod publisher currently excludes standalone historical-daily-kpi.json,
so lack of a newer verified input is an explicit BLOCKED result.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta
import hashlib
import importlib.util
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo

CITIES_COUNT = 23
MANIFEST_SCHEMA = "verified-air-alert-html-archive-v1"
REPORT_SCHEMA = "seo-monthly-readiness-v1"


def git_blob_sha(content: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(content)).encode("ascii") + b"\0" + content).hexdigest()


def month_before(local_day: date) -> str:
    if local_day.day < 1:
        raise ValueError("Invalid day")
    return (local_day.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")


def _historical_validator():
    file = Path(__file__).with_name("build_historical_static_archive.py")
    spec = importlib.util.spec_from_file_location("seo_archive_generator", file)
    module = importlib.util.module_from_spec(spec)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load verification contract")
    spec.loader.exec_module(module)
    return module


def _base_report(now: date, source_bytes: bytes) -> dict:
    return {
        "schema": REPORT_SCHEMA,
        "as_of": now.isoformat(),
        "expected_completed_month": month_before(now),
        "source_git_blob": git_blob_sha(source_bytes),
        "decision": "BLOCKED",
        "reason": "NOT_EVALUATED",
        "updated_cities": [],
        "missing_month_cities": [],
        "production_deploy_allowed": False,
        "git_publish_allowed": False,
        "neon_access_allowed": False,
    }


def evaluate(source_bytes: bytes, published: dict | None, *, as_of: date) -> dict:
    """READY only if each of the 23 cities advances with complete verified months.

    published must be an actual published Netlify static-archive-manifest.json,
    not an unapproved preview. Caller is responsible for HTTP origin checks.
    """
    out = _base_report(as_of, source_bytes)
    try:
        source = json.loads(source_bytes)
        generated_at = source["meta"]["generated_at"]
        captured = datetime.fromisoformat(generated_at).astimezone(ZoneInfo("Europe/Kyiv"))
        date_captured = captured.date()
        out["source_generated_at"] = generated_at
    except (ValueError, TypeError, KeyError, json.JSONDecodeError, OverflowError):
        out["reason"] = "INVALID_SOURCE_METADATA"
        return out
    if captured.utcoffset() is None:
        out["reason"] = "SOURCE_TIMEZONE_MISSING"
        return out
    if date_captured > as_of:
        out["reason"] = "SOURCE_FROM_FUTURE"
        return out
    if date_captured < as_of.replace(day=1):
        out["reason"] = "SOURCE_BEFORE_MONTH_END"
        return out
    try:
        builder = _historical_validator()
        data = builder.verified_series(source)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        out["reason"] = "UNVERIFIED_SOURCE"
        out["detail"] = str(exc)[:180]
        return out
    if len(data) != CITIES_COUNT:
        out["reason"] = "NOT_ALL_CITIES_VERIFIED"
        return out
    month = out["expected_completed_month"]
    absent = sorted(slug for slug, entry in data.items()
                    if month not in [m["ym"] for m in entry["months"]])
    if absent:
        out["reason"] = "PREVIOUS_MONTH_NOT_VERIFIED_FOR_23"
        out["missing_month_cities"] = absent
        return out
    out["verified_full_months"] = sum(len(r["months"]) for r in data.values())
    out["per_city_months"] = {slug: len(r["months"]) for slug, r in sorted(data.items())}
    if published is None:
        out["reason"] = "NO_VERIFIED_PUBLISHED_BASELINE"
        return out
    if (not isinstance(published, dict) or published.get("schema") != MANIFEST_SCHEMA
        or published.get("cities") != CITIES_COUNT):
        out["reason"] = "INVALID_PUBLISHED_BASELINE"
        return out
    prior = published.get("per_city_months")
    digest = published.get("source_git_blob")
    if (not isinstance(prior, dict) or set(prior) != set(data)
        or any(not isinstance(v, int) or isinstance(v, bool) or v < 0 for v in prior.values())
        or not isinstance(digest, str) or not re.fullmatch("[a-f0-9]{40}", digest)):
        out["reason"] = "INVALID_PUBLISHED_BASELINE"
        return out
    changes = {slug: out["per_city_months"][slug] - prior[slug] for slug in data}
    if any(delta < 0 for delta in changes.values()):
        out["reason"] = "PUBLISHED_COVERAGE_REGRESSION"
        return out
    grew = sorted(slug for slug, delta in changes.items() if delta > 0)
    out["updated_cities"] = grew
    out["published_source_git_blob"] = digest
    out["published_months_by_city"] = prior
    if not grew:
        if digest == out["source_git_blob"]:
            out["decision"], out["reason"] = "NO_CHANGE", "ALREADY_PUBLISHED"
        else:
            out["reason"] = "HISTORICAL_REVISION_REQUIRES_REVIEW"
        return out
    if len(grew) != CITIES_COUNT:
        out["reason"] = "PARTIAL_CITY_MONTH_ADVANCEMENT"
        return out
    # The source validator above checks *every* claimed month against the daily
    # arrays and exact monthly summary; only then is a preview candidate ready.
    out["decision"] = "READY_FOR_DRAFT"
    out["reason"] = "ALL_23_MONTHS_VERIFIED_AND_NEW"
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--published-manifest", type=Path)
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    prior = (json.loads(args.published_manifest.read_text(encoding="utf-8"))
             if args.published_manifest else None)
    proof = evaluate(args.source.read_bytes(), prior, as_of=args.as_of)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(proof, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print("SEO_MONTHLY_READINESS", proof["decision"], proof["reason"],
          "target=" + proof["expected_completed_month"],
          "source=" + proof["source_git_blob"])
    # A valid blocked/unchanged source is an expected preflight outcome. CI fails
    # on test / I/O errors, never authorizes production publication here.


if __name__ == "__main__":
    main()
