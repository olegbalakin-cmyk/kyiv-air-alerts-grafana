#!/usr/bin/env python3
"""Run accepted adapter functions, UNMODIFIED, at the shadow-01 pinned cutoff.

The ZIP hash, manifest and CRC are checked by the workflow before extraction.
Adapter's default CLI reads dashboard meta.generated_at (05:45 UTC), whereas
the accepted integrated shadow pins 06:11 UTC. This wrapper injects that cutoff
into its physical guarded read while retaining production generator's original
now timestamp for published period semantics.
"""
import hashlib
import json
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path

PINNED_CUTOFF="2026-10-30T06:11:07.648388+00:00"
ROOT=Path("/tmp/c6-22city-approved/C6-22CITY-READER-01")
SITE=Path.cwd()/"pinned-site/kyiv-air-alerts-grafana"
OUT=Path("c6_23city_integrated_shadow02_proof/accepted-22city")
EXPECTED="f6dda060a0ed48b01b4726625b36c33b472955f687be6877aef918fc3c8bddf2"

def save(name,obj):
    (OUT/name).write_text(json.dumps(obj,indent=2,ensure_ascii=False,default=str)+"\n",encoding="utf-8")

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    if (OUT/"approved_adapter_archive.sha256").read_text().strip()!=EXPECTED:
        raise RuntimeError("APPROVED_SOURCE_SHA_MISMATCH")
    sys.path.insert(0,str(ROOT))
    import adapter
    from derived import create_derived,diff_derived
    receipt=adapter.verify_reference(SITE)
    baseline=adapter.load_json(SITE/"data/dashboard_data.json")
    now=adapter.aware(baseline["meta"]["generated_at"])
    cutoff=datetime.fromisoformat(PINNED_CUTOFF)
    dsn=os.environ.get("C6_B1_READONLY_DATABASE_URL","")
    rows, db=adapter.read_physical_neon(dsn,cutoff)
    os.environ.pop("C6_B1_READONLY_DATABASE_URL",None)
    receipt["database"]=db
    receipt["physical_origin"]="ACTUAL_NEON_PSYCOG_READONLY"
    assert db["asof_utc"]==cutoff.isoformat()
    assert db["row_count"]==28951, "ASOF_EPISODE_UNIVERSE_CHANGED"
    projection,diagnostics,alerts22=adapter.build_projection_from_site(rows,baseline,now,SITE)
    save("22city_neon_projection.json",projection)
    save("UTC_union_diagnostics.json",diagnostics)
    m=adapter.diff_rows(baseline,projection,max_details=1000)
    save("machine_diff.json",m)
    prior_derived=adapter.load_json(SITE/"data/site_derived.json")
    modules=adapter.import_site_modules(SITE)
    derived_projection=create_derived(projection,prior_derived,alerts22,now,SITE,modules)
    save("site_derived_22city_projection.json",derived_projection)
    d=diff_derived(prior_derived,derived_projection)
    save("machine_derived_diff.json",d)
    save("machine_verdict.json",{
        "verdict":"PARTIAL","metrics_diff":m["verdict"],
        "blocking_differences":m["total_diff_items"],
        "source_to_physical_uid_provenance":"NOT_PROVEN",
        "derived_explorations_full_comparison":d["verdict"],
        "neon_authority":False,"production_reader_switch":False,
        "approved_adapter_sha256":EXPECTED,
        "exact_accepted_functions":["verify_reference","read_physical_neon",
          "build_projection_from_site","diff_rows","create_derived","diff_derived"],
        "why_wrapper":"original CLI uses dashboard meta.generated_at, whereas accepted 23-city snapshot cutoff is 06:11 UTC",
        "production_period_now":now.isoformat(),
        "receipt":receipt
    })
    print("APPROVED_ADAPTER_FUNCTIONS_EXECUTED",db["row_count"],
          "snapshot",db["snapshot"],"diff",m["total_diff_items"],
          "derived",d["total_diff_sections"],flush=True)
    return 0

if __name__=="__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        OUT.mkdir(parents=True,exist_ok=True)
        save("wrapper_failure.json",{"status":"BLOCKED","error":type(exc).__name__,
                                      "message":str(exc)[:240]})
        traceback.print_exc()
        sys.exit(3)
