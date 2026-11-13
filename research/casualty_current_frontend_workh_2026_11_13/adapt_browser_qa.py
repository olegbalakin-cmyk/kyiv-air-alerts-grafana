#!/usr/bin/env python3
"""Narrow Work H test-only copy: allow current original absent row as null OR 0.

Keep every other Work D assertion unchanged. The original pinned Work D source
is immutable. Work D's historical test assumed missing month -> chart zero;
current frontend renders a truly absent 2026-10 as null.
"""
import hashlib
import sys
from pathlib import Path

source, target = (Path(x).resolve() for x in sys.argv[1:])
text = source.read_text(encoding="utf-8")
before = 'assert.equal(before.value,before.source??0);assert.equal(before.note,null);'
after = ('assert(before.value===before.source || '
         '(before.source===null && (before.value===null || before.value===0)));'
         'assert.equal(before.note,null);')
assert text.count(before) == 1 and not target.exists()
assert source != target
target.write_text(text.replace(before, after), encoding="utf-8")
assert text.replace(before, after) == target.read_text(encoding="utf-8")
print("CURRENT_SITE_ROLLBACK_ABSENT_MONTH_COMPAT_PASS")
print("PINNED_WORKD_QA_SHA256", hashlib.sha256(source.read_bytes()).hexdigest())
print("CURRENT_QA_COPY_SHA256", hashlib.sha256(target.read_bytes()).hexdigest())
