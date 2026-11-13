"""Narrow offline tests: C6 read-only redacted pre-capture status."""
import io
import json
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory
from contextlib import redirect_stdout
import unittest
from scripts import c6_precapture_diag as d

ROOT = Path(__file__).resolve().parents[1]

class PreCaptureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repo = self.root / "site"
        self.repo.mkdir()
        for args in [("init", "-q"), ("checkout", "-qb", "site-prod"),
                     ("config", "user.name", "C6 offline"),
                     ("config", "user.email", "c6@example.invalid")]:
            self.git(*args)
        self.write(d.DASHBOARD, "{}")
        self.write(d.CHECKPOINTS, "{}")
        self.write(d.GRAFANA, "{}")
        self.write("private/outside-secret.txt", "secret")
        self.git("add", ".")
        self.git("commit", "-qm", "fixture")
        self.head = self.git("rev-parse", "HEAD").strip()

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.repo), *args],
                                       text=True, stderr=subprocess.DEVNULL)

    def write(self, path, data):
        p = self.repo / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(data)
        return p

    def test_clean_and_no_index_mutation(self):
        index = (self.repo / ".git/index").read_bytes()
        result = d.inspect(self.repo, self.head)
        self.assertEqual(result["head"], self.head)
        self.assertEqual(result["branch"], "site-prod")
        self.assertEqual(result["scoped_changes"], 0)
        self.assertTrue(result["checkpoint_file_regular"])
        self.assertFalse(result["dashboard_changed"])
        self.assertEqual((self.repo / ".git/index").read_bytes(), index)

    def test_staged_modified_empty_untracked_and_scope(self):
        self.write(d.DASHBOARD, '{"new":true}')
        self.write(d.CHECKPOINTS, '{"new":true}')
        self.git("add", d.CHECKPOINTS)
        self.write(d.DATA + "/NEON_DATABASE_URL=secret", "")
        self.write("private/outside-secret.txt", "changed")
        result = d.inspect(self.repo, self.head)
        self.assertEqual(result["xy_counts"], {" M": 1, "M ": 1, "??": 1})
        self.assertEqual(result["scoped_changes"], 3)
        self.assertEqual(result["file_check_counts"], {
            "regular": 3, "nonempty": 2, "size_ok": 2})
        self.assertTrue(result["dashboard_changed"])
        self.assertNotIn("NEON_DATABASE_URL", str(result))
        self.assertNotIn("outside-secret", str(result))
        self.assertTrue(all(re.fullmatch("[0-9a-f]{16}", x["id"])
                            for x in result["path_ids"]))

    def test_real_rename_delete_and_symlink(self):
        source = d.DATA + "/src name.json"
        dest = d.DATA + "/dst name.json"
        deleted = d.DATA + "/deleted.json"
        self.write(source, '{"unique_source":"rename-me"}')
        self.write(deleted, '{"unique_deleted":"delete-me"}')
        self.git("add", ".")
        self.git("commit", "-qm", "extra files")
        self.git("mv", source, dest)
        self.git("rm", deleted)
        (self.repo / d.DATA / "link.json").symlink_to(
            self.repo / "private/outside-secret.txt")
        result = d.inspect(self.repo, self.git("rev-parse", "HEAD").strip())
        self.assertEqual(result["scoped_changes"], 3)
        self.assertEqual(result["types"]["renamed"], 1)
        self.assertEqual(result["types"]["deleted"], 1)
        self.assertEqual(result["types"]["untracked"], 1)
        self.assertEqual(result["file_check_counts"]["regular"], 1)
        renamed = next(x for x in result["path_ids"] if x["type"] == "renamed")
        self.assertEqual(renamed["paired_from_id"], d.path_id(source))
        self.assertEqual(renamed["id"], d.path_id(dest))
        self.assertNotIn("src name", str(result))

    def test_rename_copy_pair_and_invalid_porcelain(self):
        self.assertEqual(d.parse_status(b"R  new\0old\0C  copy\0source\0"),
                         [("R ", "new", "old"), ("C ", "copy", "source")])
        with self.assertRaises(ValueError):
            d.parse_status(b"R  new\0")
        with self.assertRaises(ValueError):
            d.parse_status(b" M missing final NUL")

    def test_bounded_identifiers(self):
        for i in range(39):
            self.write(d.DATA + "/new%02d.json" % i, "{}")
        result = d.inspect(self.repo, self.head)
        self.assertEqual(result["scoped_changes"], 39)
        self.assertEqual(len(result["path_ids"]), 32)
        self.assertEqual(result["path_ids_truncated"], 7)

    def test_branch_redaction_and_failure_nonblocking(self):
        self.git("checkout", "-qb", "PRIVATE-BRANCH-SECRET")
        self.assertEqual(d.inspect(self.repo, self.head)["branch"], "other")
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(d.main(["--checkout", str(self.root / "SECRET"),
                                     "--expected-head", self.head]), 0)
        self.assertIn('"status":"unavailable"', output.getvalue())
        self.assertNotIn(str(self.root), output.getvalue())
        self.assertNotIn("SECRET", output.getvalue())

    def test_workflow_immediate_pre_capture_gating_and_identity(self):
        text = (ROOT / ".github/workflows/update-netlify-site.yml").read_text()
        name = "      - name: Read-only redacted Git status before C6 capture\n"
        capture = "      - name: Freeze same-run C2 checkpoint delta (no commit/push)\n"
        self.assertEqual(text.count(name), 1)
        between = text.split(name, 1)[1].split(capture, 1)[0]
        self.assertIn("continue-on-error: true", between)
        self.assertIn("working-directory: .", between)
        self.assertIn("c6-auto-integration/scripts/c6_precapture_diag.py", between)
        self.assertIn('--checkout "$GITHUB_WORKSPACE/kyiv-air-alerts-grafana"', between)
        self.assertIn('--expected-head "' + '$' + '{PHASE1_INPUT_SHA}"', between)
        a = re.search(r"^        if: (.+)$", between, re.MULTILINE)
        b = re.search(r"^        if: (.+)$", text.split(capture, 1)[1], re.MULTILINE)
        self.assertIsNotNone(a)
        self.assertIsNotNone(b)
        self.assertEqual(a.group(1), b.group(1))

if __name__ == "__main__":
    unittest.main()
