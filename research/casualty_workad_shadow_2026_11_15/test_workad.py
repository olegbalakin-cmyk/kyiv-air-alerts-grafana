"""Work AD strictly offline integration regression, 17 independent scenarios.

Synthetic XML/articles never count as real source evidence. Saved Work Z
proof and pre-existing WIP queue are checked separately, with no source HTTP.
"""
import hashlib
import json
import os
import socket
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"kyiv-air-alerts-grafana/scripts"))
import casualty_workac_capture as ac
import casualty_workj_rules as j
import monitor_casualty_candidates as monitor

NOW = datetime(2026, 11, 15, tzinfo=timezone.utc)
SOURCE = "https://mig.com.ua/workad-offline/"
GOOGLE = "https://news.google.com/rss/articles/opaque-fixture"
FILLER = ("Рятувальники оглянули пошкоджену територію після удару. "
          "Інформацію про подію надали для перевірки журналістам. "
          "Обставини обстрілу потребують окремого підтвердження. ")
FATAL = "У Запоріжжі після ракетного удару загинули троє людей. " + FILLER


def candidate(n, url=SOURCE, **extra):
    return {"source":"Google News RSS", "candidate_id":"ad-"+str(n),
            "city_key":"zaporizhzhia", "city":"Запоріжжя", "url":url,
            "title":"У Запоріжжі загинули люди після ракетного удару",
            "published_at":"2026-11-14T20:00:00Z", **extra}


def page(text):
    return ("<html><main><article>"+text+"</article></main></html>").encode()


def fake(text):
    return lambda url:(page(text),"text/html; charset=utf-8",200,"identity")


def cycle(text, n="one"):
    return ac.capture_cycle([candidate(n)],{},{},NOW,enabled=True,fetch=fake(text))


def rss_to_candidate(link, guid=None, is_permalink="false"):
    guidxml = (f'<guid isPermaLink="{is_permalink}">{escape(guid)}</guid>'
               if guid is not None else "")
    body = (f"<rss version='2.0'><channel><item><title>"
            "У Запоріжжі загинули троє людей після ракетного удару</title>"
            f"<link>{escape(link)}</link>{guidxml}"
            "<pubDate>Sat, 14 Nov 2026 20:00:00 GMT</pubDate>"
            "<description>У Запоріжжі після ракетного удару загинули троє людей</description>"
            "<source url='https://mig.com.ua/'>Видання</source>"
            "</item></channel></rss>").encode()
    class Response:
        status_code=200
        content=body
        def raise_for_status(self): pass
    monitor.HTTP_REQUESTS_THIS_RUN=0
    with patch.object(monitor.requests,"get",return_value=Response()) as get:
        rows,_=monitor.search_city_news("zaporizhzhia",NOW-timedelta(days=8),NOW)
        assert get.call_count==1
        assert get.call_args.kwargs["timeout"]==15
        assert get.call_args.kwargs["allow_redirects"] is False
    q=[]
    assert len(rows)==1
    assert monitor.add_news_candidates(q,"zaporizhzhia",rows,[],NOW,independent=True)==1
    return q[0]


class WorkAD(unittest.TestCase):
    def test_01_direct_rss_link(self):
        c=rss_to_candidate(SOURCE)
        self.assertEqual(ac.resolve_original_url(c),(SOURCE,"rss_item_link"))
        _,i,s=ac.capture_cycle([c],{},{},NOW,enabled=True,fetch=fake(FATAL))
        self.assertEqual((s["article_gets"],len(i["cards"])),(1,1))

    def test_02_google_guid_true_only(self):
        c=rss_to_candidate(GOOGLE,SOURCE,"true")
        self.assertEqual(ac.resolve_original_url(c),(SOURCE,"rss_guid_permalink"))
        _,i,s=ac.capture_cycle([c],{},{},NOW,enabled=True,fetch=fake(FATAL))
        self.assertEqual(i["cards"][0]["feed_url"],GOOGLE)
        self.assertEqual(i["cards"][0]["source_url_resolution_method"],"rss_guid_permalink")

    def test_03_unresolved_not_publisher_homepage(self):
        c=rss_to_candidate(GOOGLE,SOURCE,"false")
        self.assertEqual(c["publisher_url"],"https://mig.com.ua/")
        st,idx,stats=ac.capture_cycle([c],{},{},NOW,enabled=True,
                                      fetch=lambda url:self.fail("network"))
        self.assertEqual(st["candidates"][c["candidate_id"]]["status"],"SOURCE_URL_UNRESOLVED")
        self.assertEqual((stats["source_url_unresolved"],stats["article_gets"]),(1,0))
        self.assertFalse(idx["cards"])

    def test_04_allowlist_and_url_conflict(self):
        c=candidate("bad","https://example.org/unknown")
        st,idx,stats=ac.capture_cycle([c],{},{},NOW,enabled=True,
                                      fetch=lambda url:self.fail("blocked"))
        self.assertEqual(st["candidates"]["ad-bad"]["status"],"SOURCE_URL_BLOCKED")
        self.assertEqual(stats["article_url_blocked"],1)
        with self.assertRaisesRegex(ac.CaptureBlocked,"SOURCE_URL_CONFLICT"):
            ac.resolve_original_url(candidate("conflict",SOURCE,
                         rss_guid_url="https://ukrinform.ua/other",
                         rss_guid_is_permalink=True))

    def test_05_three_deaths_with_complete_quote(self):
        _,idx,stats=cycle(FATAL)
        row=idx["cards"][0]
        self.assertEqual(row["fatal_total_claimed_not_credited"],3)
        self.assertEqual(row["count_kind_claimed"],"cumulative")
        self.assertTrue(any(x["claim_number"]==3 for x in row["source_excerpts"]))
        self.assertEqual(row["response_sha256"],hashlib.sha256(page(FATAL)).hexdigest())
        self.assertEqual(row["source_url_resolution_method"],"rss_item_link")
        self.assertEqual(stats["numeric_cumulative"],1)

    def test_06_late_death_not_cumulative(self):
        text="У Запоріжжі після ракетного удару померла ще одна людина. "+FILLER
        _,idx,stats=cycle(text,"delta")
        row=idx["cards"][0]
        self.assertEqual(row["count_kind_claimed"],"delta")
        self.assertIsNone(row["fatal_total_claimed_not_credited"])
        self.assertIn("LATE_DEATH_REQUIRES_INCIDENT_LINK_AND_BASELINE",row["reasons"])
        self.assertEqual(stats["numeric_delta_held"],1)
        self.assertIsNone(j._fatal_total("померла ще одна людина"))

    def test_07_wounded_not_dead(self):
        _,idx,s=cycle("У Запоріжжі після ракетного удару поранені троє людей. "+FILLER,"wounded")
        self.assertIsNone(idx["cards"][0]["fatal_total_claimed_not_credited"])
        self.assertEqual(s["numeric_cumulative"],0)

    def test_08_age_numbers_not_counts(self):
        _,idx,_=cycle("Від ракетного удару в Запоріжжі постраждали 37, 38 і 69-річні. "+FILLER,"ages")
        self.assertIsNone(idx["cards"][0]["fatal_total_claimed_not_credited"])
        _,idx,_=cycle("У Запоріжжі після ракетного удару загинули троє людей віком 37, 38 і 69 років. "+FILLER,"age-with-count")
        self.assertEqual(idx["cards"][0]["fatal_total_claimed_not_credited"],3)

    def test_09_multiple_attacks_cannot_merge(self):
        text=("22 жовтня 2026 року атакували Запоріжжя ракетою вранці. "
              "Загинули двоє людей. Також окремо атакували Запоріжжя увечері. "
              "Загинули троє людей. "+FILLER)
        _,idx,_=cycle(text,"multi")
        row=idx["cards"][0]
        self.assertIsNone(row["fatal_total_claimed_not_credited"])
        self.assertIn("MULTIPLE_POSSIBLE_INCIDENTS",row["reasons"])

    def test_10_18_20_23_not_61(self):
        q=[candidate(n,f"https://mig.com.ua/workad-offline/{n}") for n in (18,20,23)]
        def get(url):
            n=int(url.rsplit("/",1)[-1])
            return page(f"У Запоріжжі після ракетного удару загинули {n} людей. "+FILLER),"text/html",200,"identity"
        _,idx,stats=ac.capture_cycle(q,{},{},NOW,enabled=True,fetch=get)
        self.assertEqual([x["fatal_total_claimed_not_credited"] for x in idx["cards"]],[18,20,23])
        self.assertEqual(stats["numeric_cumulative"],3)
        self.assertEqual(sum(x["automatic_credits"] for x in idx["cards"]),0)
        self.assertTrue(all(x["incident_id"] is None for x in idx["cards"]))

    def test_11_replay_idempotence(self):
        q=[candidate("repeat")]
        st,idx,_=ac.capture_cycle(q,{},{},NOW,enabled=True,fetch=fake(FATAL))
        st,idx,stats=ac.capture_cycle(q,st,idx,NOW+timedelta(hours=4),
                                     enabled=True,fetch=fake(FATAL))
        self.assertEqual((len(idx["cards"]),stats["evidence_new"],
                          stats["evidence_replay_duplicates"]),(1,0,1))

    def test_12_failure_queue_retention(self):
        q=[candidate("retry")]
        old=json.dumps(q,sort_keys=True)
        def fail(url): raise TimeoutError("offline")
        st,idx,stats=ac.capture_cycle(q,{},{},NOW,enabled=True,fetch=fail)
        self.assertEqual(st["candidates"]["ad-retry"]["status"],"RETRY_PENDING")
        self.assertEqual(json.dumps(q,sort_keys=True),old)
        self.assertEqual(stats["article_errors"],1)
        _,idx,s=ac.capture_cycle(q,st,idx,NOW+timedelta(hours=4),enabled=True,fetch=fake(FATAL))
        self.assertEqual(s["evidence_new"],1)

    def test_13_saved_workz_unchanged_insufficient(self):
        p=Path(os.environ.get("WORKAB_OUT","/tmp/workab"))/"saved_evidence_summary.json"
        self.assertTrue(p.is_file(),"saved Work Z proof must be present in exact-head CI")
        d=json.loads(p.read_text())
        self.assertEqual(d["source_index_summary"]["total"],3)
        self.assertEqual(set(d["pair_decisions"].values()),{"INSUFFICIENT_EVIDENCE"})
        self.assertEqual(d["incident_id_proven"],0)

    def test_14_budgets_dns_and_payload(self):
        self.assertEqual((monitor.MAX_RSS_GETS,monitor.RSS_TIMEOUT_SECONDS),(23,15))
        self.assertEqual((ac.MAX_ARTICLE_GETS,ac.CONNECT_TIMEOUT,ac.TOTAL_TIMEOUT),(10,8,20))
        self.assertEqual(ac.MAX_BYTES,2*1024*1024)
        q=[candidate(n,f"https://mig.com.ua/workad-offline/{n}") for n in range(23)]
        calls=[]
        def fail(url):
            calls.append(url)
            raise TimeoutError("mock")
        _,_,s=ac.capture_cycle(q,{},{},NOW,enabled=True,fetch=fail)
        self.assertEqual((len(calls),s["article_gets"],s["article_errors"]),(10,10,10))
        with self.assertRaises(ac.CaptureBlocked):
            ac._decode_limited(b"x"*(ac.MAX_BYTES+1),"identity")
        with patch.object(ac.socket,"getaddrinfo",return_value=[
            (socket.AF_INET,socket.SOCK_STREAM,6,"",("127.0.0.1",443))]):
            with self.assertRaises(ac.CaptureBlocked):
                ac._public_dns("mig.com.ua",ac.time.monotonic()+2)

    def test_15_hard_off_and_no_credits(self):
        q=[candidate("off")]
        st,idx,s=ac.capture_cycle(q,{},{},NOW,enabled=False,fetch=lambda u:self.fail("off"))
        self.assertEqual(s["article_gets"],0)
        st,idx,s=ac.capture_cycle(q,st,idx,NOW,enabled=True,fetch=fake(FATAL))
        self.assertEqual(s["PROMOTE"],"OFF")
        self.assertEqual(s["automatic_credits"],0)
        self.assertFalse(s["publication_allowed"])
        self.assertTrue(all(x["incident_id"] is None and x["automatic_credits"]==0 and
                            x["publication_allowed"] is False for x in idx["cards"]))

    def test_16_no_external_sockets(self):
        with patch.object(socket,"socket",side_effect=AssertionError("NETWORK_ATTEMPT")), \
             patch.object(monitor.requests,"get",side_effect=AssertionError("RSS_ATTEMPT")):
            _,idx,s=cycle(FATAL,"socket")
            self.assertEqual(idx["cards"][0]["fatal_total_claimed_not_credited"],3)

    def test_17_physical_proof(self):
        q=[candidate("d"),candidate("g",GOOGLE,rss_guid_url=SOURCE,rss_guid_is_permalink=True),
           candidate("u",GOOGLE,publisher_url="https://mig.com.ua/"),
           candidate("b","https://example.org/blocked")]
        st,idx,stats=ac.capture_cycle(q,{},{},NOW,enabled=True,fetch=fake(FATAL))
        self.assertEqual([st["candidates"][x["candidate_id"]]["status"] for x in q],
                         ["CAPTURED","CAPTURED","SOURCE_URL_UNRESOLVED","SOURCE_URL_BLOCKED"])
        self.assertEqual(stats["numeric_cumulative"],2)
        z=json.loads((Path(os.environ.get("WORKAB_OUT","/tmp/workab"))/
                      "saved_evidence_summary.json").read_text())
        self.assertEqual(set(z["pair_decisions"].values()),{"INSUFFICIENT_EVIDENCE"})
        saved_queue=json.loads((ROOT/"kyiv-air-alerts-grafana/data/casualties/multicity_review_queue.json").read_text())
        saved=[x for x in saved_queue if isinstance(x,dict) and x.get("source")=="Google News RSS"][:25]
        counts={"resolved":0,"unresolved":0,"blocked":0}
        for x in saved:
            try:
                ac.resolve_original_url(x)
                counts["resolved"]+=1
            except ac.CaptureBlocked as exc:
                counts["unresolved" if str(exc)=="SOURCE_URL_UNRESOLVED" else "blocked"]+=1
        import subprocess
        self.assertFalse(subprocess.check_output(["git","diff","--name-only"],cwd=ROOT,text=True).strip())
        result={
            "exact_head":os.getenv("GITHUB_SHA","LOCAL"),
            "fixture_separation":{"rss_xml":"synthetic","article_html":"synthetic",
                                  "workj":"verbatim_helpers_from_pr121",
                                  "saved_workz":"retained_real_short_evidence",
                                  "saved_queue":"retained_real_candidates_no_rss_xml"},
            "synthetic_url_resolution":{"resolved":2,"unresolved":1,"blocked":1},
            "saved_wip_queue_sample_25":{"sample_size":len(saved),**counts},
            "synthetic_claims":{"cumulative":2,"delta_held":1,
                                "blocked_categories":["wounded","ages","multiple_attacks"]},
            "saved_t03_t05":{"pair_decisions":z["pair_decisions"],
                             "all_insufficient_evidence":True,"incident_ids_verified":0},
            "source_http_gets":0,"rss_budget":23,"rss_timeout_sec":15,"article_budget":10,
            "article_connect_timeout_sec":8,"article_total_timeout_sec":20,
            "article_limit_bytes":2*1024*1024,"redirects_followed":0,
            "automatic_retries":0,"automatic_credits":0,"PROMOTE":"OFF",
            "publication_allowed":False,"real_rss_to_verified_counted_card":False,
            "main_siteprod_wip_mutations_by_this_work":0
        }
        p=Path(os.getenv("WORKAD_OUT","/tmp/workad"))/"workad_results.json"
        p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(json.dumps(result,sort_keys=True,ensure_ascii=False,indent=2)+"\n")


if __name__=="__main__":
    unittest.main()
