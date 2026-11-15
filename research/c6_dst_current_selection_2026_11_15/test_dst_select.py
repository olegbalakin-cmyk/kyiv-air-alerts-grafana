"""Fail-closed four-case physical Neon → historical calculation selector."""
import copy
import unittest

from research.c6_dst_current_selection_2026_11_15.dst_select import (
    BAD, WITNESSES, EXPECTED, VERSION, Blocked, filter_display
)


def fixture():
    rows = []
    for city, matches in EXPECTED.items():
        for uid, legacy, start, end, _bad in matches:
            rows.append(dict(uid=uid, legacy_episode_id=legacy, start_at=start,
                             end_at=end, city_key=city, alert_type="AIR",
                             episode_state="closed",
                             canonicalization_version="alert-canonicalization-v1"))
    rows.append(dict(uid="0" * 36, legacy_episode_id="unrelated",
                     start_at="2026-10-25T02:45:00Z",
                     end_at="2026-10-25T03:00:00Z", city_key="kyiv",
                     alert_type="AIR", episode_state="closed",
                     canonicalization_version="alert-canonicalization-v1"))
    return rows


class CurrentPhysicalCorrection(unittest.TestCase):
    def test_three_stale_parents_excluded_without_modifying_physical(self):
        rows = fixture()
        before = copy.deepcopy(rows)
        after, proof = filter_display(rows)
        self.assertEqual(rows, before)
        self.assertEqual(len(after), len(rows) - 3)
        self.assertEqual({r["uid"] for r in after}, {r["uid"] for r in rows} - BAD)
        self.assertEqual(proof["version"], VERSION)
        self.assertEqual(proof["physical_neon_rows_deleted"], 0)
        self.assertFalse(proof["production_publication_allowed"])
        self.assertEqual(len(WITNESSES), 8)
        for city, item in proof["four_city_windows"].items():
            self.assertEqual(item["accepted_in_window"], 2)
            self.assertEqual(item["physical_in_window"], 2 if city == "cherkasy" else 3)

    def test_bad_old_parent_absent_fails(self):
        for uid in BAD:
            rows = [r for r in fixture() if r["uid"] != uid]
            with self.subTest(uid=uid), self.assertRaises(Blocked):
                filter_display(rows)

    def test_boundary_or_legacy_drift_fails(self):
        for field, value in (("end_at", "2026-10-25T03:00:00Z"),
                             ("legacy_episode_id", "wrong"),
                             ("canonicalization_version", "unknown")):
            rows = fixture()
            rows[0][field] = value
            with self.subTest(field=field), self.assertRaises(Blocked):
                filter_display(rows)

    def test_unexpected_overlap_fails(self):
        rows = fixture()
        rows.append(dict(uid="2" * 36, legacy_episode_id="unexpected",
                         city_key="poltava", alert_type="AIR",
                         canonicalization_version="alert-canonicalization-v1",
                         episode_state="closed",
                         start_at="2026-10-25T00:10:00Z",
                         end_at="2026-10-25T00:20:00Z"))
        with self.assertRaisesRegex(Blocked, "UNEXPECTED_PHYSICAL_OVERLAP"):
            filter_display(rows)

    def test_double_application_fails_closed(self):
        one, _ = filter_display(fixture())
        with self.assertRaises(Blocked):
            filter_display(one)


if __name__ == "__main__":
    unittest.main()
