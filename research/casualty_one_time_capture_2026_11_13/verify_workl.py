"""Work L artifact verifier: synthetic facts and hashes, no external HTTP."""
import argparse
import hashlib
import json
from pathlib import Path

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",type=Path,required=True)
    root=p.parse_args().output
    folder=root/"synthetic"
    files={x.name for x in folder.glob("*.json")}
    assert files=={"capture_receipts.json","minimal_capture_facts.json",
                   "fact_preview_unverified.json","summary.json","manifest.json"}
    hashes=json.loads((folder/"manifest.json").read_text())["files_sha256"]
    assert len(hashes)==4
    for name,digest in hashes.items():
        assert hashlib.sha256((folder/name).read_bytes()).hexdigest()==digest
    facts=json.loads((folder/"minimal_capture_facts.json").read_text())["facts"]
    assert len(facts)==3
    assert [c["claim_deaths"] for c in facts]==[2,3,3]
    assert [c["source_role"] for c in facts]==["publisher","publisher","official"]
    assert all(c["decision"]=="NEEDS_REVIEW" for c in facts)
    assert all(len(e["text"])<=170 for c in facts for e in c["excerpts"])
    assert all(c["document_sha256"] and len(c["document_sha256"])==64 for c in facts)
    assert json.loads((folder/"summary.json").read_text())["automatic_death_credits"]==0
    proof={"decision":"WORKL_SYNTHETIC_OFFLINE_PASS","source_http_get":0,
      "approved_live_authorization":False,"capture_workflow_trigger":"special_launch_commit_only",
      "reruns_allowed":False,"source_count":3,"mock_source_cards":3,
      "verified_manifest_hashes":4,"prior_credits_unverified":True,
      "police_matched_to_attack":False,"count_2_plus_3_is_5":False,
      "publication_allowed":False,"file_sha256":hashes}
    (root/"workl-proof.json").write_text(json.dumps(proof,indent=2,sort_keys=True)+"\n")
    print("WORKL_SYNTHETIC_OFFLINE_PASS 0 SOURCE HTTP")
if __name__=="__main__":main()
