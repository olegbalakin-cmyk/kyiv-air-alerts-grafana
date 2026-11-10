"""Ensure blocked exports reveal only trusted diagnostic codes; no source bytes."""
import unittest

from scripts.c2_shadow_bundle import BundleBlocked, safe_block_diagnostic


class C2SafeDiagnosticTests(unittest.TestCase):
    def test_safe_static_block_reason(self):
        self.assertEqual(
            safe_block_diagnostic(BundleBlocked("C2_GATE_NOT_CONFIRMED")),
            "reason=C2_GATE_NOT_CONFIRMED error_type=BundleBlocked",
        )

    def test_capture_failure_omits_city_and_any_untrusted_trailer(self):
        output = safe_block_diagnostic(
            ValueError("CAPTURE_REPLAY_MISMATCH:kyiv postgres://hidden:password")
        )
        self.assertEqual(
            output, "reason=CAPTURE_REPLAY_MISMATCH error_type=ValueError"
        )
        self.assertNotIn("postgres", output)
        self.assertNotIn("kyiv", output)

    def test_unknown_exception_never_echoes_payload(self):
        secret = "postgres://hidden:password@private.example/db"
        output = safe_block_diagnostic(FileNotFoundError(secret))
        self.assertEqual(output, "reason=UNCLASSIFIED error_type=FileNotFoundError")
        self.assertNotIn(secret, output)

    def test_unknown_code_never_echoes_payload(self):
        output = safe_block_diagnostic(BundleBlocked("API_PASSWORD=SUPERSECRET"))
        self.assertEqual(output, "reason=UNCLASSIFIED error_type=BundleBlocked")


if __name__ == "__main__":
    unittest.main()
