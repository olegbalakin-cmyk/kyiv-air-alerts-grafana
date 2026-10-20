#!/usr/bin/env python3
"""Independent Git-only evidence verifier, including deliberate corruption controls."""
import base64,hashlib,io,json,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent/"new_original_artifacts"
def sha(v):return hashlib.sha256(v).hexdigest()
def verify(copy,spec,mut_zip=None,mut_sha=None):
 raw=base64.b64decode((ROOT/spec["zip_b64_file"]).read_bytes(),validate=False) if mut_zip is None else mut_zip
 assert len(raw)==spec["zip_bytes"] and sha(raw)==(mut_sha or spec["zip_sha256"])
 with zipfile.ZipFile(io.BytesIO(raw)) as z:
  assert z.testzip() is None
  assert set(z.namelist())==set(x["member"] for x in spec["reports"].values())
  for typ,data in spec["reports"].items():
   original=(ROOT/data["file"]).read_bytes()
   assert len(original)==data["bytes"] and sha(original)==data["sha256"]
   assert original==z.read(data["member"])
   obj=json.loads(original)
   assert obj["copy"]==copy and obj["verdict"]==data["verdict"]
   assert obj["total"]==obj["passed"]==data["total"]
   assert not obj["errors"]
   if typ=="rollback":assert obj["acl_physical_residual"]==["relations"]
 return True
def main():
 m=json.loads((ROOT/"manifest.json").read_bytes())
 assert m["source_run"]==39403057471
 assert m["tested_commit"]=="1a1a63e61eef1e43bb7eefbb5a736bf920e56071"
 assert set(m["records"])=={"A","B"}
 controls=0
 for copy,spec in m["records"].items():
  assert verify(copy,spec)
  raw=base64.b64decode((ROOT/spec["zip_b64_file"]).read_bytes())
  for mutation,digest in [(raw[:-1]+bytes([raw[-1]^1]),None),(raw,"0"*64)]:
   try:verify(copy,spec,mutation,digest)
   except (AssertionError,zipfile.BadZipFile,ValueError):controls+=1
   else:raise AssertionError("ZIP corruption unobserved")
  typ="cas"
  d=spec["reports"][typ]
  old=(ROOT/d["file"]).read_bytes()
  try:
   (ROOT/d["file"]).write_bytes(old+b"x")
   try:verify(copy,spec)
   except (AssertionError,zipfile.BadZipFile,ValueError):controls+=1
   else:raise AssertionError("JSON corruption unobserved")
  finally:(ROOT/d["file"]).write_bytes(old)
  try:verify(copy,spec,raw,"f"*64)
  except (AssertionError,zipfile.BadZipFile,ValueError):controls+=1
  else:raise AssertionError("digest corruption unobserved")
 assert controls==8
 print(json.dumps({"verdict":"PASS","original_zips":2,"original_json_reports":4,
   "deliberate_corruptions_rejected":controls,"tested_commit":m["tested_commit"]},sort_keys=True))
if __name__=="__main__":main()
