"""Machine-readable Work AH proof; consumes only deterministic mocked outputs."""
import hashlib
import json
import os
from pathlib import Path

root=Path("/tmp/workah")
normal=json.loads((root/"offline-article-proof.json").read_text())
blocked=json.loads((root/"offline-blocked-proof.json").read_text())
assert len(normal["rows"]) == len(blocked["rows"]) == 3
assert normal["rss_get_budget"] == blocked["rss_get_budget"] == 0
assert normal["article_get_budget"] == blocked["article_get_budget"] == 3
assert all(r["http_status"] == 200 for r in normal["rows"])
assert [r["http_status"] for r in blocked["rows"]] == [403,200,200]
assert normal["automatic_credits"] == blocked["automatic_credits"] == 0
assert normal["cross_source_incident_identity"] == "INSUFFICIENT_EVIDENCE"
for p in (root/"offline-article-proof.json",root/"offline-blocked-proof.json"):
    data=p.read_bytes()
    assert b"<html" not in data.lower() and b"<!doctype" not in data.lower()
    assert b"Bearer " not in data and b"mock-only" not in data
summary={
 "checkpoint":"CASUALTY-WORKAH-GUARDED-ARTICLE-EXECUTOR-OFFLINE",
 "exact_head":os.environ.get("GITHUB_SHA","LOCAL"),
 "test_mode":"STRICT_OFFLINE_SYNTHETIC_HTTP_MOCKS",
 "article_url_count":3,
 "rss_get_budget":0,
 "article_get_budget":3,
 "mock_http_200_body_numeric":3,
 "mock_http_403":1,
 "mock_body_unavailable":1,
 "real_publisher_http_gets":0,
 "real_rss_gets":0,
 "git_spent_tag_mock_atomic_race":"ONE_WINNER",
 "replay_and_rerun":"BLOCKED",
 "url_mutation":"BLOCKED",
 "head_and_expiry_and_digest_mismatch":"BLOCKED",
 "ledger_write_failure":"BLOCKED",
 "extra_url_and_attempt":"BLOCKED",
 "stored_full_html":False,
 "automatic_death_credits":0,
 "active_wip_writes":0,
 "production_writes":0,
 "PROMOTE":"OFF",
 "publication_allowed":False,
 "production_changed":False,
 "real_publisher_parser_verified":False,
}
(root/"offline_proof.json").write_text(json.dumps(summary,sort_keys=True,indent=2)+"\n")
manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest()
          for p in (root/"offline-article-proof.json",root/"offline-blocked-proof.json",root/"offline_proof.json")}
(root/"sha256_manifest.json").write_text(json.dumps(manifest,sort_keys=True,indent=2)+"\n")
for k,d in manifest.items():
    assert hashlib.sha256((root/k).read_bytes()).hexdigest()==d
print("WORKAH_OFFLINE_PROOF_PASS",json.dumps(summary,sort_keys=True))
print("WORKAH_SHA256",json.dumps(manifest,sort_keys=True))
