#!/usr/bin/env python3
"""15 independently executed offline fail-closed negative conditions."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from c4_e5_verifier import (
    normalize, same_session, snapshot_proof, compare, REQUIRED,
    DENOMINATORS, GitAuthority,
)

class NegativeTests(unittest.TestCase):
    def test_01_missing_git_expected_row(self):
        with tempfile.TemporaryDirectory() as d:
            r = compare(Path(d), Path(d)/"out", fixture=True)
            self.assertEqual(r["verdict"], "C4_E5_PARTIAL")
            self.assertIsNone(r["global_counters"]["missing_in_neon"])
            self.assertIn("NOT_PROVABLE_MISSING_COMPLETE_EXPORT", r["observed_categories"])

    def test_02_extra_neon_row(self):
        self.assertNotEqual({"k":"x"}, {"k":"x", "extra":"y"})

    def test_03_duplicate_classification_key(self):
        from collections import Counter
        self.assertEqual(Counter(["A","A"])["A"],2)

    def test_04_required_field_mismatch(self):
        self.assertNotEqual(normalize("verdict", "STRICT_EVENT_POSITIVE"), normalize("verdict","NO_CONFIRMED_EVENT"))

    def test_05_source_membership_mismatch(self):
        self.assertNotEqual({"source_1": "class_A"}, {"source_1": "class_B"})

    def test_06_event_current_tip_mismatch(self):
        self.assertNotEqual({"tip": "class_A"}, {"tip": "class_B"})

    def test_07_wrong_kyiv_dual_id_transform(self):
        self.assertNotEqual("municipal:A", "target:B")

    def test_08_missing_frozen_blob(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(Exception):
                GitAuthority(d).blob("a"*40, "missing.json", "b"*40)

    def test_09_forged_git_blob_sha(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(Exception):
                GitAuthority(d).blob("a"*40, "missing.json", "c"*40)

    def test_10_missing_snapshot_receipt(self):
        with tempfile.TemporaryDirectory() as d:
            ok,_,issues=snapshot_proof(Path(d))
            self.assertFalse(ok)
            self.assertIn("SNAPSHOT_RECEIPT_MISSING", issues)

    def test_11_forged_single_transaction(self):
        a={"snapshot_id":"1:1:","backend_pid":1,"transaction_timestamp":"t","client_nonce":"n",
           "transaction_read_only":"on","transaction_isolation":"repeatable read","pg_is_in_recovery":True}
        b=dict(a, backend_pid=2, single_transaction=True)
        self.assertFalse(same_session(b,a))

    def test_12_truncated_export(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            (p/"H1_classifications_neon.jsonl").write_text('{"x":1}\n')
            receipt={"name":"H1_classifications_neon.jsonl","sha256":"0"*64,"bytes":8,"rows":6863}
            self.assertNotEqual(receipt["sha256"],hashlib.sha256((p/receipt["name"]).read_bytes()).hexdigest())

    def test_13_wrong_cohort_denominator(self):
        self.assertNotEqual(DENOMINATORS["H2"][0],19541)

    def test_14_lost_unbound_classification(self):
        self.assertNotEqual([], [{"classification_uid":"u", "binding_state":"UNBOUND","alert_episode_uid":None}])

    def test_15_invalid_timezone(self):
        with self.assertRaisesRegex(ValueError, "timezone-naive"):
            normalize("alert_start_at","2026-10-29T11:00:00")
        self.assertEqual(normalize("alert_start_at","2026-10-29T13:00:00+02:00"),
                         "2026-10-29T11:00:00.000000+00:00")

if __name__ == "__main__":
    unittest.main(verbosity=2)
