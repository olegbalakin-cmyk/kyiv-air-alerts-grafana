"""Work AG designated one-shot publisher article executor. NEVER scheduled.

The owner must separately approve exact HEAD, approved grant SHA256, and
1-3 literal article URLs. The prior Work AE grant cannot be reused.
No publication, active WIP, incident reconciliation or death credits.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kyiv-air-alerts-grafana/scripts"))
import casualty_go_guard as guard
import casualty_workac_capture as capture

class PilotBlocked(RuntimeError):
    pass

def validate_environment(environ):
    if environ.get("CASUALTY_ARTICLE_NETWORK") != "OWNER_APPROVED_ONE_SHOT":
        raise PilotBlocked("ARTICLE_NETWORK_OFF")
    if environ.get("GITHUB_RUN_ATTEMPT") != "1":
        raise PilotBlocked("RERUN_BLOCKED")
    if environ.get("GITHUB_EVENT_NAME") not in {"workflow_dispatch", "push"}:
        raise PilotBlocked("UNEXPECTED_TRIGGER")
    # This file is intentionally inert in the existing test workflow.
    sha = environ.get("GITHUB_SHA", "")
    if len(sha) != 40 or any(c not in "0123456789abcdef" for c in sha):
        raise PilotBlocked("INVALID_HEAD")
    if not environ.get("GITHUB_TOKEN") or not environ.get("GITHUB_REPOSITORY"):
        raise PilotBlocked("GITHUB_ATOMIC_LEDGER_REQUIRED")
    return sha

def execute(grant, *, approved_digest, environ, output):
    head = validate_environment(environ)
    guard.validate_grant(grant, approved_digest=approved_digest, head=head)
    if (grant["rss_get_budget"] != 0 or grant["allowed_urls"]["rss"] or
        not 1 <= grant["article_get_budget"] <= 3 or
        len(grant["allowed_urls"]["article"]) != grant["article_get_budget"]):
        raise PilotBlocked("ARTICLE_ONLY_EXACT_THREE_OR_FEWER")
    for url in grant["allowed_urls"]["article"]:
        capture.allowed_article_url(url)
    # Always consume before first network attempt. Uncertain tag creation blocks.
    lease = guard.claim_grant(
        grant, approved_digest=approved_digest, head=head,
        repo=environ["GITHUB_REPOSITORY"], token=environ["GITHUB_TOKEN"])
    results = []
    for url in grant["allowed_urls"]["article"]:
        try:
            # HTTP request goes only through analyze_direct_article, which
            # checks the unique claimed GO and decrements the attempt budget.
            row = capture.analyze_direct_article(url, owner_go=lease)
            card = row["card"]
            if card["automatic_credits"] or card["publication_allowed"]:
                raise PilotBlocked("UNSAFE_EVIDENCE_CARD")
            results.append({"url_sha256": hashlib.sha256(url.encode()).hexdigest(),
                            "status": "REVIEW_ONLY",
                            "card": card})
        except Exception as exc:
            # Never retry a failed URL and never replay the grant.
            results.append({"url_sha256": hashlib.sha256(url.encode()).hexdigest(),
                            "status": "CAPTURE_BLOCKED",
                            "reason": type(exc).__name__})
    out = Path(output)
    if out.exists():
        raise PilotBlocked("OUTPUT_ALREADY_EXISTS")
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {"head": head, "go_id": grant["owner_go_id"],
               "article_get_budget": grant["article_get_budget"],
               "source_http_attempts_max": len(results),
               "automatic_credits": 0, "publication_allowed": False,
               "PROMOTE": "OFF", "rows": results}
    # No full HTML, no extracted full body, no active-WIP writes.
    data = (json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)+"\n").encode()
    out.write_bytes(data)
    return hashlib.sha256(data).hexdigest()

if __name__ == "__main__":
    e = os.environ
    # Missing flags/grant fail before any GitHub or media HTTP.
    validate_environment(e)
    grant_path = e.get("CASUALTY_OWNER_GO_FILE", "")
    digest = e.get("CASUALTY_OWNER_GO_DIGEST", "")
    if not grant_path or not digest:
        raise PilotBlocked("EXACT_OWNER_MANIFEST_REQUIRED")
    grant = json.loads(Path(grant_path).read_text())
    digest_result = execute(
        grant, approved_digest=digest, environ=e,
        output="/tmp/casualty_workag_live_proof.json")
    print("WORKAG_REVIEW_ONLY_PROOF_SHA256", digest_result)
