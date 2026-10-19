#!/usr/bin/env python3
"""Offline-only byte exact H2 A/B report/ZIP and provenance verifier."""
import copy,hashlib,io,json
from pathlib import Path
from zipfile import ZipFile,BadZipFile
P=Path(__file__).resolve().parent
PIN={"A":{"job":118274404141,"artifact":12217413297,"zip":"e495895b0a37cf5638bdf40bbe770f40e946445928c435e07e739ec57d49bec2","json":"cabcf5a884c2f4be1ab95f1e47d5d8e4ba87a630d201e5046a53e746d5cdfef0","zipblob":"157cdbe84bdca238c3290d8fb49364fa04557892","jsonblob":"21674dbb7b8098e5f41f81279171cb210c3e7c13","crc":"e7b251ef","size":964},"B":{"job":118274403678,"artifact":12217258590,"zip":"bfb069ba3686b1aac9008b73b3270c551d0cd39191a64e6c05dcaaa476fe2b79","json":"77978f45f97c6e00e48386409b3e0ac33b0a8c1eebfc27d93cb0ce0e981e0a01","zipblob":"82f6037b8aade831527f1d389f52bc8e0253ab23","jsonblob":"89e5cd121e9a19e0ef82bf8c6c2864c364817de0","crc":"481e8a19","size":965}}
NAMES=["pg18","role_is_owner","no_duplicate_successors","root_index","head_registry","app_is_nonowner","no_role_inheritance","writer_can_read_classification","reject_historical_update","reject_historical_delete","reject_history_truncate","reject_table_alter","reject_privilege_grant","reject_head_update","reject_role_escalation","initial_insert","initial_root_duplicate_rejected","append_success","stale_tip_rejected","state_preserved_after_rejection","unaffected_independent_chain","cross_chain_parent_rejected","two_connection_duplicate_successor","concurrent_tip_consistent","exact_history_no_orphans","two_chains_unchanged","restart_idempotent_readback","full_transaction_rollback","retry_after_failure","persisted_tip_chain","negative_control_unprotected_owner_can_mutate"]
class Bad(Exception):pass
def check(ok,why):
 if not ok:raise Bad(why)
def sha(b):return hashlib.sha256(b).hexdigest()
def blob(b):return hashlib.sha1(b"blob "+str(len(b)).encode()+bytes([0])+b).hexdigest()
def verify(M,R,J,Z):
 check(M["schema_version"]=="h2.pg18.original.ab.v1","manifest version")
 check(M["origin"]=={"repository":"olegbalakin-cmyk/kyiv-air-alerts-grafana","workflow_run":39315105462,"workflow_id":389806057,"event":"push","tested_commit":"2e21903e3ad97e12fdfb7b6ade186c865778adc6","research_parent_commit":"c1c0b1efb17c17fd2ff22711dbc6b5e4aaa2b26a"},"origin")
 check(M["original_receipt_git_blob"]=="485aa5256a8768058930c03e55370eca84a4e3a0","original receipt provenance")
 check(M["owner_mutation_negative_control"]=="NOT_EXECUTED_HARDCODED_TRUE","owner negative-control disclaimer")
 check(M["matrix_unchanged"]=={"MATCH":203,"MISMATCH":3,"UNVERIFIED":7},"matrix")
 check(M["safety"]=={"NEON_AUTHORITY_ACTIVE":"NO","PRODUCTION_CUTOVER_EXECUTED":"NO","WIP_ACTIVATION":"NO-GO"},"safety")
 check(R["tested_commit"]==M["origin"]["tested_commit"] and R["matrix_unchanged"]==M["matrix_unchanged"],"receipt")
 check(R["workflow_run"].endswith("/39315105462"),"receipt run")
 check(all(R[k]==v for k,v in M["safety"].items()),"receipt safety")
 check(len(R["jobs"])==2 and set(x["copy"] for x in R["jobs"])=={"A","B"},"receipt copies")
 check(set(M["reports"])=={"A","B"},"manifest copies")
 for k,p in PIN.items():
  m=M["reports"][k]
  expected={"job_id":p["job"],"artifact_id":p["artifact"],"artifact_name":"h2-pg18-revision-hardening-"+k,"zip_size":p["size"],"zip_sha256":p["zip"],"zip_git_blob":p["zipblob"],"zip_crc":p["crc"],"json_size":3578,"json_sha256":p["json"],"json_git_blob":p["jsonblob"],"member":"h2_pg18_result.json","json_path":"original_"+k+".json","zip_path":"original_"+k+".zip"}
  check(m==expected,k+" manifest")
  job=next(x for x in R["jobs"] if x["copy"]==k)
  check(job["id"]==p["job"] and job["artifact_id"]==p["artifact"] and job["report_sha256_from_CI_verifier"]==p["json"] and job["assertions"]==job["passed"]==31 and job["conclusion"]=="success",k+" attribution")
  a,b=Z[k],J[k]
  check(len(a)==p["size"] and sha(a)==p["zip"] and blob(a)==p["zipblob"],k+" ZIP bytes")
  check(len(b)==3578 and sha(b)==p["json"] and blob(b)==p["jsonblob"],k+" JSON bytes")
  try:
   with ZipFile(io.BytesIO(a)) as f:
    t=f.infolist()
    check(len(t)==1 and t[0].filename=="h2_pg18_result.json",k+" ZIP members")
    check(f.testzip() is None and format(t[0].CRC,"08x")==p["crc"],k+" ZIP CRC")
    check(f.read(t[0])==b,k+" ZIP extracted equality")
  except (BadZipFile,OSError) as e:raise Bad(k+" ZIP invalid") from e
  j=json.loads(b)
  check(j["verdict"]=="PASS" and j["assertions"]==j["passed"]==31,k+" verdict")
  check(j["pg_version"]=="18.6 (Debian 18.6-1.pgdg13+2)",k+" PG version")
  check(j["scope"]=="observed-partial-schema synthetic PG18, not Neon; owner can bypass role protections",k+" scope")
  check(len(j["checks"])==31 and [c["name"] for c in j["checks"]]==NAMES and all(c["pass"] is True for c in j["checks"]),k+" checks")
  check(j["checks"][-1]["detail"]=="owner remains capable; no owner-proof append-only claim",k+" unexecuted negative")
  check(len(j["race"])==2 and {x["status"] for x in j["race"]}=={"committed","rejected"} and next(x for x in j["race"] if x["status"]=="rejected")["sqlstate"]=="23505",k+" race")
def main():
 m=json.loads((P/"A_B_original_evidence_manifest_v1.json").read_bytes())
 r=json.loads((P/"A_B_execution_receipt.json").read_bytes())
 j={k:(P/("original_"+k+".json")).read_bytes() for k in "AB"}
 z={k:(P/("original_"+k+".zip")).read_bytes() for k in "AB"}
 verify(m,r,j,z)
 tests=[
 ("flip_A",lambda m,r,j,z:j.__setitem__("A",j["A"][:-1]+b"x")),
 ("replace_A_with_B",lambda m,r,j,z:j.__setitem__("A",j["B"])),
 ("truncate_B",lambda m,r,j,z:j.__setitem__("B",j["B"][:-1])),
 ("corrupt_ZIP_A",lambda m,r,j,z:z.__setitem__("A",z["A"][:-2]+b"xx")),
 ("substitute_ZIP_B",lambda m,r,j,z:z.__setitem__("B",z["A"])),
 ("swap_manifest_A_job",lambda m,r,j,z:m["reports"]["A"].__setitem__("job_id",PIN["B"]["job"])),
 ("forge_manifest_B_hash",lambda m,r,j,z:m["reports"]["B"].__setitem__("json_sha256","0"*64)),
 ("swap_receipt_B_job",lambda m,r,j,z:next(x for x in r["jobs"] if x["copy"]=="B").__setitem__("id",PIN["A"]["job"])),
 ("misrepresent_owner_negative",lambda m,r,j,z:m.__setitem__("owner_mutation_negative_control","EXECUTED")),
 ("change_verdict_A",lambda m,r,j,z:j.__setitem__("A",j["A"].replace(b'"verdict": "PASS"',b'"verdict": "FAIL"')))]
 rejected=0
 for name,modify in tests:
  mm,rr,jj,zz=copy.deepcopy(m),copy.deepcopy(r),dict(j),dict(z)
  modify(mm,rr,jj,zz)
  try:verify(mm,rr,jj,zz)
  except Bad:rejected+=1
  else:raise Bad("corruption accepted: "+name)
 print(json.dumps({"verdict":"PASS_GIT_ONLY","original_reports":"2/2","ZIP_CRC":"2/2","checks":"31/31 A + 31/31 B","corruption_rejected":str(rejected)+"/10","owner_mutation_control":"NOT_EXECUTED_DISCLOSED"},sort_keys=True))
if __name__=="__main__":
 try:main()
 except (Bad,OSError,ValueError,KeyError,TypeError) as e:raise SystemExit("FAIL GIT_ONLY: "+str(e))
