#!/usr/bin/env python3
"""Work I local-only redirect safety test suite."""
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from research.casualty_controlled_capture_preflight_2026_11_13 import test_preflight as g

e=g.e
U=g.PLAN["targets"][0]["url"]

def policy(redirects=None):
    a=g.live_shaped()
    a["targets"][0]["approved_redirect_urls"]=list(redirects or [])
    e.validate_capture_approval(a,True,g.Preflight.queue)
    return a

def attempt(replies,redirects=None,used=0,a=None):
    opener=g.FakeOpener(replies)
    budget={"used":used}
    with patch.object(e.time,"sleep") as pause:
        receipt,body=e._capture_once(U,a or policy(redirects),budget,opener)
    return receipt,body,opener.urls,budget["used"],pause

class StrictRedirect(unittest.TestCase):
    def test_01_initial_url_pass(self):
        rec,body,urls,used,_=attempt([g.Response()])
        self.assertEqual(urls,[U])
        self.assertEqual(used,1)
        self.assertTrue(body)
        self.assertEqual(rec["resolved_url"],U)
    def test_02_same_host_new_path_blocked_before_second_get(self):
        dest="https://zprz.city/other-attack"
        rec,body,urls,used,_=attempt([g.Response(302,dest)])
        self.assertEqual((urls,used,body),([U],1,""))
        self.assertEqual(rec["reason"],"REDIRECT_NOT_EXACT_APPROVED")
        self.assertEqual(rec["blocked_redirect_url"],dest)
    def test_03_exact_approved_redirect_pass(self):
        dest="https://zprz.city/approved/second?x=1"
        rec,body,urls,used,pause=attempt([g.Response(302,dest),g.Response()],[dest])
        self.assertEqual(urls,[U,dest])
        self.assertEqual(used,2)
        self.assertEqual(rec["request_attempt_urls"],urls)
        self.assertTrue(body)
        pause.assert_called_once_with(1)
    def test_04_foreign_host_http_userinfo_port_ip_all_blocked(self):
        for dest in ("https://evil.invalid/p","http://zprz.city/p",
            "https://name:pass@zprz.city/p","https://zprz.city:8443/p",
            "https://127.0.0.1/p","https://zprz.city.attacker.invalid/p"):
            with self.subTest(dest=dest):
                rec,_,urls,used,_=attempt([g.Response(302,dest)])
                self.assertEqual((urls,used),([U],1))
                self.assertEqual(rec["reason"],"REDIRECT_NOT_ALLOWLISTED")
    def test_05_query_amp_slash_are_not_canonicalized(self):
        for dest in (U+"?x=2",U+"/",U+"?utm_source=abc",
                     U.replace("/news/view/","/amp/news/view/")):
            with self.subTest(dest=dest):
                rec,_,urls,_,_=attempt([g.Response(302,dest)])
                self.assertEqual(urls,[U])
                self.assertEqual(rec["reason"],"REDIRECT_NOT_EXACT_APPROVED")
    def test_06_other_initial_source_not_allowed_as_redirect(self):
        dest=g.PLAN["targets"][1]["url"]
        a=g.live_shaped()
        a["targets"][0]["approved_redirect_urls"]=[dest]
        with self.assertRaisesRegex(RuntimeError,"REDIRECT_CROSSES_SOURCE_TARGET"):
            e.validate_capture_approval(a,True,g.Preflight.queue)
        rec,_,urls,_,_=attempt([g.Response(302,dest)])
        self.assertEqual(urls,[U])
        self.assertEqual(rec["reason"],"REDIRECT_NOT_EXACT_APPROVED")
    def test_07_self_loop_and_two_node_cycle(self):
        rec,_,urls,_,_=attempt([g.Response(302,U)])
        self.assertEqual((rec["reason"],urls),("REDIRECT_LOOP",[U]))
        a="https://zprz.city/a"
        rec,_,urls,used,_=attempt([g.Response(302,a),g.Response(302,U)],[a])
        self.assertEqual((rec["reason"],urls,used),("REDIRECT_LOOP",[U,a],2))
    def test_08_more_than_three_redirects(self):
        hops=["https://zprz.city/approved/"+str(i) for i in range(3)]
        rec,_,urls,used,_=attempt([g.Response(302,hops[0]),g.Response(302,hops[1]),
            g.Response(302,hops[2]),g.Response(302,"https://zprz.city/not-approved")],hops)
        self.assertEqual(rec["reason"],"REDIRECT_LIMIT")
        self.assertEqual((urls,used),([U]+hops,4))
    def test_09_aggregate_budget_blocks_before_request(self):
        dest="https://zprz.city/approved/budget"
        rec,_,urls,used,_=attempt([g.Response(302,dest)],[dest],used=19)
        self.assertEqual((rec["reason"],urls,used),("REQUEST_BUDGET_EXCEEDED",[U],20))
        rec,_,urls,used,_=attempt([],used=20)
        self.assertEqual((rec["reason"],urls),("REQUEST_BUDGET_EXCEEDED",[]))
    def test_10_expired_and_over_24h_auth(self):
        a=g.live_shaped()
        a["expires_at_utc"]=(datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat()
        with self.assertRaisesRegex(RuntimeError,"EXPIRED"):
            e.validate_capture_approval(a,True,g.Preflight.queue)
        rec,_,urls,_,_=attempt([],a=a)
        self.assertEqual((rec["reason"],urls),("AUTHORIZATION_EXPIRED",[]))
        a=g.live_shaped()
        a["expires_at_utc"]=(datetime.now(timezone.utc)+timedelta(hours=25)).isoformat()
        with self.assertRaisesRegex(RuntimeError,"EXPIRED"):
            e.validate_capture_approval(a,True,g.Preflight.queue)
    def test_11_disabled_flag_no_socket(self):
        with patch.object(e,"_capture_once",side_effect=AssertionError("GET")) as capture:
            with self.assertRaisesRegex(RuntimeError,"DEFAULT_OFF"):
                e.controlled_capture(g.TEMPLATE,g.Preflight.queue,enabled=False)
            capture.assert_not_called()
    def test_12_invalid_explicit_redirect_approval(self):
        for dest in ("http://zprz.city/new","https://zprz.city:444/new",
                     "https://user:pass@zprz.city/new"):
            with self.subTest(dest=dest):
                a=g.live_shaped()
                a["targets"][0]["approved_redirect_urls"]=[dest]
                with self.assertRaisesRegex(RuntimeError,"REDIRECT_TARGET_NOT_EXACT"):
                    e.validate_capture_approval(a,True,g.Preflight.queue)
    def test_13_stop_entire_pilot_on_redirect_violation(self):
        mock={"reason":"REDIRECT_NOT_EXACT_APPROVED","redirect_chain":[]}
        with patch.object(e,"_capture_once",return_value=(mock,"")) as capture:
            data,audit=e.controlled_capture(policy(),g.Preflight.queue,enabled=True)
        self.assertEqual(capture.call_count,1)
        self.assertEqual(audit["stop_reason"],"REDIRECT_NOT_EXACT_APPROVED")
        self.assertFalse(audit["publication_allowed"])
        self.assertEqual(data["articles"],[])
    def test_14_exact_key_preserves_query_case_and_path(self):
        u="https://zprz.city/news?x=1&y=2"
        self.assertEqual(e._exact_request_key(u),
                         e._exact_request_key("https://ZPRZ.CITY:443/news?x=1&y=2"))
        for v in (u+"/",u.replace("x=1&y=2","y=2&x=1"),
                  u.replace("/news","/NEWS"),u+"#fragment"):
            self.assertNotEqual(e._exact_request_key(u),e._exact_request_key(v))
        self.assertIsNone(e._exact_request_key("https://user@zprz.city/new"))

if __name__=="__main__":
    unittest.main(verbosity=2)
