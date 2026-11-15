"""Work AH: strict offline executor and GO regression tests, NO publisher network."""
import copy
import hashlib
import json
import os
import socket
import sys
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"kyiv-air-alerts-grafana/scripts"))
sys.path.insert(0,str(ROOT/"research/casualty_workag_2026_11_15"))
import casualty_go_guard as go
import casualty_workac_capture as capture
import article_oneshot as runner
from test_workag import html_page

HEAD="a"*40
NOW=datetime(2026,11,15,12,tzinfo=timezone.utc)
def grant():
    return {"owner_go_id":"workahsynthetic20261115","approved_head":HEAD,
            "allowed_urls":{"rss":[],"article":list(runner.URLS)},
            "rss_get_budget":0,"article_get_budget":3,
            "allowed_methods":["GET"],"expires_at":"2026-11-19T00:00:00Z"}

def env(**kw):
    e={"CASUALTY_ARTICLE_NETWORK":"OWNER_APPROVED_ONE_SHOT",
       "GITHUB_EVENT_NAME":"workflow_dispatch","GITHUB_ACTOR":runner.OWNER,
       "GITHUB_TRIGGERING_ACTOR":runner.OWNER,
       "GITHUB_REF":"refs/heads/"+runner.RESEARCH_BRANCH,
       "GITHUB_RUN_ATTEMPT":"1","GITHUB_SHA":HEAD,
       "CASUALTY_APPROVED_HEAD":HEAD,
       "CASUALTY_OWNER_GO_ID":"workahsynthetic20261115",
       "GITHUB_REPOSITORY":runner.OWNER+"/kyiv-air-alerts-grafana",
       "GITHUB_TOKEN":"mock-only"}
    e.update(kw)
    return e

class Ledger:
    def __init__(self):
        self.lock=threading.Lock();self.refs={}
    def create(self,ref,sha):
        with self.lock:
            if ref in self.refs:raise go.GoBlocked("REF_EXISTS")
            self.refs[ref]=sha
        return True
    def claim(self,g,*,approved_digest,head,repo,token,now=None):
        return go.claim_grant(g,approved_digest=approved_digest,head=head,
                              repo=repo,token=token,now=now,create_ref=self.create)

class WorkAH(unittest.TestCase):
    def test_01_exact_urls_host_budget(self):
        self.assertEqual(len(runner.URLS),3)
        self.assertEqual([capture.allowed_article_url(u) for u in runner.URLS],list(runner.URLS))
        self.assertEqual((capture.MAX_BYTES,capture.CONNECT_TIMEOUT,capture.TOTAL_TIMEOUT),(2097152,8,20))
        g=grant()
        runner.validate_scope(g,approved_digest=go.canonical_digest(g),environ=env(),now=NOW)
        self.assertEqual((g["rss_get_budget"],g["article_get_budget"]),(0,3))

    def test_02_environment_fail_closed(self):
        for key,value in [("CASUALTY_ARTICLE_NETWORK","OFF"),
                          ("GITHUB_EVENT_NAME","push"),
                          ("GITHUB_ACTOR","other"),
                          ("GITHUB_TRIGGERING_ACTOR","other"),
                          ("GITHUB_RUN_ATTEMPT","2"),
                          ("GITHUB_REF","refs/heads/main"),
                          ("GITHUB_SHA","b"*40),
                          ("CASUALTY_APPROVED_HEAD","b"*40),
                          ("GITHUB_REPOSITORY","other/repo"),
                          ("GITHUB_TOKEN","")]:
            e=env(**{key:value})
            with self.subTest(key=key),patch.object(socket,"socket",side_effect=AssertionError("network")):
                with self.assertRaises(runner.PilotBlocked):
                    runner.validate_environment(e)

    def test_03_grant_mutations_block_before_ledger(self):
        g=grant();d=go.canonical_digest(g);ledger=Ledger()
        variants=[]
        for k,v in [("approved_head","b"*40),("article_get_budget",4),
                    ("rss_get_budget",1),("expires_at","2026-11-14T00:00:00Z"),
                    ("allowed_methods",["POST"]),("owner_go_id","other-grant")]:
            x=copy.deepcopy(g);x[k]=v;variants.append(x)
        for path in ("article","rss"):
            x=copy.deepcopy(g);x["allowed_urls"][path].append("https://example.com/extra");variants.append(x)
        x=copy.deepcopy(g);x["allowed_urls"]["article"][0]="https://mig.com.ua/changed";variants.append(x)
        for x in variants:
            with self.subTest(variant=x),patch.object(socket,"socket",side_effect=AssertionError("publisher network")):
                with self.assertRaises((go.GoBlocked,runner.PilotBlocked)):
                    runner.validate_scope(x,approved_digest=d,environ=env(),now=NOW)
        self.assertFalse(ledger.refs)

    def test_04_two_parallel_claims_exactly_one(self):
        g=grant();d=go.canonical_digest(g);ledger=Ledger()
        with ThreadPoolExecutor(max_workers=2) as p:
            def attempt(_):
                try:return ledger.claim(g,approved_digest=d,head=HEAD,repo="a/b",token="mock",now=NOW)
                except go.GoBlocked:return None
            results=list(p.map(attempt,range(2)))
        self.assertEqual(sum(x is not None for x in results),1)
        self.assertEqual(len(ledger.refs),1)
        self.assertIsNone(attempt(3))

    def test_05_repeated_same_url_and_budget(self):
        g=grant();d=go.canonical_digest(g);ledger=Ledger()
        lease=ledger.claim(g,approved_digest=d,head=HEAD,repo="a/b",token="mock",now=NOW)
        lease.authorize_get("article",runner.URLS[0])
        with self.assertRaisesRegex(go.GoBlocked,"URL_ALREADY_ATTEMPTED"):
            lease.authorize_get("article",runner.URLS[0])
        for u in runner.URLS[1:]:lease.authorize_get("article",u)
        with self.assertRaises(go.GoBlocked):
            lease.authorize_get("article","https://mig.com.ua/notapproved")
        self.assertEqual(lease.attempts["article"],3)
        with self.assertRaises(go.GoBlocked):lease.authorize_get("rss",runner.URLS[0])
        g["allowed_urls"]["article"].append("https://mig.com.ua/injected")
        with self.assertRaises(go.GoBlocked):lease.authorize_get("article",g["allowed_urls"]["article"][-1])

    def test_06_ledger_error_before_any_fetch(self):
        g=grant();d=go.canonical_digest(g)
        failures=[lambda *_:False,lambda *_: (_ for _ in ()).throw(OSError("gh unreachable"))]
        for create in failures:
            with self.assertRaises(go.GoBlocked),patch.object(socket,"socket",side_effect=AssertionError("publisher network")):
                go.claim_grant(g,approved_digest=d,head=HEAD,repo="a/b",token="mock",now=NOW,create_ref=create)

    def test_07_mocked_end_to_end_metadata_and_no_html(self):
        g=grant();d=go.canonical_digest(g);ledger=Ledger();calls=[]
        def fake(url):
            calls.append(url)
            page=html_page("ukrinform")
            return page,"text/html",200,"identity"
        output=Path("/tmp/workah/offline-article-proof.json")
        output.parent.mkdir(parents=True,exist_ok=True)
        output.unlink(missing_ok=True)
        with patch.object(capture,"get_html",side_effect=AssertionError("real GET")):
            sha=runner.execute(g,approved_digest=d,
                               environ={**env(),"CASUALTY_ARTICLE_NETWORK":"OFFLINE_MOCK"},
                               output=output,now=NOW,claim=ledger.claim,fetch=fake)
        obj=json.loads(output.read_text())
        self.assertEqual(len(calls),3)
        self.assertEqual(calls,list(runner.URLS))
        self.assertEqual(len(ledger.refs),1)
        self.assertEqual(hashlib.sha256(output.read_bytes()).hexdigest(),sha)
        self.assertTrue(all(r["http_status"]==200 and r["html_extraction"]=="BODY_EXTRACTED"
                            and r["numeric_extraction"]=="CLAIM_FOUND" and r["incident_id"] is None
                            and r["response_sha256"] and r["dedup_status"]=="NEEDS_REVIEW"
                            for r in obj["rows"]))
        self.assertEqual(obj["automatic_credits"],0)
        self.assertEqual(obj["promote"],"OFF")
        self.assertEqual(obj["cross_source_incident_identity"],"INSUFFICIENT_EVIDENCE")
        self.assertNotIn("<html",output.read_text().lower())
        self.assertNotIn("Рятувальники працювали",output.read_text())
        with self.assertRaises(go.GoBlocked):
            runner.execute(g,approved_digest=d,environ={**env(),"CASUALTY_ARTICLE_NETWORK":"OFFLINE_MOCK"},
                           output="/tmp/workah/should-not-create.json",now=NOW,claim=ledger.claim,fetch=fake)
        self.assertEqual(len(calls),3)

    def test_08_non200_and_unavailable_body_do_not_retry(self):
        g=grant();d=go.canonical_digest(g);ledger=Ledger();calls=[]
        def fake(url):
            calls.append(url)
            if len(calls)==1:return b"blocked","text/html",403,"identity"
            if len(calls)==2:return b"<html><body><div id='root'></div></body></html>","text/html",200,"identity"
            return html_page("ukrinform"),"text/html",200,"identity"
        output=Path("/tmp/workah/offline-blocked-proof.json");output.unlink(missing_ok=True)
        runner.execute(g,approved_digest=d,environ={**env(),"CASUALTY_ARTICLE_NETWORK":"OFFLINE_MOCK"},
                       output=output,now=NOW,claim=ledger.claim,fetch=fake)
        rows=json.loads(output.read_text())["rows"]
        self.assertEqual(len(calls),3)
        self.assertEqual(rows[0]["http_status"],403)
        self.assertEqual(rows[0]["error"],"HTTP_STATUS_NOT_200_403")
        self.assertEqual(rows[1]["error"],"ARTICLE_BODY_UNAVAILABLE")
        self.assertEqual(rows[1]["numeric_extraction"],"NOT_AVAILABLE")
        self.assertEqual(rows[2]["numeric_extraction"],"CLAIM_FOUND")
        self.assertEqual(len(ledger.refs),1)

    def test_09_transport_injection_forbidden_live(self):
        g=grant();d=go.canonical_digest(g)
        with self.assertRaises(runner.PilotBlocked):
            runner.execute(g,approved_digest=d,environ=env(),output="/tmp/workah/notallowed.json",
                           fetch=lambda x:None)

if __name__=="__main__":
    unittest.main()
