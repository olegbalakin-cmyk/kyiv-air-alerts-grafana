"""Work K physical runner and retention verification. Pure mocks, no HTTP."""
import copy
import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from research.casualty_one_time_capture_2026_11_13 import run_capture as r
from research.casualty_controlled_capture_preflight_2026_11_13 import test_preflight as g

CID03 = "7c3ac3280ba7ad4b9c10f3b1"
CID04 = "dcdd2fe28fd1464e7fbabdc1"


def queue():
    return [
        {"candidate_id": cid, "city_key": "zaporizhzhia", "city": "Запоріжжя",
         "url": "https://news.google.com/rss/articles/fixture",
         "published_at": "2026-10-22T12:00:00Z", "title": "fixture", "snippet": ""}
        for cid in (CID03, CID04)
    ]


def mock_inputs():
    plan = json.loads(r.PLAN_PATH.read_text(encoding="utf-8"))
    t03, t04, t05 = plan["targets"]
    bodies = [
        "22 жовтня російська ракета атакувала Запоріжжя. Загинули 2 людини. Відомості потребують перевірки.",
        "22 жовтня російська ракета атакувала Запоріжжя. Кількість загиблих зросла до 3 людей. Відомості уточнюють.",
        "22 жовтня поліція повідомила про російські атаки у Запорізькій області. Загинули 3 людини. Зв'язок з конкретною атакою невідомий.",
    ]
    hashes = [hashlib.sha256(("mock-html-response-"+str(i)).encode()).hexdigest() for i in range(3)]
    original = {
        "articles": [
            {"candidate_id": CID03, "url": t03["url"], "text": bodies[0], "observed_at": "2026-10-22T12:00:00Z"},
            {"candidate_id": CID04, "url": t04["url"], "text": bodies[1], "observed_at": "2026-10-22T13:00:00Z"},
        ],
        "official_articles": [{"url": t05["url"], "text": bodies[2],
                               "observed_at": "2026-10-22T14:00:00Z",
                               "response_sha256": hashes[2]}],
        "receipts": [
            {"candidate_id": cid, "resolved_url": t["url"],
             "response_sha256": hashes[i], "http_status": 200}
            for i, (cid, t) in enumerate(((CID03,t03),(CID04,t04)))
        ],
    }
    audit = {"requests_used": 3, "targets": [
        {"requested_url": t["url"], "resolved_url": t["url"],
         "response_sha256": hashes[i], "http_status": 200,
         "reason": "BODY_EXTRACTED_NOT_VERIFIED", "redirect_chain": []}
        for i,t in enumerate(plan["targets"])
    ]}
    return plan, original, audit, bodies


def synthetic_launch():
    now = datetime.now(timezone.utc)
    return {
        "scope": r.SCOPE, "expected_source_base_sha": r.EXPECTED_BASE,
        "owner_approval_record": "SYNTHETIC-TEST-ONLY",
        "authorization_id": "CASUALTY-T03-T05-SYNTHETIC-TEST-ONLY",
        "expected_previous_commit_sha": "a"*40,
        "approved_at_utc": (now-timedelta(minutes=1)).isoformat(),
        "expires_at_utc": (now+timedelta(hours=1)).isoformat(),
        "publication_allowed": False, "automatic_promote_allowed": False,
        "repeat_allowed": False,
    }


def synthetic_env():
    return {"GITHUB_REF": "refs/heads/"+r.EXPECTED_BRANCH,
            "GITHUB_EVENT_NAME": "push", "GITHUB_RUN_ATTEMPT": "1",
            "GITHUB_EVENT_BEFORE": "a"*40}


class WorkK(unittest.TestCase):
    def test_01_exact_three_targets_default_off(self):
        p, t = r.check_scope(queue())
        self.assertEqual([x["target_id"] for x in p["targets"]], ["T03","T04","T05"])
        self.assertEqual(p["allowed_hosts"], ["mig.com.ua","ukrinform.ua","zp.npu.gov.ua"])
        self.assertEqual(t["max_requests_total"], 6)
        self.assertEqual(t["status"], "NOT_AUTHORIZED")
        self.assertFalse(t["enable_controlled_capture"])
        self.assertEqual([x["approved_redirect_urls"] for x in t["targets"]],[[],[],[]])
        self.assertFalse((r.HERE/"launch.json").exists())

    def test_02_workj_called_and_cards_written_to_proof(self):
        p, original, audit, bodies = mock_inputs()
        with tempfile.TemporaryDirectory() as td:
            with patch.object(r.e,"minimal_capture_facts",wraps=r.e.minimal_capture_facts) as called:
                r.retain_results(queue(),p,original,audit,Path(td),authorization_id="SYNTHETIC")
            called.assert_called_once()
            files = {x.name for x in Path(td).glob("*.json")}
            self.assertEqual(files,{"capture_receipts.json","fact_preview_unverified.json",
                                    "minimal_capture_facts.json","summary.json","manifest.json"})
            facts = json.loads((Path(td)/"minimal_capture_facts.json").read_text())["facts"]
            self.assertEqual(len(facts),3)
            for c in facts:
                self.assertTrue(c["source_url"].startswith("https://"))
                self.assertIn(c["source_role"],("official","publisher"))
                self.assertRegex(c["document_sha256"],"^[0-9a-f]{64}$")
                self.assertEqual(c["decision"],"NEEDS_REVIEW")
                self.assertTrue(all(len(x["text"])<=170 for x in c["excerpts"]))
            self.assertEqual([c["source_role"] for c in facts],["publisher","publisher","official"])
            self.assertEqual([c["claim_deaths"] for c in facts],[2,3,3])
            for source_body in bodies:
                for filename in files:
                    self.assertNotIn(source_body,(Path(td)/filename).read_text())

    def test_03_manifest_content_hashes_match(self):
        p,original,audit,_ = mock_inputs()
        with tempfile.TemporaryDirectory() as td:
            r.retain_results(queue(),p,original,audit,Path(td),authorization_id="SYNTHETIC")
            manifest=json.loads((Path(td)/"manifest.json").read_text())
            self.assertEqual(len(manifest["files_sha256"]),4)
            for file, digest in manifest["files_sha256"].items():
                self.assertEqual(hashlib.sha256((Path(td)/file).read_bytes()).hexdigest(),digest)

    def test_04_two_then_three_never_five(self):
        p,original,audit,_=mock_inputs()
        with tempfile.TemporaryDirectory() as td:
            result=r.retain_results(queue(),p,original,audit,Path(td),authorization_id="SYNTHETIC")
            facts=json.loads((Path(td)/"minimal_capture_facts.json").read_text())["facts"]
            self.assertEqual([x["claim_deaths"] for x in facts],[2,3,3])
            self.assertFalse(any(x["claim_deaths"]==5 for x in facts))
            self.assertEqual(result["automatic_death_credits"],0)
            self.assertIsNone(result["proposed_new_credits"])
            self.assertFalse(result["oct22_prior_credit_reconciled"])

    def test_05_publisher_quote_not_official_confirmation(self):
        p,original,audit,_=mock_inputs()
        original["articles"][0]["text"]="22 жовтня ракета атакувала Запоріжжя. За даними поліції, загинули 2 людини."
        with tempfile.TemporaryDirectory() as td:
            r.retain_results(queue(),p,original,audit,Path(td),authorization_id="SYNTHETIC")
            facts=json.loads((Path(td)/"minimal_capture_facts.json").read_text())
            self.assertEqual(facts["facts"][0]["source_role"],"publisher")
            self.assertIsNone(facts["facts"][2]["candidate_id"])
            self.assertEqual(facts["official_incidents_automatically_matched"],0)

    def test_06_missing_evidence_has_needs_review_reason(self):
        p,original,audit,_=mock_inputs()
        original["articles"].pop(1)
        original["receipts"].pop(1)
        with tempfile.TemporaryDirectory() as td:
            r.retain_results(queue(),p,original,audit,Path(td),authorization_id="SYNTHETIC")
            decisions=json.loads((Path(td)/"fact_preview_unverified.json").read_text())["source_decisions"]
            self.assertEqual(decisions[1]["decision"],"NEEDS_REVIEW")
            self.assertNotEqual(decisions[1]["reason"],"SOURCE_FACTS_RETAINED_UNVERIFIED")

    def test_07_unknown_redirect_blocks_before_second_get(self):
        _,template=r.check_scope(queue())
        policy=r.validate_launch(synthetic_launch(),template,queue(),environ=synthetic_env())
        opener=g.FakeOpener([g.Response(302,"https://www.ukrinform.ua/unknown-path")])
        plan=json.loads(r.PLAN_PATH.read_text())
        receipt,body=r.e._capture_once(plan["targets"][0]["url"],policy,{"used":0},opener)
        self.assertEqual(receipt["reason"],"REDIRECT_NOT_EXACT_APPROVED")
        self.assertEqual(len(opener.urls),1)
        self.assertFalse(body)

    def test_08_expired_and_reused_grant_blocks(self):
        _,template=r.check_scope(queue())
        grant=synthetic_launch()
        self.assertEqual(r.validate_launch(grant,template,queue(),environ=synthetic_env())["max_requests_total"],6)
        grant["expires_at_utc"]=(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()
        with self.assertRaisesRegex(RuntimeError,"EXPIRED"):
            r.validate_launch(grant,template,queue(),environ=synthetic_env())
        env=synthetic_env()
        env["GITHUB_RUN_ATTEMPT"]="2"
        with self.assertRaisesRegex(RuntimeError,"FRESH_SINGLE_PUSH"):
            r.validate_launch(synthetic_launch(),template,queue(),environ=env)

    def test_09_previous_scope_and_authorization_rejected(self):
        _,template=r.check_scope(queue())
        grant=synthetic_launch()
        grant["scope"]="EXACT_PR111_T01_TO_T10_SINGLE_EXECUTION"
        with self.assertRaisesRegex(RuntimeError,"NEW_OWNER_GRANT_SCOPE"):
            r.validate_launch(grant,template,queue(),environ=synthetic_env())
        grant=synthetic_launch()
        grant["authorization_id"]="CASUALTY-T01-T10-OWNER-20261113-ONE-SHOT-01"
        with self.assertRaisesRegex(RuntimeError,"NEW_OWNER_GRANT_SCOPE"):
            r.validate_launch(grant,template,queue(),environ=synthetic_env())

    def test_10_no_launch_no_capture(self):
        import sys
        with tempfile.TemporaryDirectory() as td:
            path=r.ROOT/"_wip/kyiv-air-alerts-grafana/data/casualties/multicity_review_queue.json"
            with patch.object(r.e,"controlled_capture",side_effect=AssertionError("OUTBOUND")) as capture:
                with patch.object(sys,"argv",["runner","--queue",str(path),"--output",td]):
                    with self.assertRaisesRegex(RuntimeError,"MISSING_SEPARATE_OWNER_GRANT"):
                        r.main()
                capture.assert_not_called()

    def test_11_no_automatic_data_change(self):
        p,original,audit,_=mock_inputs()
        with tempfile.TemporaryDirectory() as td:
            summary=r.retain_results(queue(),p,original,audit,Path(td),authorization_id="SYNTHETIC")
            for k in ("production_changed","wip_changed","neon_changed","publication_allowed",
                      "full_article_bodies_saved","official_links_verified","oct22_prior_credit_reconciled"):
                self.assertFalse(summary[k])
            self.assertEqual(summary["automatic_death_credits"],0)

    def test_12_missing_short_excerpt_explicit_reason(self):
        p,original,audit,_=mock_inputs()
        original["articles"][0]["text"]="22 жовтня російська ракета атакувала Запоріжжя. Загинули двоє людей."
        with tempfile.TemporaryDirectory() as td:
            r.retain_results(queue(),p,original,audit,Path(td),authorization_id="SYNTHETIC")
            facts=json.loads((Path(td)/"minimal_capture_facts.json").read_text())["facts"]
            self.assertEqual(facts[0]["decision"],"NEEDS_REVIEW")
            self.assertIn("SHORT_EVIDENCE_NOT_EXTRACTED",facts[0]["reasons"])

    def test_13_aggregate_request_budget_enforced(self):
        p,original,audit,_=mock_inputs()
        audit["requests_used"]=7
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(RuntimeError,"BUDGET"):
                r.retain_results(queue(),p,original,audit,Path(td),authorization_id="SYNTHETIC")

    def test_14_short_excerpts_redact_contact_details(self):
        p,original,audit,_=mock_inputs()
        original["articles"][0]["text"]="22 жовтня загинули 2 людини. Зв'язок test.private@example.com +380671234567."
        with tempfile.TemporaryDirectory() as td:
            r.retain_results(queue(),p,original,audit,Path(td),authorization_id="SYNTHETIC")
            text=(Path(td)/"minimal_capture_facts.json").read_text()
            self.assertNotIn("test.private@example.com",text)
            self.assertNotIn("+380671234567",text)
