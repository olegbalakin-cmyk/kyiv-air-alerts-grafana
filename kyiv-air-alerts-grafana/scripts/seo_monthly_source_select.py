#!/usr/bin/env python3
"""Choose the newest *verified* historical index from read-only site-prod files.

Standalone historical-daily-kpi.json is not currently in the C6 automatic
Git-only publisher's DELIVERED allowlist. The embedded dashboard index might
therefore be fresher. Do not mistake the old standalone file for updated data,
or silently accept an unbound embedded index.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path

from seo_monthly_archive_gate import git_blob_sha


def read_json(path: Path) -> tuple[dict, bytes]:
    data = path.read_bytes()
    obj = json.loads(data)
    if not isinstance(obj, dict):
        raise ValueError("Expected JSON dictionary")
    return obj, data


def timestamp(obj: dict) -> datetime:
    date_text = obj.get("meta", {}).get("generated_at")
    if not isinstance(date_text, str):
        raise ValueError("Missing source generated_at")
    value = datetime.fromisoformat(date_text)
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Missing timezone in generated_at")
    return value


def choose(standalone: dict, dashboard: dict) -> tuple[dict, str]:
    standalone_date = timestamp(standalone)
    nested = dashboard.get("historical_daily_kpi")
    if nested is None:
        return standalone, "standalone_historical_daily_kpi"
    if not isinstance(nested, dict):
        raise ValueError("Invalid embedded historical KPI")
    dashboard_date = timestamp(dashboard)
    nested_date = timestamp(nested)
    nested_ref = nested.get("meta", {}).get("source_dashboard_generated_at")
    if nested_ref != dashboard.get("meta", {}).get("generated_at"):
        raise ValueError("Embedded historical index not bound to dashboard generation")
    if nested_date > dashboard_date:
        raise ValueError("Embedded index newer than containing dashboard")
    if nested_date > standalone_date:
        return nested, "embedded_dashboard_historical_daily_kpi"
    if nested_date == standalone_date and nested != standalone:
        # Do not silently choose between differing statistical snapshots.
        raise ValueError("Same generation but conflicting historical indexes")
    return standalone, "standalone_historical_daily_kpi"


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--standalone", type=Path, required=True)
    p.add_argument("--dashboard", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--receipt", type=Path, required=True)
    args = p.parse_args()
    standalone, standalone_raw = read_json(args.standalone)
    dashboard, dashboard_raw = read_json(args.dashboard)
    selected, source_kind = choose(standalone, dashboard)
    if source_kind == "standalone_historical_daily_kpi":
        selected_raw = standalone_raw
    else:
        # This normalized extraction is an explicit *derived* blob, not a file
        # claiming to have been committed separately to site-prod.
        selected_raw = (json.dumps(selected, ensure_ascii=False, sort_keys=True,
                                   separators=(",", ":")) + "\n").encode("utf-8")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(selected_raw)
    receipt = {
        "schema": "seo-monthly-readonly-selection-v1",
        "selected_from": source_kind,
        "selected_generated_at": selected["meta"]["generated_at"],
        "selected_derived_blob": git_blob_sha(selected_raw),
        "standalone_git_blob": git_blob_sha(standalone_raw),
        "dashboard_git_blob": git_blob_sha(dashboard_raw),
        "standalone_generated_at": standalone["meta"]["generated_at"],
        "dashboard_generated_at": dashboard["meta"]["generated_at"],
        "no_production_mutation": True,
    }
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt, ensure_ascii=False, indent=2,
                                      sort_keys=True) + "\n", encoding="utf-8")
    print("SEO_MONTHLY_INPUT_SELECTION", source_kind,
          "generated_at=" + receipt["selected_generated_at"],
          "blob=" + receipt["selected_derived_blob"])


if __name__ == "__main__":
    main()
