"""Isolated Git remotes: the C6 publisher may follow UI changes, never data drift.

No C2 writer, Neon, external HTTP, Netlify, or real production push.
"""
from pathlib import Path
from tempfile import TemporaryDirectory
import subprocess
import unittest

from scripts import c6_neon_auto_git as auto


def git(where, *args):
    return subprocess.check_output(
        ["git", "-C", str(where), *args], text=True).strip()


class C6UIRaceTest(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.remote = self.root / "remote.git"
        self.work = self.root / "work"
        self.publisher = self.root / "publisher"
        subprocess.run(["git", "init", "-q", "--bare", str(self.remote)], check=True)
        subprocess.run(["git", "clone", "-q", str(self.remote), str(self.work)],
                       check=True)
        git(self.work, "checkout", "-q", "-b", "site-prod")
        git(self.work, "config", "user.name", "Offline C6")
        git(self.work, "config", "user.email", "offline@example.invalid")
        self.dashboard = "kyiv-air-alerts-grafana/data/dashboard_data.json"
        self.ui = "kyiv-air-alerts-grafana/pages-preview/app.js"
        self.write(self.dashboard, '{"version":1}\n')
        self.write(self.ui, "const version = 1;\n")
        self.commit("baseline")
        git(self.work, "push", "-q", "-u", "origin", "site-prod")
        self.input_sha = git(self.work, "rev-parse", "HEAD")
        subprocess.run(["git", "clone", "-q", "--branch", "site-prod",
                        str(self.remote), str(self.publisher)], check=True)
        git(self.publisher, "config", "user.name", "Offline C6")
        git(self.publisher, "config", "user.email", "offline@example.invalid")

    def write(self, name, data):
        path = self.work / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data)

    def commit(self, msg):
        git(self.work, "add", ".")
        git(self.work, "commit", "-qm", msg)
        git(self.work, "push", "-q", "origin", "site-prod") if msg != "baseline" else None

    def test_ui_release_is_preserved_and_fast_forwarded(self):
        self.write(self.ui, "const version = 2;\n")
        self.commit("UI release while C2 runs")
        ui_sha = git(self.work, "rev-parse", "HEAD")
        got = auto.refresh_site_prod_for_ui_only(self.publisher, self.input_sha)
        self.assertEqual(got, ui_sha)
        self.assertEqual(git(self.publisher, "rev-parse", "HEAD"), ui_sha)
        self.assertEqual((self.publisher / self.ui).read_text(),
                         "const version = 2;\n")
        self.assertEqual((self.publisher / self.dashboard).read_text(),
                         '{"version":1}\n')

    def test_data_modification_blocks_stale_c2(self):
        self.write(self.dashboard, '{"version":2}\n')
        self.commit("concurrent data publication")
        with self.assertRaisesRegex(
                auto.Blocked, "SITE_PROD_DATA_CHANGED_REQUIRE_NEW_C2"):
            auto.refresh_site_prod_for_ui_only(self.publisher, self.input_sha)
        self.assertEqual(git(self.publisher, "rev-parse", "HEAD"), self.input_sha)

    def test_non_ui_file_blocks(self):
        self.write("scripts/c6_neon_auto_git.py", "changed\n")
        self.commit("concurrent C6 script change")
        with self.assertRaisesRegex(
                auto.Blocked, "SITE_PROD_NON_UI_CHANGED_REQUIRE_NEW_C2"):
            auto.refresh_site_prod_for_ui_only(self.publisher, self.input_sha)

    def test_non_presentation_test_change_blocks(self):
        self.write("tests/test_c6_neon_auto_git.py", "changed\\n")
        self.commit("backend regression test changed")
        with self.assertRaisesRegex(
                auto.Blocked, "SITE_PROD_NON_UI_CHANGED_REQUIRE_NEW_C2"):
            auto.refresh_site_prod_for_ui_only(self.publisher, self.input_sha)

    def test_concurrent_ui_release_with_test_changes_allowed(self):
        self.write(self.ui, "const version = 3;\\n")
        self.write("tests/test_active23_daily28_url.cjs", "test('rollover', () => {});\\n")
        self.write(".github/workflows/active23-production-once.yml", "name: UI one-shot\\n")
        self.commit("UI fix and corresponding test/workflow")
        latest = git(self.work, "rev-parse", "HEAD")
        self.assertEqual(auto.refresh_site_prod_for_ui_only(
            self.publisher, self.input_sha), latest)

    def test_unchanged_head_preserved(self):
        self.assertEqual(auto.refresh_site_prod_for_ui_only(
            self.publisher, self.input_sha), self.input_sha)

    def test_dirty_publisher_checkout_blocks(self):
        (self.publisher / self.ui).write_text("dirty\n")
        with self.assertRaisesRegex(
                auto.Blocked, "SITE_PROD_MOVED_OR_UNCLEAN"):
            auto.refresh_site_prod_for_ui_only(self.publisher, self.input_sha)

    def test_divergent_input_sha_blocks(self):
        with self.assertRaisesRegex(
                auto.Blocked, "SITE_PROD_DIVERGED_REQUIRE_NEW_C2"):
            auto.refresh_site_prod_for_ui_only(self.publisher, "a" * 40)


if __name__ == "__main__":
    unittest.main()
