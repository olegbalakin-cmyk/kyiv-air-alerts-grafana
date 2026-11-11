"""C6 exact-run closed episode selection; offline-only, no SQL, HTTP or writes."""
import copy
import hashlib
import unittest
from datetime import datetime, timezone
from uuid import UUID

from scripts.c6_exact_canonical_selection import (
    SelectionBlocked, select_c2_canonical_closed,
)

CUT = "2026-11-11T16:34:13.678Z"
VERSION = "alert-canonicalization-v1"


def entry(legacy_id, city, start, end, *, uid=None, stamp="2026-11-11T16:34:11Z"):
    source = {
        "legacy_episode_id": legacy_id, "city_key": city, "alert_type": "AIR",
        "episode_state": "closed", "start_at": start, "end_at": end,
        "canonicalization_version": VERSION,
    }
    row = {
        **source, "uid": uid or str(UUID(int=int(hashlib.sha256(legacy_id.encode()).hexdigest()[:16], 16))),
        "updated_at": stamp,
    }
    return source, row


class CanonicalSelectionTests(unittest.TestCase):
    def sample(self):
        # Distinct, REAL overlapping events may both be canonical.
        a, aa = entry("a", "kyiv", "2026-10-01T10:00:00Z", "2026-10-01T11:00:00Z")
        b, bb = entry("b", "kyiv", "2026-10-01T10:30:00Z", "2026-10-01T11:30:00Z")
        c, cc = entry("c", "sumy", "2026-10-01T13:00:00Z", "2026-10-01T14:00:00Z")
        _, stale = entry("old", "kyiv", "2026-10-01T10:05:00Z", "2026-10-01T10:20:00Z")
        return [a, b, c], [aa, stale, bb, cc]

    def choose(self, episodes, rows):
        return select_c2_canonical_closed(
            episodes, rows, city_keys=["kyiv", "sumy"], ingest_committed_at=CUT)

    def test_distinct_overlapping_canonical_events_both_survive(self):
        e, rows = self.sample()
        kept, proof = self.choose(e, rows)
        self.assertEqual({r["legacy_episode_id"] for r in kept}, {"a", "b", "c"})
        self.assertEqual(proof["historical_rows_not_selected"], 1)
        self.assertFalse(proof["temporal_overlap_deletion"])
        self.assertFalse(proof["publication_allowed"])

    def test_newer_time_does_not_override_corpus_membership(self):
        e, rows = self.sample()
        rows[1]["updated_at"] = "2026-11-11T16:34:12Z"
        kept, _ = self.choose(e, rows)
        self.assertEqual(len(kept), 3)

    def test_duplicate_and_missing_ids_fail_closed(self):
        e, rows = self.sample()
        with self.assertRaisesRegex(SelectionBlocked, "DUPLICATE"):
            self.choose(e, rows + [rows[0]])
        with self.assertRaisesRegex(SelectionBlocked, "MISSING_EPISODES"):
            self.choose(e, rows[:-1])
        with self.assertRaisesRegex(SelectionBlocked, "C2_DUPLICATE"):
            self.choose(e + [e[0]], rows)

    def test_semantic_tamper_fails_closed(self):
        e, rows = self.sample()
        for key, value in (("start_at", "2026-10-01T11:00:01Z"),
                           ("episode_state", "open"), ("canonicalization_version", "v2"),
                           ("city_key", "sumy")):
            other = copy.deepcopy(rows)
            other[0][key] = value
            with self.subTest(key=key), self.assertRaises(SelectionBlocked):
                self.choose(e, other)

    def test_latest_db_update_and_naive_time_fail_closed(self):
        e, rows = self.sample()
        rows[1]["updated_at"] = "2026-11-11T16:35:00Z"
        with self.assertRaisesRegex(SelectionBlocked, "OUTRUNS_C2"):
            self.choose(e, rows)
        rows[1]["updated_at"] = "2026-11-11T16:34:11"
        with self.assertRaisesRegex(SelectionBlocked, "NAIVE_TIMESTAMP"):
            self.choose(e, rows)

    def test_missing_city_and_bad_uid_fail_closed(self):
        e, rows = self.sample()
        with self.assertRaisesRegex(SelectionBlocked, "MISSING_CITY"):
            self.choose(e[:2], rows)
        rows[0]["uid"] = "bad-uuid"
        with self.assertRaisesRegex(SelectionBlocked, "UID_INVALID"):
            self.choose(e, rows)

    def test_history_is_never_removed_from_input(self):
        e, rows = self.sample()
        copy_rows = copy.deepcopy(rows)
        self.choose(e, rows)
        self.assertEqual(rows, copy_rows)
