#!/usr/bin/env python3
"""C4 read-only check: archived Sep 7-16 Alerts.in.ua bridge vs Lviv gap days.
No network fetch, no database calls, no production writes."""
import base64
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
from datetime import datetime
root=Path("site-prod-snapshot/kyiv-air-alerts-grafana/data")
meta_path=root/"alerts_in_ua_bridge_2026-09-07_16.meta.json"
payload_path=root/"alerts_in_ua_bridge_2026-09-07_16.csv.gz.b64"
meta_bytes=meta_path.read_bytes()
payload=payload_path.read_bytes()
sha=lambda x: hashlib.sha256(x).hexdigest()
git_blob=lambda x: hashlib.sha1(("blob "+str(len(x))).encode()+b"\x00"+x).hexdigest()
assert git_blob(payload)=="1ece234379381b4d7c0d10f851a86aa61aa958f6", "unexpected pinned bridge blob"
assert meta_path.is_file()
meta=json.loads(meta_bytes)
assert meta["timezone"]=="Europe/Kyiv"
assert "alerts_2026-09-14.csv" in meta["coverage_files"] and "alerts_2026-09-16.csv" in meta["coverage_files"]
decoded=gzip.decompress(base64.b64decode(payload.strip()))
reader=csv.DictReader(io.StringIO(decoded.decode("utf-8-sig")))
assert reader.fieldnames==["city_key","start","end"],reader.fieldnames
rows=list(reader)
lviv=sorted([r for r in rows if r["city_key"]=="lviv"],key=lambda x:x["start"])
assert len(lviv)==meta["target_summary"]["lviv"]["completed_events"],(len(lviv),meta["target_summary"]["lviv"])
assert meta["target_summary"]["lviv"]["incomplete_rows_dropped"]==0
assert len(lviv)==3
report={
  "status":"PASS_BOUNDED_ARCHIVED_BRIDGE_REPLAY",
  "site_prod_ref":"634fc6beffbcdf76026d64b9866314fdb53ab0e4",
  "bridge_source":"alerts.in.ua manual CSV export",
  "independence":"same provider as new CSV; separate archived material, NOT independent vendor",
  "meta_sha256":sha(meta_bytes),"payload_file_git_blob":git_blob(payload),
  "payload_b64_sha256":sha(payload),"decompressed_csv_sha256":sha(decoded),
  "coverage_files":meta["coverage_files"],"timezone":meta["timezone"],
  "lviv_completed_episode_count":len(lviv),"lviv_dropped_incomplete":0,
  "lviv_events":lviv,
  "limits":["Aggregated bridge cannot reconstruct original raw CSV row numbers","No source files for Sep 3-6 are included","Does not establish UkraineAlarm or Vadimkin independent agreement"]
}
print("C4_ARCHIVED_LVIV_BRIDGE|"+json.dumps(report,ensure_ascii=False,separators=(",",":")))
ua_path=root/"ukrainealarm_bridge.json"
try:
    ua=json.loads(ua_path.read_text(encoding="utf-8"))
    print("C4_UKRAINEALARM_STRUCTURE|"+json.dumps({"type":type(ua).__name__,
      "keys":list(ua)[:24] if isinstance(ua,dict) else None,
      "rows":len(ua) if isinstance(ua,list) else None,
      "sha256":sha(ua_path.read_bytes())},ensure_ascii=False,separators=(",",":")))
except Exception as e:
    print("C4_UKRAINEALARM_UNREADABLE|"+repr(e))
