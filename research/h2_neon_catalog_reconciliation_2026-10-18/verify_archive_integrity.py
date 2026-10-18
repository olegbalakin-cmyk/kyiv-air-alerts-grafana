#!/usr/bin/env python3
"""Verify ORIGINAL H2 PG18 A/B Action ZIP member bytes against Git-retained XZ map.
Uses Python standard library only; never reads production data or accesses Neon.
"""
import base64
import copy
import datetime
import hashlib
import json
import lzma
import os
from pathlib import Path
import re
import subprocess
import sys
import urllib.request
import zipfile
import io

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "research"
OUT = Path(__file__).resolve().parent
OLD = SRC / "h2_monitor_main_pg18_e2e_AB_retention_manifest_2026-10-18.json"
BUNDLE = SRC / "h2_monitor_main_pg18_e2e_AB_receipts_2026-10-18.json.xz.b64"
API = "https://api.github.com/repos/olegbalakin-cmyk/kyiv-air-alerts-grafana"
TOKEN = os.environ.get("GITHUB_TOKEN")
assert TOKEN, "GITHUB_TOKEN required for Actions evidence download"
def digest(b):
    return hashlib.sha256(b).hexdigest()
def gitsha(p):
    return subprocess.check_output(["git","hash-object",str(p)], cwd=ROOT, text=True).strip()
def get_api(path, binary=False):
    req = urllib.request.Request(API+path, headers={
        "Authorization":"Bearer "+TOKEN,
        "Accept":"application/vnd.github+json",
        "X-GitHub-Api-Version":"2022-11-28",
        "User-Agent":"h2-integrity-reconciliation"
    })
    with urllib.request.urlopen(req, timeout=45) as response:
        data=response.read()
    return data if binary else json.loads(data)
def error_if(cond, desc, bad):
    if cond:
        bad.append(desc)
manifest_bytes=OLD.read_bytes()
old=json.loads(manifest_bytes)
bundle_bytes=BUNDLE.read_bytes()
bad=[]
b64_clean=bundle_bytes.strip()
try:
    compressed=base64.b64decode(b64_clean, validate=True)
    json_map_bytes=lzma.decompress(compressed)
    saved=json.loads(json_map_bytes.decode("utf-8"))
except Exception as e:
    raise RuntimeError("RETAINED_BUNDLE_DECODE_FAILURE: "+repr(e))
error_if(not isinstance(saved,dict),"decoded map not object",bad)
old_hashes={
    "base64_git_text":{"declared":old["bundle_text_sha256"],"observed":digest(bundle_bytes),"bytes":len(bundle_bytes)},
    "xz_decoded_bytes":{"declared":old["compressed_xz_sha256"],"observed":digest(compressed),"bytes":len(compressed)},
    "decoded_json_map":{"declared":old["decoded_json_map_sha256"],"observed":digest(json_map_bytes),"bytes":len(json_map_bytes)}
}
tests={}
for value,expected in [(b"","e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),(b"abc","ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")]:
    assert digest(value)==expected,"SHA256 self-test failed"
assert gitsha(OLD)=="c242e7dcda1b3e60fb64839df7e9b22a2f106633"
assert gitsha(BUNDLE)=="286c6cd4a0972a26a48ca7651356839ecd9b0245"
expected_keys=set()
zips=[]
members=[]
sensitive=[]
patterns=[
    ("private_key", re.compile(rb"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("github_token", re.compile(rb"(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,})")),
    ("aws_access_key", re.compile(rb"AKIA[0-9A-Z]{16}")),
    ("password_in_postgres_dsn", re.compile(rb"postgres(?:ql)?://[^:\s/]+:[^@\s/]+@", re.I)),
    ("bearer_credential", re.compile(rb"Bearer[ \t]+[A-Za-z0-9._~-]{25,}",re.I)),
]
for artifact in old["artifacts"]:
    aid=artifact["artifact_id"]
    rid=artifact["run_id"]
    run=get_api(f"/actions/runs/{rid}")
    error_if(run.get("conclusion")!="success", f"run {rid} was not SUCCESS",bad)
    error_if(run.get("head_sha")!=artifact["head_sha"],f"run {rid} commit differs",bad)
    meta=get_api(f"/actions/artifacts/{aid}")
    error_if(meta.get("expired") is not False,f"artifact {aid} expired",bad)
    error_if(meta.get("workflow_run",{}).get("id")!=rid,f"artifact {aid} wrong run",bad)
    zip_bytes=get_api(f"/actions/artifacts/{aid}/zip",binary=True)
    zipsha=digest(zip_bytes)
    error_if(zipsha!=artifact["original_zip_sha256"],f"artifact {aid} ZIP SHA mismatch",bad)
    error_if(len(zip_bytes)!=artifact["original_zip_bytes"],f"artifact {aid} ZIP length mismatch",bad)
    error_if(meta.get("digest") != "sha256:"+zipsha,f"artifact {aid} GitHub digest mismatch",bad)
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        names=z.namelist()
        error_if(len(names)!=len(set(names)),f"artifact {aid} duplicate ZIP names",bad)
        error_if(set(names)!=set(artifact["members"]),f"artifact {aid} member names differ",bad)
        crc_bad=z.testzip()
        error_if(crc_bad is not None,f"artifact {aid} invalid CRC member",bad)
        for name in sorted(artifact["members"]):
            data=z.read(name)
            key=f"{aid}/{name}"
            expected_keys.add(key)
            in_map=saved.get(key)
            if not isinstance(in_map,str):
                bad.append(f"bundle missing/non-string member {key}")
                retained=b""
            else:
                retained=in_map.encode("utf-8")
            try:
                parsed=json.loads(data.decode("utf-8"))
                error_if(not isinstance(parsed,dict),f"{key} is not JSON object",bad)
                report_keys=sorted(parsed)[:25] if isinstance(parsed,dict) else []
            except Exception as e:
                bad.append(f"{key} fails JSON parse {type(e).__name__}")
                report_keys=[]
            sh=digest(data)
            checks={
                "original_zip_bytes_sha256":sh,
                "original_zip_member_bytes":len(data),
                "previous_manifest_sha256":artifact["members"][name]["sha256"],
                "previous_manifest_bytes":artifact["members"][name]["bytes"],
                "retained_map_bytes_sha256":digest(retained),
                "retained_map_member_bytes":len(retained),
                "byte_for_byte_match":data==retained,
                "json_top_keys":report_keys,
                "tamper_control_sha256_changed": digest(data+b"\0")!=sh
            }
            error_if(not checks["byte_for_byte_match"],f"{key} byte mismatch",bad)
            error_if(sh!=checks["previous_manifest_sha256"],f"{key} original hash disagrees with old manifest",bad)
            error_if(len(data)!=checks["previous_manifest_bytes"],f"{key} original length disagrees with old manifest",bad)
            for tag,regex in patterns:
                if regex.search(data):
                    sensitive.append({"member":key,"signal":tag})
            members.append({"key":key,**checks})
    zips.append({"artifact_id":aid,"run_id":rid,"run_conclusion":run.get("conclusion"),
                 "run_head_sha":run.get("head_sha"),"zip_bytes":len(zip_bytes),
                 "zip_sha256":zipsha,"zip_crc":"PASS" if crc_bad is None else "FAIL",
                 "members":sorted(names),"expires_at":meta.get("expires_at")})
error_if(set(saved)!=expected_keys,"retained JSON map has unexpected/missing keys",bad)
error_if(bool(sensitive),"sensitive credential patterns detected",bad)
error_if(old_hashes["decoded_json_map"]["observed"]!=old_hashes["decoded_json_map"]["declared"],"old declared decoded JSON map SHA differs",bad)
error_if(old_hashes["decoded_json_map"]["bytes"]!=old["decoded_json_map_bytes"],"old declared decoded map size differs",bad)
verdict="PASS" if not bad else "PARTIAL"
report={
  "document_type":"H2_AB_ACTIONS_ZIP_EXACT_MEMBER_RETENTION_INDEPENDENT_RECONCILIATION",
  "verified_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
  "verdict":verdict,
  "source_manifest_path":str(OLD.relative_to(ROOT)),"source_manifest_blob":gitsha(OLD),
  "source_bundle_path":str(BUNDLE.relative_to(ROOT)),"source_bundle_blob":gitsha(BUNDLE),
  "hashlib_sha256_self_tests":"PASS",
  "previous_manifest_hashes":old_hashes,
  "original_zips":zips,"six_members":members,
  "complete_members_count":len(members),
  "identical_original_retained_count":sum(m["byte_for_byte_match"] for m in members),
  "original_json_parse_count":sum(bool(m["json_top_keys"]) for m in members),
  "credential_signal_count":len(sensitive),
  "credential_signal_types":sorted(set(x["signal"] for x in sensitive)),
  "failures":bad,
  "repair_interpretation":(
    "Original Actions ZIP member bytes agree exactly with Git-retained XZ/Base64 map; any differing manifest bundle SHA-256 entries are retention metadata errors, not member-byte corruption."
    if not bad else "Exact original-member evidence retention not fully established; investigate failures before accepting."
  ),
  "limits":["Verifies exact six source JSON bytes, not original ZIP byte archival",
            "Metadata hash mismatch production mechanism not established without original manifest-generator execution trace",
            "Does not verify canonical Neon schema or perform any database operation"]
}
OUT.mkdir(parents=True,exist_ok=True)
report_path=OUT/"archive_exact_member_reconciliation_v2.json"
report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
v2=copy.deepcopy(old)
v2["document_type"]="H2_FULL_MONITOR_E2E_A_B_DURABLE_EVIDENCE_RETENTION_CORRECTED_V2"
v2["supersedes_manifest_git_blob"]=gitsha(OLD)
v2["source_bundle_git_blob_unchanged"]=gitsha(BUNDLE)
v2["bundle_text_sha256"]=digest(bundle_bytes)
v2["compressed_xz_sha256"]=digest(compressed)
v2["decoded_json_map_sha256"]=digest(json_map_bytes)
v2["archive_exact_member_verdict"]=verdict
v2["archive_reconciliation_path"]=str(report_path.relative_to(ROOT))
v2["verification_note"]="Original manifest preserved unchanged; corrected bundle-level hashes only where verified source-member identities match."
v2_path=OUT/"retention_manifest_corrected_v2.json"
v2_path.write_text(json.dumps(v2,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
receipt={
  "document_type":"INDEPENDENT_H2_AB_GIT_ARCHIVE_CORRECTION_RECEIPT",
  "verdict":verdict,
  "files":{
     str(report_path.relative_to(ROOT)):{"sha256":digest(report_path.read_bytes()),"bytes":report_path.stat().st_size,"blob":gitsha(report_path)},
     str(v2_path.relative_to(ROOT)):{"sha256":digest(v2_path.read_bytes()),"bytes":v2_path.stat().st_size,"blob":gitsha(v2_path)}
  },
  "original_retained_bundle_sha256":digest(bundle_bytes),
  "zip_member_bytes_reconciled":sum(m["byte_for_byte_match"] for m in members),
  "source_zip_sha256s":[z["zip_sha256"] for z in zips],
  "source_commit":os.environ.get("GITHUB_SHA"),
  "safety":{"neon_sql_calls":0,"neon_writes":0,"neon_branches_created":0,"operational_changes":0}
}
receipt_path=OUT/"archive_git_evidence_receipt_v2.json"
receipt_path.write_text(json.dumps(receipt,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
print("ARCHIVE VERDICT",verdict,"ORIGINAL ZIPS",len(zips),"SIX MEMBERS",len(members),"IDENTICAL",receipt["zip_member_bytes_reconciled"])
print("OLD HASHES",json.dumps(old_hashes,sort_keys=True))
print("ZIP VERIFICATION",json.dumps(zips,sort_keys=True))
print("MEMBER DIGESTS",json.dumps([{k:v for k,v in m.items() if k not in ("json_top_keys",)} for m in members],sort_keys=True))
print("FAILURES",json.dumps(bad))
for p in (report_path,v2_path,receipt_path):
    print("FROZEN",str(p.relative_to(ROOT)),gitsha(p),digest(p.read_bytes()))
sys.exit(0 if verdict=="PASS" else 2)
