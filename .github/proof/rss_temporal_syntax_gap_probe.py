#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

SOURCE_SHA = "5ebd77a7a1066fa4a2dabe62c98ee5c6b30d60c817282d560e8908f482ff8ef8"
TARGETS = [
    "f958519cfda65d5cd8eb81e5",
    "ecf26b3980c9dcac8234f689",
    "383e064c794bece60e20d4ca",
    "5b93c789ce785522030a51f4",
    "ccc799cf4b6706daac05f35e",
    "130a62ecc060e529737c7326",
    "7b99452890d6b851455983af",
]

def main() -> None:
    source = Path(sys.argv[1])
    out = Path(sys.argv[2])
    raw = source.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == SOURCE_SHA
    doc = json.loads(raw)
    ledger = doc["candidate_level_durability_ledger"]
    assert len(ledger) == 228
    rows = {row["candidate_id"]: row for row in ledger}
    assert set(TARGETS) <= set(rows)

    result = []
    for cid in TARGETS:
        row = rows[cid]
        selected = {
            "candidate_id": cid,
            "row_keys": sorted(row),
            "city": row.get("city"),
            "rss_title": row.get("rss_title"),
            "rss_snippet": row.get("rss_snippet"),
            "rss_url": row.get("rss_url"),
            "rss_published_at": row.get("rss_published_at"),
            "published_at": row.get("published_at"),
            "counterfactual": row.get("counterfactual"),
            "audit_contexts": row.get("audit_contexts"),
        }
        for key, value in row.items():
            if any(token in key.lower() for token in ("episode", "temporal", "classif", "match", "alert")):
                selected.setdefault("relevant_fields", {})[key] = value
        result.append(selected)

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
