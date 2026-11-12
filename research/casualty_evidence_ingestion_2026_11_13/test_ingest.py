#!/usr/bin/env python3
import importlib.util
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

spec = importlib.util.spec_from_file_location("ingestion", Path(__file__).with_name("ingest.py"))
e = importlib.util.module_from_spec(spec)
spec.loader.exec_module(e)

def auth():
    now=datetime.now(timezone.utc)
    return {"authorization_id":"SYNTHETIC-TEST-NOT-OWNER-APPROVAL",
            "approved_at_utc":(now-timedelta(hours=1)).isoformat(),
            "expires_at_utc":(now+timedelta(hours=1)).isoformat(),
            "allowed_hosts":["suspilne.media"],
            "targets":[{"url":"https://suspilne.media/zaporizhzhia/test",
                        "role":"publisher","candidate_ids":["fake-id"]}],
            "max_requests_total":1,"max_response_bytes":4096,"min_delay_seconds":1.0}

class TestFailClosed(unittest.TestCase):
    def test_disabled(self):
        with self.assertRaisesRegex(RuntimeError,"DEFAULT_OFF"):
            e.validate_capture_approval(auth(),False,[{"candidate_id":"fake-id"}])
        with self.assertRaisesRegex(RuntimeError,"WRITTEN_OWNER"):
            e.validate_capture_approval({},True,[{"candidate_id":"fake-id"}])
    def test_exact_hosts_and_wrappers(self):
        self.assertEqual(e.source_class("https://news.google.com/rss/articles/x"),"AGGREGATOR_NOT_ORIGINAL")
        self.assertEqual(e.source_class("https://zp.npu.gov.ua/news/x"),"OFFICIAL_PRIMARY")
        self.assertEqual(e.source_class("https://zprz.city/news/x"),"PUBLISHER_OR_REPRINT")
        self.assertNotIn(e.host("https://suspilne.media.attacker.test/article"),e.CAPTURE_HOSTS)
        self.assertEqual(e.host("https://name:pass@suspilne.media/article"),"")
        a=auth()
        a["targets"][0]["url"]="https://suspilne.media.attacker.test/article"
        with self.assertRaisesRegex(RuntimeError,"TARGET_NOT_EXACT"):
            e.validate_capture_approval(a,True,[{"candidate_id":"fake-id"}])
    def test_expired(self):
        a=auth()
        a["expires_at_utc"]=(datetime.now(timezone.utc)-timedelta(minutes=2)).isoformat()
        with self.assertRaisesRegex(RuntimeError,"EXPIRED"):
            e.validate_capture_approval(a,True,[{"candidate_id":"fake-id"}])
    def test_rate_budget_limit(self):
        for field,value in (("max_requests_total",31),("max_response_bytes",1000001),
                             ("min_delay_seconds",0)):
            a=auth()
            a[field]=value
            with self.subTest(field=field),self.assertRaises(RuntimeError):
                e.validate_capture_approval(a,True,[{"candidate_id":"fake-id"}])
    def test_unknown_candidate(self):
        a=auth()
        a["targets"][0]["candidate_ids"]=["wrong"]
        with self.assertRaisesRegex(RuntimeError,"UNPINNED_WIP"):
            e.validate_capture_approval(a,True,[{"candidate_id":"fake-id"}])
    def test_http200_body_missing(self):
        candidate={"candidate_id":"fake-id","city_key":"zaporizhzhia",
                   "title":"fake","snippet":"","url":"https://news.google.com/rss/articles/fake",
                   "published_at":"2026-10-22"}
        r={"candidate_id":"fake-id","candidate_fingerprint":e.fingerprint(candidate),
           "resolved_url":"https://zprz.city/news/fake","http_status":200}
        articles,errors=e.work_a.anchored_articles([candidate],{
            "receipts":[r],"articles":[{"candidate_id":"fake-id","url":r["resolved_url"],
                "observed_at":"2026-11-12T00:00:00Z","text":""}]})
        self.assertEqual(articles,[])
        self.assertEqual(errors["fake-id"],"BLOCKED_SOURCE_CONTENT")
    def test_same_source_not_independent(self):
        urls=["https://zabor.zp.ua/new/x","https://zabor.zp.ua/new/x?utm_source=foo"]
        self.assertEqual(len({e.canonical_url(u) for u in urls}),1)
    def test_late_death_not_auto_confirmed(self):
        from casualty_auto_review import _fatal_total
        self.assertIsNone(_fatal_total("можлива загибель після атаки, офіційно не підтверджено"))
    def test_short_excerpts(self):
        result=e._short_excerpts("ДСНС уточнила: загинули 23 людини. name@example.com",[23])
        self.assertEqual(len(result),1)
        self.assertLessEqual(len(result[0]["text"]),170)
    def test_no_full_article_output(self):
        self.assertNotIn("raw_articles.json",e.ALLOWED_OUTPUTS)
        self.assertEqual(e.MODE_DEFAULT,"OFFLINE_REPLAY")

if __name__=="__main__":
    unittest.main()
