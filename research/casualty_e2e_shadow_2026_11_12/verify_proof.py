#!/usr/bin/env python3
"""Physical proof gate. Partial shadow is deliberately not END_TO_END_PASS."""
import json
import sys
from pathlib import Path

def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def main(first, repeat):
    a, b = load(first / "summary.json"), load(repeat / "summary.json")
    proposals = load(first / "proposals.json")
    events = load(first / "attack_decisions.json")
    candidates = load(first / "candidate_decisions.json")
    probe = load(first / "generator_probe.json")
    assert a["city_count"] == 23 and a["candidates_seen"] == len(candidates), a
    assert a["shadow_proposals"] == 1 and a["generator_probe"] == "PASS", a
    assert b["shadow_proposals"] == 0 and b["generator_probe"] == "SKIPPED_ALREADY_RESERVED", b
    assert len(events) == 6, events
    assert len([e for e in events if e["status"] == "AUTO_READY"]) == 1, events
    assert len([e for e in events if e["status"] == "NEEDS_REVIEW"]) == 5, events
    assert len(proposals) == 1 and proposals[0]["deaths_delta"] == "23", proposals
    assert proposals[0]["count_kind"] == "cumulative" and proposals[0]["baseline_credited"] == "0"
    assert all(proposals[0][k] for k in ("incident_id", "identity_proof",
                                        "credited_proof", "candidate_ids", "source_url"))
    assert probe["new_delta"] == 23 and probe["before_month"] == 0
    assert all(e["publication_allowed"] is False for e in events)
    for folder in (first, repeat):
        assert load(folder / "manifest.json")["input_unchanged"]
    assert not a["publication_allowed"] and not b["publication_allowed"]
    verdict = {"status": "PARTIAL_SHADOW_PASS", "end_to_end_pass": False,
               "first_run": a, "idempotent_replay": b,
               "production_mutated": False, "new_publisher_http": False}
    Path("/tmp/casualty-verdict.json").write_text(json.dumps(verdict, indent=2) + "\n")
    print("PARTIAL_SHADOW_PASS", a["candidates_seen"], "candidate(s),",
          len(events), "attacks,", len(proposals), "proposal(s),",
          b["shadow_proposals"], "repeat proposals")

if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
