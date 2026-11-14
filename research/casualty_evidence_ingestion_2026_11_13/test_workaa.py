"""Work AA offline regression; synthetic examples never establish real deaths."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import unittest
from research.casualty_one_time_capture_2026_11_13 import run_capture as r
from research.casualty_evidence_ingestion_2026_11_13 import workaa_offline as aa
from research.casualty_evidence_ingestion_2026_11_13 import workx_evidence as x


class WorkAA(unittest.TestCase):
    def test_complete_sentence_and_unmodified_meaning(self):
        text = ("22 жовтня ракета влучила у приватний будинок у Запоріжжі. "
                "Загинули двоє людей.")
        got = r.retain_incident_review_clues(text)["evidence_mentions"]
        self.assertTrue(any("Загинули двоє людей." == a.get("excerpt") for a in got))
        self.assertTrue(all(a.get("context_status") == "COMPLETE" for a in got))
        self.assertEqual([a["article_sentence_order"] for a in got],sorted(a["article_sentence_order"] for a in got))

    def test_overlong_sentence_is_never_truncated_to_fake_quote(self):
        text = "Внаслідок обстрілу загинули двоє людей, " + "інформацію уточнюють " * 20 + "."
        got = r.retain_incident_review_clues(text)["evidence_mentions"]
        self.assertTrue(any(a["context_status"] == "CONTEXT_INCOMPLETE" for a in got))
        self.assertTrue(all(a.get("excerpt") is None for a in got))
        self.assertTrue(all(len(a["sentence_sha256"]) == 64 for a in got))

    def test_multi_attack_segments_are_distinct_hints(self):
        text = ("Вранці ракета влучила у приватний будинок у Запоріжжі, загинули двоє людей. "
                "Увечері того ж дня інша ракета влучила у школу в Запоріжжі, загинула людина.")
        m = r.retain_incident_review_clues(text)["evidence_mentions"]
        self.assertEqual(len({z["article_segment_hint"] for z in m}), 2)
        self.assertFalse(r.retain_incident_review_clues(text)["attack_identity_verified"])

    def test_two_to_three_sequence_preserved_as_unverified(self):
        text = ("Вранці 22 жовтня ракета влучила в будинок у Запоріжжі. "
                "Спочатку повідомили про двох загиблих. "
                "Пізніше також загинула 69-річна жінка. "
                "Згодом повідомили про трьох загиблих.")
        rev = r.retain_incident_review_clues(text)
        mentions=rev["evidence_mentions"]
        self.assertTrue(any("Спочатку" in (z.get("excerpt") or "") for z in mentions))
        self.assertTrue(any("Пізніше" in (z.get("excerpt") or "") for z in mentions))
        self.assertFalse(rev["direct_two_to_three_update_proven"])

    def test_publication_date_cannot_replace_missing_attack_date(self):
        quote = "Унаслідок атаки загинули двоє людей."
        source={"publication_allowed":False,"automatic_credits":0,"facts":[{
            "decision":"NEEDS_REVIEW","publication_allowed":False,
            "source_url":"https://mig.com.ua/synthetic-test","source_role":"publisher",
            "publication_date":"2026-10-23T12:00:00Z","attack_date_explicit":None,
            "document_sha256":"a"*64,"extracted_text_sha256":"b"*64,
            "excerpts":[{"text":quote,"excerpt_sha256":x._sha(quote)}],
            "incident_review":{"evidence_mentions":[]},
        }]}
        result=x.build_review_index(source,include_unretained=False)["cards"][0]
        self.assertEqual(result["attack_date_status"],"UNKNOWN")
        self.assertIsNone(result["attack_date_claimed_not_verified"])
        self.assertEqual(result["publication_date_claimed"],"2026-10-23T12:00:00Z")

    def test_legal_abbreviation_is_one_sentence(self):
        t="За фактом ракетного удару розпочали розслідування (ч. 2 ст. 438 КК України)."
        self.assertEqual(r._review_sentences(t),[t])

    def test_stored_context_incomplete_never_passes_as_full_quote(self):
        card={"publication_allowed":False,"decision":"NEEDS_REVIEW",
              "source_url":"https://mig.com.ua/synthetic-test",
              "incident_review":{"evidence_mentions":[{
                  "article_sentence_order":7,"context_status":"CONTEXT_INCOMPLETE",
                  "sentence_sha256":"c"*64,"excerpt":None}]}}
        review=x.build_review_index({"publication_allowed":False,"automatic_credits":0,
                                     "facts":[card]},include_unretained=False)
        row=review["cards"][0]
        self.assertEqual(row["unverified_context"][0]["context_status"],"CONTEXT_INCOMPLETE")
        self.assertIsNone(row["unverified_context"][0]["excerpt"])
        self.assertIn("CONTEXT_INCOMPLETE",row["reasons"])

    def test_real_saved_workz_three_pairs_and_no_queue_noise(self):
        root=os.getenv("WORKAA_Z_DIRECTORY")
        if not root:
            self.skipTest("Work Z original artifact supplied by offline CI")
        d=Path(root)
        out=aa.compact_existing(json.loads((d/"minimal_capture_facts.json").read_text()),
                                json.loads((d/"capture_receipts.json").read_text()))
        self.assertEqual(out["evidence_index"]["summary"]["total"],3)
        self.assertEqual(out["evidence_index"]["summary"]["automatic_credits"],0)
        self.assertEqual(out["source_get"],0)
        self.assertEqual(len(out["pair_decisions"]),3)
        self.assertEqual(set(out["pair_decisions"].values()),{"INSUFFICIENT_EVIDENCE"})
        self.assertEqual(out["attack_date"],"UNKNOWN")
        self.assertTrue(all(card["incident_id"] is None for card in out["evidence_index"]["cards"]))
        self.assertTrue(any("CONTEXT_INCOMPLETE" in c["reasons"] for c in out["evidence_index"]["cards"]))

    def test_replay_same_body_zero_credit_and_no_identity_promote(self):
        q="Загинули двоє людей."
        c={"candidate_id":"test","decision":"NEEDS_REVIEW","publication_allowed":False,
           "source_url":"https://mig.com.ua/synthetic","source_role":"publisher",
           "document_sha256":"a"*64,"excerpts":[{"text":q,"excerpt_sha256":x._sha(q)}]}
        source={"facts":[c],"automatic_credits":0,"publication_allowed":False}
        first=x.build_review_index(source,include_unretained=False)
        second=x.build_review_index(source,previous=first["cards"],include_unretained=False)
        self.assertEqual(second["summary"]["duplicate_source_replay"],1)
        self.assertEqual(second["summary"]["automatic_credits"],0)
        self.assertIsNone(second["cards"][0]["incident_id"])


if __name__=="__main__":
    unittest.main()
