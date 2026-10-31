import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[2] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import coordination_docs as docs
import coordination_docs_pr as bot


def fixture(root, n=12, managed=True, body_bytes=200):
    for name in docs.ROOTS:
        level = '##' if name == docs.ROOTS[0] else '###'
        head = b'# Coordination\n\n## Current blockers\n\nKeep this OPEN blocker and next task exactly.\n\n'
        blocks = b''.join((f'{level} TEST-CP-{i:02d} — result\n\n' + 'я' * body_bytes + '\n\n').encode() for i in range(n, 0, -1))
        (root / name).write_bytes(head + (docs.START if managed else b'') + blocks + (docs.END + b'\n\n' if managed else b'') + b'## Current next task\n\nPreserve current scope.\n')


class RepoFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        fixture(self.root)

    def snapshot(self):
        return {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}



class ArchivalTests(RepoFixture):
    def test_exact_thresholds(self):
        for size, expected in [(12287, 'PASS'), (12288, 'PASS'), (12289, 'WARNING'),
                               (16383, 'WARNING'), (16384, 'WARNING'), (16385, 'FAIL')]:
            with self.subTest(size=size):
                self.assertEqual(docs.classify(size), expected)

    def test_utf8_bytes_and_cli_exit_codes(self):
        for size, exit_code in [(12288, 0), (12289, 0), (16384, 0), (16385, 1)]:
            # Cyrillic characters prove this is byte-counted, not len(text).
            (self.root / docs.ROOTS[0]).write_bytes(('я' * (size // 2)).encode() + b'x' * (size % 2))
            with contextlib.redirect_stdout(io.StringIO()) as output:
                code = docs.main(['check', '--root', str(self.root), '--github'])
            self.assertEqual(code, exit_code)
            self.assertIn(f'{size} UTF-8 bytes', output.getvalue())
            if exit_code:
                self.assertIn('::error file=PROJECT_STATE.md::', output.getvalue())
                self.assertIn('archive --dry-run', output.getvalue())

    def test_dry_run_writes_nothing(self):
        before = self.snapshot()
        result = docs.archive(self.root, '2026-10-31', dry_run=True, force=True)
        self.assertEqual(result['moved_records'], 18)  # 11 state + 7 changelog
        self.assertEqual(before, self.snapshot())

    def test_archival_preserves_exact_records_and_current_blockers(self):
        originals = {n: (self.root / n).read_bytes() for n in docs.ROOTS}
        result = docs.archive(self.root, '2026-10-31', force=True)
        self.assertEqual(result['moved_records'], 18)
        index = docs.read_index(self.root)
        for name in docs.ROOTS:
            current = (self.root / name).read_bytes()
            self.assertEqual(docs.protected(originals[name], name), docs.protected(current, name))
            snap = next(e for e in index['snapshots'] if Path(e['archive']).name.startswith(Path(name).stem + '.'))
            self.assertEqual(originals[name], (self.root / snap['archive']).read_bytes())
            for record in docs.records(originals[name], name):
                raw = originals[name][record['start']:record['end']]
                self.assertTrue(raw in current or raw in (self.root / snap['archive']).read_bytes())
        self.assertEqual(len(docs.records((self.root / docs.ROOTS[0]).read_bytes(), docs.ROOTS[0])), 1)
        self.assertEqual(len(docs.records((self.root / docs.ROOTS[1]).read_bytes(), docs.ROOTS[1])), 5)
        self.assertEqual(docs.verify(self.root)['verified_archives'], 2)

    def test_idempotent_even_with_different_date(self):
        docs.archive(self.root, '2026-10-31', force=True)
        before = self.snapshot()
        self.assertEqual(docs.archive(self.root, '2026-11-01', force=True)['changes'], [])
        self.assertEqual(before, self.snapshot())

    def test_pinned_current_checkpoint_survives(self):
        p = self.root / docs.ROOTS[0]
        p.write_bytes(p.read_bytes().replace(
            b'## TEST-CP-03 \xe2\x80\x94 result\n', b'## TEST-CP-03 \xe2\x80\x94 result\n<!-- coordination:keep -->\n'))
        docs.archive(self.root, '2026-10-31', force=True)
        self.assertIn(b'TEST-CP-03', p.read_bytes())
        self.assertIn(b'TEST-CP-12', p.read_bytes())

    def test_fenced_headings_not_checkpoints(self):
        p = self.root / docs.ROOTS[0]
        p.write_bytes(p.read_bytes().replace(b'## TEST-CP-12', b'```md\n## FAKE-CP-00\n```\n## TEST-CP-12'))
        self.assertEqual(len(docs.records(p.read_bytes(), p.name)), 12)

    def test_corruption_and_missing_snapshot_rejected(self):
        docs.archive(self.root, '2026-10-31', force=True)
        item = docs.read_index(self.root)['snapshots'][0]
        path = self.root / item['archive']
        raw = path.read_bytes()
        path.write_bytes(raw + b'changed')
        with self.assertRaisesRegex(ValueError, 'SHA-256 mismatch'):
            docs.verify(self.root)
        path.unlink()
        with self.assertRaises(FileNotFoundError):
            docs.verify(self.root)

    def test_corrupt_manifest_rejected(self):
        docs.archive(self.root, '2026-10-31', force=True)
        item = docs.read_index(self.root)['snapshots'][0]
        (self.root / item['manifest']).write_text('{}')
        with self.assertRaisesRegex(ValueError, 'SHA-256 mismatch'):
            docs.verify(self.root)

    def test_invalid_marker_or_date_no_mutation(self):
        p = self.root / docs.ROOTS[0]
        p.write_bytes(p.read_bytes().replace(docs.END, b''))
        before = self.snapshot()
        with self.assertRaises(ValueError):
            docs.archive(self.root, '2026-10-31', force=True)
        self.assertEqual(before, self.snapshot())
        with self.assertRaises(ValueError):
            docs.archive(self.root, '../not-a-date', force=True)

    def test_oversized_active_state_refuses_loss(self):
        p = self.root / docs.ROOTS[0]
        p.write_bytes(b'# Current state\n' + b'X' * 13000)
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'No files written'):
            docs.archive(self.root, '2026-10-31')
        self.assertEqual(before, self.snapshot())

    def test_legacy_roots_and_empty_date_heading(self):
        fixture(self.root, managed=False)
        p = self.root / docs.ROOTS[1]
        p.write_bytes(p.read_bytes().replace(b'### TEST-CP-07', b'## 2026-10-30\n\n### TEST-CP-07'))
        docs.archive(self.root, '2026-10-31', force=True)
        self.assertNotIn(b'## 2026-10-30', p.read_bytes())
        docs.verify(self.root)

    def test_retention_bounds(self):
        for keep in (4, 11):
            with self.assertRaises(ValueError):
                docs.archive(self.root, '2026-10-31', keep_changelog=keep)

    def test_archive_path_traversal_rejected(self):
        (self.root / docs.INDEX).parent.mkdir(parents=True)
        (self.root / docs.INDEX).write_text(json.dumps({'snapshots': [
            {'archive': '../outside', 'manifest': '../outside', 'sha256': '', 'manifest_sha256': ''}]}))
        with self.assertRaisesRegex(ValueError, 'escapes repository'):
            docs.verify(self.root)


class GitHistoryTests(RepoFixture):
    def git(self, *args):
        return subprocess.run(['git', *args], cwd=self.root, check=True, capture_output=True, text=True).stdout.strip()

    def setUp(self):
        super().setUp()
        self.git('init', '-b', 'main')
        self.git('config', 'user.name', 'Test')
        self.git('config', 'user.email', 'test@example.com')
        self.git('add', '.')
        self.git('commit', '-m', 'base')
        self.base = self.git('rev-parse', 'HEAD')

    def test_git_base_records_are_all_preserved(self):
        docs.archive(self.root, '2026-10-31', force=True)
        self.assertEqual(docs.verify(self.root, self.base)['base_checkpoint_records_preserved'], 24)

    def test_silent_checkpoint_loss_is_rejected(self):
        p = self.root / docs.ROOTS[0]
        data = p.read_bytes()
        entry = docs.records(data, p.name)[-1]
        p.write_bytes(data[:entry['start']] + data[entry['end']:])
        with self.assertRaisesRegex(ValueError, 'LOST checkpoint'):
            docs.verify(self.root, self.base)

    def test_old_index_entries_cannot_be_removed(self):
        docs.archive(self.root, '2026-10-31', force=True)
        self.git('add', '.')
        self.git('commit', '-m', 'archive')
        base = self.git('rev-parse', 'HEAD')
        (self.root / docs.INDEX).write_text('{"version": 1, "snapshots": []}')
        with self.assertRaisesRegex(ValueError, 'index entry removed'):
            docs.verify(self.root, base)


class BotTests(unittest.TestCase):
    def test_never_operates_from_feature_ref(self):
        with patch.dict(os.environ, {'GITHUB_REF': 'refs/heads/feature'}), patch.object(bot, 'run') as run:
            self.assertEqual(bot.main(), 0)
            run.assert_not_called()

    def test_denied_pr_permission_leaves_main_untouched_and_recovers_existing_branch(self):
        with tempfile.TemporaryDirectory() as temp:
            root, remote = Path(temp) / 'work', Path(temp) / 'remote.git'
            root.mkdir()
            def git(*args):
                return subprocess.run(['git', *args], cwd=root, check=True, capture_output=True, text=True).stdout.strip()
            git('init', '--bare', str(remote))
            git('init', '-b', 'main')
            git('config', 'user.name', 'Test')
            git('config', 'user.email', 'test@example.com')
            fixture(root, n=14, body_bytes=700)
            (root / '.gitignore').write_text('__pycache__/\n')
            # Bot validates actual script/tests from the trusted base too.
            (root / 'tests/coordination').mkdir(parents=True)
            (root / 'tests/coordination/test_smoke.py').write_text(
                "import unittest\nfrom pathlib import Path\nclass Smoke(unittest.TestCase):\n def test_latest_retained(self):\n  self.assertIn('TEST-CP-14', Path('PROJECT_STATE.md').read_text())\n")
            git('add', '.')
            git('commit', '-m', 'base')
            base = git('rev-parse', 'HEAD')
            git('remote', 'add', 'origin', str(remote))
            git('push', 'origin', 'main')
            actual = bot.run
            calls = []
            def fake(*args, **kwargs):
                calls.append(args)
                if args[:3] == ('gh', 'pr', 'list'):
                    return subprocess.CompletedProcess(args, 0, '[]', '')
                if args[:3] == ('gh', 'pr', 'create'):
                    raise subprocess.CalledProcessError(1, args, stderr='GitHub Actions is not permitted to create pull requests')
                return actual(*args, **kwargs)
            previous_cwd = Path.cwd()
            try:
                with patch.dict(os.environ, {'GITHUB_REF': 'refs/heads/main', 'GITHUB_REPOSITORY': 'owner/repo'}), patch.object(bot, 'run', side_effect=fake):
                    with self.assertRaises(subprocess.CalledProcessError) as denial:
                        bot.main(root)
                    self.assertIn('not permitted to create pull requests', denial.exception.stderr)
                    self.assertEqual(git('rev-parse', 'main'), base)
                    self.assertEqual(git('ls-remote', 'origin', 'refs/heads/main').split()[0], base)
                    self.assertTrue(any(a[0:2] == ('git', 'push') and 'refs/heads/automation/' in a[-1] for a in calls))
                    self.assertFalse(any('--force' in a or a[-1:] == ('main',) for a in calls if a[0:2] == ('git', 'push')))
                    # Rerun after denial reuses and verifies the pushed branch, no second commit/push.
                    calls.clear()
                    git('switch', 'main')
                    with self.assertRaises(subprocess.CalledProcessError):
                        bot.main(root)
                    self.assertFalse(any(a[0:2] == ('git', 'push') for a in calls))
            finally:
                os.chdir(previous_cwd)


if __name__ == '__main__':
    unittest.main()
