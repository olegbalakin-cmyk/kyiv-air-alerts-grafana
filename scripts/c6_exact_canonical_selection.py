"""Research-only C6 selection from a verified same-run C2 canonical payload.

The caller MUST first verify the immutable C2 corpus digest, receipt, run
identity, read-only Neon snapshot, and C2 row semantics. Time overlap never
establishes supersession. Unknown older rows remain in the DB/readback evidence.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
from uuid import UUID

VERSION = "alert-canonicalization-v1"


class SelectionBlocked(ValueError):
    pass


def require(ok, reason):
    if not ok:
        raise SelectionBlocked(reason)


def utc(value):
    dt = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    require(dt.tzinfo is not None, "CANONICAL_NAIVE_TIMESTAMP")
    return dt.astimezone(timezone.utc)


def select_c2_canonical_closed(c2_episodes, closed_rows, *, city_keys, ingest_committed_at):
    """Select exact C2 IDs and seven-field identities; preserve every other DB row.

    This is only an exact-run, SHA-bound projection. It is NOT a general policy
    for determining canonical status from two overlapping historical intervals.
    Post-C2 insertions are excluded from that older C2 projection only if
    created_at and updated_at prove their insertion happened AFTER C2.
    Changes to ANY row already present at that C2 cutoff remain fail-closed.
    """
    require(ingest_committed_at is not None, "CANONICAL_C2_COMMIT_REQUIRED")
    cutoff = utc(ingest_committed_at)
    require(bool(city_keys) and len(set(city_keys)) == len(city_keys),
            "CANONICAL_CITY_BOUNDARY_INVALID")
    expected = {}
    by_city = Counter()
    for episode in c2_episodes:
        key = episode.get("legacy_episode_id")
        require(isinstance(key, str) and key and key not in expected,
                "CANONICAL_C2_DUPLICATE_OR_MISSING_ID")
        require(episode.get("city_key") in city_keys and episode.get("alert_type") == "AIR" and
                episode.get("episode_state") == "closed" and
                episode.get("canonicalization_version") == VERSION and
                utc(episode["start_at"]) < utc(episode["end_at"]),
                "CANONICAL_C2_EPISODE_INVALID")
        expected[key] = episode
        by_city[episode["city_key"]] += 1
    require(set(by_city) == set(city_keys), "CANONICAL_C2_MISSING_CITY")
    seen = set()
    retained = []
    ignored_ids = []
    post_c2_inserted_ids = []
    post_c2_inserted_by_city = Counter()
    raw_by_city = Counter()
    for row in closed_rows:
        key = row.get("legacy_episode_id")
        require(row.get("city_key") in city_keys and row.get("alert_type") == "AIR" and
                row.get("episode_state") == "closed" and
                isinstance(key, str) and bool(key),
                "CANONICAL_RAW_EPISODE_INVALID")
        # A later snapshot may contain *new* episodes from later C2 runs.
        # Those episodes cannot belong to this immutable earlier C2 corpus.
        # Never accept a later mutation to a row that already existed at C2.
        updated = utc(row["updated_at"])
        raw_by_city[row["city_key"]] += 1
        if updated > cutoff:
            created = row.get("created_at")
            require(key not in expected and created is not None and
                    utc(created) > cutoff and utc(created) <= updated,
                    "CANONICAL_SNAPSHOT_OUTRUNS_C2")
            post_c2_inserted_ids.append(key)
            post_c2_inserted_by_city[row["city_key"]] += 1
            continue
        if key not in expected:
            ignored_ids.append(key)
            continue
        require(key not in seen, "CANONICAL_DUPLICATE_NEON_ID")
        src = expected[key]
        require(all(row.get(field) == src.get(field) for field in
                    ("legacy_episode_id", "city_key", "alert_type",
                     "episode_state", "canonicalization_version")) and
                utc(row["start_at"]) == utc(src["start_at"]) and
                utc(row["end_at"]) == utc(src["end_at"]),
                "CANONICAL_NEON_C2_FIELD_MISMATCH")
        try:
            UUID(str(row["uid"]))
        except (KeyError, TypeError, ValueError):
            raise SelectionBlocked("CANONICAL_NEON_UID_INVALID") from None
        retained.append(row)
        seen.add(key)
    require(len(seen) == len(expected) and seen == set(expected),
            "CANONICAL_NEON_C2_MISSING_EPISODES")
    retained_by_city = Counter(row["city_key"] for row in retained)
    require(retained_by_city == by_city, "CANONICAL_NEON_C2_CITY_MISMATCH")
    evidence = {
        "schema": "c6-exact-c2-membership-only-v1",
        "selection": "VERIFIED_C2_ID_AND_SEVEN_FIELDS",
        "temporal_overlap_deletion": False,
        "publication_allowed": False,
        "canonicalization_version": VERSION,
        "cities": len(city_keys),
        "raw_closed_episodes": len(closed_rows),
        "c2_canonical_episodes": len(retained),
        "historical_rows_not_selected": len(ignored_ids),
        "historical_rows_id_sha256": hashlib.sha256(
            "\n".join(sorted(ignored_ids)).encode("ascii")).hexdigest(),
        "post_c2_inserted_rows_not_selected": len(post_c2_inserted_ids),
        "post_c2_inserted_ids_sha256": hashlib.sha256(
            "\n".join(sorted(post_c2_inserted_ids)).encode("ascii")).hexdigest(),
        "by_city": {city: {
            "raw_closed": raw_by_city[city],
            "selected": retained_by_city[city],
            "not_selected": raw_by_city[city] - retained_by_city[city],
            "post_c2_inserted": post_c2_inserted_by_city[city],
        } for city in sorted(city_keys)},
    }
    return retained, evidence
