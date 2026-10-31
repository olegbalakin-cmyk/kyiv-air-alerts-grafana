#!/usr/bin/env python3
"""Offline-only, fail-closed DST 2026-10-25 four-case repair preflight.

Never connects to Neon or executes SQL. The fixture contains bounded historical
readback evidence, NOT live state. Produces deterministic JSON to stdout.
"""
import datetime as dt
import json
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
INPUT = HERE / "fixtures" / "historical_correction_candidates.json"
UTC = dt.timezone.utc
KYIV = ZoneInfo("Europe/Kyiv")
WRONG_UIDS = {
    "kharkiv": "bb7d4952-52a3-45f8-a1db-13153c8f6ca3",
    "poltava": "74ba1017-63af-4137-a5ba-246795613615",
    "zhytomyr": "b40c570e-f9db-4c7d-b7e4-3f7769e12a95",
}
PRESERVED_CHERKASY_UID = "ff046d6c-fc7e-4cd2-9470-3e5433c3d582"
EXPECTED_DELTA_US = {
    "cherkasy": 256663871, "kharkiv": -3311259182,
    "poltava": -3042657209, "zhytomyr": -2962107438,
}
def parse(value):
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
def duration_us(row):
    return round((parse(row["end_utc"]) - parse(row["start_utc"])).total_seconds() * 1000000)
def decorate(row):
    start, end = parse(row["start_utc"]), parse(row["end_utc"])
    assert start.utcoffset() == end.utcoffset() == dt.timedelta(0) and end > start
    return {**row, "start_kyiv": start.astimezone(KYIV).isoformat(timespec="microseconds"),
            "end_kyiv": end.astimezone(KYIV).isoformat(timespec="microseconds"),
            "duration_us": duration_us(row)}
def run():
    source = json.loads(INPUT.read_text(encoding="utf-8"))
    rows = source["candidate_records"]
    assert {r["city_key"] for r in rows} == {*WRONG_UIDS, "cherkasy"}
    assert source["new_required_legacy_ids_count"] == 7
    assert source["wrong_physical_record_count"] == 3
    assert source["current_unmodified_cherkasy_earlier_episode"]["episode_uid"] == PRESERVED_CHERKASY_UID
    ids, before, after, cases = set(), [], [], []
    for row in rows:
        city = row["city_key"]
        old = row["existing_incorrect_physical_record"]
        if city == "cherkasy":
            assert old is None and len(row["new_candidate_utc_intervals"]) == 1
        else:
            assert old["episode_uid"] == WRONG_UIDS[city] and len(row["new_candidate_utc_intervals"]) == 2
            assert all(v == 0 for v in row["physical_association_counts_on_wrong_row"].values())
            before.append(decorate({"city_key": city, **old}))
        new = [decorate({"city_key": city, **v}) for v in row["new_candidate_utc_intervals"]]
        for item in new:
            assert item["legacy_episode_id"] not in ids, "duplicate new legacy ID"
            ids.add(item["legacy_episode_id"])
        assert len({(x["start_utc"], x["end_utc"]) for x in new}) == len(new)
        s = sorted(new, key=lambda x: parse(x["start_utc"]))
        assert all(parse(a["end_utc"]) < parse(b["start_utc"]) for a, b in zip(s,s[1:])), "corrected intervals overlap/touch"
        delta = sum(x["duration_us"] for x in new) - (duration_us(old) if old else 0)
        assert delta == EXPECTED_DELTA_US[city], f"wrong duration delta for {city}"
        assert row["new_legacy_ids_present_in_neon_at_readback"] is False
        after += new
        cases.append({"city": city, "action": "INSERT_MISSING" if old is None else "SUPERSEDE_AND_SPLIT",
                      "before": decorate(old) if old else None,
                      "after": new, "count_delta": len(new) - (1 if old else 0),
                      "duration_delta_us": delta,
                      "requires_fresh_snapshot": True,
                      "physical_write_authorized": False})
    assert len(ids) == len(after) == 7 and len(before) == 3
    total = sum(c["duration_delta_us"] for c in cases)
    assert total == -9059359958 and sum(c["count_delta"] for c in cases) == 4
    old_cherkasy = source["current_unmodified_cherkasy_earlier_episode"]
    assert old_cherkasy["legacy_episode_id"] not in ids
    for x in after:
        assert not (x["city_key"] == "cherkasy" and
                    parse(x["start_utc"]) < parse(old_cherkasy["end_utc"]) and
                    parse(x["end_utc"]) > parse(old_cherkasy["start_utc"]))
    return {"status": "PASS_OFFLINE_FIXTURE_ONLY", "physical_repair": "NOT_EXECUTED",
            "source_checkpoint": "C6-DST-UTC-01",
            "preflight_snapshot_utc": source["evidence_read_only_neon"]["replica_preflight_utc"],
            "scope": "FOUR_CONFIRMED_CASES_NOT_FULL_PARITY",
            "before_count": 3, "after_count": 7, "count_delta": 4,
            "duration_delta_us": total, "legacy_ids_unique": True,
            "non_target_rows_changed": 0, "preserved_cherkasy_uid": PRESERVED_CHERKASY_UID,
            "cases": cases,
            "blocking_gates": ["OWNER_REPAIR_AUTHORIZATION_ABSENT",
              "FRESH_REPEATABLE_READ_SOURCE_AND_DB_SNAPSHOT_REQUIRED",
              "EXTERNAL_DEPENDENCIES_AND_LINEAGE_UNCERTIFIED",
              "WRITER_UTC_FIX_NOT_PROMOTED",
              "NO_APPROVED_HISTORY_VERSION_ALIAS_CONTRACT",
              "NO_AUTHORIZED_ROLLBACK_PLAN_OR_PHYSICAL_VERIFICATION"],
            "cutover": "NO"}
if __name__ == "__main__":
    try:
        print(json.dumps(run(), ensure_ascii=False, sort_keys=True, indent=2))
    except Exception as exc:
        print(json.dumps({"status":"BLOCKED","reason":str(exc)}), file=sys.stderr)
        sys.exit(1)
