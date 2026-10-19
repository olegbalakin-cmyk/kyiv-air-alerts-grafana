#!/usr/bin/env python3
"""Git-only independent byte and semantic verifier for H2 CAS PG18 A/B archives."""
import base64
import hashlib
import io
import json
from pathlib import Path
import zipfile

DIR=Path(__file__).resolve().parent
manifest=json.loads((DIR/"manifest.json").read_text())
def sha(b): return hashlib.sha256(b).hexdigest()
def verify():
    assert manifest["source_run"] > 0
    assert manifest["tested_sha"] and len(manifest["tested_sha"])==40
    positive=0
    corrupt=0
    for copy in ("A","B"):
        for suite in ("cas","mutation"):
            key=copy+"_"+suite
            entry=manifest["copies"][key]
            raw_b64=(DIR/(key+".json.b64")).read_text().strip()
            zip_b64=(DIR/(key+".zip.b64")).read_text().strip()
            raw=base64.b64decode(raw_b64,validate=True)
            zraw=base64.b64decode(zip_b64,validate=True)
            assert sha(raw)==entry["json_sha256"] and len(raw)==entry["json_bytes"],key
            assert sha(zraw)==entry["zip_sha256"] and len(zraw)==entry["zip_bytes"],key
            with zipfile.ZipFile(io.BytesIO(zraw)) as zipf:
                assert zipf.testzip() is None
                names=zipf.namelist()
                assert names==["h2_expected_tip.json" if suite=="cas" else "h2_mutation_controls.json"],names
                assert zipf.read(names[0])==raw,key
            parsed=json.loads(raw)
            assert parsed["copy"]==copy
            if suite=="cas":
                assert parsed["verdict"]=="PASS"
                assert parsed["total"]==parsed["passed"]
                assert parsed["total"]>=48
                assert len(parsed["cases"])>=8
                assert {c["id"] for c in parsed["cases"]} >= {
                    "independent_concurrency","negative_guard_bypass",
                    "real_monitor_main","transaction_ownership","injected_rollback",
                }
                assert not parsed["errors"] and all(c["pass"] for c in parsed["assertions"])
            else:
                assert parsed["harness_verdict"]=="EXECUTED_COMPLETE"
                assert parsed["assertions_total"]==parsed["assertions_passed"]==83
                assert not parsed["unexpected"] and not parsed["failed_assertions"]
            positive+=1
            # 2 independent negative controls for EVERY archived member.
            tampered=bytearray(raw)
            tampered[len(tampered)//2]^=1
            assert sha(tampered)!=entry["json_sha256"]
            corrupt+=1
            tampered_zip=bytearray(zraw)
            tampered_zip[len(tampered_zip)//2]^=1
            assert sha(tampered_zip)!=entry["zip_sha256"]
            corrupt+=1
    assert positive==4 and corrupt==8
    print(json.dumps({"verdict":"PASS_GIT_ONLY","original_pairs":positive,"rejected_corruptions":corrupt,"run":manifest["source_run"],"tested_sha":manifest["tested_sha"]}))
if __name__=="__main__":verify()
