#!/usr/bin/env python3
"""Independent Git-only verifier for ORIGINAL H2 migration A/B Actions artifacts.

No network, credentials, PostgreSQL, or production state is accessed.
B64 text files contain the exact downloaded GitHub Actions envelope ZIP bytes,
not a locally reconstructed archive. JSON files contain exact original members.
"""
import base64
import copy
import hashlib
import io
import json
import pathlib
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent
OUT = ROOT / "original_artifacts"
SCHEMA = "h2-original-migration-ab-evidence-v1"
KNOWN = {
    "success_A": dict(run_id=39332325216, job_id=118333286878,
        artifact_id=12225295967, artifact_name="h2-pg18-migration-A",
        head_sha="6e53ae59115199499910a29916ebd0c501c60ff1",
        zip_sha256="a989a88ef545777264a71165bb10434047f8123e9d2b56e24313fa1802a6d1e6",
        copy="A", verdict="PASS", total=37, passed=37),
    "success_B": dict(run_id=39332325216, job_id=118333286498,
        artifact_id=12224907771, artifact_name="h2-pg18-migration-B",
        head_sha="6e53ae59115199499910a29916ebd0c501c60ff1",
        zip_sha256="31f591f34eaab758611d4b6e17d9356a08cb096fd46b77a10088b6197015c672",
        copy="B", verdict="PASS", total=37, passed=37),
    "failure_A": dict(run_id=39332206445, job_id=118332894278,
        artifact_id=12225136563, artifact_name="h2-pg18-migration-A",
        head_sha="4ae83d14cae6a33956f991cb5af68e81576c7697",
        zip_sha256="b7bbe81c7f84d75d2831febfdf25f118955f58fa3e37285b14f2eb9d5d4248a7",
        copy="A", verdict="FAIL", total=30, passed=30),
    "failure_B": dict(run_id=39332206445, job_id=118332894783,
        artifact_id=12224254157, artifact_name="h2-pg18-migration-B",
        head_sha="4ae83d14cae6a33956f991cb5af68e81576c7697",
        zip_sha256="87015f8688b380357536fdf5b0d619f40b6120df5d14519ede8c03849b8d2fc5",
        copy="B", verdict="FAIL", total=30, passed=30),
}

def digest(data):
    return hashlib.sha256(data).hexdigest()

def read_bytes(path, overrides=None):
    if overrides and str(path) in overrides:
        return overrides[str(path)]
    return (OUT / path).read_bytes()

def verify(manifest, overrides=None):
    assert manifest["schema"] == SCHEMA, "manifest schema"
    assert set(manifest["records"]) == set(KNOWN), "artifact enumeration"
    for ident, trusted in KNOWN.items():
        rec = manifest["records"][ident]
        for prop, value in trusted.items():
            assert rec[prop] == value, ident + ": trusted metadata " + prop
        zp = rec["zip_b64_path"]
        jp = rec["json_path"]
        assert zp == ident + ".github_original_zip.b64", "zip identity"
        assert jp == ident + ".original.json", "json identity"
        encoded = read_bytes(zp, overrides)
        original_zip = base64.b64decode(encoded.strip(), validate=True)
        original_json = read_bytes(jp, overrides)
        assert digest(original_zip) == trusted["zip_sha256"], ident + ": pinned original ZIP"
        assert digest(original_zip) == rec["zip_sha256"], ident + ": manifest ZIP hash"
        assert len(original_zip) == rec["zip_length"], ident + ": ZIP size"
        assert digest(original_json) == rec["json_sha256"], ident + ": JSON SHA"
        assert len(original_json) == rec["json_length"], ident + ": JSON size"
        with zipfile.ZipFile(io.BytesIO(original_zip)) as archive:
            assert archive.testzip() is None, ident + ": ZIP CRC"
            names = archive.namelist()
            assert len(names) == 1, ident + ": unexpected ZIP contents"
            assert names[0] == rec["member"], ident + ": member name"
            assert names[0].endswith("h2_migration_" + trusted["copy"] + ".json"), ident + ": swapped member"
            assert archive.read(names[0]) == original_json, ident + ": original member bytes"
        obj = json.loads(original_json)
        for prop in ("copy", "verdict", "total", "passed"):
            assert obj[prop] == trusted[prop], ident + ": original JSON " + prop
        assert obj["git_commit"] == trusted["head_sha"], ident + ": tested commit"
        assert len(obj["checks"]) == trusted["total"], ident + ": check list count"
        assert sum(bool(ch["pass"]) for ch in obj["checks"]) == trusted["passed"], ident + ": pass count"
        assert obj["cases"], ident + ": cases absent"
        assert obj["source_sha256"], ident + ": source provenance absent"
        if trusted["verdict"] == "PASS":
            assert not obj["errors"] and all(c["status"] == "PASS" for c in obj["cases"]), ident + ": unexpected success errors"
        else:
            assert obj["errors"] and any(c["status"] == "FAIL" for c in obj["cases"]), ident + ": missing failure"
            errs = json.dumps(obj["errors"]).lower()
            assert "permission denied" in errs and "h2_classification_heads" in errs, ident + ": wrong failure"
    return True

def negative_controls(manifest):
    checks = []
    def reject(name, altered, overrides=None):
        try:
            verify(altered, overrides)
        except (AssertionError, ValueError, KeyError, OSError, zipfile.BadZipFile):
            checks.append(name)
        else:
            raise AssertionError("NEGATIVE CONTROL FAILED: " + name)
    for name, change in (
        ("manifest_job_swapped", lambda m: m["records"]["success_A"].update(job_id=KNOWN["success_B"]["job_id"])),
        ("manifest_artifact_swapped", lambda m: m["records"]["success_B"].update(artifact_id=KNOWN["success_A"]["artifact_id"])),
        ("manifest_zip_hash_altered", lambda m: m["records"]["success_A"].update(zip_sha256="0"*64)),
        ("manifest_json_hash_altered", lambda m: m["records"]["success_A"].update(json_sha256="0"*64)),
        ("manifest_count_altered", lambda m: m["records"]["success_A"].update(total=38)),
        ("manifest_verdict_altered", lambda m: m["records"]["failure_A"].update(verdict="PASS")),
    ):
        m=copy.deepcopy(manifest)
        change(m)
        reject(name, m)
    a=manifest["records"]["success_A"]
    b=manifest["records"]["success_B"]
    ap, bp=a["zip_b64_path"],b["zip_b64_path"]
    reject("swapped_A_B_zip_bytes", manifest, {ap:read_bytes(bp),bp:read_bytes(ap)})
    reject("original_zip_corrupted", manifest, {ap:b"@@not-base64@@"})
    reject("original_json_corrupted", manifest, {a["json_path"]:read_bytes(a["json_path"])+b" "})
    raw=read_bytes(a["json_path"])
    for label, key, new_value in [("json_verdict_forged","verdict","FAIL"),("json_test_count_forged","total",38)]:
        mutated=json.loads(raw); mutated[key]=new_value
        reject(label,manifest,{a["json_path"]:json.dumps(mutated).encode()})
    return checks

if __name__ == "__main__":
    m=json.loads((OUT/"manifest.json").read_bytes())
    assert verify(m)
    controls=negative_controls(m)
    assert len(controls)==11, controls
    print(json.dumps({"gate":"H2_ORIGINAL_MIGRATION_AB_EVIDENCE_FREEZE",
         "verdict":"PASS","original_artifacts":len(KNOWN),
         "original_zip_crc_pass":len(KNOWN),
         "negative_controls_rejected":len(controls),"corruptions":controls},sort_keys=True))
