"""Fail-closed tests for the one-shot publisher (never calls a remote)."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import c6_neon_one_shot_publisher as release
from scripts import c6_neon_git_candidate as candidate


class PublisherReleaseTests(unittest.TestCase):
    def test_missing_owner_grant_blocks_before_readback(self):
        with self.assertRaisesRegex(candidate.Blocked, "EXPLICIT_OWNER_GRANT_MISSING"):
            release.validate({}, {}, ".", ".", c2_run={}, work_a_run={},
                             c2_artifact={}, work_a_artifact={},
                             repository="olegbalakin-cmyk/kyiv-air-alerts-grafana")

    def test_forged_grant_without_repository_blocks(self):
        grant={"schema":release.RECEIPT_SCHEMA,"decision":release.APPROVAL,
               "global_cutover":"OWNER_SEPARATELY_APPROVED",
               "dst_correction":"OFF"}
        with self.assertRaisesRegex(candidate.Blocked, "REPOSITORY_GRANT_MISMATCH"):
            release.validate(grant, {}, ".", ".", c2_run={}, work_a_run={},
                             c2_artifact={}, work_a_artifact={},
                             repository="olegbalakin-cmyk/kyiv-air-alerts-grafana")

    def test_no_clean_exact_checkout_cannot_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(release, "git", return_value="wrong-sha"):
                with self.assertRaisesRegex(candidate.Blocked, "GIT_CHECKOUT_NOT_PINNED"):
                    release.publish(Path(tmp), Path(tmp), {"files":{}},
                                    expected_head="a"*40)
            self.assertEqual(list(Path(tmp).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
