"""Bounded, read-only historical DST display selection. No Neon mutation.

The known stale merged parents are retained in physical Neon provenance.
Eight exact physical source witnesses already coexist with the three stale
parents. The reader may exclude only those three parents from calculation,
provided every accepted UID/legacy ID/UTC boundary and surrounding interval
membership matches exactly. This module never activates itself.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json

VERSION = "c6-dst-physical-overlap-selection-v2"

# Accepted source witnesses from 25 Oct 2026 (PR #161, C6-DST-UTC-01);
# physical Neon exact READ ONLY as observed on 2026-11-15.
EXPECTED = {
    "cherkasy": (
        ("ff046d6c-fc7e-4cd2-9470-3e5433c3d582", "a7dd6c572640b6396fb7bec7", "2026-10-25T00:06:18.166695Z", "2026-10-25T00:26:58.650073Z", False),
        ("3ef00516-4320-4a07-99d0-d5261fa46112", "cdbf2515f5abb87b26588794", "2026-10-25T01:14:53.333785Z", "2026-10-25T01:19:09.997656Z", False),
    ),
    "kharkiv": (
        ("04136e25-d835-48ed-823f-33cfe83fb541", "5e1419914aca832269aecd97", "2026-10-24T23:24:46.944947Z", "2026-10-25T00:30:17.068083Z", False),
        ("bb7d4952-52a3-45f8-a1db-13153c8f6ca3", "604d9e3f63fa9bc3cbd78adb", "2026-10-24T23:24:46.944947Z", "2026-10-25T02:22:46.862159Z", True),
        ("a6c6c128-6aea-4de5-af6c-b51066155400", "1f926bf2181429b41da57787", "2026-10-25T01:25:28.327265Z", "2026-10-25T02:22:46.862159Z", False),
    ),
    "poltava": (
        ("e72950fd-30bc-4c89-9dae-31d0cd050180", "9d82fda26301c5813fd5995e", "2026-10-25T00:06:15.155767Z", "2026-10-25T00:26:57.986096Z", False),
        ("74ba1017-63af-4137-a5ba-246795613615", "81ba41902e7642b95aacde52", "2026-10-25T00:06:15.155767Z", "2026-10-25T01:29:42.507155Z", True),
        ("842f78fc-0cf9-4452-bdc2-ddf4175481bf", "a8bb035a0a6b812384a61f9a", "2026-10-25T01:17:40.643305Z", "2026-10-25T01:29:42.507155Z", False),
    ),
    "zhytomyr": (
        ("18579c59-7291-4be1-aeae-80c9fb1534b1", "770e55ab0c608d531c7d1f05", "2026-10-25T00:06:17.978268Z", "2026-10-25T00:26:58.980319Z", False),
        ("b40c570e-f9db-4c7d-b7e4-3f7769e12a95", "3d1ae87e479c137d912f9b49", "2026-10-25T00:06:17.978268Z", "2026-10-25T01:30:52.777820Z", True),
        ("c0441b7e-ab28-412e-84c8-0bfdf1248852", "7a37899cb0e694f822b56661", "2026-10-25T01:16:21.087757Z", "2026-10-25T01:30:52.777820Z", False),
    ),
}
BAD = {e[0] for group in EXPECTED.values() for e in group if e[4]}
WITNESSES = {e[0] for group in EXPECTED.values() for e in group if not e[4]}


class Blocked(ValueError):
    pass


def aware(value):
    result = value if isinstance(value, datetime) else datetime.fromisoformat(
        str(value).replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise Blocked("DST_NAIVE_TIMESTAMP")
    return result.astimezone(timezone.utc)


def exact(row, expected, city):
    uid, legacy, start, end, _ = expected
    return (row.get("uid") == uid
            and row.get("legacy_episode_id") == legacy
            and row.get("city_key") == city
            and row.get("alert_type") == "AIR"
            and row.get("episode_state") == "closed"
            and row.get("canonicalization_version") == "alert-canonicalization-v1"
            and aware(row["start_at"]) == aware(start)
            and aware(row["end_at"]) == aware(end))


def filter_display(closed):
    """Return a new list and proof; original physical rows remain untouched."""
    index = {row.get("uid"): row for row in closed}
    if len(index) != len(closed):
        raise Blocked("DST_DUPLICATE_PHYSICAL_UID")
    windows = {}
    for city, witnesses in EXPECTED.items():
        for expected in witnesses:
            row = index.get(expected[0])
            if row is None or not exact(row, expected, city):
                raise Blocked("DST_PHYSICAL_IDENTITY_OR_BOUNDARY_DRIFT:" + city)
        good = sorted((e for e in witnesses if not e[4]), key=lambda e: aware(e[2]))
        if len(good) != 2 or not aware(good[0][3]) < aware(good[1][2]):
            raise Blocked("DST_WITNESS_SEPARATION_INVALID:" + city)
        a = min(aware(e[2]) for e in witnesses)
        z = max(aware(e[3]) for e in witnesses)
        overlapping = {row["uid"] for row in closed
                       if row.get("city_key") == city
                       and aware(row["start_at"]) < z
                       and aware(row["end_at"]) > a}
        if overlapping != {e[0] for e in witnesses}:
            raise Blocked("DST_UNEXPECTED_PHYSICAL_OVERLAP:" + city)
        windows[city] = {"physical_in_window": len(witnesses),
                         "accepted_in_window": 2}
    if len(BAD) != 3 or len(WITNESSES) != 8:
        raise Blocked("DST_EXPECTED_ID_COUNT")
    filtered = [row for row in closed if row["uid"] not in BAD]
    if len(filtered) != len(closed) - 3:
        raise Blocked("DST_BAD_PARENT_COUNT")
    selected = [row for row in filtered if row["uid"] in WITNESSES]
    if len(selected) != 8:
        raise Blocked("DST_WITNESS_COUNT")
    receipt = {
        "version": VERSION,
        "physical_neon_rows_deleted": 0,
        "excluded_from_calculation_only": sorted(BAD),
        "accepted_witness_uids": sorted(WITNESSES),
        "four_city_windows": windows,
        "unaffected_rows_preserved": len(filtered) - len(selected),
        "correction_applied_to_projection": True,
        "requires_independent_23_city_same_run_proof": True,
        "production_publication_allowed": False,
    }
    receipt["selection_sha256"] = hashlib.sha256(
        json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return filtered, receipt
