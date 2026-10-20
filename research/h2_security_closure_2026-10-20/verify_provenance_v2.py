#!/usr/bin/env python3
"""Git-only exact A/B provenance verifier with independently pinned source anchors.
Does not contact GitHub or Neon; pinning is verified against the original Git blobs.
"""
import base64, copy, hashlib, io, json, re, subprocess, zipfile
from pathlib import Path

P=Path("research/h2_security_closure_2026-10-20/provenance_v2")
M=json.loads((P/"manifest_v2.json").read_text())
LEGACY="research/h2_rollback_adversarial_2026-10-20/frozen_2026-10-20"
ORIGINAL_MANIFEST_SHA="3755d2b81558631fe0869575ea29b472ed02eaf2"
TESTED="142bd18757a432fee57f5c3536e2a40a3ccdb072"
RUN=39446642675
# These immutable anchors were separately read from original GitHub job logs,
# Actions artifact metadata, and original Git blob API, NOT copied from v2.
ANCHORS={
 "A":{"job":118710199384,"job_name":"pg18 (A)","artifact_id":12276507122,
      "artifact_name":"h2-adversarial-A","zip_sha":"c46a42ef4b579aad9235b4d5080d24abfa387d9de9746312640ca058d68d0203",
      "zip_size":12337,"json_sha":"f14387800f9f119e9c7643bd96ba3705917b92edc4503b586f337682b4aa5dfa",
      "log_blob":"3e31361967c956390d7cc4fe5e9160eb42dd2bb3","zip_blob":"272e832416cb172c7ad69353485b0cf18d03a879"},
 "B":{"job":118710199075,"job_name":"pg18 (B)","artifact_id":12275672717,
      "artifact_name":"h2-adversarial-B","zip_sha":"865e577087eea0835a66520b70d21c8762eb2fc41add54a1608ff5401a5d4b60",
      "zip_size":12353,"json_sha":"599de47a12b049ccab7eaa871ce08036db163961bac9af4ae3225f5b6908310d",
      "log_blob":"ca91fce136537500d188549165b46057f6d8a055","zip_blob":"2bd4032bd606b0004b149d4647e123251e4b1f90"}
}
def git_blob(path, ref="HEAD"):
 return subprocess.check_output(["git","rev-parse",ref+":"+path],text=True).strip()
def sha(data): return hashlib.sha256(data).hexdigest()
class Rejected(ValueError):
 pass
def need(condition,reason):
 if not condition: raise Rejected(reason)
def match_line(log,needle):
 return any(needle in ln and ln.startswith("2026-") for ln in log.splitlines())
def check(manifest,label,override_log=None):
 x=ANCHORS[label]; c=manifest["copies"][label]
 need(manifest["run_id"]==RUN,"run_id")
 need(manifest["original_manifest_git_blob"]==ORIGINAL_MANIFEST_SHA,"original_manifest")
 need(manifest["tested_commit"]==TESTED,"tested_commit")
 need(manifest["reported_verdict"]=="PARTIAL","verdict")
 need(c["job"]==x["job"],"job_id")
 need(c["job_name"]==x["job_name"],"job_name")
 need(c["artifact_id"]==x["artifact_id"],"artifact_id")
 need(c["uploaded_artifact_id"]==x["artifact_id"],"uploaded_artifact_id")
 need(c["artifact_name"]==x["artifact_name"],"artifact_name")
 need(c["h2_copy"]==label,"h2_copy")
 need(c["job_log_excerpt_git_blob"]==x["log_blob"],"job_log_blob_reference")
 need(c["zip_base64_git_blob"]==x["zip_blob"],"zip_blob_reference")
 log_path=P/(label+".job_log_excerpt.txt")
 need(git_blob(str(log_path))==x["log_blob"],"job_log_git_blob")
 log=log_path.read_text() if override_log is None else override_log
 # For corruption control, hash Git blob representation, not normalized text.
 payload=("blob "+str(len(log.encode()))+"\0").encode()+log.encode()
 need(hashlib.sha1(payload).hexdigest()==x["log_blob"],"job_log_integrity")
 for v in ["H2_COPY: "+label,"name: "+x["artifact_name"],
           "path: /tmp/h2_adversarial_"+label+".json",
           "SHA256 digest of uploaded artifact zip is "+x["zip_sha"],
           "Artifact "+x["artifact_name"]+".zip successfully finalized. Artifact ID "+str(x["artifact_id"]),
           "Artifact "+x["artifact_name"]+" has been successfully uploaded! Final size is "+
                str(x["zip_size"])+" bytes. Artifact ID is "+str(x["artifact_id"])]:
  need(match_line(log,v),"job_log_upload_attribution")
 need(match_line(log,TESTED),"job_log_tested_commit")
 need(c["zip_sha256"]==x["zip_sha"],"zip_sha256")
 need(c["size_zip"]==x["zip_size"],"zip_bytes")
 need(c["json_sha256"]==x["json_sha"],"json_sha256")
 archive_path=LEGACY+"/"+label+".original.zip.b64"
 need(git_blob(archive_path)==x["zip_blob"],"frozen_zip_git_blob")
 z=base64.b64decode(Path(archive_path).read_bytes(),validate=False)
 need(sha(z)==x["zip_sha"] and len(z)==x["zip_size"],"original_zip_integrity")
 with zipfile.ZipFile(io.BytesIO(z)) as zz:
  need(zz.testzip() is None and zz.namelist()==[c["json_member"]],"original_zip_crc")
  raw=zz.read(c["json_member"])
 need(sha(raw)==x["json_sha"] and len(raw)==c["json_bytes"],"original_json_integrity")
 report=json.loads(raw)
 need(report["tested_commit"]==TESTED and report["copy"]==label,"original_json_attribution")
 need(report["verdict"]=="PARTIAL" and not report["errors"],"original_partial_verdict")
 need(report["totals"]==c["totals"] and report["gates"]==c["gate_results"],"original_bounded_matrix")
 return {"copy":label,"job":x["job"],"artifact":x["artifact_id"],"zip_sha256":sha(z),"json_sha256":sha(raw),"result":"PASS"}
def main():
 need(git_blob(LEGACY+"/manifest.json")==ORIGINAL_MANIFEST_SHA,"legacy_source_must_not_change")
 legacy=json.loads(Path(LEGACY+"/manifest.json").read_text())
 need(legacy["copies"]["A"]["job"]==ANCHORS["B"]["job"] and
      legacy["copies"]["B"]["job"]==ANCHORS["A"]["job"],"legacy_swapped_proof")
 for p,s in M["tested_executables"].items():
  need(git_blob(p)==s and git_blob(p,TESTED)==s,"tested_source_git_blob")
 for label in ("A","B"): print(json.dumps(check(M,label),sort_keys=True))
 def mutated(name,edit,why,log=None):
  t=copy.deepcopy(M);edit(t)
  try:check(t,"A",override_log=log)
  except Rejected as e:
   need(str(e)==why,"incorrect_negative_reason_"+name+"_got_"+str(e))
   print("CORRUPTION_REJECTED",name,why)
  else:raise RuntimeError("CORRUPTION_ACCEPTED "+name)
 mutated("wrong_job_id",lambda m:m["copies"]["A"].update(job=118710199075),"job_id")
 mutated("swapped_both_job_ids",lambda m:(
   m["copies"]["A"].update(job=118710199075),
   m["copies"]["B"].update(job=118710199384)),"job_id")
 mutated("wrong_artifact_id",lambda m:m["copies"]["A"].update(artifact_id=12275672717),"artifact_id")
 mutated("incorrect_job_artifact_join",lambda m:m["copies"]["A"].update(uploaded_artifact_id=12275672717),"uploaded_artifact_id")
 mutated("wrong_copy_label",lambda m:m["copies"]["A"].update(h2_copy="B"),"h2_copy")
 mutated("wrong_zip_sha256",lambda m:m["copies"]["A"].update(zip_sha256="0"*64),"zip_sha256")
 mutated("wrong_json_sha256",lambda m:m["copies"]["A"].update(json_sha256="0"*64),"json_sha256")
 mutated("wrong_tested_commit",lambda m:m.update(tested_commit="0"*40),"tested_commit")
 mutated("wrong_original_verdict",lambda m:m.update(reported_verdict="PASS"),"verdict")
 log=(P/"A.job_log_excerpt.txt").read_text()
 mutated("tampered_frozen_job_log",lambda m:None,"job_log_integrity",log=log+"X")
 print("H2_ADVERSARIAL_AB_JOB_ATTRIBUTION=PASS")
 print("H2_ADVERSARIAL_COMPLETE_PROVENANCE_FREEZE=PASS_BOUNDED_SELECTED_JOB_LOG_EXCERPTS")
 print("H2_ADVERSARIAL_CORRECTED_GIT_ONLY_VERIFICATION=PASS")
 print("PROVENANCE_NEGATIVE_REJECTIONS=10")
if __name__=="__main__":main()
