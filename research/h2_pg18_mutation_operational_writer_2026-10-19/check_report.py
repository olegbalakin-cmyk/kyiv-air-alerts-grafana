#!/usr/bin/env python3
"""Independent report shape and recorded assertion verifier; never repair failures."""
import json,sys,hashlib
from pathlib import Path
p=Path(sys.argv[1])
if not p.is_file():
    raise SystemExit("BLOCKED: report missing; no green interpretation")
raw=p.read_bytes()
a=json.loads(raw)
assert a["schema"]=="h2-offline-mutation-operational-v1"
assert a["copy"] in ("A","B")
assert a["pg_version"].startswith("18.")
assert a["operational_writer_git_blob"]=="0118ca9e5f1308173e657257f1b49fe91cc19fe1"
assert a["assertions_total"]==len(a["assertions"])
assert a["assertions_passed"]==sum(bool(x["pass"]) for x in a["assertions"])
assert a["failed_assertions"]==[x["name"] for x in a["assertions"] if not x["pass"]]
for x in a["assertions"]:
    assert x["pass"]==(x["expected"]==x["observed"]),x["name"]
print(json.dumps({"copy":a["copy"],"sha256":hashlib.sha256(raw).hexdigest(),
"pg":a["pg_version"],"assertions":a["assertions_total"],"passed":a["assertions_passed"],
"verdict":a["harness_verdict"],"failures":a["failed_assertions"],
"unexpected":a["unexpected"]},sort_keys=True))
if a["harness_verdict"]!="EXECUTED_COMPLETE":
    raise SystemExit("BOUNDED NO-GO: genuine failing proof retained in artifact")
