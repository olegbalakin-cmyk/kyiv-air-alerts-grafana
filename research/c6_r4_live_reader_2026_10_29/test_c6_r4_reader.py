import json
import unittest
from pathlib import Path
from unittest.mock import patch
from datetime import datetime, timezone
from c6_r4_reader_wrapper import (_verify_full_parity, _interval_digest, verify_control_plane_metadata,
    verify_git_authority, execute_r4, ReaderGateError, EXPECTED_SITE_PROD,
    EXPECTED_INPUT_BLOB, EXPECTED_CROSSWALK_BLOB, verify_live_neon_control_plane)
from test_c6_r3_reader import ReaderTests
import psycopg

class R4FaultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import os
        cls.url=os.environ["PG_TEST_DATABASE_URL"]
        cls.cw=json.loads(Path(__file__).with_name("exact_nine_uuid_crosswalk.json").read_text())
        cls.expected=[]
        for row in cls.cw["rows"]:
            cls.expected.append({"start":row["canonical_start"],"end":row["canonical_end"],
                  "duration_minutes":round(row["canonical_duration_seconds"]/60,3)})
    def invoke(self,scope="september",**kw):
        from c6_r4_reader_wrapper import execute
        opts={"crosswalk":self.cw,"pinned_sha":EXPECTED_SITE_PROD,
              "input_blob":EXPECTED_INPUT_BLOB,"mapping_blob":EXPECTED_CROSSWALK_BLOB,
              "expected_intervals":self.expected}
        opts.update(kw)
        with psycopg.connect(self.url) as c:
            return execute(c,scope,**opts)
    def rejected(self,code,scope="september",**kw):
        with self.assertRaisesRegex(ReaderGateError,code):
            self.invoke(scope,**kw)
    def test_positive_nine_exact_rows(self):
        r=self.invoke()
        self.assertEqual(r["physical_intervals"],9)
        self.assertEqual(r["source_row_parity"],"PASS")
    def test_missing_authority(self):
        self.rejected("HARD_FAIL_MISSING_SOURCE_AUTHORITY",require_neon_identity=True,identity_verified=True,expected_intervals=None)
    def test_control_plane_verified(self):
        b={"id":"br-bold-mode-b5rub8pq","project_id":"green-cake-44216048"}
        e={"id":"ep-calm-rice-b5073ypp","project_id":"green-cake-44216048",
           "branch_id":"br-bold-mode-b5rub8pq","type":"read_only","host":"sample.readonly"}
        self.assertTrue(verify_control_plane_metadata(b,e,conn_host="sample.readonly"))
    def test_wrong_compute_identity(self):
        b={"id":"br-bold-mode-b5rub8pq","project_id":"green-cake-44216048"}
        e={"id":"ep-wrong","project_id":"green-cake-44216048","branch_id":"br-bold-mode-b5rub8pq",
           "type":"read_only","host":"sample.readonly"}
        with self.assertRaisesRegex(ReaderGateError,"IDENTITY_NOT_PROVEN"):
            verify_control_plane_metadata(b,e,conn_host="sample.readonly")
    def test_missing_control_plane(self):
        class ConnInfo: host="example"
        class Conn: info=ConnInfo()
        with patch.dict("os.environ",{"NEON_API_KEY":""}):
            with self.assertRaisesRegex(ReaderGateError,"IDENTITY_NOT_PROVEN"):
                verify_live_neon_control_plane(Conn())
    def test_wrong_end_boundary(self):
        mutate=json.loads(json.dumps(self.cw))
        mutate["rows"][0]["canonical_end"]="2026-09-29T16:30:26+03:00"
        self.rejected("HARD_FAIL_GIT_LINEAGE_CONFLICT",crosswalk=mutate)
    def test_wrong_version(self):
        with psycopg.connect(self.url,autocommit=True) as c:
            c.execute("UPDATE public.alert_episodes SET canonicalization_version='invalid' WHERE episode_uid=%s",
                      (self.cw["rows"][0]["canonical_uid"],))
        try:self.rejected("HARD_FAIL_VERSION_MISMATCH")
        finally:
            with psycopg.connect(self.url,autocommit=True) as c:
                c.execute("UPDATE public.alert_episodes SET canonicalization_version='alert-canonicalization-v1' WHERE episode_uid=%s",
                          (self.cw["rows"][0]["canonical_uid"],))
    def test_wrong_source_identity(self):
        with psycopg.connect(self.url,autocommit=True) as c:
            c.execute("UPDATE public.alert_episodes SET alert_type='OTHER' WHERE episode_uid=%s",
                      (self.cw["rows"][0]["canonical_uid"],))
        try:self.rejected("HARD_FAIL_SOURCE_IDENTITY_MISMATCH")
        finally:
            with psycopg.connect(self.url,autocommit=True) as c:
                c.execute("UPDATE public.alert_episodes SET alert_type='AIR' WHERE episode_uid=%s",
                          (self.cw["rows"][0]["canonical_uid"],))
    def test_missing_canonical_parent(self):
        uid=self.cw["rows"][0]["canonical_uid"];r=self.cw["rows"][0]
        with psycopg.connect(self.url,autocommit=True) as c:
            c.execute("DELETE FROM public.alert_episodes WHERE episode_uid=%s",(uid,))
        try:self.rejected("HARD_FAIL_MISSING_CANONICAL_PARENT")
        finally:
            with psycopg.connect(self.url,autocommit=True) as c:
                c.execute("INSERT INTO public.alert_episodes VALUES (%s,'kyiv','AIR','closed','alert-canonicalization-v1',%s,%s)",
                          (uid,r["canonical_start"],r["canonical_end"]))
    def test_duplicate_mapping(self):
        mutate=json.loads(json.dumps(self.cw))
        mutate["rows"][1]["canonical_uid"]=mutate["rows"][0]["canonical_uid"]
        self.rejected("HARD_FAIL_AMBIGUOUS_MAPPING",crosswalk=mutate)
    def test_mismatched_source_intervals(self):
        mutate=json.loads(json.dumps(self.expected))
        mutate[0]["end"]="2026-09-29T16:31:25+03:00"
        mutate[0]["duration_minutes"]=round((datetime.fromisoformat(mutate[0]["end"])-datetime.fromisoformat(mutate[0]["start"])).total_seconds()/60,3)
        self.rejected("HARD_FAIL_SEPTEMBER_ROW_PARITY",expected_intervals=mutate)
    def test_source_duration_drift(self):
        mutate=json.loads(json.dumps(self.expected));mutate[0]["duration_minutes"]=0
        self.rejected("HARD_FAIL_SOURCE_DURATION",expected_intervals=mutate)
    def test_valid_empty_selection(self):
        result=self.invoke(scope="fixture_empty")
        self.assertEqual(result["physical_intervals"],0)
    def test_failed_gate_empty_selection(self):
        self.rejected("HARD_FAIL_PROJECTION",scope="fixture_empty",fail_stage="projection")
    def test_alias_without_parent_remains_unbound(self):
        r=self.invoke()
        self.assertEqual(r["unbound_without_parent"],25)
    def test_early_fault_no_callback(self):
        called=[]
        self.rejected("HARD_FAIL_AFTER_PROJECTION",consumer=called.append,fail_stage="after_projection")
        self.assertEqual(called,[])
    def test_unknown_october_no_callback(self):
        called=[]
        self.rejected("HARD_FAIL_UNCERTIFIED_OCTOBER_ALIASES",scope="october",consumer=called.append)
        self.assertEqual(called,[])
    def test_event_source_join_not_performed(self):
        with psycopg.connect(self.url,autocommit=True) as c:
            c.execute("INSERT INTO public.attack_event_sources VALUES ('eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee',%s,'sample') ON CONFLICT DO NOTHING",
                      (self.cw["rows"][0]["a5_classification_uid"],))
            c.execute("INSERT INTO public.attack_event_sources VALUES ('dddddddd-dddd-dddd-dddd-dddddddddddd',%s,'sample2') ON CONFLICT DO NOTHING",
                      (self.cw["rows"][0]["a5_classification_uid"],))
        try:
            r=self.invoke()
            self.assertEqual(r["a5_classifications"],9)
            self.assertGreaterEqual(r["source_count"],2)
        finally:
            with psycopg.connect(self.url,autocommit=True) as c:
                c.execute("DELETE FROM public.attack_event_sources WHERE attack_event_source_uid::text IN ('eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee','dddddddd-dddd-dddd-dddd-dddddddddddd')")
    def test_incomplete_relationship(self):
        with psycopg.connect(self.url,autocommit=True) as c:
            c.execute("INSERT INTO public.attack_event_sources VALUES ('eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee','cccccccc-cccc-cccc-cccc-cccccccccccc','orphan') ON CONFLICT DO NOTHING")
        try:self.rejected("HARD_FAIL_INCOMPLETE_RELATIONSHIP_SNAPSHOT")
        finally:
            with psycopg.connect(self.url,autocommit=True) as c:
                c.execute("DELETE FROM public.attack_event_sources WHERE attack_event_source_uid='eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee'")
    def test_connection_fault(self):
        self.rejected("HARD_FAIL_DB_CONNECTION",fail_stage="connection")
    def test_repeat_does_not_write(self):
        with psycopg.connect(self.url) as c:
            before=c.execute("SELECT count(*) FROM public.attack_event_classifications").fetchone()[0]
        self.invoke();self.invoke()
        with psycopg.connect(self.url) as c:
            after=c.execute("SELECT count(*) FROM public.attack_event_classifications").fetchone()[0]
        self.assertEqual(before,after)
    def test_authority_missing_git_fails(self):
        with self.assertRaisesRegex(ReaderGateError,"HARD_FAIL_GIT_OBJECT_UNAVAILABLE"):
            verify_git_authority("/nonexistent/c6r4/repo")

if __name__=="__main__":
    unittest.main()
