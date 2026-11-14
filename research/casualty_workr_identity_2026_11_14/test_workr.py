"""Work R: bounded incident review cues from volatile source text. OFFLINE ONLY."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research.casualty_one_time_capture_2026_11_13 import run_capture as r
from research.casualty_one_time_capture_2026_11_13.test_workk import queue, mock_inputs


class WorkRIncidentIdentity(unittest.TestCase):
    def sample(self):
        return (
            "Вранці 22 жовтня російська ракета влучила у приватний будинок у Запоріжжі. "
            "Спочатку повідомляли про двох загиблих людей. "
            "Пізніше стало відомо, що загинула також 69-річна жінка. "
            "Поліція повідомила про трьох загиблих. "
            "Відомості потребують перевірки за оригінальними повідомленнями. "
            + "Опис роботи рятувальних служб і наслідків обстрілу. " * 9
        )

    def test_01_retained_tags_do_not_establish_incident_identity(self):
        x = r.retain_incident_review_clues(self.sample())
        self.assertEqual(x["status"], "INSUFFICIENT_EVIDENCE")
        for k in ("attack_identity_verified", "direct_two_to_three_update_proven",
                  "independent_police_link_proven"):
            self.assertFalse(x[k])
        for k in ("attack_date_verified", "attack_time_verified",
                  "locality_verified", "struck_object_verified"):
            self.assertIsNone(x[k])
        self.assertTrue(x["chronology_is_source_sentence_order_only"])
        self.assertTrue(x["evidence_mentions"])
        tags = {t for item in x["evidence_mentions"] for t in item["tags"]}
        self.assertIn("DATE_MENTION_NOT_ATTACK_DATE", tags)
        self.assertIn("STRUCK_OBJECT_MENTION", tags)
        self.assertIn("REPORT_SEQUENCE_MENTION_NOT_LINK", tags)
        self.assertIn("ATTACK_METHOD_OR_IMPACT_MENTION", tags)

    def test_02_short_pseudonymized_provenance_order_and_budget(self):
        x = r.retain_incident_review_clues(self.sample())
        mentions = x["evidence_mentions"]
        self.assertEqual([m["article_sentence_order"] for m in mentions],
                         sorted(m["article_sentence_order"] for m in mentions))
        self.assertLessEqual(len(mentions), 8)
        self.assertLessEqual(sum(len(m["excerpt"]) for m in mentions),
                             min(650, len(self.sample()) // 4))
        for m in mentions:
            self.assertLessEqual(len(m["excerpt"]), 170)
            self.assertEqual(m["excerpt_sha256"],
                             hashlib.sha256(m["excerpt"].encode()).hexdigest())
            self.assertNotIn("Запоріжжі", m["excerpt"])
            self.assertNotIn("Запоріжжя", m["excerpt"])
            self.assertEqual(m["decision"], "NEEDS_REVIEW")
        self.assertEqual(r.retain_incident_review_clues(self.sample()), x)

    def test_03_missing_unclear_conflicting_is_fail_closed(self):
        for txt in ("", None, "Уточнено без подробиць.", "Загинули двоє людей. Загинули троє людей."):
            x = r.retain_incident_review_clues(txt)
            self.assertEqual(x["status"], "INSUFFICIENT_EVIDENCE")
            self.assertFalse(x["direct_two_to_three_update_proven"])
            self.assertFalse(x["independent_police_link_proven"])

    def test_04_private_address_and_names_are_withheld(self):
        private = ("О 09:56 будинок 14 на вулиці Польовій, повідомив Петро Іваненко. "
                   + "Опис наслідків атаки у місті. " * 25)
        x = r.retain_incident_review_clues(private)
        all_text = json.dumps(x,ensure_ascii=False)
        self.assertNotIn("Петро", all_text)
        self.assertNotIn("Польовій", all_text)
        self.assertNotIn("будинок 14", all_text)
        self.assertFalse(x["attack_identity_verified"])

    def test_05_no_raw_html_or_full_text_retained(self):
        full = self.sample() + "Унікальний непридатний для зберігання вміст. " * 30
        x = r.retain_incident_review_clues(full)
        s = json.dumps(x,ensure_ascii=False)
        self.assertNotIn(full,s)
        self.assertNotIn("<html>",s)
        self.assertTrue(all(len(z["excerpt"]) <= 170 for z in x["evidence_mentions"]))

    def test_06_existing_retention_integration_zero_credits(self):
        plan, volatile, audit, _ = mock_inputs()
        volatile["articles"][0]["text"] = self.sample()
        with tempfile.TemporaryDirectory() as td:
            r.retain_results(queue(), plan, volatile, audit, Path(td),
                             authorization_id="OFFLINE_REVIEW_MOCK")
            cards=json.loads((Path(td)/"minimal_capture_facts.json").read_text())["facts"]
            self.assertEqual(len(cards),3)
            self.assertTrue(cards[0]["incident_review"]["evidence_mentions"])
            self.assertTrue(all(c["incident_review"]["status"] ==
                                "INSUFFICIENT_EVIDENCE" for c in cards))
            summary=json.loads((Path(td)/"summary.json").read_text())
            self.assertEqual(summary["automatic_death_credits"],0)
            self.assertFalse(summary["publication_allowed"])
            self.assertFalse(summary["official_links_verified"])
            self.assertNotIn(volatile["articles"][0]["text"],
                             "\n".join(p.read_text() for p in Path(td).glob("*.json")))
            self.assertEqual(len(json.loads((Path(td)/"manifest.json").read_text())
                                 ["files_sha256"]),4)

    def test_07_grant_ancestry_budget_and_branch_pins_preserved(self):
        self.assertEqual(r.EXPECTED_BASE, "657fd70564bf5393d3fcd209e47d95fa986f3010")
        self.assertEqual(r.WORKK_HEAD, "69e7d023b4104c3583943eaf59f38b1d05ee32e5")
        self.assertEqual(r.EXPECTED_BRANCH, "research-casualty-workr-identity-2026-11-14")
        self.assertEqual(r.LIMITS["max_requests_total"],6)
        self.assertEqual(r.LIMITS["authorization_max_hours"],24)
        self.assertEqual(r.LIMITS["retries"],0)
        self.assertFalse((r.HERE/"launch.json").exists())
        from research.casualty_one_time_capture_2026_11_13.test_workk import synthetic_launch, synthetic_env
        self.assertEqual(r.validate_launch(synthetic_launch(), r.check_scope(queue())[1],
                                           queue(), environ=synthetic_env())["max_requests_total"],6)

    def test_08_source_http_is_not_called_in_review(self):
        with patch.object(r.e, "controlled_capture", side_effect=AssertionError("SOURCE_GET_FORBIDDEN")):
            x = r.retain_incident_review_clues(self.sample())
            self.assertEqual(x["status"],"INSUFFICIENT_EVIDENCE")


if __name__ == "__main__":
    unittest.main()
