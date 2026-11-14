#!/usr/bin/env python3
"""Work H only: ensure isolated rollback app fetches ORIGINAL rollback data.

Existing Work D preparer gives both pages an absolute /data/ URL; without this
narrow correction, the rollback page silently reads preview data from /data/.
"""
from pathlib import Path
import sys
import hashlib

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

rollback = Path(sys.argv[1]).resolve()
preview = Path(sys.argv[2]).resolve()
a = rollback / "app.js"
p = preview / "app.js"
original = 'const RAW_DATA_BASE = "/data/";'
fixed = 'const RAW_DATA_BASE = "/rollback/data/";'
before = p.read_text(encoding="utf-8")
value = a.read_text(encoding="utf-8")
assert before == value and before.count(original) == 1, "unexpected local app"
assert a != p and rollback != preview
a.write_text(value.replace(original, fixed), encoding="utf-8")
assert sha(p) == hashlib.sha256(before.encode("utf-8")).hexdigest()
assert fixed in a.read_text(encoding="utf-8")
print("WORKH_ROLLBACK_ORIGINAL_DATA_ROUTE_PASS", sha(a), sha(p))
