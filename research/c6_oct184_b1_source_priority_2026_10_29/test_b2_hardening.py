"""B2 offline/CLI fail-closed cases. These are NOT PG16 integration tests."""
import argparse
import copy
import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import source_priority_reader as r
from test_source_priority_reader import frozen, row, physical, combined, ts


def a5_fixture():
    base = datetime(2026, 9, 1, tzinfo=timezone.utc)
    rows, official, crosswalk = [], [], []
    for i in range(190):
        s = base+timedelta(hours=3*i, seconds=10+i%49)
        e = s+timedelta(minutes=22, seconds=13)
        official_row = row(f"sepo{i}", s, e, "official_json")
        rows.append(physical(official_row))
        official.append(combined(official_row))
        if i < 9:
            alias = row(f"sepa{i}", s.replace(second=0), e.replace(second=0),
                        "kyiv_digital_live")
            rows.append(physical(alias))
            crosswalk.append({"alias_uid":alias["uid"],
                              "canonical_uid":official_row["uid"],
                              "alias_start_utc":alias["start"],
                              "alias_end_utc":alias["end"],
                              "canonical_start":official_row["start"],
                              "canonical_end":official_row["end"]})
    return {"raw_rows":rows, "combined_official":official, "crosswalk":crosswalk}


def lab_files(path):
    b = frozen()
    rel = {"classifications": sorted(b["classes"],key=lambda x:x["uid"]),
           "source_links": sorted(b["links"],key=lambda x:x["uid"]),"events":[]}
    manifest = {"schema_version":"c6-oct184-b1-bundle-v1", "source_rows":b["src"],
                "combined":b["git"],"display_overrides":b["overrides"],
                "expected_relationships":{"classifications":55,"source_links":223,
                                          "sha256":r.sha256_canonical(rel)}}
    live = [x for x in b["src"] if x["uid"].startswith("fresh")]
    transitions = []
    for x in live:
        transitions += [{"at":x["start"],"kind":"start"},
                        {"at":x["end"],"kind":"end"}]
    capture = {"source_kind":"kyiv_digital_live", "publisher":"kyiv_digital",
               "publisher_http_status":200,"capture_git_blob":"fixture-commit-blobs",
               "capture_git_commit":"fixture-commit", "captured_at_utc":"2026-10-29T19:00:00Z",
               "transitions":transitions}
    data = {"bundle":manifest, "git_json":b["git"],
            "previous": [x for x in b["src"] if x["source_kind"] == "official_json"],
            "a5":a5_fixture(),"capture":capture,
            "snapshot":{"episodes":b["raw"],"classifications":b["classes"],
                        "source_links":b["links"],"events":[]}}
    for name, value in data.items():
        (path / (name+'.json')).write_text(json.dumps(value, sort_keys=True, indent=2)+'\n')
    return data


def arguments(path, **overrides):
    args = dict(bundle=path/'bundle.json',approved_bundle=None,provenance_receipt=None,
                git_json=path/'git_json.json',previous_municipal=path/'previous.json',
                correction_approvals=None,september_guard=path/'a5.json',
                live_capture=path/'capture.json',as_of_utc='2026-10-29T20:00:00Z',
                neon_identity=None,start_utc='2026-09-30T21:00:00Z',
                end_utc='2026-10-31T22:00:00Z',fixture_snapshot=path/'snapshot.json',
                lab_pg16_url=None,lab_mode=True,result=path/'report.json')
    args.update(overrides)
    return argparse.Namespace(**args)


class TestB2VersionGuards(unittest.TestCase):
    def setUp(self):
        self.old={"uid":"o-01","source_kind":"official_json",
                  "start":"2026-10-01T00:00:00Z","end":"2026-10-01T01:00:00Z",
                  "duration_seconds":3600,"alert_type":"AIR",
                  "origin_git_blob":"a"*40,"origin_git_commit":"c"*40}
        self.new={**self.old,"origin_git_blob":"b"*40,"origin_git_commit":"d"*40}

    def approve(self, old, new):
        return {"old_uid":old["uid"],"new_uid":new["uid"],
                "old_sha256":r._source_fingerprint(old),
                "new_sha256":r._source_fingerprint(new),
                "old_source_blob":old["origin_git_blob"],
                "new_source_blob":new["origin_git_blob"],
                "decision_scope":"HISTORICAL_CORRECTION_ONLY",
                "authority":"OWNER_APPROVED_SOURCE_CORRECTION"}

    def test_same_uid_end_correction_rejected_even_on_new_blob(self):
        n={**self.new,"end":"2026-10-01T01:05:00Z"}
        with self.assertRaisesRegex(r.ReaderGateError,"UNAPPROVED_SAME_UID_CORRECTION"):
            r.verify_source_versions([self.old],[n])

    def test_same_uid_start_correction_rejected(self):
        n={**self.new,"start":"2026-10-01T00:01:00Z"}
        with self.assertRaisesRegex(r.ReaderGateError,"UNAPPROVED_SAME_UID_CORRECTION"):
            r.verify_source_versions([self.old],[n])

    def test_same_uid_duration_correction_rejected(self):
        n={**self.new,"duration_seconds":3601}
        with self.assertRaisesRegex(r.ReaderGateError,"UNAPPROVED_SAME_UID_CORRECTION"):
            r.verify_source_versions([self.old],[n])

    def test_other_material_field_correction_rejected(self):
        n={**self.new,"alert_type":"NOT_AIR"}
        with self.assertRaisesRegex(r.ReaderGateError,"UNAPPROVED_SAME_UID_CORRECTION"):
            r.verify_source_versions([self.old],[n])

    def test_same_uid_approved_fingerprints_only(self):
        n={**self.new,"end":"2026-10-01T01:05:00Z"}
        approval=self.approve(self.old,n)
        self.assertEqual(r.verify_source_versions([self.old],[n],[approval])["retained_uid_changes"],1)
        approval["new_sha256"]='invalid'
        with self.assertRaisesRegex(r.ReaderGateError,"CORRECTION_FINGERPRINT_MISMATCH"):
            r.verify_source_versions([self.old],[n],[approval])

    def test_same_uid_requires_new_source_version(self):
        n={**self.old,"end":"2026-10-01T01:05:00Z"}
        approval=self.approve(self.old,n)
        with self.assertRaisesRegex(r.ReaderGateError,"MISSING_NEW_OFFICIAL_SOURCE_VERSION"):
            r.verify_source_versions([self.old],[n],[approval])

    def test_same_uid_requires_new_commit(self):
        n={**self.new,"origin_git_commit":self.old["origin_git_commit"],
           "end":"2026-10-01T01:05:00Z"}
        approval=self.approve(self.old,n)
        with self.assertRaisesRegex(r.ReaderGateError,"MISSING_NEW_OFFICIAL_SOURCE_COMMIT"):
            r.verify_source_versions([self.old],[n],[approval])

    def test_uid_replacement_requires_approved_version(self):
        n={**self.new,"uid":"new-01"}
        with self.assertRaisesRegex(r.ReaderGateError,"UNVERIFIED_MUNICIPAL_CONTRACTION"):
            r.verify_source_versions([self.old],[n])
        self.assertEqual(r.verify_source_versions([self.old],[n],[self.approve(self.old,n)])["corrections"],1)

    def test_spurious_or_duplicate_approval_rejected(self):
        approval=self.approve(self.old,self.new)
        with self.assertRaisesRegex(r.ReaderGateError,"UNUSED_SOURCE_CORRECTION_APPROVAL"):
            r.verify_source_versions([self.old],[self.new],[approval])
        with self.assertRaisesRegex(r.ReaderGateError,"DUPLICATE_CORRECTION"):
            r.verify_source_versions([self.old],[{**self.new,"end":"2026-10-01T01:10:00Z"}],
                                     [approval,approval])

    def test_duplicate_uid_rejected(self):
        with self.assertRaisesRegex(r.ReaderGateError,"DUPLICATE_MUNICIPAL_UID"):
            r.verify_source_versions([self.old,self.old],[self.new])

    def test_signed_same_uid_cannot_be_legacy_pair(self):
        n={**self.new,"end":"2026-10-01T01:05:00Z"}
        with self.assertRaisesRegex(r.ReaderGateError,"SAME_UID_REQUIRES_FINGERPRINT_APPROVAL"):
            r.verify_source_versions([self.old],[n],[(self.old["uid"],self.old["uid"])])


class TestB2AuthorityAndLive(unittest.TestCase):
    def test_self_asserted_approval_is_not_enough(self):
        payload=json.dumps({"source_authority":{"policy":r.APPROVED_VIEW_SCOPE}}).encode()
        with self.assertRaisesRegex(r.ReaderGateError,"UNAPPROVED_FROZEN_MANIFEST_BLOB"):
            r.verify_approved_frozen_bundle(payload,payload)

    def test_approved_manifest_override_rejected(self):
        with self.assertRaisesRegex(r.ReaderGateError,"UNAPPROVED_BUNDLE_PIN_OVERRIDE"):
            r.verify_approved_frozen_bundle(b"{}",b"{}",expected_blob='bad')

    def test_wrong_neon_identity_blocked_before_network(self):
        proof={"project_id":"green-cake-44216048", "branch_id":"another",
               "id":"ep-calm-rice-b5073ypp", "type":"read_only",
               "host":"ep-calm-rice-b5073ypp.eu.neon.tech"}
        with self.assertRaisesRegex(r.ReaderGateError,"WRONG_NEON_PROJECT_BRANCH_COMPUTE"):
            r.verify_neon_control_plane(proof,"postgresql://x:x@ep-calm-rice-b5073ypp.eu.neon.tech/neondb")

    def test_wrong_neon_dsn_blocked(self):
        proof={"project_id":"green-cake-44216048", "branch_id":"br-bold-mode-b5rub8pq",
               "id":"ep-calm-rice-b5073ypp", "type":"read_only",
               "host":"ep-calm-rice-b5073ypp.eu.neon.tech"}
        with self.assertRaisesRegex(r.ReaderGateError,"NEON_DSN_COMPUTE_MISMATCH"):
            r.verify_neon_control_plane(proof,"postgresql://x:x@other.eu.neon.tech/neondb")

    def test_no_neon_control_plane_key_fails_closed(self):
        with self.assertRaisesRegex(r.ReaderGateError,"NEON_CONTROL_PLANE_API_CREDENTIAL_UNAVAILABLE"):
            r.fetch_live_neon_endpoint(None)

    def test_expired_or_future_live_capture_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=lab_files(Path(tmp))
            fresh=[x for x in b["bundle"]["source_rows"] if x["uid"].startswith("fresh")]
            for asof in ('2026-10-30T10:00:00Z','2026-10-29T18:00:00Z'):
                with self.assertRaisesRegex(r.ReaderGateError,'STALE_OR_FUTURE_KYIV_DIGITAL_CAPTURE'):
                    r.verify_live_capture(b['capture'], fresh, asof)

    def test_gap_missing_or_duplicate_live_transitions(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=lab_files(Path(tmp))
            fresh=[x for x in b['bundle']['source_rows'] if x['uid'].startswith('fresh')]
            bad=copy.deepcopy(b['capture']);bad['transitions'].pop()
            with self.assertRaisesRegex(r.ReaderGateError,'LIVE_SEQUENCE_INCOMPLETE'):
                r.verify_live_capture(bad,fresh,'2026-10-29T20:00:00Z')
            bad=copy.deepcopy(b['capture']);bad['transitions']=bad['transitions'][:-2]
            with self.assertRaisesRegex(r.ReaderGateError,'LIVE_SEQUENCE_NOT_EQUAL_TO_PINNED_COMPLETED_TAIL'):
                r.verify_live_capture(bad,fresh,'2026-10-29T20:00:00Z')

    def test_malformed_source_capture_rejected(self):
        with self.assertRaisesRegex(r.ReaderGateError,'LIVE_CAPTURE_PROVENANCE_REQUIRED'):
            r.verify_live_capture({'source_kind':'kyiv_digital_live','transitions':[]},[],
                                  '2026-10-29T20:00:00Z')


class TestB2CLI(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)
        self.bundle=lab_files(self.path)
    def tearDown(self):
        self.tmp.cleanup()

    def test_all_guards_executed_before_result(self):
        hits=[]
        report=r.execute_cli(arguments(self.path),after_guards=lambda item: hits.append(item))
        self.assertEqual(len(hits),1)
        self.assertEqual(report['status'],'PASS_ALERTS_ONLY')
        self.assertEqual(report['counts']['raw'],382)
        self.assertEqual(report['counts']['display'],198)
        self.assertEqual(report['september_a5']['exact_parity'],'190/190')
        self.assertEqual((report['counts']['classifications'],report['counts']['source_links']),(55,223))
        self.assertEqual(report['live_source_guard']['completed'],14)
        self.assertEqual(report['publication_callbacks'],0)
        self.assertEqual(report['source_approval'],'LAB_SYNTHETIC_ONLY')

    def test_result_written_after_guard_failure_never(self):
        b=copy.deepcopy(self.bundle['bundle'])
        b['source_rows'][0]['start']='2026-10-01T12:00:00Z'
        (self.path/'bundle.json').write_text(json.dumps(b))
        hits=[]
        with self.assertRaises(r.ReaderGateError):
            r.execute_cli(arguments(self.path),after_guards=lambda x:hits.append(x))
        self.assertEqual(hits,[])
        self.assertFalse((self.path/'report.json').exists())

    def test_cli_missing_september_guard_blocks_before_result(self):
        with self.assertRaisesRegex(r.ReaderGateError,'CLI_MANDATORY_GUARDS_MISSING'):
            r.execute_cli(arguments(self.path,september_guard=None))
        self.assertFalse((self.path/'report.json').exists())

    def test_cli_september_mutation_blocks_before_result(self):
        a5=copy.deepcopy(self.bundle['a5']);a5['raw_rows'][0]['end_at']='2026-09-01T01:00:00Z'
        (self.path/'a5.json').write_text(json.dumps(a5))
        with self.assertRaisesRegex(r.ReaderGateError,'A5_CANONICAL_INTERVAL_CHANGED'):
            r.execute_cli(arguments(self.path))
        self.assertFalse((self.path/'report.json').exists())

    def test_cli_incomplete_live_blocks_before_result(self):
        cap=copy.deepcopy(self.bundle['capture']);cap['transitions'].pop()
        (self.path/'capture.json').write_text(json.dumps(cap))
        with self.assertRaisesRegex(r.ReaderGateError,'LIVE_SEQUENCE_INCOMPLETE'):
            r.execute_cli(arguments(self.path))
        self.assertFalse((self.path/'report.json').exists())

    def test_cli_same_uid_changed_end_blocks_before_result(self):
        b=copy.deepcopy(self.bundle['bundle']);b['source_rows'][1]['end']='2026-10-01T00:14:00Z'
        (self.path/'bundle.json').write_text(json.dumps(b))
        with self.assertRaises(r.ReaderGateError):
            r.execute_cli(arguments(self.path))
        self.assertFalse((self.path/'report.json').exists())

    def test_cli_unknown_overlap_blocks_before_result(self):
        b=copy.deepcopy(self.bundle['bundle'])
        s=datetime.fromisoformat(b['source_rows'][1]['start'].replace('Z','+00:00'))
        e=datetime.fromisoformat(b['source_rows'][1]['end'].replace('Z','+00:00'))
        extra=row('unknown-extra',s+timedelta(seconds=45),e+timedelta(seconds=45),
                  'kyiv_digital_live',blob='new-unknown')
        b['source_rows'].append(extra);b['combined'].append(combined(extra))
        b['expected_relationships']=self.bundle['bundle']['expected_relationships']
        snap=copy.deepcopy(self.bundle['snapshot']);snap['episodes'].append(physical(extra))
        (self.path/'bundle.json').write_text(json.dumps(b))
        (self.path/'snapshot.json').write_text(json.dumps(snap))
        (self.path/'git_json.json').write_text(json.dumps(b['combined']))
        with self.assertRaises(r.ReaderGateError):
            r.execute_cli(arguments(self.path))
        self.assertFalse((self.path/'report.json').exists())

    def test_cli_result_preexists_rejected(self):
        (self.path/'report.json').write_text('STALE\n')
        with self.assertRaisesRegex(r.ReaderGateError,'RESULT_PATH_ALREADY_EXISTS'):
            r.execute_cli(arguments(self.path))
        self.assertEqual((self.path/'report.json').read_text(),'STALE\n')

    def test_cli_offline_fixture_not_live_neon(self):
        report=r.execute_cli(arguments(self.path))
        self.assertEqual(report['execution_mode'],'OFFLINE_FIXTURE_NOT_PG16_OR_NEON')
        self.assertEqual(report['database_writes'],0)
        self.assertEqual(report['production_changes'],0)

    def test_cli_replay_idempotence_distinct_receipts(self):
        a=r.execute_cli(arguments(self.path,result=self.path/'report_a.json'))
        b=r.execute_cli(arguments(self.path,result=self.path/'report_b.json'))
        self.assertEqual(r.sha256_canonical(a),r.sha256_canonical(b))


if __name__=='__main__':
    unittest.main(verbosity=2)
