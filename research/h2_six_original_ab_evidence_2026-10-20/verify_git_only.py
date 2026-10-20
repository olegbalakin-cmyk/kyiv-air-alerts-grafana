#!/usr/bin/env python3
"""Read-only Git-only original ZIP/JSON verification. No network or DB calls."""
import copy,hashlib,io,json,subprocess,sys,zipfile
from pathlib import Path
P=Path(__file__).resolve().parent
ROOT=P.parents[1]
PINNED_MANIFEST_GIT_BLOB="6a2a06d3bdaadb99eaf8e7f02e22a00ffeb18dac"
# Independent pins: suite/copy -> run, job, artifact, tested SHA, zip SHA, JSON SHA, verdict
PINS={
"H11/A":(39473109411,118802020276,12288715326,"d649595bc9ae113f75471085e6833f68a859dee4","347ca94f389b044a489b60ba3befd8c8060d6b99146b7e26108c494376b74580","76b8e05b865154fb1228a1617b5b113e8a8ff92497a9b4fd9b2b96b1ea877fb8","PASS_BOUNDED_SNAPSHOT"),
"H11/B":(39473109411,118802020005,12288935012,"d649595bc9ae113f75471085e6833f68a859dee4","bcaebe679fb8c297a0e915fd5b307e05ec71a2f9c263965bdfdcecba7bea29c4","266baa394a5db83112ce92de98ce17f39aea268208035745e62834fd0b73a2d4","PASS_BOUNDED_SNAPSHOT"),
"R09/A":(39472805865,118800960144,12288440536,"3a8dbc5ed5bf6484706ba1cfaf281883e1a4cf0d","6dbf790ab4fcca1c6270f851377c91d73454baa872a35eeb5a421f53fe5b3795","4eed71dbe5650dd88900c11d2c640ed7c0153d7925a8836e3690552837e7e082","PASS_BOUNDED_PRECHECK"),
"R09/B":(39472805865,118800960444,12287314240,"3a8dbc5ed5bf6484706ba1cfaf281883e1a4cf0d","17f2d39d1fa6672368b018335f5c437365be3182717e37404144bac2fb3fd5ca","efe4c70fd5f2aadc6fd20a39c970a943a75a6eef0d3b6c2a7cb885b1c780ae1e","PASS_BOUNDED_PRECHECK"),
"ACL/A":(39473170811,118802223389,12288660574,"8edca3570d2472b1d9c63a82956a8c02e322581a","1e25b9b4f1fb22a7602739362b439231cecdb1d3d0a366009ce72f0b7cc739f7","c010291bc6da8f0158f0927af3e23a9aa5a32e5d230bf1bd4d73eeaa300eb5c4","PARTIAL"),
"ACL/B":(39473170811,118802223072,12288755142,"8edca3570d2472b1d9c63a82956a8c02e322581a","a7da3ce9002803a8b239a3f36763454093aa7da793ba60b9465149f143413838","61d66a50c4f31b639241967db0d60da5e50bce4ed2d6b023a5d53d35a4ca119a","PARTIAL")}
IDS={"H11":["empty","root","chain","three","independent","stale_tip","missing_head","wrong_identity","repeated","orphan_head","lock_barrier"],"R09":["safe","inherit_owner","set_only_owner","direct_history_grant","guard_membership","schema_create","indirect_owner"],"ACL":["pg_dump_repeat_normalization","raw_catalog_residual_identified","history_stable","pg_dump_actual","future_grant_revoke_1","future_grant_revoke_2","future_grant_revoke_3","future_grant_revoke_4","late_three_changes_transaction_abort"]}
class Reject(Exception):pass
def demand(ok,label):
 if not ok:raise Reject(label)
def sha(b):return hashlib.sha256(b).hexdigest()
def git(*args):
 p=subprocess.run(["git","-C",str(ROOT),*args],capture_output=True,text=True)
 demand(p.returncode==0,"GIT_COMMAND_FAIL "+p.stderr);return p.stdout.strip()
def check(m,mutzip=None,inner=False,source=True):
 demand(m.get("version")==1 and m.get("repository")=="olegbalakin-cmyk/kyiv-air-alerts-grafana","MANIFEST_META")
 demand(m.get("accepted_prior_checkpoint")=="032400cb7cb7fed2c24ed1f003e997247118475c","PRIOR")
 demand(len(m["entries"])==6,"ENTRY_COUNT")
 seen=set()
 for e in m["entries"]:
  suite,copy=e["suite"],e["copy"]; key=suite+"/"+copy
  demand(key in PINS and key not in seen,"PAIR");seen.add(key)
  run,job,artifact,tested,ziphash,jsonhash,verdict=PINS[key]
  data={"run_id":run,"job_id":job,"artifact_id":artifact,"tested_commit":tested,"zip_sha256":ziphash,"json_sha256":jsonhash,"verdict":verdict,"environment":"H2_COPY="+copy,"artifact_name":"h2-"+suite.lower()+"-v2-"+copy,"zip_file":suite.lower()+"_"+copy+".zip","json_member":"h2_"+suite.lower()+"_"+copy+".json","case_count":len(IDS[suite])}
  for k,v in data.items():demand(e.get(k)==v,"PIN_"+k+"_"+key)
  b=mutzip if mutzip is not None and key=="H11/A" else (P/e["zip_file"]).read_bytes()
  if not inner:demand(sha(b)==ziphash and len(b)==e["zip_size"],"ZIP_DIGEST_"+key)
  try:
   with zipfile.ZipFile(io.BytesIO(b)) as z:
    infos=z.infolist();demand(len(infos)==1 and infos[0].filename==e["json_member"],"MEMBER_"+key)
    demand(z.testzip() is None,"ZIP_CRC_"+key)
    if not inner:demand(f"{infos[0].CRC:08x}"==e["crc32"],"CRC_MANIFEST_"+key)
    payload=z.read(e["json_member"])
  except (zipfile.BadZipFile,OSError,EOFError) as x:raise Reject("BAD_ZIP_"+key) from x
  demand(sha(payload)==jsonhash and len(payload)==e["json_size"],"JSON_DIGEST_"+key)
  j=json.loads(payload)
  demand(j["copy"]==copy and j["commit"]==tested and j["verdict"]==verdict,"JSON_PROVENANCE_"+key)
  demand([x["id"] for x in j["cases"]]==IDS[suite] and all(x["status"]=="PASS" for x in j["cases"]),"JSON_CASES_"+key)
  if suite=="H11":
   demand(all(sorted(x["expected"])==sorted(x["actual"]) and x["history_before"]==x["history_after"] for x in j["cases"][:-1]),"H11_CASES")
   demand(j["cases"][-1]["actual_sqlstate"]=="55P03" and j["cases"][-1]["history_unchanged"],"H11_LOCK")
  if suite=="R09":
   demand(all(x["actual_unsafe"]==x["expected_unsafe"] and x["preflight_sqlstate"]==("42501" if x["expected_unsafe"] else "00000") and x["unchanged_schema"] for x in j["cases"]),"R09_CASES")
  if suite=="ACL":
   d=j["pg_dump_comparison"]
   demand(d["normalized_equal"] and len({d["original_normalized"],d["rolled_normalized"],d["original_repeat_normalized"]})==1,"ACL_NORMALIZATION")
   demand(j["cases"][-1]["details"]["sqlstate"]=="23514" and j["cases"][-1]["details"]["before_equal_after"],"ACL_ROLLBACK")
  if source:
   for path,blob in e["source_blobs"].items():
    demand(git("rev-parse",tested+":"+path)==blob,"TESTED_BLOB_"+key)
    demand(git("rev-parse","HEAD:"+path)==blob,"FINAL_BLOB_"+key)
  print("PASS",key,e["artifact_id"],e["verdict"])
 demand(seen==set(PINS),"ALL_PAIRS")
def negatives(m):
 tests=[]
 def edit(field,val):
  c=copy.deepcopy(m);c["entries"][0][field]=val;return c
 for n,field,value in [("wrong_job","job_id",118802020005),("swapped_A_B","environment","H2_COPY=B"),("wrong_artifact","artifact_id",12288715327),("wrong_tested_commit","tested_commit","0"*40),("incorrect_verdict","verdict","PASS"),("corrupted_manifest","version",99)]:
  tests.append((n,({**m,"version":99} if n=="corrupted_manifest" else edit(field,value)),None,False))
 b=(P/"h11_A.zip").read_bytes()
 z=bytearray(b);z[30]^=1;tests.append(("modified_zip",m,bytes(z),False))
 with zipfile.ZipFile(io.BytesIO(b)) as f:name=f.namelist()[0];payload=f.read(name)
 demand(b'"status": "PASS"' in payload,"SETUP_JSON")
 changed=payload.replace(b'"status": "PASS"',b'"status": "FAIL"',1)
 out=io.BytesIO()
 with zipfile.ZipFile(out,"w",compression=zipfile.ZIP_DEFLATED) as f:f.writestr(name,changed)
 tests.append(("modified_JSON",m,out.getvalue(),True))
 for name,obj,data,inner in tests:
  try:check(obj,data,inner,source=False)
  except (Reject,ValueError,KeyError):print("NEGATIVE_REJECTED",name)
  else:raise Reject("NEGATIVE_FALSE_PASS_"+name)
 print("PASS NEGATIVES 8/8")
def main():
 demand(git("hash-object",str(P/"manifest.json"))==PINNED_MANIFEST_GIT_BLOB,"MANIFEST_BLOB_PIN")
 raw_manifest=(P/"manifest.json").read_bytes()
 print("MANIFEST_SHA256",sha(raw_manifest),"MANIFEST_GIT_BLOB",PINNED_MANIFEST_GIT_BLOB)
 manifest=json.loads(raw_manifest)
 check(manifest)
 negatives(manifest)
 print("PASS GIT_ONLY 6/6 ZIP JSON SOURCE AND 8/8 NEGATIVE CONTROLS")
if __name__=="__main__":
 try:main()
 except (Reject,KeyError,ValueError,AssertionError) as x:print("BLOCKED",x,file=sys.stderr);sys.exit(1)
