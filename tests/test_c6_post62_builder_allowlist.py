"""Exact post-PR62 Sevastopol source allowlist; no network or Neon access."""
import unittest
from unittest.mock import patch

from scripts import neon_json_shadow_generator as generator


class Post62AllowlistTests(unittest.TestCase):
    PATH = "scripts/add_sevastopol_exact.py"
    ACCEPTED_ORIGINAL = "e4c091a677622eb28e504b0592a89e4d92d5fe02"
    POST62_BLOB = "6698ec743b6efcd9aeb059dd81b51cc05ae93493"

    def test_exact_owner_approved_post62_blob_is_allowed(self):
        self.assertEqual(generator.C6_SEVASTOPOL_CHECKPOINT_BLOBS[self.PATH],
                         (self.ACCEPTED_ORIGINAL, self.POST62_BLOB))
        with patch.object(generator, "blob", return_value=self.POST62_BLOB):
            self.assertTrue(generator.accepted_builder_blob(
                self.PATH, b"post62", self.ACCEPTED_ORIGINAL))

    def test_unknown_blob_still_fails_closed(self):
        with patch.object(generator, "blob", return_value="0" * 40):
            self.assertFalse(generator.accepted_builder_blob(
                self.PATH, b"drift", self.ACCEPTED_ORIGINAL))

    def test_other_builders_cannot_use_sevastopol_allowance(self):
        with patch.object(generator, "blob", return_value=self.POST62_BLOB):
            self.assertFalse(generator.accepted_builder_blob(
                "scripts/update_data.py", b"drift", self.ACCEPTED_ORIGINAL))

    def test_wrong_accepted_baseline_does_not_bypass_allowance(self):
        with patch.object(generator, "blob", return_value=self.POST62_BLOB):
            self.assertFalse(generator.accepted_builder_blob(
                self.PATH, b"drift", "1" * 40))


if __name__ == "__main__":
    unittest.main()
