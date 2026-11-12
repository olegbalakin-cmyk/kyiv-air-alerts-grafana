"""Offline PR93 exact-blob positive/negative guard; no Neon, source HTTP or writer."""
import os
import unittest
from pathlib import Path

from scripts import neon_json_shadow_generator as gen

PARSER_PATH = Path(os.environ.get(
    "C6_PR93_SITE_PARSER",
    "approved-site/kyiv-air-alerts-grafana/scripts/add_sevastopol_exact.py",
))
PATH = "scripts/add_sevastopol_exact.py"
ORIGINAL = "e4c091a677622eb28e504b0592a89e4d92d5fe02"
PR93 = "d31c5ac43ac9e76491ee38033f9a46838c5abfbb"


class ExactPr93ParserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not PARSER_PATH.is_file():
            raise AssertionError("IMMUTABLE_C2_SITE_PARSER_MISSING")
        cls.parser_raw = PARSER_PATH.read_bytes()

    def test_exact_c2_input_has_merged_pr93_git_blob(self):
        self.assertEqual(gen.blob(self.parser_raw), PR93)
        self.assertEqual(gen.C6_SEVASTOPOL_PR93_BLOBS, {PATH: (ORIGINAL, PR93)})

    def test_positive_merged_pr93_parser_accepted(self):
        self.assertTrue(gen.accepted_builder_blob(PATH, self.parser_raw, ORIGINAL))

    def test_negative_changed_parser_bytes_rejected(self):
        tampered = self.parser_raw + b"\n# unauthorized parser modification\n"
        self.assertNotEqual(gen.blob(tampered), PR93)
        self.assertFalse(gen.accepted_builder_blob(PATH, tampered, ORIGINAL))

    def test_negative_unrelated_path_cannot_use_pr93_allowlist(self):
        self.assertFalse(gen.accepted_builder_blob("scripts/update_data.py",
                                                   self.parser_raw,
                                                   "cebc2b455fb08ee16e03b9e4fcdb17aa2d9d6833"))

    def test_negative_arbitrary_parser_sha_rejected(self):
        self.assertFalse(gen.accepted_builder_blob(PATH, b"unapproved parser", ORIGINAL))

    def test_existing_checkpoint_allowlist_is_unchanged(self):
        self.assertEqual(gen.C6_SEVASTOPOL_CHECKPOINT_BLOBS,
                         {PATH: (ORIGINAL, "6698ec743b6efcd9aeb059dd81b51cc05ae93493")})


if __name__ == "__main__":
    unittest.main()
