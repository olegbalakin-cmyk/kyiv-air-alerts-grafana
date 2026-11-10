#!/usr/bin/env python3
"""Offline-only WIP RSS token inventory; zero publisher/Google HTTP."""
import base64
import json
import re
from pathlib import Path
from urllib.parse import urlsplit
from run_pilot import QUEUE, select_candidates, EXPECTED_QUEUE_BLOB, git_blob

assert git_blob(QUEUE) == EXPECTED_QUEUE_BLOB
candidates, recent = select_candidates(json.loads(QUEUE.read_text(encoding="utf-8")))
rows = []
for c in candidates:
    p = urlsplit(c["url"])
    token = p.path.rsplit("/", 1)[-1]
    decoded = b""
    try:
        if re.fullmatch(r"[A-Za-z0-9_-]{5,900}", token):
            decoded = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
    except ValueError:
        pass
    rows.append({
        "city": c["city_key"],
        "host": p.hostname,
        "path_prefix": p.path.rsplit("/", 1)[0],
        "id_prefix": token[:12],
        "id_length": len(token),
        "decoded_prefix": decoded[:28].decode("utf-8", "replace"),
        "decoded_length": len(decoded),
        "embedded_http": b"https://" in decoded,
    })
print(json.dumps({"recent_candidates": recent, "sample_count": len(rows),
                  "format_counts": {
                      "opaque_AU": sum("AU_yqL" in x["decoded_prefix"] for x in rows),
                      "embedded_url": sum(x["embedded_http"] for x in rows)
                  }, "sample": rows[:8]}, ensure_ascii=False))
