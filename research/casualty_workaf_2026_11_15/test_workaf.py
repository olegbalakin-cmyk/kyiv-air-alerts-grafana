"""Work AF strict offline tests. No DNS, media HTTP, or WIP writes."""
import concurrent.futures
import copy
import hashlib
import json
import os
import socket
import sys
import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"kyiv-air-alerts-grafana/scripts"))
import casualty_go_guard as go
import casualty_workac_capture as ac
import monitor_casualty_candidates as monitor

NOW=datetime(2026,11,15,12,tzinfo=timezone.utc)
A=Path(os.environ.get("WORKAF_A","/tmp/workaf/ae-a"))
B=Path(os.environ.get("WORKAF_B","/tmp/workaf/ae-b"))
OUT=Path(os.environ.get("WORKAF_OUT","/tmp/workaf"))
KNOWN_A="ce2e86e194bd48ea4fa08e5dcdfde72bda121068271c1f38c1ba7c6ae0a7dde0"
KNOWN_B="4e9aefeb1d2c1326c8959819c6a94d10110fa1248102c32571338fbabbea11f4"

def grant():
    g={"owner_go_id":"workaf-synthetic-20261115", "approved_head":"a"*40,
       "allowed_urls":{"rss":["https://www.ukrinform.ua/rss/block-lastnews"],
                       "article":["https://www.ukrinform.ua/rubric-ato/test"]},
       "rss_get_budget":1, "article_get_budget":1,
       "allowed_methods":["GET"],"expires_at":"2026-11-17T00:00:00Z"}
    return g,go.canonical_digest(g)

class InMemoryAtomicGitHub:
    def __init__(self):self.lock=threading.Lock();self.refs={}
    def create(self,ref,head):
        with self.lock:
            if ref in self.refs:raise go.GoBlocked("REF_EXISTS")
            self.refs[ref]=head
        return True

def retained(path,name,digest):
    data=(path/name).read_bytes()
    assert hashlib.sha256(data).hexdigest()==digest
    assert json.loads((path/"sha256_manifest.json").read_text())[name]==digest
    return json.loads(data)

class WorkAF(unittest.TestCase):
    def test_01_retrieval_cases_old_vs_new(self):
        cases=[
         ("У Харкові після ракетного удару загинули двоє","kharkiv","FATAL_ATTACK_CANDIDATE",True),
         ("В Одесі після обстрілу померла раніше поранена людина","odesa","FATAL_ATTACK_CANDIDATE",False),
         ("У Запоріжжі після атаки поранені троє","zaporizhzhia","ATTACK_FOLLOWUP_CANDIDATE",False),
         ("У Сумах після удару зруйновано будівлю","sumy","ATTACK_FOLLOWUP_CANDIDATE",False),
         ("У Запоріжжі загинули двоє людей","zaporizhzhia","NEEDS_ARTICLE_CAUSALITY_CHECK",False),
         ("На Харківщині після атаки загинули люди","kharkiv","NEEDS_ARTICLE_CITY_CHECK",True),
         ("У Сумах і Харкові після ударів загинули люди","sumy","NEEDS_ARTICLE_CITY_CHECK",True),
         ("Річниця ракетної атаки: у Києві загинули люди","kyiv","HISTORICAL_CONTEXT_NEEDS_REVIEW",True),
         ("Зведення Генштабу: втрати рф під Києвом","kyiv","OUT_OF_SCOPE",False),
         ("У Києві оголосили тривогу","kyiv","OUT_OF_SCOPE",False)]
        for text,city,status,old in cases:
            with self.subTest(text=text):
                self.assertEqual(monitor.classify_source_news(city,text),status)
                self.assertEqual(monitor.relevant_news(text),old)

    def test_02_no_region_queue_no_automatic_credit(self):
        rows=[{"url":"https://www.ukrinform.ua/region","title":"oblast",
               "routing_status":"NEEDS_ARTICLE_CITY_CHECK"},
              {"url":"https://www.ukrinform.ua/city","title":"city",
               "routing_status":"ATTACK_FOLLOWUP_CANDIDATE"}]
        queue=[]
        self.assertEqual(monitor.add_news_candidates(
            queue,"odesa",rows,[],NOW,independent=True),1)
        self.assertEqual(queue[0]["routing_status"],"ATTACK_FOLLOWUP_CANDIDATE")
        self.assertEqual(queue[0]["status"],"needs_review")
        self.assertNotIn("incident_id",queue[0])

    def test_03_exact_allowlist(self):
        for host in ("www.radiosvoboda.org","www.pravda.com.ua",
                     "en.interfax.com.ua","hromadske.radio"):
            ac.allowed_article_url("https://"+host+"/test")
        for host in ("other.radiosvoboda.org","m.radiosvoboda.org",
                     "news.pravda.com.ua","test.en.interfax.com.ua",
                     "www.hromadske.radio","example.com","127.0.0.1"):
            with self.assertRaises(ac.CaptureBlocked):
                ac.allowed_article_url("https://"+host+"/test")
        with self.assertRaises(ac.CaptureBlocked):
            ac.allowed_article_url("http://www.radiosvoboda.org/test")
        self.assertEqual((ac.MAX_BYTES,ac.CONNECT_TIMEOUT,ac.TOTAL_TIMEOUT),
                         (2*1024*1024,8,20))
        with patch.object(ac.socket,"getaddrinfo",return_value=[
            (socket.AF_INET,socket.SOCK_STREAM,6,"",("192.168.0.1",443))]):
            with self.assertRaises(ac.CaptureBlocked):
                ac._public_dns("www.radiosvoboda.org",ac.time.monotonic()+3)
        with patch.object(ac.PinnedHTTPS,"connect",side_effect=ac.CaptureBlocked("OFFLINE")):
            with self.assertRaises(ac.CaptureBlocked):
                ac.get_html("https://www.radiosvoboda.org/test")
        with self.assertRaises(ac.CaptureBlocked):
            ac._decode_limited(b"z"*(ac.MAX_BYTES+1),"identity")

    def test_04_atomic_race_rerun(self):
        g,digest=grant()
        ledger=InMemoryAtomicGitHub()
        def attempt():
            try:return go.claim_grant(g,approved_digest=digest,head="a"*40,
                    repo="owner/repo",token="offline",create_ref=ledger.create,now=NOW)
            except go.GoBlocked:return None
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            winners=list(pool.map(lambda _:attempt(),range(2)))
        self.assertEqual(sum(x is not None for x in winners),1)
        self.assertEqual(len(ledger.refs),1)
        self.assertIsNone(attempt())
        winner=next(x for x in winners if x is not None)
        winner.authorize_get("rss",g["allowed_urls"]["rss"][0])
        with self.assertRaises(go.GoBlocked):
            winner.authorize_get("rss",g["allowed_urls"]["rss"][0])
        with self.assertRaises(go.GoBlocked):
            winner.authorize_get("article","https://example.com/not-approved")

    def test_05_mutations_and_ledger_failure_fail_closed(self):
        g,digest=grant()
        variants=[]
        for key,value in (("approved_head","b"*40),("rss_get_budget",2),
                          ("allowed_methods",["POST"]),("expires_at","2026-11-14T00:00:00Z")):
            x=copy.deepcopy(g);x[key]=value;variants.append(x)
        x=copy.deepcopy(g);x["allowed_urls"]["article"][0]="https://example.com/change"
        variants.append(x)
        for x in variants:
            with self.assertRaises(go.GoBlocked):
                go.claim_grant(x,approved_digest=digest,head="a"*40,
                    repo="owner/repo",token="offline",
                    create_ref=lambda *_:self.fail("passed invalid grant"),now=NOW)
        with self.assertRaises(go.GoBlocked):
            go.claim_grant(g,approved_digest=digest,head="a"*40,
                repo="owner/repo",token="offline",
                create_ref=lambda *_: (_ for _ in ()).throw(OSError("offline fail")),now=NOW)

    def test_06_saved_pilot_integrity_filter_and_hosts(self):
        a=retained(A,"pilot_receipt.json",KNOWN_A)
        b=retained(B,"rss_pilot_metadata.json",KNOWN_B)
        self.assertEqual((a["get_attempts"],b["get_attempts"]),(6,6))
        self.assertEqual((a["article_gets"],b["article_gets"]),(0,0))
        self.assertEqual((a["automatic_credits"],b["automatic_credits"]),(0,0))
        self.assertEqual(sum(x.get("relevant_title_summary_keyword_candidates",0)
                         for x in b["results"]),6)
        self.assertEqual(sum(x.get("counts",{}).get("relevant_23city_keyword_hits",0)
                         for x in a["feeds"]),1)
        hostmap={x["rss_url"]: x["first_3_link_hashes"][0]["link_host"]
                 for x in b["results"] if x["http_status"]==200}
        self.assertEqual(hostmap,{
         "https://www.ukrinform.ua/rss/block-lastnews":"www.ukrinform.ua",
         "https://www.radiosvoboda.org/api/zrqiteuuir":"www.radiosvoboda.org",
         "https://www.pravda.com.ua/rss/view_news/":"www.pravda.com.ua",
         "https://en.interfax.com.ua/news/last.rss":"en.interfax.com.ua",
         "https://hromadske.radio/feed":"hromadske.radio",
        })
        self.assertEqual((monitor.MAX_RSS_GETS,ac.MAX_ARTICLE_GETS),(23,10))
        self.assertEqual(ac.capture_cycle([],{}, {},NOW,enabled=False)[2]["PROMOTE"],"OFF")

if __name__=="__main__":
    unittest.main()
