#!/usr/bin/env python3
"""Aggregate strictly public-safe metadata; never copy original publisher bytes."""
import hashlib
import json
from pathlib import Path

PROOF = Path("research/bbc_publisher_http_2026_10_12/proof")
TARGET = "https://www.bbc.com/ukrainian/articles/ck9dzex1zp3qo"


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main():
    observation = json.loads((PROOF / "observation.json").read_text(encoding="utf-8"))
    a = json.loads((PROOF / "verify_A.json").read_text(encoding="utf-8"))
    b = json.loads((PROOF / "verify_B.json").read_text(encoding="utf-8"))
    raw_equality = bool(
        a.get("transport_hash_consistent") is True
        and b.get("transport_hash_consistent") is True
        and a.get("raw_entity_size_bytes") == b.get("raw_entity_size_bytes")
        and a.get("raw_entity_sha256") == b.get("raw_entity_sha256")
    )
    decoded_equal = bool(
        a.get("decoded_html_sha256")
        and a.get("decoded_html_sha256") == b.get("decoded_html_sha256")
        and a.get("decoded_size_bytes") == b.get("decoded_size_bytes")
    )
    article_identity = bool(a.get("article_identity_proven") and b.get("article_identity_proven"))
    status = observation.get("http_status")
    if status is None:
        verdict = "ISOLATED SINGLE-BBC-PUBLISHER HTTP CAPTURE = BLOCKED"
    else:
        # Controlled durable raw persistence does not exist in this public-repository runner.
        verdict = "ISOLATED SINGLE-BBC-PUBLISHER HTTP CAPTURE = PARTIAL"
    adjudication = {
        "schema": "single_bbc_publisher_http_capture_adjudication_v1",
        "verdict": verdict,
        "accepted_predecessor": "GOOGLE NEWS BBC ARTICLE URL RESOLUTION = PROVEN — ACCEPTED",
        "predecessor_acceptance_commit": "220ea11ae168afba2ea5057b3d625dd21ca7d63b",
        "predecessor_frozen_proof_commit": "cbfc7707b37e04ed03298a89ed5a0bd60cce9e4e",
        "predecessor_actions_run": 38285649877,
        "predecessor_zip_sha256": "a90baf7622396b486a2c0617c7fe96cee7ed47d8833e799fa12ce85b341a3ff7",
        "exact_article_url": TARGET,
        "http_transport_observed": status is not None,
        "http_status": status,
        "response_read_complete": observation.get("reading_finished_normally", False),
        "no_redirects_followed": observation.get("redirect_followed") is False,
        "no_retries_claimed_by_source_code": observation.get("automatic_retries") is False,
        "no_cookies_sent_by_script": observation.get("cookies_and_authorization_sent_by_script") is False,
        "raw_bytes_size": observation.get("raw_received_entity_size_bytes"),
        "raw_sha256": observation.get("raw_received_entity_sha256"),
        "two_implementations_raw_sha256_match": raw_equality,
        "two_implementations_decoded_bytes_match": decoded_equal,
        "article_identity_approved_by_both": article_identity,
        "html_canonical_a": a.get("canonical_url"),
        "html_canonical_b": b.get("canonical_url"),
        "html_og_url_a": a.get("open_graph_url"),
        "html_og_url_b": b.get("open_graph_url"),
        "document_title_a": a.get("document_title"),
        "document_title_b": b.get("document_title"),
        "substantive_article_body_a": a.get("body_substantive"),
        "substantive_article_body_b": b.get("body_substantive"),
        "verification_A_error": a.get("error_class"),
        "verification_B_error": b.get("error_class"),
        "offline_A_B_same_temporary_raw_snapshot": True,
        "offline_A_B_algorithmically_distinct": True,
        "external_independent_validation_of_durable_raw": False,
        "durable_permitted_raw_storage": False,
        "restricted_raw_readback": False,
        "raw_storage_lifetime": "GitHub runner temp; deleted at end; not an Actions artifact",
        "public_repository_body_commits": 0,
        "monitor_integration": False,
        "historical_first_availability_proven": False,
        "detection_latency_proven": False,
        "monitor_completeness_proven": False,
        "G1_authorized": False,
        "independent_acceptance_pending": True,
        "smallest_remaining_blocker": (
            "No HTTPS response status observed."
            if status is None else
            "No controlled durable raw-body preservation or independent restricted read-back."
            if raw_equality and decoded_equal and article_identity and observation.get("reading_finished_normally") else
            "HTTP transport observed; article identity, completeness or independent raw verification remains incomplete, and no durable restricted raw preservation exists."
        ),
    }
    write_json(PROOF / "adjudication.json", adjudication)
    readme = (
        "# Isolated BBC publisher single-GET HTTP proof (unaccepted)\n\n"
        "Exact URL: `https://www.bbc.com/ukrainian/articles/ck9dzex1zp3qo`.\n\n"
        f"Verdict: `{verdict}`.\n\n"
        "Original publisher entity bytes were stored only in a GitHub-hosted runner private temporary file "
        "(directory mode 0700, file mode 0600) for offline verification. They are not in this "
        "repository, its Git objects, logs or Actions artifacts, and were deleted after execution. "
        "This is not durable preserved publisher evidence.\n\n"
        "`observation.json` contains client-observed transport metadata and the captured raw entity SHA-256. "
        "`verify_A.json` is the offline gzip/HTMLParser check, `verify_B.json` is the separate "
        "offline zlib/regex check. Both inspect one ephemeral raw snapshot; these are distinct "
        "implementations, not third-party independent confirmation or later durable read-back. "
        "`adjudication.json` distinguishes transport, exact article identity, completeness and preservation. "
        "`sha256_manifest.json` authenticates the public-safe metadata only.\n\n"
        "This proof does not establish BBC first availability, casualty detection latency, monitoring "
        "recall or G1 eligibility. Production, historical data, main, site-prod, casualty WIP, "
        "Neon, source monitors and the predecessor proof were not modified.\n"
    )
    (PROOF / "README.md").write_text(readme, encoding="utf-8")
    manifest = {"schema": "public_safe_bbc_http_metadata_sha256_manifest_v1", "members": {}}
    for filename in ("observation.json", "verify_A.json", "verify_B.json", "adjudication.json", "README.md"):
        data = (PROOF / filename).read_bytes()
        manifest["members"][filename] = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    write_json(PROOF / "sha256_manifest.json", manifest)
    mdig = hashlib.sha256((PROOF / "sha256_manifest.json").read_bytes()).hexdigest()
    (PROOF / "sha256_manifest.sha256").write_text(mdig + "  sha256_manifest.json\n", encoding="ascii")
    # End-to-end offline verification of the metadata manifest; never read private raw into a public output.
    for name, receipt in manifest["members"].items():
        assert len((PROOF / name).read_bytes()) == receipt["bytes"]
        assert hashlib.sha256((PROOF / name).read_bytes()).hexdigest() == receipt["sha256"]
    print(json.dumps({"verdict": verdict, "manifest_sha256": mdig,
                      "A_B_raw_equal": raw_equality, "A_B_decoded_equal": decoded_equal,
                      "identity_by_both": article_identity, "no_durable_raw_storage": True}, sort_keys=True))


if __name__ == "__main__":
    main()