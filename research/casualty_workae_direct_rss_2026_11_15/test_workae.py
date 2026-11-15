"""Work AE: direct RSS integration, synthetic offline-only source fixtures."""
import json
import socket
import sys
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"kyiv-air-alerts-grafana/scripts"))
import casualty_workac_capture as ac
import monitor_casualty_candidates as monitor

NOW=datetime(2026,11,15,10,tzinfo=timezone.utc)
FEED1="https://www.ukrinform.ua/rss/block-lastnews"
FEED2="https://www.ukrinform.ua/rss/other"
ARTICLE="https://www.ukrinform.ua/rubric-ato/one-article.html"
PHRASE="У Запоріжжі після російського ракетного удару загинули троє людей."
FILLER=" Рятувальники обстежили місце атаки й повідомили про наслідки для цивільних. "*5

def rss(links, date="Sun, 15 Nov 2026 09:30:00 +0200"):
    items=[]
    for link,title in links:
        items.append("<item><title>"+title+"</title><link>"+link+"</link><pubDate>"+date+
                     "</pubDate><description>"+PHRASE+"</description></item>")
    return ("<?xml version='1.0' encoding='utf-8'?><rss version='2.0'><channel>"+
           "".join(items)+"</channel></rss>").encode()

def html():
    return ("<html><main><article>"+PHRASE+FILLER+"</article></main></html>").encode()

class WorkAE(unittest.TestCase):
    def setUp(self):
        monitor.HTTP_REQUESTS_THIS_RUN=0
        self.queue=[]
        self.state={}
        self.index={}

    def read(self,feed,items, fail=False):
        def transport(url,**kw):
            if fail: raise TimeoutError("mock source error")
            self.assertEqual(url,feed)
            self.assertTrue(kw["expect_xml"])
            self.assertEqual(kw["total_timeout"],15)
            return rss(items),"application/rss+xml",200,"identity"
        with patch.object(ac,"get_html",side_effect=transport),patch.object(monitor.requests,"get",side_effect=AssertionError("unapproved HTTP")):
            return monitor.search_city_news("zaporizhzhia",NOW-timedelta(hours=48),NOW,feed_url=feed,feed_name="Укрінформ")

    def test_direct_rss_to_workj_workx(self):
        rows,url=self.read(FEED1,[(ARTICLE,PHRASE)])
        self.assertEqual(url,FEED1)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["published_at"],"2026-11-15T07:30:00Z")
        self.assertEqual(rows[0]["source"],"Direct RSS")
        self.assertEqual(monitor.add_news_candidates(self.queue,"zaporizhzhia",rows,[],NOW,independent=True),1)
        with patch.object(socket,"socket",side_effect=AssertionError("real socket")):
            st,idx,stats=ac.capture_cycle(self.queue,{},{},NOW,enabled=True,fetch=lambda u:(html(),"text/html",200,"identity"))
        self.assertEqual(stats["article_gets"],1)
        self.assertEqual(len(idx["cards"]),1)
        self.assertEqual(idx["cards"][0]["fatal_total_claimed_not_credited"],3)
        self.assertEqual(idx["cards"][0]["decision"],"NEEDS_REVIEW")
        self.assertEqual(idx["cards"][0]["automatic_credits"],0)
        self.assertFalse(idx["cards"][0]["publication_allowed"])
        self.assertEqual(stats["PROMOTE"],"OFF")

    def test_two_feeds_same_article_single_candidate(self):
        for feed,title in [(FEED1,PHRASE),(FEED2,PHRASE+" — оновлено")]:
            rows,_=self.read(feed,[(ARTICLE,title)])
            monitor.add_news_candidates(self.queue,"zaporizhzhia",rows,[],NOW,independent=True)
        self.assertEqual(len(self.queue),1)
        self.assertEqual(sorted(self.queue[0]["discovered_feeds"]),sorted([FEED1,FEED2]))
        st,idx,stats=ac.capture_cycle(self.queue,{},{},NOW,enabled=True,fetch=lambda u:(html(),"text/html",200,"identity"))
        self.assertEqual((len(idx["cards"]),stats["evidence_new"]),(1,1))
        st,idx,stats=ac.capture_cycle(self.queue,st,idx,NOW+timedelta(hours=4),enabled=True,fetch=lambda u:(html(),"text/html",200,"identity"))
        self.assertEqual((len(idx["cards"]),stats["evidence_new"]),(1,0))

    def test_feed_failure_cursor_stays(self):
        prior="2026-11-15T06:00:00Z"
        state={"cities":{"zaporizhzhia":{"last_independent_source_scan_at":prior}}}
        with self.assertRaises(TimeoutError):
            self.read(FEED1,[(ARTICLE,PHRASE)],fail=True)
        self.assertEqual(state["cities"]["zaporizhzhia"]["last_independent_source_scan_at"],prior)
        self.assertEqual(self.queue,[])

    def test_bad_hosts_and_nonrss(self):
        with self.assertRaises(ac.CaptureBlocked):
            monitor.search_city_news("zaporizhzhia",NOW-timedelta(hours=48),NOW,feed_url="https://example.com/feed")
        with patch.object(ac,"get_html",return_value=(b"<html/>","application/rss+xml",200,"identity")):
            with self.assertRaisesRegex(RuntimeError,"DIRECT_FEED_NOT_RSS2_XML"):
                monitor.search_city_news("zaporizhzhia",NOW-timedelta(hours=48),NOW,feed_url=FEED1)

    def test_different_attacks_not_auto_combined(self):
        rows,_=self.read(FEED1,[(ARTICLE,PHRASE),("https://www.ukrinform.ua/rubric-ato/two-article.html",PHRASE)])
        monitor.add_news_candidates(self.queue,"zaporizhzhia",rows,[],NOW,independent=True)
        self.assertEqual(len(self.queue),2)
        st,idx,stats=ac.capture_cycle(self.queue,{},{},NOW,enabled=True,fetch=lambda u:(html(),"text/html",200,"identity"))
        self.assertEqual(len(idx["cards"]),2)
        self.assertTrue(all(c["incident_id"] is None for c in idx["cards"]))
        self.assertEqual(stats["automatic_credits"],0)

    def test_budgets_default_no_activated_network(self):
        self.assertEqual((monitor.MAX_RSS_GETS,ac.MAX_ARTICLE_GETS),(23,10))
        self.assertEqual(monitor.GOOGLE_NEWS_URL,"https://news.google.com/rss/search")
        self.assertEqual(monitor.HTTP_REQUESTS_THIS_RUN,0)
        self.assertEqual(ac.capture_cycle([],{},{},NOW,enabled=False)[2]["article_gets"],0)

if __name__=="__main__":
    unittest.main()
