#!/usr/bin/env python3
"""Verify original unmodified GitHub Actions v3 A/B ZIPs, with corruption controls."""
from pathlib import Path
import hashlib, io, json, zipfile
ROOT=Path(__file__).resolve().parent
manifest=json.loads((ROOT/"manifest.json").read_bytes())
def sha(data): return hashlib.sha256(data).hexdigest()
def verify(label, data, spec):
    assert len(data)==spec["zip_size"] and sha(data)==spec["zip_sha256"], "ZIP fingerprint"
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        assert z.testzip() is None, "CRC"
        assert z.namelist()==[spec["member"]], "member identity"
        raw=z.read(spec["member"])
    assert len(raw)==spec["member_size"] and sha(raw)==spec["member_sha256"], "JSON fingerprint"
    report=json.loads(raw)
    assert report["copy"]==label and report["commit"]==manifest["source"]["tested_commit"], "attribution"
    assert report["verdict"]==spec["verdict"] and report["total"]==spec["assertions"] and report["passed"]==spec["assertions"], "verdict"
    assert len(report["checks"])==spec["assertions"] and all(c["pass"] for c in report["checks"]) and not report["errors"], "actual checks"
    return True
def main():
    rejected=0
    for label,spec in manifest["artifacts"].items():
        original=(ROOT/spec["zip_file"]).read_bytes()
        assert verify(label,original,spec)
        for variation, mutated, changed in [
            ("zip_byte", original[:-1]+bytes([original[-1]^1]), spec),
            ("digest", original, {**spec,"zip_sha256":"0"*64}),
            ("member_digest", original, {**spec,"member_sha256":"0"*64}),
            ("copy_attribution", original, {**spec,"member": "WRONG.json"})
        ]:
            try: verify(label,mutated,changed)
            except (AssertionError,ValueError,zipfile.BadZipFile,KeyError): rejected+=1
            else: raise AssertionError("corruption escaped: "+variation)
    assert rejected==8
    print(json.dumps({"verdict":"PASS","original_zip_members":2,"corruptions_rejected":rejected},sort_keys=True))
if __name__=="__main__":main()
