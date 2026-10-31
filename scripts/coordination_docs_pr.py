#!/usr/bin/env python3
"""Create an archive PR from checked-out main; never push main or force a ref."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from coordination_docs import ROOTS, ARCHIVE, archive, protected, records, revision, sizes, verify


def run(*args, check=True):
    return subprocess.run(args, check=check, text=True, capture_output=True)


def main(root=None):
    root = root or Path(__file__).resolve().parents[1]
    os.chdir(root)
    # Code is executed only on trusted main, not from pull_request_target.
    if os.environ.get('GITHUB_REF') != 'refs/heads/main':
        print('Archive PR creation is restricted to main. Use the documented CLI on other branches.')
        return 0
    if run('git', 'status', '--porcelain').stdout.strip():
        raise ValueError('Refusing to operate with a dirty worktree')
    head = revision(root)
    branch = f'automation/coordination-docs-{head[:12]}'
    repo = os.environ['GITHUB_REPOSITORY']
    force = os.environ.get('ARCHIVE_FORCE', 'false') == 'true'
    need = force or any(v['bytes'] > 12288 for v in sizes(root).values()) or len(records((root / ROOTS[1]).read_bytes(), ROOTS[1])) > 10
    if not need:
        print('No archival needed; no branch or PR created.')
        return 0
    existing = run('gh', 'pr', 'list', '--repo', repo, '--head', branch, '--state', 'open', '--json', 'url')
    if json.loads(existing.stdout):
        print(existing.stdout)
        return 0
    remote = run('git', 'ls-remote', '--heads', 'origin', branch).stdout.strip()
    if remote:
        # A previous run may have pushed successfully and then failed to open the PR.
        # Never change that ref. Verify it before recovering PR creation.
        run('git', 'fetch', 'origin', branch)
        run('git', 'switch', '--detach', 'FETCH_HEAD')
        verify(root, head)
        for name in ROOTS:
            original = run('git', 'show', f'{head}:{name}').stdout.encode()
            if protected(original, name) != protected((root / name).read_bytes(), name):
                raise ValueError('Existing automation branch changed protected current state')
        if any(v['status'] != 'PASS' for v in sizes(root).values()):
            raise ValueError('Existing automation branch exceeds size limits')
        if run('git', 'merge-base', '--is-ancestor', head, 'HEAD', check=False).returncode:
            raise ValueError('Existing automation branch diverged; manual review required')
        paths = run('git', 'diff', '--name-only', head, 'HEAD').stdout.splitlines()
        if not paths or any(p not in ROOTS and not p.startswith(ARCHIVE + '/') for p in paths):
            raise ValueError('Existing automation branch has unexpected changes')
    else:
        date = run('git', 'show', '-s', '--format=%cs', head).stdout.strip()
        run('git', 'switch', '-c', branch)
        result = archive(root, date, force=force)
        if not result['changes']:
            raise ValueError('Threshold exceeded but no safe archival is possible; compact active prose manually')
        run(sys.executable, '-m', 'unittest', 'discover', '-s', 'tests/coordination')
        verify(root, head)
        for name in ROOTS:
            original = run('git', 'show', f'{head}:{name}').stdout.encode()
            if protected(original, name) != protected((root / name).read_bytes(), name):
                raise ValueError('Existing automation branch changed protected current state')
        if any(v['status'] != 'PASS' for v in sizes(root).values()):
            raise ValueError('Safe archival did not reach PASS; no push performed')
        run('git', 'config', 'user.name', 'github-actions[bot]')
        run('git', 'config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com')
        run('git', 'add', '--', *ROOTS, ARCHIVE)
        run('git', 'commit', '-m', 'docs: archive older coordination checkpoints [skip netlify]')
        run('git', 'push', 'origin', f'HEAD:refs/heads/{branch}')
    body = ('Move older coordination checkpoints into dated byte-exact snapshots. '
            'Keep current blockers and the newest checkpoint; retain the latest five changelog transitions.\n\n'
            'Validation: unit tests, UTF-8 size limits, SHA-256 manifests and checkpoint preservation against the base. '
            'No automatic merge or direct main push.\n')
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md') as f:
        f.write(body)
        f.flush()
        result = run('gh', 'pr', 'create', '--repo', repo, '--base', 'main', '--head', branch,
                     '--title', 'Archive older coordination checkpoints', '--body-file', f.name)
    print(result.stdout)
    # Token-created PR workflows may need human approval; explicit dispatch can run CI.
    dispatch = run('gh', 'workflow', 'run', 'coordination-docs.yml', '--repo', repo, '--ref', branch, check=False)
    if dispatch.returncode:
        raise ValueError('PR created, but CI dispatch denied. Run coordination-docs.yml manually on the PR branch.')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, subprocess.CalledProcessError) as e:
        detail = e.stderr if isinstance(e, subprocess.CalledProcessError) else str(e)
        print('::error::Archive PR could not be completed: ' + detail.replace('\n', ' '), file=sys.stderr)
        print('Fallback: python scripts/coordination_docs.py archive --dry-run; then archive, commit to a branch and open a PR.', file=sys.stderr)
        sys.exit(1)
