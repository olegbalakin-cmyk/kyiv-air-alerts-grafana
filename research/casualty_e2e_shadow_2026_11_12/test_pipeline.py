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


    def test_injuries_without_fatalities_cannot_become_a_count(self):
        from casualty_auto_review import _fatal_total
        self.assertIsNone(_fatal_total("Троє людей поранено внаслідок атаки, загиблих немає.".casefold()))

    def test_two_to_three_cumulative_snapshot_is_not_five(self):
        import importlib.util
        from datetime import date
        generator_path = bridge.ROOT / "_site" / "kyiv-air-alerts-grafana" / "scripts" / "update_casualties.py"
        if not generator_path.is_file():
            self.skipTest("Exact site-prod generator loaded only by GitHub Actions")
        spec = importlib.util.spec_from_file_location("shadow_gen_test", generator_path)
        gen = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gen)
        # Artificial contract rows for unit safety testing ONLY, not factual evidence.
        baseline = {"incident_id": "incident:fake-2026-10-22-private-home",
                    "city_key": "zaporizhzhia", "attack_date": date(2026,10,22),
                    "count_kind": "cumulative", "baseline_credited": "0",
                    "identity_proof": "sha256:"+"a"*64, "credited_proof": "sha256:"+"b"*64,
                    "candidate_ids": "synthetic-publication",
                    "source_url": "https://example.org/test",
                    "status": "confirmed"}
        first = {**baseline, "record_id": "synthetic-2", "deaths_delta":2,
                 "observed_at": "2026-10-22T18:00:00+03:00"}
        second = {**baseline, "record_id": "synthetic-3", "deaths_delta":3,
                  "observed_at": "2026-10-23T08:00:00+03:00"}
        effective = gen.reconcile_confirmed_revisions([first, second])
        self.assertEqual(len(effective), 1)
        self.assertEqual(effective[0]["deaths_delta"],3)

    def test_same_day_different_attacks_not_automatically_collapsed(self):
        from datetime import date
        generator_path = bridge.ROOT / "_site" / "kyiv-air-alerts-grafana" / "scripts" / "update_casualties.py"
        if not generator_path.is_file():
            self.skipTest("Exact site-prod generator loaded only by GitHub Actions")
        spec = importlib.util.spec_from_file_location("shadow_gen_test_two", generator_path)
        gen = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gen)
        base = {"city_key": "zaporizhzhia", "attack_date": date(2026,10,22),
                "count_kind":"cumulative", "baseline_credited":"0",
                "credited_proof":"sha256:"+"b"*64, "status":"confirmed"}
        first={**base, "record_id":"synthetic-a","incident_id":"incident:synthetic-attack-a",
               "deaths_delta":1, "candidate_ids":"synthetic-candidate-a",
               "source_url":"https://example.org/a","identity_proof":"sha256:"+"a"*64,
               "observed_at":"2026-10-22T18:00:00+03:00"}
        second={**base, "record_id":"synthetic-b","incident_id":"incident:synthetic-attack-b",
               "deaths_delta":2, "candidate_ids":"synthetic-candidate-b",
               "source_url":"https://example.org/b","identity_proof":"sha256:"+"c"*64,
               "observed_at":"2026-10-22T20:00:00+03:00"}
        effective = gen.reconcile_confirmed_revisions([first,second])
        self.assertEqual(len(effective),2)
        self.assertEqual(sorted(r["deaths_delta"] for r in effective),[1,2])

    def test_same_candidate_across_distinct_incidents_is_rejected(self):
        from datetime import date
        generator_path = bridge.ROOT / "_site" / "kyiv-air-alerts-grafana" / "scripts" / "update_casualties.py"
        if not generator_path.is_file():
            self.skipTest("Exact site-prod generator loaded only by GitHub Actions")
        spec = importlib.util.spec_from_file_location("shadow_gen_test_three", generator_path)
        gen = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gen)
        base = {"city_key":"zaporizhzhia","attack_date":date(2026,10,22),
                "count_kind":"cumulative","baseline_credited":"0",
                "credited_proof":"sha256:"+"b"*64,"status":"confirmed",
                "deaths_delta":1,"candidate_ids":"same-test-publication",
                "observed_at":"2026-10-22T18:00:00+03:00"}
        a={**base,"record_id":"synthetic-a","incident_id":"incident:synthetic-attack-a",
           "source_url":"https://example.org/a","identity_proof":"sha256:"+"a"*64}
        b={**base,"record_id":"synthetic-b","incident_id":"incident:synthetic-attack-b",
           "source_url":"https://example.org/b","identity_proof":"sha256:"+"c"*64}
        with self.assertRaisesRegex(RuntimeError,"Ambiguous candidate_id"):
            gen.reconcile_confirmed_revisions([a,b])

if __name__ == "__main__":
    unittest.main()
