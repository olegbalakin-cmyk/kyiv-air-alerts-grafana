#!/usr/bin/env python3
"""Physical synthetic proof of Work K retained cards and manifest (no network)."""
import argparse
import hashlib
import json
from pathlib import Path

from research.casualty_one_time_capture_2026_11_13 import run_capture as r
from research.casualty_one_time_capture_2026_11_13.test_workk import mock_inputs, queue


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    out=args.output.resolve()
    out.mkdir(parents=True,exist_ok=True)
    plan,volatile,audit,bodies=mock_inputs()
    summary=r.retain_results(queue(),plan,volatile,audit,out,authorization_id="SYNTHETIC-NO-OWNER-GRANT")
    facts=json.loads((out/"minimal_capture_facts.json").read_text())["facts"]
    manifest=json.loads((out/"manifest.json").read_text())["files_sha256"]
    assert [x["source_role"] for x in facts]==["publisher","publisher","official"]
    assert [x["claim_deaths"] for x in facts]==[2,3,3]
    assert summary["automatic_death_credits"]==0
    assert summary["proposed_new_credits"] is None
    assert all(x["decision"]=="NEEDS_REVIEW" for x in facts)
    assert all(x["document_sha256"] for x in facts)
    assert all(x["source_url"].startswith("https://") for x in facts)
    for name,digest in manifest.items():
        assert hashlib.sha256((out/name).read_bytes()).hexdigest()==digest
    for doc in bodies:
        assert all(doc not in file.read_text() for file in out.glob("*.json"))
    proof={
      "decision":"THREE_SOURCE_SYNTHETIC_RETENTION_PASS",
      "real_T03_T04_T05_originals_tested":False,
      "source_http_get":0,
      "source_targets":["T03","T04","T05"],
      "source_claims":[2,3,3],
      "publisher_cards":2,"unlinked_police_cards":1,
      "official_incident_match":False,
      "prior_credit_reconciled":False,
      "automatic_death_credits":0,
      "publication_allowed":False,
      "file_sha256":manifest}
    (out.parent/"workk-proof.json").write_text(json.dumps(proof,sort_keys=True,indent=2)+"\n")
    print("WORKK_SYNTHETIC_RETENTION_PASS (zero source HTTP)")


if __name__=="__main__":
    main()
