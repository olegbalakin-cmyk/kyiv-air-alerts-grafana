import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("coordination_docs", Path(__file__).resolve().parents[1] / "scripts/coordination_docs.py")
docs = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(docs)
sys.modules["coordination_docs"] = docs
PR_SPEC = importlib.util.spec_from_file_location("archive_pr", Path(docs.__file__).with_name("coordination_archive_pr.py"))
archive_pr = importlib.util.module_from_spec(PR_SPEC)
PR_SPEC.loader.exec_module(archive_pr)


class CoordinationDocsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.legacy = patch.object(docs, "LEGACY", {})
        self.legacy.start()
        self.addCleanup(self.legacy.stop)
        (self.root / docs.ARCHIVE).mkdir(parents=True)
        (self.root / docs.MANIFEST).write_text('{"version": 1, "snapshots": []}\n')
        for name in docs.FILES:
            heading = b"## " if name == docs.FILES[0] else b"### "
            history = b"".join(heading + f"CHECKPOINT-{i:02} — proof\n\n".encode() +
                               f"sha-{i} https://github.com/org/repo/actions/runs/{i} artifact {i}\n\n".encode()
                               for i in range(9, 0, -1))
            (self.root / name).write_bytes(b"# Current\n\nLive blocker: CURRENT-ISSUE; do not remove.\n"
                b"[Archive](docs/coordination-archive/README.md)\n" + docs.START + history + docs.END + b"\nNext task: retain me.\n")

    def state(self):
        return {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}

    def run_archive(self, dry=False, date="2026-10-31"):
        return docs.archive(self.root, date, "a" * 40, dry)

    def test_threshold_boundaries(self):
        self.assertEqual([docs.status(n) for n in [12287, 12288, 12289, 16384, 16385]],
                         ["PASS", "PASS", "WARNING", "WARNING", "FAIL"])

    def test_utf8_bytes_not_characters(self):
        (self.root / docs.FILES[0]).write_text("ї" * 6145, encoding="utf-8")
        item = docs.check(self.root)[0]
        self.assertEqual((item["bytes"], item["status"]), (12290, "WARNING"))

    def test_dry_run_changes_nothing(self):
        before = self.state()
        report = self.run_archive(True)
        self.assertEqual(self.state(), before)
        self.assertEqual([c["removed_records"] for c in report["changes"]], [8, 4])

    def test_exact_text_links_latest_and_blockers_survive(self):
        before = self.state()
        self.run_archive()
        index = docs.manifest(self.root)
        for name in docs.FILES:
            after = docs.read(self.root, name)
            a, b = docs.region(before[name])
            c, d = docs.region(after)
            self.assertEqual(after[:c], before[name][:a])
            self.assertEqual(after[d:], before[name][b:])
            self.assertEqual(docs.records(after)[0], docs.records(before[name])[0])
            snap = next(s for s in index["snapshots"] if s["source_file"] == name)
            self.assertEqual(docs.read(self.root, snap["path"]), before[name])
        self.assertEqual(docs.verify(self.root)["removed_records_verified"], 12)

    def test_repeat_next_day_no_duplicates(self):
        self.run_archive()
        before = self.state()
        self.assertEqual(self.run_archive(date="2026-11-01")["changes"], [])
        self.assertEqual(self.state(), before)

    def test_more_than_ten_transitions_can_be_archived(self):
        p = self.root / docs.FILES[1]
        p.write_bytes(p.read_bytes().replace(docs.START, docs.START +
            b'### CHECKPOINT-12\n\nnew 12\n\n### CHECKPOINT-11\n\nnew 11\n\n'))
        self.run_archive()
        self.assertEqual(len(docs.records(p.read_bytes())), 5)

    def test_oversized_live_state_aborts_all_writes(self):
        p = self.root / docs.FILES[0]
        p.write_bytes(b"x" * 17000 + p.read_bytes())
        before = self.state()
        with self.assertRaisesRegex(ValueError, "live text remains too large"):
            self.run_archive()
        self.assertEqual(self.state(), before)

    def test_oversized_retained_checkpoint_not_truncated(self):
        self.run_archive()
        p = self.root / docs.FILES[0]
        p.write_bytes(p.read_bytes().replace(b"sha-9", b"y" * 17000))
        before = self.state()
        with self.assertRaisesRegex(ValueError, "cannot be safely reduced"):
            self.run_archive()
        self.assertEqual(self.state(), before)

    def test_missing_or_reversed_marker_rejected(self):
        for data in [b"no markers", docs.END + docs.START]:
            with self.subTest(data=data), self.assertRaises(ValueError):
                docs.region(data)

    def test_duplicate_record_rejected(self):
        p = self.root / docs.FILES[1]
        p.write_bytes(p.read_bytes().replace(b"CHECKPOINT-08", b"CHECKPOINT-09"))
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            self.run_archive()

    def test_archive_corruption_rejected(self):
        self.run_archive()
        snap = docs.manifest(self.root)["snapshots"][0]
        (self.root / snap["path"]).write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "integrity mismatch"):
            docs.verify(self.root)

    def test_offset_corruption_rejected(self):
        self.run_archive()
        index = docs.manifest(self.root)
        index["snapshots"][0]["removed_records"][0]["start"] += 1
        (self.root / docs.MANIFEST).write_text(json.dumps(index))
        with self.assertRaisesRegex(ValueError, "Lost or changed"):
            docs.verify(self.root)

    def test_history_loss_against_git_base_rejected(self):
        subprocess.run(["git", "init", "-q", self.root], check=True)
        subprocess.run(["git", "add", "."], cwd=self.root, check=True)
        subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.com",
                        "commit", "-qm", "baseline"], cwd=self.root, check=True)
        self.run_archive()
        docs.verify(self.root, "HEAD")
        # Delete both the old entry and its snapshot, with a consistent manifest.
        index = docs.manifest(self.root)
        victim = index["snapshots"].pop()
        (self.root / victim["path"]).unlink()
        (self.root / docs.MANIFEST).write_text(json.dumps(index))
        with self.assertRaisesRegex(ValueError, "Historical record lost"):
            docs.verify(self.root, "HEAD")

    def test_existing_archive_cannot_be_removed_from_manifest(self):
        self.run_archive()
        subprocess.run(["git", "init", "-q", self.root], check=True)
        subprocess.run(["git", "add", "."], cwd=self.root, check=True)
        subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.com",
                        "commit", "-qm", "baseline"], cwd=self.root, check=True)
        index = docs.manifest(self.root)
        victim = index["snapshots"].pop()
        (self.root / victim["path"]).unlink()
        (self.root / docs.MANIFEST).write_text(json.dumps(index))
        with self.assertRaisesRegex(ValueError, "removed or rewritten"):
            docs.verify(self.root, "HEAD")

    def test_cli_failure_names_file_bytes_and_remedy(self):
        (self.root / docs.FILES[0]).write_bytes(b"x" * 16385)
        proc = subprocess.run(["python", str(Path(docs.__file__)), "check", "--root", str(self.root)], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 1)
        for expected in ["PROJECT_STATE.md", "16385", "archive --dry-run"]:
            self.assertIn(expected, proc.stderr)

    def simulate_pr(self, deny=False):
        calls = []
        def fake_run(*args):
            calls.append(args)
            if args[:3] == ("git", "rev-parse", "HEAD"):
                return "a" * 40
            if args[:3] == ("gh", "pr", "list"):
                return "[]"
            if args[:3] == ("gh", "pr", "create"):
                if deny:
                    raise subprocess.CalledProcessError(1, ["gh", "pr", "create"])
                return "https://github.com/org/repo/pull/1"
            return ""
        with patch.object(archive_pr, "__file__", str(self.root / "scripts/pr.py")), \
             patch.object(docs, "check", return_value=[{"bytes": 13000}]), \
             patch.object(archive_pr, "run", side_effect=fake_run), \
             patch.object(subprocess, "check_output", return_value=b"test patch"), \
             contextlib.redirect_stdout(io.StringIO()):
            code = archive_pr.main()
        return code, calls, json.loads((self.root / "coordination-archive-pr-report.json").read_text())

    def test_bot_pr_pushes_only_isolated_branch_and_dispatches_checks(self):
        code, calls, report = self.simulate_pr()
        self.assertEqual(code, 0)
        self.assertEqual(report["automatic_pr"], "CREATED")
        pushes = [c for c in calls if c[:2] == ("git", "push")]
        self.assertEqual(pushes, [("git", "push", "origin", "HEAD:refs/heads/automation/coordination-archive-aaaaaaaaaaaaaaaa")])
        self.assertFalse(any("--force" in c or "merge" in c for c in calls))
        self.assertIn(("gh", "workflow", "run", "coordination-docs.yml", "--ref",
                       "automation/coordination-archive-aaaaaaaaaaaaaaaa"), calls)

    def test_bot_pr_permission_denial_keeps_cli_patch(self):
        code, calls, report = self.simulate_pr(deny=True)
        self.assertEqual(code, 1)
        self.assertEqual(report["automatic_pr"], "UNAVAILABLE")
        self.assertFalse(report["main_push"])
        self.assertEqual((self.root / "coordination-archive.patch").read_bytes(), b"test patch")


if __name__ == "__main__":
    unittest.main()
