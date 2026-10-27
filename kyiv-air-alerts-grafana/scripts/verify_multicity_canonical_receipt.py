#!/usr/bin/env python3
"""Independent fail-closed receipt gate for the canonical shadow.

No database connections. A diagnostic file is not automatically evidence of a
successful commit: it must have a complete, internally consistent success receipt.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")


class CanonicalReceiptError(ValueError):
    pass


def verify_receipt(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise CanonicalReceiptError("canonical receipt must be an object")
    if data.get("status") != "succeeded":
        raise CanonicalReceiptError("canonical persistence was not successful")
    if data.get("failure_policy") != "fail_closed":
        raise CanonicalReceiptError("canonical failure policy is not fail_closed")
    if data.get("production_output_mutation") is not False:
        raise CanonicalReceiptError("canonical shadow violated output boundary")
    if data.get("persistence_status") not in {"persisted", "already_persisted"}:
        raise CanonicalReceiptError("canonical writer did not confirm commit or exact retry")
    if data.get("city_count") != 23:
        raise CanonicalReceiptError("not exactly 23 cities")
    total = data.get("canonical_episode_count")
    inserted = data.get("episodes_inserted")
    existing = data.get("episodes_existing")
    updated = data.get("episodes_updated")
    writes = data.get("writes")
    if any(type(v) is not int or v < 0 for v in (total, inserted, existing, updated, writes)):
        raise CanonicalReceiptError("missing/invalid numeric counts")
    if total == 0 or inserted + existing != total or updated != 0:
        raise CanonicalReceiptError("canonical episode counts are inconsistent")
    if not DIGEST_RE.fullmatch(str(data.get("corpus_sha256") or "")):
        raise CanonicalReceiptError("canonical corpus hash is absent/invalid")
    if not SHA_RE.fullmatch(str(data.get("workflow_sha") or "")):
        raise CanonicalReceiptError("workflow Git SHA is absent/invalid")
    if not SHA_RE.fullmatch(str(data.get("input_sha") or "")):
        raise CanonicalReceiptError("input Git SHA is absent/invalid")
    if not str(data.get("db_branch") or "").strip():
        raise CanonicalReceiptError("database branch is not identified")
    if data["persistence_status"] == "persisted":
        if inserted == 0 or not data.get("run_id") or writes < inserted + 2:
            raise CanonicalReceiptError("committed writer receipt is incomplete")
    elif inserted != 0 or existing != total or writes != 0 or data.get("run_id") is not None:
        raise CanonicalReceiptError("exact-retry receipt is inconsistent")
    return data


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("usage: verify_multicity_canonical_receipt.py PATH", file=sys.stderr)
        return 2
    try:
        result = verify_receipt(argv[0])
    except (OSError, ValueError, TypeError) as exc:
        # Do not include exception values; the file can contain sensitive text.
        print(f"canonical persistence receipt REJECTED ({type(exc).__name__})", file=sys.stderr)
        return 1
    print(json.dumps({
        "canonical_persistence_receipt": "accepted",
        "persistence_status": result["persistence_status"],
        "city_count": result["city_count"],
        "canonical_episode_count": result["canonical_episode_count"],
        "episodes_inserted": result["episodes_inserted"],
        "episodes_existing": result["episodes_existing"],
        "corpus_sha256": result["corpus_sha256"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
