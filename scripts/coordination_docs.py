#!/usr/bin/env python3
"""Bound coordination roots; archive exact bytes, never summarize checkpoint prose."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOTS = ('PROJECT_STATE.md', 'CHANGELOG.md')
WARN_BYTES = 12 * 1024
FAIL_BYTES = 16 * 1024
ARCHIVE = 'docs/coordination-archive'
INDEX = f'{ARCHIVE}/index.json'
START = b'<!-- coordination:checkpoints:start -->\n'
END = b'<!-- coordination:checkpoints:end -->'
LEGACY = {
    f'{ARCHIVE}/PROJECT_STATE_full_before_compaction_2026-10-30.md': 'ebcc286b3bfc93372a61567f1de5fe1d3e49bc2a',
    f'{ARCHIVE}/CHANGELOG_full_before_compaction_2026-10-30.md': '732e7a07f3e92e1138aafe311bff5561f56d60ee',
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def blob_sha(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n').encode()


def safe_path(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f'Path escapes repository: {relative}')
    return path


def read_index(root):
    p = root / INDEX
    return json.loads(p.read_bytes()) if p.exists() else {'version': 1, 'snapshots': []}


def records(data, name):
    """Return byte ranges of checkpoint sections; ignore headings inside code fences."""
    data.decode('utf-8', errors='strict')
    managed = START in data or END in data
    lo, hi = 0, len(data)
    if managed:
        if data.count(START) != 1 or data.count(END) != 1:
            raise ValueError(f'{name}: require one matched checkpoint marker pair')
        lo, hi = data.index(START) + len(START), data.index(END)
        if hi < lo:
            raise ValueError(f'{name}: reversed checkpoint markers')
    headings, pos, fence = [], 0, None
    for line in data.splitlines(keepends=True):
        # Markdown fenced blocks can contain apparent checkpoint headings.
        stripped = line.lstrip(b' ')
        fm = re.match(rb'(`{3,}|~{3,})', stripped)
        if fm:
            mark = fm.group(1)
            if fence is None:
                fence = mark
            elif mark[:1] == fence[:1] and len(mark) >= len(fence):
                fence = None
        elif fence is None and lo <= pos < hi:
            m = re.match(rb'^(#{1,6}) (.+?)\r?\n?$', line)
            if m:
                headings.append((pos, len(m[1]), m[2].decode('utf-8')))
        pos += len(line)
    wanted = 2 if name == ROOTS[0] else 3
    out, date = [], None
    for i, (start, level, title) in enumerate(headings):
        if level == 2 and re.fullmatch(r'\d{4}-\d{2}-\d{2}', title):
            date = title
        match = re.match(r'[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+\b', title)
        if level != wanted or (name == ROOTS[0] and not match):
            continue
        end = next((h[0] for h in headings[i + 1:] if h[1] <= level), hi)
        raw = data[start:end]
        out.append({'title': title, 'checkpoint': match[0] if match else title,
                    'date': date, 'start': start, 'end': end, 'sha256': sha(raw),
                    'pinned': b'<!-- coordination:keep -->' in raw})
    return out


def protected(data, name):
    if START in data:
        a = data.index(START) + len(START)
        b = data.index(END)
        return data[:a] + data[b:]
    return None


def classify(size):
    return 'FAIL' if size > FAIL_BYTES else 'WARNING' if size > WARN_BYTES else 'PASS'


def sizes(root):
    return {name: {'bytes': len((root / name).read_bytes()),
                   'status': classify(len((root / name).read_bytes()))} for name in ROOTS}


def revision(root):
    r = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=root, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def archive(root, date, dry_run=False, force=False, keep_changelog=5):
    dt.date.fromisoformat(date)
    if not 5 <= keep_changelog <= 10:
        raise ValueError('keep-changelog must be between 5 and 10')
    verify(root)
    index = read_index(root)
    if all((root / path).exists() for path in LEGACY):
        index['require_legacy'] = True
    writes, changes = {}, []
    for name in ROOTS:
        before = (root / name).read_bytes()
        entries = records(before, name)
        keep = 1 if name == ROOTS[0] else keep_changelog
        should_trim = force or len(before) > WARN_BYTES or len(entries) > (1 if name == ROOTS[0] else 10)
        moved = entries[keep:] if should_trim else []
        moved = [e for e in moved if not e['pinned']]
        after, cursor = b'', 0
        for e in moved:
            after += before[cursor:e['start']]
            cursor = e['end']
        after += before[cursor:]
        # Do not leave empty date headings in the managed history region.
        after = re.sub(rb'^## \d{4}-\d{2}-\d{2}\r?\n\s*(?=## |<!-- coordination:checkpoints:end -->|\Z)', b'', after, flags=re.M)
        if protected(before, name) != protected(after, name):
            raise ValueError(f'{name}: refusing to alter protected current state/blockers')
        if len(after) > WARN_BYTES and should_trim:
            raise ValueError(f'{name}: {len(after)} bytes remain after safe archival; shorten current prose manually, '
                             'move full proofs out of root, or unpin obsolete records. No files written.')
        if after == before:
            continue
        digest = sha(before)
        prefix = f'{ARCHIVE}/{date}/{Path(name).stem}.{digest[:16]}'
        path, manifest_path = prefix + '.md', prefix + '.json'
        manifest = {'version': 1, 'source': name, 'source_commit': revision(root), 'date': date,
                    'archive': path, 'before_bytes': len(before), 'after_bytes': len(after),
                    'before_sha256': digest, 'after_sha256': sha(after), 'git_blob_sha': blob_sha(before),
                    'records': [dict(e, disposition='archived' if e in moved else 'retained') for e in entries]}
        writes[path] = before
        writes[manifest_path] = encoded(manifest)
        writes[name] = after
        item = {'archive': path, 'sha256': digest, 'manifest': manifest_path,
                'manifest_sha256': sha(writes[manifest_path])}
        if item not in index['snapshots']:
            index['snapshots'].append(item)
        # Verify each removed byte range before preparing any writes.
        assert all(before[e['start']:e['end']] in writes[path] for e in moved)
        changes.append({'file': name, 'before_bytes': len(before), 'after_bytes': len(after),
                        'moved': len(moved), 'archive': path})
    if changes and not dry_run:
        writes[INDEX] = encoded(index)
        for path, content in writes.items():
            target = safe_path(root, path)
            if path not in ROOTS and path != INDEX and target.exists() and target.read_bytes() != content:
                raise ValueError(f'Immutable archive collision: {path}')
        # Evidence and index are durable before either root is replaced.
        ordered = [p for p in writes if p not in ROOTS] + [p for p in ROOTS if p in writes]
        for path in ordered:
            target = safe_path(root, path)
            target.parent.mkdir(parents=True, exist_ok=True)
            temp = target.with_suffix(target.suffix + '.tmp')
            temp.write_bytes(writes[path])
            temp.replace(target)
        verify(root)
    return {'dry_run': dry_run, 'changes': changes, 'moved_records': sum(c['moved'] for c in changes)}


def verify(root, base=None):
    checked, inventory = 0, []
    # Immutable blobs from the previous compaction remain independently pinned.
    for path, expected in LEGACY.items():
        file = root / path
        if file.exists():
            if blob_sha(file.read_bytes()) != expected:
                raise ValueError(f'Legacy archive Git blob mismatch: {path}')
            checked += 1
        elif read_index(root).get('require_legacy'):
            raise ValueError(f'Missing legacy archive: {path}')
    for item in read_index(root)['snapshots']:
        raw = safe_path(root, item['archive']).read_bytes()
        mf_raw = safe_path(root, item['manifest']).read_bytes()
        if sha(raw) != item['sha256'] or sha(mf_raw) != item['manifest_sha256']:
            raise ValueError(f'Archive or manifest SHA-256 mismatch: {item["archive"]}')
        mf = json.loads(mf_raw)
        if sha(raw) != mf['before_sha256'] or blob_sha(raw) != mf['git_blob_sha'] or len(raw) != mf['before_bytes']:
            raise ValueError(f'Archive source mismatch: {item["archive"]}')
        parsed = records(raw, mf['source'])
        if [{k: v for k, v in e.items() if k != 'disposition'} for e in mf['records']] != parsed:
            raise ValueError(f'Checkpoint inventory mismatch: {item["manifest"]}')
        for e in mf['records']:
            if sha(raw[e['start']:e['end']]) != e['sha256']:
                raise ValueError(f'Checkpoint SHA-256 mismatch: {e["checkpoint"]}')
        inventory.append(raw)
        checked += 1
    recovered = 0
    if base:
        # Only checkpoint records are immutable; current-state prose can be edited normally.
        for name in ROOTS:
            result = subprocess.run(['git', 'show', f'{base}:{name}'], cwd=root, capture_output=True)
            if result.returncode:
                raise ValueError(f'Cannot read {base}:{name}; fetch the comparison base')
            old = result.stdout
            available = [(root / name).read_bytes(), *inventory]
            for e in records(old, name):
                raw = old[e['start']:e['end']]
                if not any(raw in candidate for candidate in available):
                    raise ValueError(f'LOST checkpoint: {name} / {e["checkpoint"]}; archive exact original bytes first')
                recovered += 1
        # A PR cannot silently drop or alter previously indexed archives.
        old_index = subprocess.run(['git', 'show', f'{base}:{INDEX}'], cwd=root, capture_output=True)
        if old_index.returncode == 0:
            current = read_index(root)['snapshots']
            if any(e not in current for e in json.loads(old_index.stdout)['snapshots']):
                raise ValueError('Existing archive index entry removed or altered')
        for path, expected in LEGACY.items():
            old_blob = subprocess.run(['git', 'rev-parse', f'{base}:{path}'], cwd=root, capture_output=True, text=True)
            if old_blob.returncode == 0 and (not (root / path).exists() or blob_sha((root / path).read_bytes()) != expected):
                raise ValueError(f'Legacy evidence removed or changed: {path}')
    return {'verified_archives': checked, 'base_checkpoint_records_preserved': recovered}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['check', 'archive', 'verify'])
    p.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument('--date', default=dt.datetime.now(dt.timezone.utc).date().isoformat())
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--force', action='store_true', help='compact even below warning threshold')
    p.add_argument('--keep-changelog', type=int, default=5)
    p.add_argument('--base', help='Git ref whose checkpoint records must remain retrievable')
    p.add_argument('--report', type=Path)
    p.add_argument('--github', action='store_true')
    args = p.parse_args(argv)
    try:
        if args.command == 'archive':
            result = archive(args.root, args.date, args.dry_run, args.force, args.keep_changelog)
            exit_code = 0
        else:
            result = verify(args.root, args.base)
            exit_code = 0
            if args.command == 'check':
                result['files'] = sizes(args.root)
                for name, info in result['files'].items():
                    remedy = 'Run: python scripts/coordination_docs.py archive --dry-run; then archive and submit a PR.'
                    message = f'{name}: {info["bytes"]} UTF-8 bytes; {info["status"]} (PASS <=12288, WARNING <=16384). {remedy}'
                    print(message)
                    if args.github and info['status'] != 'PASS':
                        level = 'error' if info['status'] == 'FAIL' else 'warning'
                        print(f'::{level} file={name}::{message}')
                    exit_code |= info['status'] == 'FAIL'
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_bytes(encoded(result))
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return int(exit_code)
    except (ValueError, OSError, KeyError, UnicodeError, json.JSONDecodeError) as e:
        print(f'ERROR: {e}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
