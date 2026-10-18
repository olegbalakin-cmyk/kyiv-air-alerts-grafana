#!/usr/bin/env python3
"""Validate durable H2 A/B recovery from Git checkout alone. No API/network."""
import argparse, base64, hashlib, json, lzma, pathlib, subprocess
def sha(b): return hashlib.sha256(b).hexdigest()
def main():
 p=argparse.ArgumentParser()
 p.add_argument("--manifest",default="research/h2_monitor_main_pg18_e2e_AB_retention_manifest_corrected_v2_2026-10-18.json")
 p.add_argument("--archive",default=None)
 a=p.parse_args();m=json.loads(pathlib.Path(a.manifest).read_bytes());path=pathlib.Path(a.archive or m["bundle_path"]);raw=path.read_bytes()
 assert len(raw)==m["bundle_text_bytes"] and sha(raw)==m["bundle_text_sha256"]
 git_blob=subprocess.check_output(["git","hash-object",str(path)],text=True).strip()
 assert git_blob==m["bundle_git_blob"]
 compressed=base64.b64decode(raw.strip(),validate=True)
 assert len(compressed)==m["xz_bytes"] and sha(compressed)==m["xz_sha256"]
 decoded=lzma.decompress(compressed)
 assert len(decoded)==m["map_bytes"] and sha(decoded)==m["map_sha256"]
 obj=json.loads(decoded);expected=set()
 for a in m["source_artifacts"]:
  for name,member in a["members"].items():
   key=f'{a["id"]}/{name}';expected.add(key);data=obj[key].encode("utf8")
   assert len(data)==member["bytes"] and sha(data)==member["sha256"]
   j=json.loads(data);assert isinstance(j,dict)
 assert set(obj)==expected and len(obj)==6
 print(json.dumps({"verdict":"PASS","members":6,"map_sha256":sha(decoded),"bundle_git_blob":git_blob},sort_keys=True))
if __name__=="__main__":main()
