#!/usr/bin/env python3
"""Independent Git-only byte-exact H2 008 A/B evidence verifier + tampering."""
import copy,hashlib,io,json,subprocess,zipfile
ROOT="research/h2_008_late_acl_2026_10_21/original_ab/"
R="39504096121"
PIN={
"A":{"job":118908548277,"artifact":12303147740,"size":6287,"sha256":"3fa001cca4c277f8e7cb481832f38ad4ee960a12b459b845009154d6ed653f49",
     "json_sha":"62fa8ce21ebc08f07cfbb9ee02793e77598cc8d9235381cffca9ff96e00ae45f","crc32":3324285729},
"B":{"job":118908548485,"artifact":12301873679,"size":6284,"sha256":"40fbb25ba0e3268c7aca6e00ffe81bb154d4c6a7b6af1508f6b405871120cac4",
     "json_sha":"6d3cec773dd7091c23037a97463bd1e0dcf7fcbd8c13cd47b2ac7341e772cbb5","crc32":942302388}}
SOURCE={
"research/h2_non_superuser_guard_acl_2026-10-20/008_non_superuser_acl_rollback.sql":"59eab59235f8aee14837ce7494649edba674e1ce",
"research/h2_008_late_acl_2026_10_21/008_late_fault_instrumented.sql":"54dbeb7945929a3dd4f808b82d96b01079cd35b0",
"research/h2_008_late_acl_2026_10_21/test_late_acl.py":"a53bac8fc5fb4373b96028b4cfed53e8eecfa4d5",
".github/workflows/h2-actual-008-late-acl-2026-10-21.yml":"6271e5789e6308db856d6d952b894bfdc84c1935"}
SHA="5213a91ae593a3ef80f4936d55c7ec08c4a5737e"
EXPECTED={"alert_episodes","ingestion_runs","ingestion_checkpoints","current_ingestion_checkpoints",
"attack_event_classifications","attack_event_sources","attack_events"}
def blob(path):return subprocess.check_output(["git","show","HEAD:"+path])
def ref(path):return subprocess.check_output(["git","rev-parse","HEAD:"+path],text=True).strip()
def sha(b):return hashlib.sha256(b).hexdigest()
def assert_true(p,msg):
    if not p:raise ValueError(msg)
def validate(manifest,files,hard_pins=True):
    assert_true(manifest["run"]==int(R) and manifest["tested_sha"]==SHA,"run or SHA changed")
    assert_true(manifest["source_blobs"]==SOURCE,"source identity changed")
    assert_true(set(manifest["copies"])==set(PIN),"copy inventory changed")
    for copy in ("A","B"):
        v=manifest["copies"][copy];pin=PIN[copy]
        assert_true(v["job"]==pin["job"] and v["artifact"]==pin["artifact"],"job/artifact attribution")
        assert_true(v["file"]==copy+".zip","file attribution")
        dat=files[copy]
        assert_true(len(dat)==v["size"]==pin["size"],"ZIP size")
        assert_true(sha(dat)==v["sha256"]==pin["sha256"],"ZIP digest")
        with zipfile.ZipFile(io.BytesIO(dat)) as z:
            assert_true(z.testzip() is None,"ZIP CRC failed")
            entries=[x for x in z.infolist() if not x.is_dir()]
            assert_true(len(entries)==1 and entries[0].filename=="h2_008_late_acl_"+copy+".json","wrong member")
            ent=entries[0];member=z.read(ent.filename)
            meta=v["members"].get(ent.filename)
            assert_true(meta is not None and len(v["members"])==1,"member inventory")
            assert_true(meta["size"]==len(member)==88030,"JSON byte length")
            assert_true(meta["sha256"]==sha(member)==pin["json_sha"],"member SHA")
            assert_true(meta["crc32"]==ent.CRC==pin["crc32"],"member CRC")
            report=json.loads(member)
            assert_true(report["copy"]==copy and report["commit"]==SHA,"report copy or commit")
            assert_true(report["original_008_git_blob"]==SOURCE[next(iter(SOURCE))],"original SQL identity")
            assert_true(report["verdict"]=="PARTIAL" and not report["errors"],"verdict")
            assert_true(report["tests_total"]==report["tests_passed"]==len(report["cases"])==15,"case count")
            assert_true(all(c["status"]=="PASS" for c in report["cases"]),"case failure")
            ids={c["case"] for c in report["cases"]}
            assert_true({"actual_008_late_fault_sqlstate_23514",
              "actual_008_late_fault_full_catalog_atomicity",
              "actual_008_late_fault_effective_rights_atomicity",
              "original_vs_instrumented_success_catalog",
              "physical_residual_enumerated",
              "future_ddl_owner_function_grant_matrix"}.issubset(ids),"case omission")
            sessions=report["instrumented_sessions"]
            fail=[s for s in sessions if s["fault"]=="late_acl"]
            assert_true(len(fail)==1 and fail[0]["sqlstate"]=="23514" and fail[0]["exit"]!=0,"not late fault")
            assert_true("H2_008_LATE_AFTER_REAL_ACL_REVOKES" in fail[0]["stderr"],"not injected fault")
            assert_true("SELECT_PRESENT=f INSERT_PRESENT=f COLUMN_UPDATE_PRESENT=f" in fail[0]["stderr"],"not three verified changes")
            raw=report["observations"]["physical_relacl_delta"]
            assert_true(set(raw)==EXPECTED,"unexpected physical residual")
            assert_true(all(v["before"] is None and v["after"]=="{h2_schema_owner_test=arwdDxtm/h2_schema_owner_test}" for v in raw.values()),"raw ACL value mismatch")
            dump=report["observations"]["dump"]
            assert_true(dump["control_normalized_sha256"]==dump["rollback_normalized_sha256"] and not dump["normalized_diff"],"normalized dump differs")
    return True
def negative(label,m,files):
    try:validate(m,files)
    except Exception:print("PASS_REJECTED",label);return
    raise AssertionError("NEGATIVE_ACCEPTED "+label)
m=json.loads(blob(ROOT+"manifest.json"))
assert_true(ref(ROOT+"manifest.json")=="b77f935effb714f5f2bb63f48a085018ed9914f4","manifest Git blob")
assert_true(all(ref(p)==h for p,h in SOURCE.items()),"source Git blob changed")
f={c:blob(ROOT+c+".zip") for c in ("A","B")}
validate(m,f);print("PASS_ORIGINAL_AB_GIT_ZIP_JSON_SOURCE_15_CASES")
negatives=[
("wrong_job",lambda x:x["copies"]["A"].update(job=PIN["B"]["job"])),
("wrong_artifact",lambda x:x["copies"]["A"].update(artifact=PIN["B"]["artifact"])),
("wrong_run",lambda x:x.update(run=1)),
("wrong_tested_sha",lambda x:x.update(tested_sha="0"*40)),
("wrong_source_blob",lambda x:x["source_blobs"].update({next(iter(SOURCE)):"0"*40})),
("wrong_zip_hash",lambda x:x["copies"]["A"].update(sha256="0"*64)),
("wrong_zip_size",lambda x:x["copies"]["A"].update(size=1)),
("wrong_member_crc",lambda x:x["copies"]["A"]["members"]["h2_008_late_acl_A.json"].update(crc32=0)),
("wrong_member_hash",lambda x:x["copies"]["A"]["members"]["h2_008_late_acl_A.json"].update(sha256="0"*64))]
for label,change in negatives:
    mm=copy.deepcopy(m);change(mm);negative(label,mm,f)
bad=dict(f);bad["A"]=f["A"][:-1]+bytes([f["A"][-1]^1])
negative("zip_byte_flip",m,bad)
swapped=dict(f);swapped["A"]=f["B"]
negative("swapped_copy_zip",m,swapped)
print("PASS_NEGATIVES",len(negatives)+2,"of",len(negatives)+2)
