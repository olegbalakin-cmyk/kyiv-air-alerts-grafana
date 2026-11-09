"""Only offline freshness/receipt contracts. No full generator or physical proof."""
from __future__ import annotations
import copy
from datetime import timedelta
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import zipfile
from scripts import c2_shadow_bundle as c2
from scripts import c6_history_freshness as h
from scripts import neon_json_shadow as shadow
from scripts import neon_json_shadow_generator as generator

class HistoryTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        no_network = patch("socket.socket.connect", side_effect=AssertionError("NO_NETWORK"))
        no_network.start(); self.addCleanup(no_network.stop)
        self.keys = ["kyiv", "sevastopol"] + ["bridge_%02d" % i for i in range(21)]
        self.checked = "2026-11-08T06:00:00Z"; self.read_at = "2026-11-08T07:00:00Z"
        self.rows = [{"city_key": k, "legacy_episode_id": k, "alert_type": "AIR",
            "episode_state": "closed", "start_at": "2026-11-01T00:00:00Z",
            "end_at": "2026-11-01T01:00:00Z", "canonicalization_version": shadow.VERSION} for k in self.keys]
        self.receipt = {"status": "succeeded", "failure_policy": "fail_closed",
            "production_output_mutation": False, "persistence_status": "persisted",
            "workflow_sha": "a"*40, "input_sha": "b"*40, "db_branch": "br-test",
            "city_count": 23, "canonical_episode_count": 23, "run_id": "canonical-run",
            "episodes_inserted": 23, "episodes_existing": 0, "episodes_updated": 0, "writes": 25,
            "corpus_sha256": h.fingerprint({"canonicalization_version": shadow.VERSION,
                "production_city_keys": self.keys, "episodes": self.rows})}
        self.payload = {"format": "multicity-canonical-same-run-v1",
            "canonicalization_version": shadow.VERSION, "cities": {
                k: {"episodes": [r], "episode_count": 1} for k,r in zip(self.keys,self.rows)}}
        self.status = {"canonical_persistence_status": "NEON_SUCCEEDED", "canonical_receipt_validated": True,
            "canonical_db_commit": "CONFIRMED", "workflow_sha": "a"*40, "input_sha": "b"*40}
        self.dashboard = {"multicity_meta": {"production_city_keys": self.keys,
            "cities": {k: {"label": k, "source_type": "exact_city"} for k in self.keys},
            "official_ukrainealarm_bridge": {
                "required_rows": self.keys[2:], "continuity_verified_rows": self.keys[2:],
                "continuity_unverified_rows": [], "fully_continuous": True, "last_fetch_error": None,
                "last_successful_fetch_at": self.checked, "rows": {k: {
                    "primary_continuous": True, "continuity_reason": "history_reaches_previous_poll",
                    "last_error": None, "last_checked_at": self.checked} for k in self.keys[2:]}}}}
        self.proof = {"c2_corpus_sha256": self.receipt["corpus_sha256"],
            "meta": {"read_only": "on", "isolation": "repeatable read", "snapshot": "1:2:", "read_at": self.read_at},
            "table_sha256": {t: "c"*64 for t in h.TABLES}, "counts": {t: 1 for t in h.TABLES},
            "mode": "offline_fixture", "physical_neon_readback_run": False}
        self.pack()

    def pack(self):
        self.files = {n: b"{}" for n in c2.MEMBERS}
        for name,obj in [("receipt.json", self.receipt), ("status.json", self.status),
                         ("payload.json", self.payload), ("site_data/dashboard_data.json", self.dashboard)]:
            self.files[name] = json.dumps(obj).encode()
        self.proof["receipt_sha256"] = h.digest(self.files["receipt.json"])
        manifest = {"schema": c2.SCHEMA, "repository": c2.REPOSITORY,
            "github_run_id": 123, "github_run_attempt": 1, "canonical_run_id": self.receipt["run_id"],
            "corpus_sha256": self.receipt["corpus_sha256"], "workflow_sha": "a"*40, "input_sha": "b"*40,
            "db_branch": "br-test", "db_endpoint": "ep-example.c-7.us-east-2.aws.neon.tech",
            "files": {n: h.digest(v) for n,v in self.files.items()}}
        self.files["manifest.json"] = json.dumps(manifest).encode()
        self.bundle = self.root / "bundle.zip"
        self.write_zip()

    def write_zip(self):
        with zipfile.ZipFile(self.bundle, "w") as z:
            for n,raw in self.files.items(): z.writestr(n,raw)
        self.sha = h.digest(self.bundle.read_bytes())

    def bind(self, **override):
        args = dict(readback_proof=self.proof, receipt=self.receipt,
            receipt_sha256=self.proof["receipt_sha256"], workflow_sha="a"*40,
            input_sha="b"*40, db_branch="br-test")
        args.update(override)
        return h.from_bundle(self.bundle, self.sha, **args)

    def evaluate(self, binding=None, now=None):
        return h.evaluate(binding or self.bind(), now=now or self.read_at, readback_proof=self.proof)

    def independent(self):
        self.dashboard["multicity_meta"]["historical_source_receipts"] = {
            k: {"source_key": source, "last_checked_at": self.checked,
                "previous_checked_at": "2026-11-08T02:00:00Z", "source_sha256": "d"*64,
                "oldest_fetched_completed_air_start": "2026-11-07T00:00:00Z", "last_error": None,
                "continuity_verified": True, "continuity_reason": "history_reaches_previous_poll"}
            for k,source in h.INDEPENDENT.items()}
        self.pack()

    def test_21_bound_two_missing(self):
        r=self.evaluate()
        self.assertEqual((r["historically_bound_cities"],r["fresh_cities"],r["status"]),(21,21,"BLOCKED"))
        for k in h.INDEPENDENT:
            self.assertIsNone(r["cities"][k]["source_checked_at_utc"])
            self.assertEqual(r["cities"][k]["reasons"],["MISSING_INDEPENDENT_SOURCE_CAPTURE_CHECKPOINT"])
        with self.assertRaises(h.Blocked): h.require_ready(r)

    def test_23_history_ready_without_live_status(self):
        self.independent(); r=self.evaluate(); h.require_ready(r)
        self.assertEqual(r["status"],"FRESHNESS_READY_FOR_INTEGRATION")
        self.assertFalse(r["publication_allowed"])

    def test_exact_36_hour_limit_and_recomputation(self):
        self.independent(); b=self.bind(); edge=h.utc(self.checked)+timedelta(hours=36)
        self.assertEqual(self.evaluate(b,edge)["fresh_cities"],23)
        r=self.evaluate(b,edge+timedelta(microseconds=1))
        self.assertEqual((r["fresh_cities"],r["historically_bound_cities"]),(0,23))
        with self.assertRaises(h.Blocked): h.require_ready(r)

    def test_quiet_city_latest_alert_is_not_source_clock(self):
        self.dashboard["multicity_meta"]["official_ukrainealarm_bridge"]["rows"][self.keys[2]]["latest_record_end"]="2022-01-01T00:00:00Z"
        self.pack()
        self.assertEqual(self.evaluate()["cities"][self.keys[2]]["source_age_seconds"],3600)

    def test_bundle_hash_and_member_drift(self):
        valid=self.sha; self.sha="0"*64
        with self.assertRaises(c2.BundleBlocked): self.bind()
        self.sha=valid; self.files["site_data/dashboard_data.json"]+=b" "; self.write_zip()
        with self.assertRaisesRegex(c2.BundleBlocked,"EXISTING_C2_MEMBER_SHA"): self.bind()

    def test_workflow_input_branch_receipt_mismatch(self):
        for field in ("workflow_sha","input_sha","db_branch","receipt_sha256"):
            with self.subTest(field=field), self.assertRaises(ValueError): self.bind(**{field:"changed"})

    def test_rehashed_payload_must_match_corpus(self):
        self.payload["cities"][self.keys[2]]["episodes"][0]["end_at"]="2026-11-02T00:00:00Z"
        self.pack()
        with self.assertRaisesRegex(h.Blocked,"HISTORY_CORPUS_MISMATCH"): self.bind()

    def test_foreign_readback_corpus_or_receipt(self):
        for field in ("c2_corpus_sha256","receipt_sha256"):
            proof=copy.deepcopy(self.proof); proof[field]="e"*64
            with self.subTest(field=field), self.assertRaisesRegex(h.Blocked,"HISTORY_READBACK_CORPUS_MISMATCH"):
                self.bind(readback_proof=proof)

    def test_exact_readback_identity_at_consumption(self):
        binding=self.bind()
        for field in ("meta","table_sha256","counts"):
            p=copy.deepcopy(self.proof); p[field][next(iter(p[field]))]="changed"
            with self.subTest(field=field), self.assertRaisesRegex(h.Blocked,"HISTORY_READBACK_IDENTITY_MISMATCH"):
                h.evaluate(binding,now=self.read_at,readback_proof=p)

    def test_binding_capture_tampering(self):
        b=self.bind(); b["sources"][self.keys[2]]["last_checked_at"]=self.read_at
        with self.assertRaisesRegex(h.Blocked,"HISTORY_BINDING_DIGEST_MISMATCH"): self.evaluate(b)

    def test_missing_coverage_discontinuity_error_future_naive_missing_clock(self):
        original=copy.deepcopy(self.dashboard)
        for field,value in (("primary_continuous",False),("last_error","timeout"),
            ("last_checked_at","2026-11-08T08:00:00Z"),("last_checked_at","2026-11-08T06:00:00"),
            ("last_checked_at",None)):
            self.dashboard=copy.deepcopy(original)
            self.dashboard["multicity_meta"]["official_ukrainealarm_bridge"]["rows"][self.keys[2]][field]=value
            self.pack()
            with self.subTest(field=field,value=value), self.assertRaises(ValueError): self.bind()
        self.dashboard=copy.deepcopy(original)
        self.dashboard["multicity_meta"]["official_ukrainealarm_bridge"]["rows"].pop(self.keys[2]); self.pack()
        with self.assertRaisesRegex(h.Blocked,"HISTORY_BRIDGE_COVERAGE_MISSING"): self.bind()

    def test_independent_hash_and_overlap_required(self):
        self.independent(); original=copy.deepcopy(self.dashboard)
        for field,value in (("source_sha256",None),("previous_checked_at",None),
            ("oldest_fetched_completed_air_start","2026-11-08T05:00:00Z")):
            self.dashboard=copy.deepcopy(original)
            self.dashboard["multicity_meta"]["historical_source_receipts"]["kyiv"][field]=value; self.pack()
            with self.subTest(field=field), self.assertRaises(ValueError): self.bind()

    def snap(self):
        rows=[{**r,"uid":"00000000-0000-0000-0000-%012d"%i,
               "created_at":self.checked,"updated_at":self.read_at} for i,r in enumerate(self.rows)]
        return {"meta": {"read_only":"on","isolation":"repeatable read","snapshot":"1:2:","read_at":self.read_at},
            "episodes":rows,"observations":[],"checkpoints":[],
            "runs":[{"run_id":self.receipt["run_id"],"db_branch":"br-test","status":"succeeded",
                     "parameters":{"corpus_sha256":self.receipt["corpus_sha256"]}}],
            "classifications":[],"source_links":[],"events":[]}

    def test_source_report_keeps_current_status_uncertified(self):
        result=generator.source_report(self.snap(),self.keys,self.dashboard,historical=self.evaluate())
        self.assertEqual(set(result),set(self.keys))
        self.assertEqual(result[self.keys[2]]["source_age_seconds"],3600)
        for row in result.values():
            self.assertFalse(row["source_capture_verified"])
            self.assertEqual(row["publication_verdict"],"BLOCKED")
        self.assertIsNone(result["kyiv"]["source_captured_at_utc"])

    def execute(self, **extra):
        site=self.root/"site"; (site/"data").mkdir(parents=True)
        inputs=self.root/"inputs"; inputs.mkdir()
        for name,raw in self.files.items():
            p=inputs/name; p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(raw)
        snap=self.snap()
        def generate(args,work,*unused):
            self.assertEqual(args.historical_freshness["fresh_cities"],23)
            candidate=work/"candidate"; candidate.mkdir()
            for name in ("dashboard_data.json","site_derived.json","alerts_combined.json",
                         "historical-daily-kpi.json",*shadow.AUXILIARIES):
                shadow.write(candidate/name,{"publication_allowed":False})
            for name in ("kyiv_selection.json","projection_lineage.json","git_dependencies.json",
                         "utc_union_diagnostics.json","active_rows_unmodified.json"):
                shadow.write(work/name,{})
            return {"candidate_sha256":{p.name:shadow.digest(p) for p in candidate.iterdir()}}
        self.generate=Mock(side_effect=generate)
        fake=SimpleNamespace(Closed=generator.Closed,fingerprint=generator.fingerprint,
            prepare=lambda *a:(None,None,{}),verify_snapshot=lambda *a:(snap["episodes"],[]),
            source_report=generator.source_report,generate=self.generate)
        args=dict(site=site,receipt_path=inputs/"receipt.json",status_path=inputs/"status.json",
            payload_path=inputs/"payload.json",dashboard_path=inputs/"site_data/dashboard_data.json",
            output=self.root/"output",database_url="postgresql://ro:secret@ep-a.neon.tech/neondb",
            writer_database_url="postgresql://writer:secret@ep-a.neon.tech/neondb",
            expected_branch="br-test",workflow_sha="a"*40,input_sha="b"*40,
            verifier=lambda p:self.receipt,reader=lambda *a,**kw:snap,generated_at=self.read_at,
            history_bundle=self.bundle,history_bundle_sha256=self.sha)
        args.update(extra)
        with patch.object(shadow,"load_generator",return_value=fake): return shadow.execute(**args)

    def test_orchestrator_missing_provenance_stops_before_generator(self):
        with self.assertRaisesRegex(h.Blocked,"HISTORY_FRESHNESS_BLOCKED"): self.execute()
        self.generate.assert_not_called()
        out=self.root/"output"; self.assertFalse((out/"candidate").exists())
        r=json.loads((out/"verdict.json").read_text())
        self.assertFalse(r["publication_allowed"])
        self.assertEqual(r["error_stage"],"VERIFY_HISTORICAL_FRESHNESS_GATE")

    def test_orchestrator_stale_stops_before_generator(self):
        self.independent()
        with self.assertRaises(h.Blocked): self.execute(generated_at="2026-11-10T00:00:00Z")
        self.generate.assert_not_called()
        self.assertFalse((self.root/"output/candidate").exists())

    def test_orchestrator_bad_sha_stops_before_generator(self):
        with self.assertRaises(c2.BundleBlocked): self.execute(history_bundle_sha256="0"*64)
        self.generate.assert_not_called()
        self.assertFalse((self.root/"output/candidate").exists())

    def test_orchestrator_preserves_six_file_contract_and_publication_false(self):
        self.independent(); r=self.execute()
        self.assertEqual(r["status"],"PASS"); self.assertEqual(len(r["candidate_files"]),6)
        self.assertFalse(r["publication_allowed"]); self.assertFalse(r["source_current_certified"])
        gates=json.loads((self.root/"output/source_gates.json").read_text())
        self.assertEqual(gates["kyiv"]["source_checked_at_utc"],self.checked)

if __name__=="__main__":
    unittest.main()
