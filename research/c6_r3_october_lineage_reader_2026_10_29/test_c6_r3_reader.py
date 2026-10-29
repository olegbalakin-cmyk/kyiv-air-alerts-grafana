import json
import unittest
from pathlib import Path
from unittest.mock import patch
import psycopg
from c6_r3_reader_wrapper import execute,ReaderGateError,EXPECTED_SITE_PROD,EXPECTED_INPUT_BLOB,EXPECTED_CROSSWALK_BLOB

class ReaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import os
        cls.url=os.environ["PG_TEST_DATABASE_URL"]
        cls.cw=json.loads(Path(__file__).with_name("exact_nine_uuid_crosswalk.json").read_text())
        cls.start=str(cls.cw["rows"][0]["alias_uid"])
        with psycopg.connect(cls.url,autocommit=True) as c:
            c.execute("""CREATE TABLE IF NOT EXISTS public.alert_episodes(
            episode_uid uuid PRIMARY KEY,city_key text,alert_type text,episode_state text,
            canonicalization_version text,start_at timestamptz,end_at timestamptz)""")
            c.execute("""CREATE TABLE IF NOT EXISTS public.attack_event_classifications(
            classification_uid uuid PRIMARY KEY,alert_episode_uid uuid,binding_state text,verdict text)""")
            c.execute("""CREATE TABLE IF NOT EXISTS public.attack_event_sources(
            attack_event_source_uid uuid PRIMARY KEY,classification_uid uuid,source_link_key text)""")
            c.execute("""CREATE TABLE IF NOT EXISTS public.attack_events(
            attack_event_uid uuid PRIMARY KEY,current_classification_uid uuid,alert_episode_uid uuid,event_status text)""")
            c.execute("TRUNCATE public.attack_events,public.attack_event_sources,public.attack_event_classifications,public.alert_episodes")
            for i,row in enumerate(cls.cw["rows"]):
                c.execute("""INSERT INTO public.alert_episodes VALUES
                (%s,'kyiv','AIR','closed','alert-canonicalization-v1',%s,%s),
                (%s,'kyiv','AIR','closed','alert-canonicalization-v1',%s,%s)""",
                (row["alias_uid"],row["alias_start_utc"],row["alias_end_utc"],row["canonical_uid"],row["canonical_start"],row["canonical_end"]))
                c.execute("INSERT INTO public.attack_event_classifications VALUES (%s,%s,'BOUND','NO_EVENT')",
                          (row["a5_classification_uid"],row["alias_uid"]))
            import uuid
            for _ in range(25):
                c.execute("INSERT INTO public.attack_event_classifications VALUES (%s,NULL,'UNBOUND','EVENT')",(str(uuid.uuid4()),))
            # Extra October precise/minute pair has no owner identity acceptance.
            c.execute("""INSERT INTO public.alert_episodes VALUES
            ('11111111-1111-1111-1111-111111111111','kyiv','AIR','closed','alert-canonicalization-v1','2026-10-02 10:00Z','2026-10-02 10:15Z'),
            ('22222222-2222-2222-2222-222222222222','kyiv','AIR','closed','alert-canonicalization-v1','2026-10-02 10:00:21Z','2026-10-02 10:15:41Z')""")
    def run_reader(self,scope="september",**kw):
        params=dict(crosswalk=self.cw,pinned_sha=EXPECTED_SITE_PROD,input_blob=EXPECTED_INPUT_BLOB,
                    mapping_blob=EXPECTED_CROSSWALK_BLOB)
        params.update(kw)
        with psycopg.connect(self.url) as c:
            return execute(c,scope,**params)
    def assert_rejected(self,code,**kw):
        with self.assertRaisesRegex(ReaderGateError,code):
            self.run_reader(**kw)
    def test_september_9(self):
        r=self.run_reader()
        self.assertEqual(r["physical_intervals"],9)
        self.assertEqual(r["a5_classifications"],9)
        self.assertEqual(r["unbound_without_parent"],25)
    def test_october_unknown(self):
        self.assert_rejected("HARD_FAIL_UNCERTIFIED_OCTOBER_ALIASES",scope="october")
    def test_missing_alias(self):
        with psycopg.connect(self.url,autocommit=True) as c:
            c.execute("DELETE FROM public.alert_episodes WHERE episode_uid=%s",(self.start,))
        try: self.assert_rejected("HARD_FAIL_MISSING_ALIAS_PARENT")
        finally:
            row=self.cw["rows"][0]
            with psycopg.connect(self.url,autocommit=True) as c:
                c.execute("INSERT INTO public.alert_episodes VALUES (%s,'kyiv','AIR','closed','alert-canonicalization-v1',%s,%s)",(row["alias_uid"],row["alias_start_utc"],row["alias_end_utc"]))
    def test_stale_sha(self): self.assert_rejected("HARD_FAIL_STALE_SITE_PROD_SHA",pinned_sha="stale")
    def test_missing_mapping_authority(self): self.assert_rejected("HARD_FAIL_MISSING_GIT_CROSSWALK_AUTHORITY",mapping_blob="wrong")
    def test_metadata_fault(self): self.assert_rejected("HARD_FAIL_METADATA_FAULT",fail_stage="metadata")
    def test_relation_fault(self): self.assert_rejected("HARD_FAIL_RELATIONSHIP_READ",fail_stage="classifications")
    def test_after_projection_fault(self): self.assert_rejected("HARD_FAIL_AFTER_PROJECTION",fail_stage="after_projection")
    def test_determinism(self):
        r1=self.run_reader();r2=self.run_reader()
        self.assertEqual(r1["physical_uids"],r2["physical_uids"])
    def test_no_publication_after_fail(self):
        done=[]
        with self.assertRaises(ReaderGateError):
            self.run_reader(scope="october",consumer=done.append)
        self.assertEqual(done,[])
if __name__=="__main__": unittest.main()
