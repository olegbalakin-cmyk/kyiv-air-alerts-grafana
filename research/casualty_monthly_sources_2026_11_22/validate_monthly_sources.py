#!/usr/bin/env python3
"""Read-only source/month gate for a candidate monthly casualty monitoring layer.

This is NOT the production air-attack casualty generator and has no network,
publishing, promotion, GitHub Actions, or automatic-credit path.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

CITIES = (
    "kyiv", "kharkiv", "sevastopol", "cherkasy", "zhytomyr", "dnipro",
    "khmelnytskyi", "poltava", "rivne", "sumy", "vinnytsia",
    "kropyvnytskyi", "lviv", "chernihiv", "mykolaiv", "lutsk",
    "uzhhorod", "ivano-frankivsk", "ternopil", "chernivtsi",
    "kherson", "odesa", "zaporizhzhia",
)
SCOPES = {"city", "community", "oblast"}
WEAPONS = {"air_only", "all_hostilities", "unspecified"}
ROLES = {"official_local", "official_local_reported_by_media",
         "official_region", "independent_monthly"}
FIELDS = (
    "record_id", "month", "city_slug", "reported_scope", "weapon_scope",
    "deaths", "source_name", "source_url", "published_at", "source_role", "notes",
)


def read_sources(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as fp:
        reader = csv.DictReader(fp)
        if tuple(reader.fieldnames or ()) != FIELDS:
            raise ValueError("SCHEMA_MISMATCH")
        records = list(reader)
    seen = set()
    for row in records:
        ident = row["record_id"].strip()
        if not re.fullmatch(r"[a-z0-9-]{6,120}", ident) or ident in seen:
            raise ValueError("INVALID_OR_DUPLICATE_ID")
        seen.add(ident)
        if row["city_slug"] not in CITIES:
            raise ValueError(f"UNKNOWN_CITY:{ident}")
        if row["reported_scope"] not in SCOPES:
            raise ValueError(f"INVALID_GEO_SCOPE:{ident}")
        if row["weapon_scope"] not in WEAPONS:
            raise ValueError(f"INVALID_WEAPON_SCOPE:{ident}")
        if row["source_role"] not in ROLES:
            raise ValueError(f"INVALID_SOURCE_ROLE:{ident}")
        if not re.fullmatch(r"20[2-9][0-9]-(0[1-9]|1[0-2])", row["month"]):
            raise ValueError(f"INVALID_MONTH:{ident}")
        try:
            reported = date.fromisoformat(row["published_at"])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"INVALID_PUBLISHED_AT:{ident}") from exc
        if reported.strftime("%Y-%m") < row["month"]:
            raise ValueError(f"PUBLICATION_BEFORE_MONTH:{ident}")
        deaths = row["deaths"].strip()
        if not re.fullmatch(r"0|[1-9][0-9]*", deaths):
            raise ValueError(f"INVALID_DEATH_COUNT:{ident}")
        parts = urlsplit(row["source_url"].strip())
        if parts.scheme != "https" or not parts.hostname or parts.username or parts.password or parts.fragment:
            raise ValueError(f"UNSAFE_SOURCE_URL:{ident}")
        if not row["source_name"].strip():
            raise ValueError(f"UNKNOWN_SOURCE:{ident}")
        row["deaths"] = int(deaths)
    return records


def summarize(records: list[dict], month: str) -> dict:
    if not re.fullmatch(r"20[2-9][0-9]-(0[1-9]|1[0-2])", month):
        raise ValueError("INVALID_REQUESTED_MONTH")
    by_city = defaultdict(list)
    for row in records:
        if row["month"] != month:
            continue
        # NOT A PROMOTION GATE. Same-scope sources must still be reconciled.
        match = row["reported_scope"] == "city" and row["weapon_scope"] == "air_only"
        by_city[row["city_slug"]].append({
            "id": row["record_id"],
            "reported_deaths": row["deaths"],
            "scope": row["reported_scope"],
            "weapon_scope": row["weapon_scope"],
            "source": row["source_name"],
            "source_url": row["source_url"],
            "eligible_for_air_only_review": match,
            "status": "REVIEW_REQUIRED" if match else "INCOMPATIBLE_WITH_AIR_ONLY_CITY_SERIES",
        })
    cities = {}
    for city in CITIES:
        candidates = by_city.get(city, [])
        cities[city] = {
            "status": "SOURCE_CANDIDATES_REVIEW_REQUIRED" if candidates else "NO_MONTHLY_SOURCE_REPORT_NOT_ZERO",
            "candidates": candidates,
            # A missing report or incompatible source MUST NOT become deaths=0.
            "published_air_only_deaths": None,
        }
    return {
        "month": month,
        "series": "source_candidates_only_not_site_series",
        "automatic_credits": False,
        "promotion": "OFF",
        "cities_with_reports": sum(bool(by_city.get(c)) for c in CITIES),
        "cities_without_reports": sum(not by_city.get(c) for c in CITIES),
        "cities": cities,
    }


def self_test() -> None:
    example = [{
        "record_id": "sample-city-oct",
        "month": "2026-10", "city_slug": "kyiv",
        "reported_scope": "city", "weapon_scope": "all_hostilities",
        "deaths": 25, "source_name": "test", "source_url": "https://example.org/report",
    }]
    result = summarize(example, "2026-10")
    assert len(CITIES) == 23
    assert result["cities"]["kyiv"]["published_air_only_deaths"] is None
    assert not result["cities"]["kyiv"]["candidates"][0]["eligible_for_air_only_review"]
    assert result["cities"]["sumy"]["status"] == "NO_MONTHLY_SOURCE_REPORT_NOT_ZERO"
    assert result["cities"]["sumy"]["published_air_only_deaths"] is None
    narrow = dict(example[0], reported_scope="city", weapon_scope="air_only")
    follow = summarize([narrow], "2026-10")["cities"]["kyiv"]["candidates"][0]
    assert follow["eligible_for_air_only_review"]
    assert follow["status"] == "REVIEW_REQUIRED"
    assert not result["automatic_credits"] and result["promotion"] == "OFF"


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline candidate source audit (never publishes)")
    parser.add_argument("--file", type=Path, default=Path(__file__).with_name("source_examples.csv"))
    parser.add_argument("--month", default="2026-10")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
    rows = read_sources(args.file)
    print(json.dumps(summarize(rows, args.month), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
