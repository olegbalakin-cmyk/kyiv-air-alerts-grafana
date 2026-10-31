"""Executable full generation plus failure injection at each acceptance boundary."""
import copy
import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from scripts import neon_json_shadow as shadow
from scripts import neon_json_shadow_generator as generator
from scripts import neon_json_shadow_offline_proof as proof
from scripts import neon_json_shadow_physical_proof as physical


class FullOfflineProof(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.site, cls.inputs, cls.snap, cls.provenance = proof.prepare_fixture(cls.root)
        cls.before = proof.file_hashes(cls.site)
        cls.results = []

    @classmethod
    def tearDownClass(cls):
        assert proof.file_hashes(cls.site) == cls.before
        target = os.getenv("NEON_SHADOW_NEGATIVE_RESULTS")
        if target:
            proof.save(Path(target), {"scenarios": cls.results, "site_inputs_unchanged": True})
        cls.temp.cleanup()

    def setUp(self):
        self.work = tempfile.TemporaryDirectory()
        self.addCleanup(self.work.cleanup)
        self.inputs_copy = Path(self.work.name) / "inputs"
        self.inputs_copy.mkdir()
        for name in ("receipt.json", "status.json", "payload.json"):
            (self.inputs_copy / name).write_bytes((self.inputs / name).read_bytes())
        self.snapshot = copy.deepcopy(self.snap)
        self.output = Path(self.work.name) / "output"
        self.args = proof.arguments(self.site, self.inputs_copy, self.snapshot, self.output)

    def change_json(self, name, mutate):
        path = self.inputs_copy / name
        obj = shadow.load(path)
        mutate(obj)
        proof.save(path, obj)

    def blocked(self, expected):
        with proof.no_network() as attempts, patch.object(shadow, "load_generator", return_value=generator):
            with self.assertRaises(Exception):
                shadow.execute(**self.args)
        verdict = shadow.load(self.output / "verdict.json")
        self.assertIn(expected, verdict["reason"])
        self.assertEqual(verdict["status"], "BLOCKED")
        self.assertFalse(verdict["publication_allowed"])
        self.assertEqual(verdict["candidate_files"], {})
        self.assertFalse((self.output / "candidate").exists())
        self.assertEqual(attempts, [])
        self.results.append({"test": self._testMethodName, "status": "PASS",
                             "reason": verdict["reason"], "accepted_candidate": False,
                             "publication_allowed": False, "network_or_sql_attempts": 0})

    def test_full_generation(self):
        # Real execute -> real C2 verifier -> stored reader -> real generator.
        target = Path(os.environ["NEON_SHADOW_PROOF_OUTPUT"]) if os.getenv("NEON_SHADOW_PROOF_OUTPUT") else self.output
        verdict = proof.run(target)
        self.assertEqual(verdict["city_count"], 23)
        self.assertEqual(len(verdict["candidate_files"]), 6)

    def test_c2_receipt_failure(self):
        self.change_json("receipt.json", lambda x: x.update(status="failed"))
        self.blocked("RECEIPT_READBACK_OR_GENERATOR_ERROR")

    def test_wrong_workflow_sha(self):
        self.args["workflow_sha"] = "c" * 40
        self.blocked("WORKFLOW_SHA_MISMATCH")

    def test_wrong_input_sha(self):
        self.args["input_sha"] = "d" * 40
        self.blocked("INPUT_SHA_MISMATCH")

    def test_wrong_branch(self):
        self.args["expected_branch"] = "br-other"
        self.blocked("NEON_BRANCH_RECEIPT_MISMATCH")

    def test_wrong_endpoint(self):
        self.args["writer_database_url"] = "postgresql://wrong.invalid/neondb"
        self.blocked("NEON_ENDPOINT_BRANCH_MISMATCH")

    def test_corpus_mismatch(self):
        self.change_json("receipt.json", lambda x: x.update(corpus_sha256="0" * 64))
        self.blocked("C2_CORPUS_BINDING_MISMATCH")

    def test_missing_canonical_parent(self):
        self.snapshot["episodes"].pop()
        self.blocked("READBACK_MISSING_OR_DUPLICATE")

    def test_missing_source_parent(self):
        self.snapshot["observations"][0]["parent_uid"] = "00000000-0000-0000-0000-000000000000"
        self.blocked("DANGLING_SOURCE_OBSERVATION")

    def test_invalid_uuid(self):
        self.snapshot["episodes"][0]["uid"] = "invalid"
        self.blocked("READBACK_UUID_INVALID")

    def test_invalid_interval(self):
        self.snapshot["episodes"][0]["end_at"] = self.snapshot["episodes"][0]["start_at"]
        self.blocked("READBACK_SEMANTIC_MISMATCH")

    def test_missing_pinned_asset(self):
        with patch.object(generator, "ASSETS", Path(self.work.name) / "absent"):
            self.blocked("ACCEPTED_ASSET:approved_22city_archive.b64")

    def test_generator_exception(self):
        with patch.object(generator, "generate", side_effect=RuntimeError("injected")):
            self.blocked("BLOCKED_GENERATOR_INPUT:RuntimeError")

    def test_incomplete_six_outputs(self):
        def incomplete(args, out, *rest):
            candidate = out / "candidate"
            candidate.mkdir()
            for name in sorted(proof.FILES)[:-1]:
                (candidate / name).write_text("{}")
            return {"candidate_sha256": {p.name: shadow.digest(p) for p in candidate.iterdir()}}
        with patch.object(generator, "generate", side_effect=incomplete):
            self.blocked("SIX_FILE_CONTRACT")

    def test_missing_b2_source_link(self):
        self.snapshot["source_links"].pop()
        self.blocked("SOURCE_LINKS_COUNT_CHANGED")

    def test_invalid_classification_parent(self):
        self.snapshot["classifications"][0]["parent_uid"] = "00000000-0000-0000-0000-000000000000"
        self.blocked("DANGLING_CLASSIFICATION_PARENT")

    def test_writable_snapshot(self):
        self.snapshot["meta"]["read_only"] = "off"
        self.blocked("READ_ONLY_SNAPSHOT_NOT_PROVEN")

    def test_wrong_c2_run_corpus(self):
        self.snapshot["runs"][-1]["parameters"]["corpus_sha256"] = "0" * 64
        self.blocked("C2_RUN_CORPUS_MISMATCH")

    def test_wrong_c2_run_branch(self):
        self.snapshot["runs"][-1]["db_branch"] = "br-other"
        self.blocked("C2_RUN_NOT_IN_READONLY_SNAPSHOT")

    def test_fixture_cannot_trigger_physical_readback(self):
        self.args["reader"] = None
        self.blocked("OFFLINE_FIXTURE_CANNOT_AUTHORIZE_PHYSICAL_READBACK")


class IsolatedWorkflowPreflight(unittest.TestCase):
    def test_manual_research_only_read_permissions(self):
        import yaml
        path = proof.ROOT / ".github/workflows/c6-neon-shadow-isolated-proof.yml"
        text = path.read_text()
        doc = yaml.load(text, Loader=yaml.BaseLoader)
        self.assertEqual(set(doc["on"]), {"workflow_dispatch"})
        self.assertEqual(doc["permissions"], {"contents": "read", "actions": "read"})
        job = doc["jobs"]["proof"]
        self.assertEqual(job["environment"], "c6-live-writer-proof")
        self.assertIn("github.sha == inputs.research_sha", job["if"])
        self.assertIn("refs/heads/research-neon-shadow-frontend-2026-10-31", job["if"])
        for forbidden in ("update-netlify-site.yml", "git push", "netlify deploy", "contents: write"):
            self.assertNotIn(forbidden, text)
        self.assertNotIn("PHASE1_PROD_SHADOW_DATABASE_URL", text)

    def test_physical_bundle_rejects_synthetic_c2_without_sql(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            values = {"receipt.json": b'{"offline_fixture":true}', "status.json": b'{}', "payload.json": b'{}'}
            values.update({"site_data/" + name: b'{}' for name in physical.SITE_DATA})
            values["manifest.json"] = json.dumps({"schema": "existing-c2-shadow-inputs-v1", "files": {
                name: proof.sha(raw) for name, raw in values.items()}}).encode()
            bundle = root / "bundle.zip"
            with zipfile.ZipFile(bundle, "w") as z:
                for name, raw in values.items():
                    z.writestr(name, raw)
            with proof.no_network() as attempts:
                with self.assertRaisesRegex(shadow.ShadowBlocked, "OFFLINE_FIXTURE_CANNOT_AUTHORIZE"):
                    physical.prepare_bundle(bundle, shadow.digest(bundle), root / "output")
            self.assertEqual(attempts, [])
            self.assertFalse((root / "output").exists())


if __name__ == "__main__":
    unittest.main()
