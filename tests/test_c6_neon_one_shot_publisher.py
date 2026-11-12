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

    def test_owner_grant_expired_blocks_before_any_publisher(self):
        grant={"schema":release.RECEIPT_SCHEMA,"decision":release.APPROVAL,
               "global_cutover":"OWNER_SEPARATELY_APPROVED",
               "dst_correction":"OFF",
               "repository":"olegbalakin-cmyk/kyiv-air-alerts-grafana",
               "expires_at":"2026-01-01T00:00:00+00:00"}
        with self.assertRaisesRegex(candidate.Blocked, "GRANT_EXPIRED_OR_TOO_LONG"):
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


    def test_remote_site_prod_moved_blocks_before_file_access(self):
        expected = "a" * 40
        def mocked_git(repo, *args):
            if args == ("rev-parse", "HEAD"):
                return expected
            if args == ("status", "--porcelain"):
                return ""
            if args == ("branch", "--show-current"):
                return "site-prod"
            if args == ("ls-remote", "origin", "refs/heads/site-prod"):
                return "b" * 40 + "\\trefs/heads/site-prod"
            raise AssertionError("unexpected Git operation")
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(release, "git", side_effect=mocked_git):
                with self.assertRaisesRegex(candidate.Blocked, "SITE_PROD_HEAD_MOVED"):
                    release.publish(Path(tmp), Path(tmp), {"files": {}},
                                    expected_head=expected)
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_c2_single_writer_and_release_mode_are_exclusive(self):
        workflow = Path(".github/workflows/update-netlify-site.yml").read_text()
        self.assertIn("group: update-netlify-site", workflow)
        self.assertIn("cancel-in-progress: false", workflow)
        self.assertIn("c6-neon-owner-gated-git-release:", workflow)
        self.assertIn("vars.C6_GIT_ONLY_PUBLISHER_PAUSED != 'true'", workflow)
        self.assertIn("test \"$GIT_ONLY_PUBLISHER_PAUSED\" = \"true\"", workflow)
        self.assertIn("github.event_name == 'workflow_dispatch' && inputs.c6_neon_git_release", workflow)
        self.assertIn("!inputs.c6_neon_git_release", workflow)


if __name__ == "__main__":
    unittest.main()
