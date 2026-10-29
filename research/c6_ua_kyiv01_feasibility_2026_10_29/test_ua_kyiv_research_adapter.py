"""Synthetic offline tests ONLY. Fixtures do not attest to actual UkraineAlarm IDs/HTTP."""
import unittest

from ua_kyiv_research_adapter import (
    PollJournal, SchemaError, ScopeNotProven, assess_transport, compare_exact,
    current_air, history_air, iso, next_safe_request_time, region_nodes, utc,
    verified_city_scope,
)

CITY = "synthetic-city-9001"
OBLAST = "synthetic-oblast-9002"
TREE = {"states": [
    {"regionId": CITY, "regionName": "м. Київ", "regionType": "State",
     "regionChildIds": []},
    {"regionId": OBLAST, "regionName": "Київська область", "regionType": "State",
     "regionChildIds": [
         {"regionId": "synthetic-raion", "regionName": "Бучанський район",
          "regionType": "District", "regionChildIds": []}
     ]},
]}


def hist_row(start, end, typ="AIR"):
    return {"alertType": typ, "startDate": start, "endDate": end}


def status(active=True, reasons=None, *, show_reason=True, typ="AIR"):
    alert = {"type": typ}
    if reasons is not None or show_reason:
        alert["activeAlertLevels"] = ([{"alertLevel": "Red", "reason": reasons}]
                                       if show_reason else [])
    return {"regionId": CITY, "regionName": "м. Київ", "activeAlerts": [alert] if active else []}


class RegionTests(unittest.TestCase):
    def test_region_tree_keeps_distinct_city_oblast_and_ancestors(self):
        nodes = region_nodes(TREE)
        self.assertEqual(len(nodes), 3)
        self.assertEqual(nodes[-1]["ancestors"], ["Київська область"])
        self.assertNotEqual(nodes[0]["regionId"], nodes[1]["regionId"])

    def test_exact_scope_requires_primary_sha_and_independent_parity(self):
        for sha, parity in [(None, True), ("sha256-of-SYNTHETIC-payload", False)]:
            with self.assertRaises(ScopeNotProven):
                verified_city_scope(TREE, CITY, primary_tree_hash=sha,
                                    independent_city_scope_parity=parity)

    def test_synthetic_only_positive_city_scope(self):
        city = verified_city_scope(TREE, CITY,
            primary_tree_hash="synthetic-sha-not-live",
            independent_city_scope_parity=True)
        self.assertEqual(city["regionId"], CITY)

    def test_oblast_or_raion_never_resolves_as_city(self):
        for rid in (OBLAST, "synthetic-raion", "147"):
            with self.assertRaises(ScopeNotProven):
                verified_city_scope(TREE, rid, primary_tree_hash="synthetic",
                                    independent_city_scope_parity=True)

    def test_same_name_beneath_oblast_is_rejected(self):
        nested = {"states": [
            {"regionId": OBLAST, "regionName": "Київська область", "regionType": "State",
             "regionChildIds": [{"regionId": CITY, "regionName": "м. Київ",
                                  "regionType": "Community"}]},
            {"regionId": "other", "regionName": "Київ", "regionType": "State"},
        ]}
        with self.assertRaises(ScopeNotProven):
            verified_city_scope(nested, CITY, primary_tree_hash="synthetic",
                                independent_city_scope_parity=True)

    def test_malformed_tree_rejected(self):
        with self.assertRaises(SchemaError):
            region_nodes({"states": [{"regionId": "x", "regionName": ""}]})


class CurrentStateTests(unittest.TestCase):
    def test_air_on_and_off(self):
        self.assertTrue(current_air(status(), CITY)["active"])
        self.assertFalse(current_air(status(False), CITY)["active"])

    def test_artillery_does_not_count_as_air(self):
        self.assertFalse(current_air(status(True, typ="ARTILLERY"), CITY)["active"])

    def test_reason_raw_values_not_taxonomy(self):
        p = status(True, ["SYNTHETIC_DRONE", "SYNTHETIC_MISSILE"])
        parsed = current_air(p, CITY)
        self.assertEqual(parsed["reasons"], ["SYNTHETIC_DRONE", "SYNTHETIC_MISSILE"])
        self.assertTrue(parsed["reason_field_seen"])

    def test_absent_reason_does_not_mean_no_threat(self):
        got = current_air(status(True, show_reason=False), CITY)
        self.assertTrue(got["active"])
        self.assertTrue(got["reason_field_unknown"])
        self.assertFalse(got["reason_field_seen"])

    def test_wrong_region_or_missing_active_alerts_fails_closed(self):
        with self.assertRaises(ScopeNotProven):
            current_air({"regionId": OBLAST, "activeAlerts": []}, CITY)
        with self.assertRaises(SchemaError):
            current_air({"regionId": CITY}, CITY)

    def test_reason_changes_do_not_create_air_episode(self):
        j = PollJournal(CITY)
        t = ["2026-10-25T00:00:00Z", "2026-10-25T00:01:00Z",
             "2026-10-25T00:02:00Z", "2026-10-25T00:03:00Z"]
        self.assertEqual(j.observe(t[0], current_air(status(True, ["A"]), CITY))[0]["event"],
                         "AIR_ON_OBSERVED")
        self.assertEqual(j.observe(t[1], current_air(status(True, ["B"]), CITY))[0]["event"],
                         "REASONS_CHANGED_OBSERVED")
        self.assertEqual(j.observe(t[2], current_air(status(False), CITY))[0]["event"],
                         "AIR_OFF_OBSERVED")
        self.assertEqual(j.observe(t[3], current_air(status(True, ["A"]), CITY))[0]["event"],
                         "AIR_ON_OBSERVED")
        self.assertEqual([e["episode_index"] for e in j.events], [1, 1, 1, 2])

    def test_repeated_poll_idempotent(self):
        j = PollJournal(CITY)
        snap = current_air(status(True, ["A"]), CITY)
        self.assertEqual(len(j.observe("2026-10-01T09:00:00Z", snap)), 1)
        self.assertEqual(j.observe("2026-10-01T09:00:00Z", snap), [])
        self.assertEqual(j.observe("2026-10-01T09:01:00Z", snap), [])
        self.assertEqual(len(j.events), 1)
        off = current_air(status(False), CITY)
        self.assertEqual(len(j.observe("2026-10-01T09:02:00Z", off)), 1)
        self.assertEqual(j.observe("2026-10-01T09:02:00Z", off), [])

    def test_reason_disappears_without_off(self):
        j = PollJournal(CITY)
        j.observe("2026-10-01T09:00:00Z", current_air(status(True, ["A"]), CITY))
        emitted = j.observe("2026-10-01T09:00:10Z", current_air(
            status(True, show_reason=False), CITY))
        self.assertEqual(emitted[0]["event"], "REASONS_CHANGED_OBSERVED")
        self.assertIsNone(emitted[0]["reasons"])
        self.assertEqual(j.episode_index, 1)

    def test_out_of_order_poll_fails_closed(self):
        j = PollJournal(CITY)
        j.observe("2026-10-01T09:00:00Z", current_air(status(False), CITY))
        with self.assertRaises(SchemaError):
            j.observe("2026-10-01T08:00:00Z", current_air(status(True), CITY))


class HistoryTests(unittest.TestCase):
    def test_finished_air_filter_and_idempotent_duplication(self):
        p = {"regionId": CITY, "alarms": [
            hist_row("2026-10-26T00:32:34Z", "2026-10-26T00:47:49Z"),
            hist_row("2026-10-26T00:32:34Z", "2026-10-26T00:47:49Z"),
            hist_row("2026-10-26T01:00:00Z", "2026-10-26T01:15:00Z", "CHEMICAL"),
        ]}
        got = history_air(p, CITY)
        self.assertEqual(len(got["completed"]), 1)
        self.assertEqual(got["air_rows"], 2)
        self.assertFalse(got["window_truncation_possible"])

    def test_open_air_is_not_given_fabricated_off(self):
        p = {"regionId": CITY, "alarms": [
            hist_row("2026-10-29T10:00:00Z", None),
        ]}
        got = history_air(p, CITY)
        self.assertEqual(got["open_air_rows"], 1)
        self.assertEqual(got["completed"], [])

    def test_repeated_on_off_stay_separate(self):
        p = {"regionId": CITY, "alarms": [
            hist_row("2026-10-01T00:00:00Z", "2026-10-01T01:00:00Z"),
            hist_row("2026-10-01T02:00:00Z", "2026-10-01T03:00:00Z"),
        ]}
        self.assertEqual(len(history_air(p, CITY)["completed"]), 2)

    def test_history_25_not_full_archive(self):
        p = {"regionId": CITY, "alarms": [
            hist_row(f"2026-10-{day:02d}T00:00:00Z",
                     f"2026-10-{day:02d}T00:05:00Z") for day in range(1, 26)
        ]}
        got = history_air(p, CITY)
        self.assertEqual(len(got["completed"]), 25)
        self.assertTrue(got["window_truncation_possible"])
        result = compare_exact(got, [
            {"start": "2026-09-30T00:00:00Z", "end": "2026-09-30T00:05:00Z"},
            {"start": "2026-10-05T00:00:00Z", "end": "2026-10-05T00:05:00Z"},
        ])
        self.assertEqual((result["matched"], result["eligible"], result["out_of_coverage"]),
                         (1, 1, 1))
        self.assertFalse(result["full_city_completeness_proven"])

    def test_seconds_exact_mismatch_not_rounded_to_minute(self):
        p = {"regionId": CITY, "alarms": [
            hist_row("2026-10-01T00:00:03Z", "2026-10-01T00:07:15Z"),
            hist_row("2026-10-02T00:00:03Z", "2026-10-02T00:07:15Z"),
        ]}
        got = compare_exact(history_air(p, CITY), [
            {"start": "2026-10-01T00:00:03Z", "end": "2026-10-01T00:07:15Z"},
            {"start": "2026-10-01T00:00:00Z", "end": "2026-10-01T00:07:00Z"},
        ])
        self.assertEqual(got["matched"], 1)
        self.assertEqual(got["missing_or_mismatched_in_window"], 1)

    def test_kyiv_dst_timezone_offsets_are_not_stripped(self):
        before = utc("2026-10-25T03:15:00+03:00")
        after = utc("2026-10-25T03:15:00+02:00")
        self.assertEqual((after - before).total_seconds(), 3600)
        self.assertEqual(iso(before), "2026-10-25T00:15:00Z")
        self.assertEqual(iso(after), "2026-10-25T01:15:00Z")

    def test_naive_datetime_refused(self):
        with self.assertRaises(SchemaError):
            utc("2026-10-25T03:15:00")

    def test_history_wrong_scope_fails_closed(self):
        with self.assertRaises(ScopeNotProven):
            history_air({"regionId": OBLAST, "alarms": []}, CITY)

    def test_reason_field_existence_is_only_observed_in_fixture(self):
        p = {"regionId": CITY, "alarms": [
            {**hist_row("2026-10-01T00:00:00Z", "2026-10-01T01:00:00Z"),
             "Reason": "SYNTHETIC"},
        ]}
        self.assertTrue(history_air(p, CITY)["reason_in_observed_history"])
        self.assertFalse(history_air({"regionId": CITY, "alarms": []},
                                     CITY)["reason_in_observed_history"])


class TransportTests(unittest.TestCase):
    def test_401_429_network_fails_closed(self):
        self.assertEqual(assess_transport(401), "AUTH_BLOCKED")
        self.assertEqual(assess_transport(429), "RATE_LIMIT_COOLDOWN")
        self.assertEqual(assess_transport(error="Timeout"), "TRANSPORT_UNAVAILABLE")
        self.assertEqual(assess_transport(error="ConnectionError"), "TRANSPORT_UNAVAILABLE")
        self.assertEqual(assess_transport(500), "FAIL_CLOSED")

    def test_no_gap_under_70_and_retry_after_honored(self):
        self.assertEqual(next_safe_request_time(100), 170)
        self.assertEqual(next_safe_request_time(100, retry_after=135), 235)


if __name__ == "__main__":
    unittest.main(verbosity=2)
