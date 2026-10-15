#!/usr/bin/env python3
"""Offline, read-only verification for a pinned Kyiv 185 research crosswalk.
Usage: python verify_identity_crosswalk.py identity_crosswalk_185.json <original_source_index.json> <modern_alerts_combined.json> <seven_gap_index.json>
Only local files; makes no network/database calls or writes.
"""
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
def load(path):
    return json.loads(Path(path).read_bytes())
def utc(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)
def iso(s):
    return utc(s).isoformat().replace("+00:00", "Z")
def eid(city, start, end):
    return hashlib.sha256(f"{city}|{start}|{end}".encode()).hexdigest()[:24]
def run(crosswalk, original, modern, seven):
    rows=crosswalk["rows"]
    originals=original["rows"]
    prod=[r for r in modern if isinstance(r, dict)]
    source={r["original_episode_id"]:r for r in originals}
    gaps={r["original_episode_id"] for r in seven["cases"]}
    assert len(rows)==len(originals)==len(source)==185
    assert len(gaps)==7
    assert len(prod)==2664
    found=set()
    for row in rows:
        oid=row["original_episode_id"]
        assert oid in source
        o=source[oid]
        start,end=o["original_times_exact_utc"]
        assert row["original_utc"]["start"]==start and row["original_utc"]["end"]==end
        assert row["original_wip"]["first_persistence_commit"]==o["first_wip_commit"]
        assert row["original_wip"]["first_persistence_state_blob"]==o["first_wip_state_blob"]
        assert row["original_wip"]["first_persistence_json_pointer"]==o["first_wip_state_pointer"]
        assert eid("kyiv",start,end)==oid
        assert (oid in gaps)==row["original_source_provenance"]["producer_runtime_evidence_gap"]
        assert not row["original_source_provenance"]["runtime_input_git_sha_independently_pinned"]
        s,e=utc(start),utc(end)
        eligible=[(i,m) for i,m in enumerate(prod) if utc(m["start"]).replace(second=0,microsecond=0)==s and utc(m["end"]).replace(second=0,microsecond=0)==e]
        overlap=[(i,m) for i,m in enumerate(prod) if utc(m["start"])<e and utc(m["end"])>s]
        assert len(eligible)==len(overlap)==1 and eligible[0][0]==overlap[0][0]
        i,m=eligible[0]
        candidate=row["modern_candidates"]
        assert len(candidate)==1
        c=candidate[0]
        assert c["json_pointer"]==f"/{i}"
        assert c["utc_start"]==iso(m["start"]) and c["utc_end"]==iso(m["end"])
        assert c["source_family"]==m["source"]=="official_json"
        assert eid("kyiv",c["utc_start"],c["utc_end"])==c["derived_episode_id"]
        assert oid!=c["derived_episode_id"]
        assert c["derived_episode_id"] not in found
        found.add(c["derived_episode_id"])
        ds=int((utc(m["start"])-s).total_seconds())
        de=int((utc(m["end"])-e).total_seconds())
        assert 0<=ds<=59 and 0<=de<=59
        assert row["temporal_comparison"]["signed_start_delta_seconds"]==ds
        assert row["temporal_comparison"]["signed_end_delta_seconds"]==de
        assert row["temporal_comparison"]["duration_delta_seconds"]==de-ds
        assert row["disposition"]=="PLAUSIBLE_UNPROVEN"
        assert row["safe_for_automatic_remapping"] is False
        assert row["geographic_semantics"]["city_oblast_or_raion_conflict"] is False
        # Negative controls: time order and geography changes must not preserve original ID.
        assert eid("kyiv",end,start)!=oid
        assert eid("kyiv_oblast",start,end)!=oid
        assert eid("kyiv",c["utc_start"],c["utc_end"])!=oid
    assert len(found)==185
    print("PASS: 185/185 original records, unique modern one-to-one minute candidates, no split/merge, 7 independent producer gaps; 0 equivalence promotions. WIP NO-GO.")
if __name__=="__main__":
    if len(sys.argv)!=5:
        raise SystemExit(__doc__)
    run(*(load(p) for p in sys.argv[1:]))
