#!/usr/bin/env python3
"""Safety tests: artificial negative inputs are not treated as casualty evidence."""
import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("casualty_shadow", Path(__file__).with_name("pipeline.py"))
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)

class ShadowSafety(unittest.TestCase):
    def test_explicit_proof_contract(self):
        self.assertEqual(bridge.CONTRACT_FIELDS,
            ("incident_id","count_kind","baseline_credited","identity_proof","credited_proof"))

    def test_missing_text_blocks_credited_source(self):
        cid=bridge.CONFIRMED_ZAP_CANDIDATE
        candidate={"candidate_id":cid, "city_key":"zaporizhzhia", "title":"x",
                   "snippet":"", "url":"https://news.google.com/rss/1", "published_at":"2026-10-11"}
        receipt={"candidate_id":cid, "candidate_fingerprint":bridge.fingerprint(candidate),
                 "resolved_url":"https://suspilne.media/zaporizhzhia/1","http_status":200}
        record={"candidate_id":cid,"url":receipt["resolved_url"],"text":"",
                "observed_at":"2026-11-11"}
        articles,errors=bridge.anchored_articles([candidate],
            {"articles":[record],"receipts":[receipt]})
        self.assertEqual(articles,[])
        self.assertEqual(errors[cid],bridge.SOURCE_MISSING)

    def test_200_transport_only_is_not_factual_evidence(self):
        cid="nonreal-test-id"
        receipts={"raw_article_text_stored":False,"candidate_receipt_index":{cid:0},
                  "source_receipts":[{"http_status":200,
                      "response_sha256":"a"*64,"resolved_url":"https://example.org/test"}]}
        matrix={"groups":[{"cluster_id":"test","candidates":[{"candidate_id":cid}]}]}
        indexed,groups=bridge.source_index(matrix,receipts)
        self.assertEqual(indexed[cid]["receipt_status"],"TRANSPORT_ONLY_NO_BODY")
        self.assertEqual(groups[0]["evidence_status"],bridge.SOURCE_MISSING)

    def test_receipt_missing_hash_fails_closed(self):
        cid="nonreal-test-id"
        receipts={"raw_article_text_stored":False,"candidate_receipt_index":{cid:0},
                  "source_receipts":[{"http_status":200,"resolved_url":"https://example.org/test"}]}
        with self.assertRaises(RuntimeError):
            bridge.source_index({"groups":[{"cluster_id":"test",
                                 "candidates":[{"candidate_id":cid}]}]},receipts)

    def test_cannot_credit_inside_baseline_coverage(self):
        cid=bridge.CONFIRMED_ZAP_CANDIDATE
        event={"category":"AUTO_READY","incident":{"city_key":"zaporizhzhia",
               "attack_date":"2026-10-10"},"messages":[{"candidate_id":cid}]}
        with self.assertRaisesRegex(ValueError,"BASELINE_EVENT_ALLOCATION_UNKNOWN"):
            bridge.make_proposal(event,{},{"validated_through":"2026-10-10"},[],[])

    def test_output_not_in_repository(self):
        with self.assertRaises(RuntimeError):
            bridge.ensure_output_isolated(bridge.ROOT/"research"/"unsafe", [])

if __name__ == "__main__":
    unittest.main()
