#!/usr/bin/env python3
"""14 primary scenarios plus negative controls. Does not touch operational Neon."""
from __future__ import annotations
import copy
import hashlib
import json
import random
import unittest
from datetime import datetime, timedelta, timezone

from source_priority_reader import (
    ReaderGateError, classify_live_sequence, duration_seconds, git_blob_sha, iso_utc,
    parse_pinned_combined, project_display, sha256_canonical, verify_september_a5_untouched,
    verify_source_versions,
)
UTC = timezone.utc


def ts(dt):
    return dt.isoformat().replace("+00:00", "Z")


def row(uid, start, end, kind, *, blob="deadbeef", retired=False):
    r = {"uid":uid,"start":ts(start),"end":ts(end),"source_kind":kind,
         "origin_git_commit":"fixture-commit-verified", "origin_git_blob":blob}
    if retired:
        r["retired_view_version"] = "fixture-old-municipal"
    return r


def physical(r):
    return {"uid":r["uid"],"start_at":r["start"],"end_at":r["end"],
            "city_key":"kyiv","alert_type":"AIR","episode_state":"closed"}


def combined(r):
    return {"start":r["start"],"end":r["end"],
            "duration_minutes":duration_seconds(r["start"],r["end"])/60,
            "source":r["source_kind"]}


def override(live, official):
    return {"live_uid":live["uid"],"official_uid":official["uid"],
            "authority":"OWNER_BOUNDED_VIEW_ONLY", "physical_identity":"NOT_PROVEN",
            "decision_scope":"DISPLAY_ONLY"}


def frozen():
    """Deterministic real-shaped 382 physical parents / 198 Git visible episodes."""
    base = datetime(2026,10,1,0,0,tzinfo=UTC)
    b = {"raw":[],"src":[],"git":[],"overrides":[],"classes":[],"links":[],"events":[]}
    for i in range(184):
        s = base + timedelta(hours=3*i,seconds=i % 59 + 1)
        e = s + timedelta(minutes=25+(i%10),seconds=(i*7)%59)
        exact = row(f"o{i:03}",s,e,"official_json")
        floored_s = s.replace(second=0,microsecond=0)
        floored_e = e.replace(second=0,microsecond=0)
        minute = row(f"l{i:03}",floored_s,floored_e,"kyiv_digital_live",blob="prev-live")
        for r in [exact,minute]:
            b["src"].append(r)
            b["raw"].append(physical(r))
        b["git"].append(combined(exact))
        b["overrides"].append(override(minute,exact))
    for i in range(14):
        s = base + timedelta(days=25,hours=4*i,minutes=3)
        e = s + timedelta(minutes=18+i)
        r = row(f"fresh{i:02}",s,e,"kyiv_digital_live",blob="current-live")
        b["src"].append(r)
        b["raw"].append(physical(r))
        b["git"].append(combined(r))
    for i in range(55):
        parent = f"l{i:03}" if i < 28 else f"o{i-28:03}"
        b["classes"].append({"uid":f"class{i:03}","parent_uid":parent,
                             "binding_state":"BOUND", "verdict":"NEEDS_REVIEW",
                             "classification_key":f"key{i:03}"})
    for i in range(223):
        b["links"].append({"uid":f"link{i:03}",
                           "classification_uid":f"class{i%55:03}",
                           "source_link_key":f"proof{i:03}"})
    return b


def project(b, expected=True, **kw):
    expectation = None
    if expected:
        rel = {"classifications":sorted(b["classes"],key=lambda x:x["uid"]),
               "source_links":sorted(b["links"],key=lambda x:x["uid"]),
               "events":sorted(b["events"],key=lambda x:x["uid"])}
        expectation = {"classifications":55,"source_links":223,"sha256":sha256_canonical(rel)}
    return project_display(b["raw"],b["src"],b["git"],b["overrides"],
                           b["classes"],b["links"],b["events"],
                           expected_relationships=expectation, **kw)


class TestB1(unittest.TestCase):
    def setUp(self):
        self.b = frozen()

    def test_01_frozen_october_382_to_198_exact(self):
        result = project(self.b)
        self.assertEqual(result["status"],"PASS_ALERTS_ONLY")
        self.assertEqual(result["counts"]["raw"],382)
        self.assertEqual(result["counts"]["display"],198)
        self.assertEqual(result["counts"]["official_display"],184)
        self.assertEqual(result["counts"]["live_display"],14)
        self.assertEqual(result["counts"]["suppressed_view_only"],184)
        self.assertEqual({(x["start_utc"],x["end_utc"],x["source_kind"]) for x in result["display_alerts"]},
                         {(iso_utc(g["start"]),iso_utc(g["end"]),g["source"]) for g in self.b["git"]})
        self.assertEqual(result["counts"]["retained_classifications_on_suppressed"],28)

    def test_02_september_a5_nine_190_exact(self):
        base=datetime(2026,9,1,tzinfo=UTC)
        original=[]; physicals=[]; pairs=[]
        for i in range(190):
            start=base+timedelta(hours=3*i,seconds=10+i%49)
            end=start+timedelta(minutes=22,seconds=13)
            official=row(f"sepo{i}",start,end,"official_json")
            original.append(combined(official))
            physicals.append(physical(official))
            if i < 9:
                minute=row(f"sepa{i}",start.replace(second=0),end.replace(second=0),"kyiv_digital_live")
                physicals.append(physical(minute))
                pairs.append({"alias_uid":minute["uid"], "canonical_uid":official["uid"],
                              "alias_start_utc":minute["start"], "alias_end_utc":minute["end"],
                              "canonical_start":official["start"],"canonical_end":official["end"]})
        assert verify_september_a5_untouched(physicals,original,pairs)["exact_parity"]=="190/190"

    def test_03_new_fresh_completed_live(self):
        b=self.b
        s=datetime(2026,10,30,10,tzinfo=UTC); e=s+timedelta(minutes=42)
        x=row("new-live",s,e,"kyiv_digital_live",blob="new-git")
        b["raw"].append(physical(x));b["src"].append(x);b["git"].append(combined(x))
        p=project(b)
        self.assertEqual((p["counts"]["display"],p["counts"]["live_display"]),(199,15))
        self.assertEqual(p["status"],"PASS_ALERTS_ONLY")

    def test_04_monday_municipal_replacement_requires_explicit_view_rule(self):
        b=self.b
        old=next(x for x in b["src"] if x["uid"]=="fresh00")
        start=datetime.fromisoformat(old["start"].replace("Z","+00:00"))+timedelta(seconds=22)
        end=datetime.fromisoformat(old["end"].replace("Z","+00:00"))+timedelta(seconds=18)
        new=row("new-official",start,end,"official_json",blob="new-weekly-git-blob")
        b["raw"].append(physical(new));b["src"].append(new)
        b["git"]=[g for g in b["git"] if (g["start"],g["end"])!=(old["start"],old["end"])]
        b["git"].append(combined(new))
        self.assertEqual(project(b)["status"],"PARTIAL_UNRESOLVED")
        b["overrides"].append(override(old,new))
        p=project(b)
        self.assertEqual((p["counts"]["display"],p["counts"]["live_display"]),(198,13))
        self.assertEqual(p["status"],"PASS_ALERTS_ONLY")

    def test_05_monday_replay_idempotent(self):
        b=self.b
        one=project(b)
        two=project(b)
        self.assertEqual(sha256_canonical(one),sha256_canonical(two))
        self.assertEqual(one["counts"]["raw"],382)

    def test_06_live_crosses_watermark_must_not_silently_drop(self):
        b=self.b
        last=max((r for r in b["src"] if r["source_kind"]=="official_json"),key=lambda x:x["end"])
        end_dt=datetime.fromisoformat(last["end"].replace("Z","+00:00"))
        start=end_dt-timedelta(minutes=10)
        cross=row("cross",start.replace(second=0),end_dt+timedelta(minutes=50),"kyiv_digital_live")
        b["raw"].append(physical(cross));b["src"].append(cross);b["git"].append(combined(cross))
        p=project(b)
        self.assertEqual(p["status"],"PARTIAL_UNRESOLVED")
        self.assertIn("UNKNOWN_CANDIDATE_FAIL_CLOSED",[x["status"] for x in p["unresolved_associations"]])
        self.assertEqual(p["counts"]["live_display"],14)

    def test_07_late_official_correction_requires_versioned_approval(self):
        old={"uid":"correction-old","source_kind":"official_json","origin_git_blob":"old"}
        new={"uid":"correction-new","source_kind":"official_json","origin_git_blob":"new"}
        with self.assertRaisesRegex(ReaderGateError,"UNVERIFIED_MUNICIPAL_CONTRACTION"):
            verify_source_versions([old],[new])
        self.assertEqual(verify_source_versions([old],[new],[("correction-old","correction-new")])["status"],"PASS")
        with self.assertRaisesRegex(ReaderGateError,"MISSING_NEW_OFFICIAL_SOURCE_VERSION"):
            verify_source_versions([old],[{**new,"origin_git_blob":"old"}],[("correction-old","correction-new")])

    def test_08_incomplete_official_gap_does_not_hide_live_tail(self):
        b=self.b
        removed=b["git"].pop(80)
        p=project(b)
        self.assertEqual(p["status"],"PARTIAL_UNRESOLVED")
        self.assertEqual(p["counts"]["live_display"],14)
        self.assertTrue(any(x["status"]=="OVERRIDE_WITHOUT_PINNED_OFFICIAL"
                            for x in p["unresolved_associations"]))

    def test_09_pinned_committed_fallback_and_tamper(self):
        payload=json.dumps(self.b["git"],ensure_ascii=False).encode()
        sha=git_blob_sha(payload)
        self.assertEqual(parse_pinned_combined(payload,sha,fallback=True),self.b["git"])
        with self.assertRaisesRegex(ReaderGateError,"UNPINNED_MUNICIPAL_FALLBACK"):
            parse_pinned_combined(payload+b" ",sha,fallback=True)

    def test_10_incomplete_and_malformed_live_sequence(self):
        ev=[{"at":"2026-10-29T07:34:00+02:00","kind":"start"},
            {"at":"2026-10-29T08:28:00+02:00","kind":"end"},
            {"at":"2026-10-29T09:46:00+02:00","kind":"start"}]
        seq=classify_live_sequence(ev)
        self.assertEqual(len(seq["completed_intervals"]),1)
        self.assertEqual(seq["status"],"UNRESOLVED_LIVE_SEQUENCE")
        p=project(self.b,new_source_completeness=seq)
        self.assertEqual(p["counts"]["live_display"],14)
        self.assertEqual(p["status"],"PARTIAL_UNRESOLVED")
        self.assertEqual(classify_live_sequence(ev[::-1])["status"],"UNRESOLVED_LIVE_SEQUENCE")

    def test_11_unknown_new_candidate_fail_closed_not_minute_merge(self):
        b=self.b
        precise=next(r for r in b["src"] if r["uid"]=="o100")
        s=datetime.fromisoformat(precise["start"].replace("Z","+00:00"))
        e=datetime.fromisoformat(precise["end"].replace("Z","+00:00"))
        live=row("unknown-double",s.replace(second=0)+timedelta(minutes=1),e.replace(second=0)+timedelta(minutes=1),"kyiv_digital_live")
        b["raw"].append(physical(live));b["src"].append(live);b["git"].append(combined(live))
        p=project(b)
        self.assertEqual(p["status"],"PARTIAL_UNRESOLVED")
        self.assertIn("UNKNOWN_CANDIDATE_FAIL_CLOSED",[x["status"] for x in p["unresolved_associations"]])
        self.assertEqual(p["counts"]["live_display"],14)

    def test_12_55_classifications_223_links_immutable_no_rebind(self):
        p=project(self.b)
        self.assertEqual((p["counts"]["classifications"],p["counts"]["source_links"]),(55,223))
        self.assertEqual(p["enrichment"]["status"],"UNRESOLVED_ALIAS_CLASSIFICATIONS")
        self.assertEqual(p["enrichment"]["rebinds"],0)
        self.b["classes"][0]["parent_uid"]="o100"
        old = frozen()
        expected_digest = sha256_canonical({"classifications":sorted(old["classes"],key=lambda r:r["uid"]),
                        "source_links":sorted(old["links"],key=lambda r:r["uid"]),"events":[]})
        with self.assertRaisesRegex(ReaderGateError,"CLASSIFICATION_RELATIONSHIPS_CHANGED"):
            project_display(self.b["raw"], self.b["src"], self.b["git"], self.b["overrides"],
                            self.b["classes"], self.b["links"], self.b["events"],
                            expected_relationships={"classifications":55,"source_links":223,
                                                    "sha256":expected_digest})

    def test_13_input_row_order_invariant(self):
        original=project(self.b)
        r=random.Random(99133)
        for field in ("raw","src","git","overrides","classes","links"):
            r.shuffle(self.b[field])
        second=project(self.b)
        self.assertEqual(sha256_canonical(original["display_alerts"]),
                         sha256_canonical(second["display_alerts"]))
        self.assertEqual(sha256_canonical(original["classification_relationships"]),
                         sha256_canonical(second["classification_relationships"]))

    def test_14_kyiv_dst_fall_back_uses_explicit_offsets(self):
        a="2026-10-25T02:45:00+03:00"
        b="2026-10-25T03:15:00+02:00"
        self.assertEqual(duration_seconds(a,b),90*60)
        self.assertEqual(iso_utc(a),"2026-10-24T23:45:00.000000Z")
        self.assertEqual(iso_utc(b),"2026-10-25T01:15:00.000000Z")
        with self.assertRaisesRegex(ReaderGateError,"NAIVE_TIME_FORBIDDEN"):
            iso_utc("2026-10-25T03:15:00")
        self.assertEqual(duration_seconds("2026-10-25T03:20:00+03:00",
                                          "2026-10-25T03:20:00+02:00"),3600)

    def test_15_gap_inside_official_period_keeps_verified_live(self):
        b=self.b
        # A vetted Kyiv Digital interval in the 184-gap is not rejected by max(start).
        exact=next(r for r in b["src"] if r["uid"]=="o101")
        s=datetime.fromisoformat(exact["end"].replace("Z","+00:00"))+timedelta(minutes=2)
        e=s+timedelta(minutes=12)
        gap=row("new-gap-live",s,e,"kyiv_digital_live",blob="pinned-gap")
        b["raw"].append(physical(gap));b["src"].append(gap);b["git"].append(combined(gap))
        p=project(b)
        self.assertEqual(p["status"],"PASS_ALERTS_ONLY")
        self.assertIn("new-gap-live",[d["uid"] for d in p["display_alerts"]])

    def test_16_unknown_parent_provenance_does_not_infer_source(self):
        b=self.b
        b["raw"].append({"uid":"unlabelled","start_at":"2026-10-30T10:00:00Z",
                         "end_at":"2026-10-30T10:35:00Z"})
        p=project(b)
        self.assertEqual(p["status"],"PARTIAL_UNRESOLVED")
        self.assertIn("UNKNOWN_INGESTION_PROVENANCE",[r["status"] for r in p["unresolved_associations"]])

    def test_17_duplicate_git_interval_rejected(self):
        b=self.b
        b["git"].append(copy.deepcopy(b["git"][0]))
        with self.assertRaisesRegex(ReaderGateError,"DUPLICATED_COMMITTED_INTERVAL"):
            project(b)


if __name__=="__main__":
    unittest.main(verbosity=2)
