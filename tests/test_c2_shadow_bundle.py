"""New export/access contracts only. Tiny synthetic inputs; no generator or DB."""
import hashlib
import json
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

import yaml

from scripts import c2_shadow_bundle as bundle
from scripts import neon_json_shadow as shadow
from scripts import neon_json_shadow_generator as generator
from scripts.neon_json_shadow_physical_proof import prepare_bundle

ROOT = Path(__file__).resolve().parents[1]
BASE = "3453492b7f5c0b1e46f115a8fa1a949e4b50109d"


class ExportContracts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.site = self.root / "site"
        (self.site / "data").mkdir(parents=True)
        keys = ["test_city_" + str(i) for i in range(23)]
        rows = [{"city_key": key, "alert_type": "AIR", "episode_state": "closed",
                 "legacy_episode_id": key, "canonicalization_version": shadow.VERSION,
                 "start_at": "2026-01-01T01:00:00Z", "end_at": "2026-01-01T02:00:00Z"}
                for key in keys]
        serial = {"canonicalization_version": shadow.VERSION, "production_city_keys": keys, "episodes": rows}
        corpus = hashlib.sha256(json.dumps(serial, ensure_ascii=False, sort_keys=True,
                                           separators=(",", ":")).encode()).hexdigest()
        receipt = {"status": "succeeded", "failure_policy": "fail_closed", "production_output_mutation": False,
                   "persistence_status": "persisted", "city_count": 23, "canonical_episode_count": 23,
                   "episodes_inserted": 23, "episodes_existing": 0, "episodes_updated": 0, "writes": 25,
                   "corpus_sha256": corpus, "workflow_sha": "a" * 40, "input_sha": "b" * 40,
                   "db_branch": "br-test-only", "run_id": "00000000-0000-4000-8000-000000000001"}
        status = {"canonical_persistence_status": "NEON_SUCCEEDED", "canonical_receipt_validated": True,
                  "canonical_db_commit": "CONFIRMED", "workflow_sha": "a" * 40, "input_sha": "b" * 40}
        payload = {"format": "multicity-canonical-same-run-v1", "canonicalization_version": shadow.VERSION,
                   "cities": {row["city_key"]: {"episode_count": 1, "episodes": [row]} for row in rows}}
        for name in bundle.SITE_DATA:
            shadow.write(self.site / "data" / name, {"fixture": "UNIT_TEST_ONLY"})
        shadow.write(self.site / "data/dashboard_data.json", {"multicity_meta": {"production_city_keys": keys}})
        for name, data in (("receipt", receipt), ("status", status), ("payload", payload)):
            shadow.write(self.root / (name + ".json"), data)
        # The accepted receipt verifier is an unchanged external site-prod dependency.
        # Stub only that existing verifier; exercise the real status + corpus binding.
        self.verifier = Mock(side_effect=shadow.load)
        self.kw = dict(enabled="true", site=self.site, receipt_path=self.root / "receipt.json",
                       status_path=self.root / "status.json", payload_path=self.root / "payload.json",
                       output=self.root / "export", run_id="123", run_attempt="1",
                       workflow_sha="a" * 40, input_sha="b" * 40, db_branch="br-test-only",
                       writer_url="postgresql://unit_user:UNIT_TEST_PASSWORD@ep-test-only.us-east-2.aws.neon.tech/neondb",
                       verifier=self.verifier)

    def export(self, **changes):
        # Any Python network access would fail this offline contract test.
        with patch("socket.socket.connect", side_effect=AssertionError("NO_NETWORK")):
            return bundle.export_bundle(**(self.kw | changes))

    def mutate(self, name, **changes):
        p = self.root / name
        shadow.write(p, shadow.load(p) | changes)

    def archive(self):
        result = self.export()
        self.assertEqual(result["status"], "EXPORTED")
        return self.kw["output"] / "c2-shadow-inputs.zip", result["bundle_sha256"]

    def test_default_off_no_artifact_or_dependency_reads(self):
        self.kw["receipt_path"].unlink()
        for flag in ("", "false", "TRUE", "1"):
            self.assertEqual(self.export(enabled=flag), {"status": "OFF"})
            self.assertFalse(self.kw["output"].exists())
        self.verifier.assert_not_called()

    def test_c2_failure_no_artifact(self):
        self.mutate("status.json", canonical_persistence_status="NEON_FAILED")
        self.kw["payload_path"].unlink()
        self.assertEqual(self.export()["status"], "C2_FAILED_NO_ARTIFACT")
        self.assertFalse(self.kw["output"].exists())
        self.verifier.assert_not_called()

    def test_success_exact_members_hashes_identity_and_physical_unpack(self):
        path, checksum = self.archive()
        self.verifier.assert_called_once()
        extracted = self.root / "unpack"
        manifest = prepare_bundle(path, checksum, extracted, run_id="123", workflow_sha="a" * 40,
                                  input_sha="b" * 40, db_branch="br-test-only",
                                  db_endpoint="ep-test-only.us-east-2.aws.neon.tech")
        self.assertEqual(manifest["github_run_attempt"], 1)
        with zipfile.ZipFile(path) as z:
            self.assertEqual(set(z.namelist()), bundle.MEMBERS | {"manifest.json"})
            self.assertNotIn(b"UNIT_TEST_PASSWORD", b"".join(z.read(n) for n in z.namelist()))
            for name, sha in manifest["files"].items():
                self.assertEqual(hashlib.sha256((extracted / name).read_bytes()).hexdigest(), sha)
        self.assertEqual((self.kw["output"] / "c2-shadow-inputs.zip.sha256").read_text().split()[0], checksum)

    def test_missing_each_input_blocks_without_output(self):
        paths = [self.root / (name + ".json") for name in ("receipt", "status", "payload")]
        paths += [self.site / "data" / name for name in bundle.SITE_DATA]
        for path in paths:
            with self.subTest(path=path.name):
                raw = path.read_bytes()
                path.unlink()
                with self.assertRaises((OSError, bundle.BundleBlocked)):
                    self.export()
                self.assertFalse(self.kw["output"].exists())
                path.write_bytes(raw)

    def test_receipt_verifier_rejection_blocks(self):
        self.verifier.side_effect = ValueError("TEST_RECEIPT_REJECTED")
        with self.assertRaises(ValueError):
            self.export()
        self.assertFalse(self.kw["output"].exists())

    def test_payload_corpus_hash_mismatch_blocks(self):
        self.mutate("receipt.json", corpus_sha256="0" * 64)
        with self.assertRaisesRegex(bundle.BundleBlocked, "CORPUS_BINDING"):
            self.export()
        self.assertFalse(self.kw["output"].exists())

    def test_export_identity_and_offline_fixture_block(self):
        for changes in ({"workflow_sha": "c" * 40}, {"input_sha": "c" * 40},
                        {"db_branch": "br-other"}, {"offline_fixture": True}):
            original = self.kw["receipt_path"].read_bytes()
            self.mutate("receipt.json", **changes)
            with self.assertRaises(bundle.BundleBlocked):
                self.export()
            self.assertFalse(self.kw["output"].exists())
            self.kw["receipt_path"].write_bytes(original)

    def test_member_hash_bundle_hash_and_manifest_identity_block(self):
        path, checksum = self.archive()
        with self.assertRaises(bundle.BundleBlocked):
            bundle.verify_archive(path, "f" * 64)
        for changes in ({"run_id": "999"}, {"db_branch": "br-other"},
                        {"db_endpoint": "ep-other.us-east-2.aws.neon.tech"}):
            with self.assertRaises(bundle.BundleBlocked):
                bundle.verify_archive(path, checksum, **changes)
        with zipfile.ZipFile(path) as z:
            files = {n: z.read(n) for n in z.namelist()}
        files["site_data/kyiv_threat_mix.json"] = b'{}'
        with zipfile.ZipFile(path, "w") as z:
            for name, raw in files.items():
                z.writestr(name, raw)
        with self.assertRaisesRegex(bundle.BundleBlocked, "MEMBER_SHA"):
            bundle.verify_archive(path, shadow.digest(path))

    def test_credential_content_rejected_without_output(self):
        self.mutate("receipt.json", password="UNIT_TEST_PASSWORD")
        with self.assertRaisesRegex(bundle.BundleBlocked, "CREDENTIAL"):
            self.export()
        self.assertFalse(self.kw["output"].exists())


class WorkflowContracts(unittest.TestCase):
    def load(self, content):
        return yaml.load(content, Loader=yaml.BaseLoader)

    def test_production_contract_unchanged_except_bound_history_arguments(self):
        path = ".github/workflows/update-netlify-site.yml"
        before = self.load(subprocess.check_output(["git", "show", BASE + ":" + path], cwd=ROOT))
        after = self.load((ROOT / path).read_text())
        steps = after["jobs"]["update-site"]["steps"]
        names = {"Check out same-workflow C2 bundle exporter", "Export verified same-run C2 shadow bundle",
                 "Upload verified C2 shadow inputs"}
        additions = [step for step in steps if step.get("name") in names]
        self.assertEqual(len(additions), 3)
        for step in additions:
            self.assertIn("vars.C2_SHADOW_BUNDLE_EXPORT_ENABLED == 'true'", step["if"])
            self.assertIn("canonical_persistence_status == 'NEON_SUCCEEDED'", step["if"])
            self.assertEqual(step["continue-on-error"], "true")
        shadow_step = next(s for s in steps if s.get("id") == "neon_json_shadow")
        lines = shadow_step["run"].splitlines(keepends=True)
        additions = [line for line in lines if "--history-bundle" in line]
        self.assertEqual(len(additions), 2)
        self.assertIn('c2-shadow-bundle/c2-shadow-inputs.zip', additions[0])
        self.assertIn('c2-shadow-bundle/c2-shadow-inputs.zip.sha256', additions[1])
        shadow_step["run"] = "".join(line for line in lines if "--history-bundle" not in line)
        self.assertEqual(after, before)

    def test_manual_proof_owner_ref_sha_and_readonly_environment(self):
        content = (ROOT / ".github/workflows/c6-neon-shadow-isolated-proof.yml").read_text()
        workflow = self.load(content)
        self.assertEqual(set(workflow["on"]), {"workflow_dispatch"})
        self.assertEqual(workflow["permissions"], {"contents": "read", "actions": "read"})
        job = workflow["jobs"]["proof"]
        self.assertEqual(job["environment"], "c6-neon-shadow-readonly")
        for clause in ("github.actor == 'olegbalakin-cmyk'", "github.sha == inputs.research_sha",
                       "refs/heads/research-c6-unblock-shadow-proof-2026-11-01", "APPROVE_ONE_READONLY_PROOF"):
            self.assertIn(clause, job["if"])
        self.assertIn("vars.C6_SHADOW_APPROVED_RESEARCH_SHA", content)
        self.assertEqual(set(__import__('re').findall(r'secrets\.([A-Z_]+)', content)),
                         {"NEON_JSON_SHADOW_READONLY_DATABASE_URL"})
        for step in job["steps"]:
            action = step.get("uses", "")
            if action:
                self.assertIn(action, {"actions/checkout@v4", "actions/setup-python@v5",
                                       "actions/download-artifact@v4", "actions/upload-artifact@v4"})
            self.assertNotIn("permissions", step)
            run = step.get("run", "")
            for forbidden in ("git push", "netlify deploy", "update-netlify-site.py", "persist_canonical",
                              "curl ", "workflow run", "gh workflow", "POST", "PATCH"):
                self.assertNotIn(forbidden, run)
        self.assertNotIn("site-prod", content)
        self.assertNotIn("c6-live-writer-proof", content)

    def test_role_gate_rejects_each_risk_and_missing_evidence(self):
        good = {key: False for key in generator.RISKS}
        for risk in generator.RISKS:
            for value in (True, None):
                cn = Mock()
                cn.execute.return_value.fetchone.return_value = good | {risk: value}
                with self.subTest(risk=risk, value=value), self.assertRaises(generator.Closed):
                    generator.verify_role(cn)
        cn = Mock()
        cn.execute.return_value.fetchone.return_value = good
        self.assertEqual(generator.verify_role(cn)["role_privilege_contract"], "NO_DML_DDL_OR_ESCALATION")
        self.assertIn("has_any_column_privilege", generator.ROLE_SQL)
        self.assertIn("has_database_privilege(r.oid, d.oid, 'CREATE')", generator.ROLE_SQL)
        self.assertNotIn("'CREATE,TEMP'", generator.ROLE_SQL)
        self.assertIn("pg_has_role", generator.ROLE_SQL)
        for risk in generator.RISKS:
            cn.execute.return_value.fetchone.return_value = {k: v for k, v in good.items() if k != risk}
            with self.subTest(missing=risk), self.assertRaises(generator.Closed):
                generator.verify_role(cn)

    def snapshot_rejection(self, meta, risks, reason):
        cn = MagicMock()

        def execute(sql):
            if sql in ("BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY", "ROLLBACK"):
                return Mock()
            if sql.startswith("SELECT current_user AS role"):
                return Mock(fetchone=Mock(return_value=meta))
            if sql == generator.ROLE_SQL:
                return Mock(fetchone=Mock(return_value=risks))
            self.fail("Rejected role reached corpus SQL")

        cn.execute.side_effect = execute
        context = MagicMock()
        context.__enter__.return_value = cn
        driver = SimpleNamespace(connect=Mock(return_value=context))
        with patch.dict("sys.modules", {"psycopg": driver,
                                      "psycopg.rows": SimpleNamespace(dict_row=object())}):
            with self.assertRaisesRegex(generator.Closed, reason):
                generator.snapshot("postgresql://unit:UNIT_TEST_PASSWORD@ep-test.neon.tech/neondb?sslmode=require",
                                   None, {}, expected_host="ep-test.neon.tech")
        self.assertEqual(driver.connect.call_args.kwargs["options"], "-c default_transaction_read_only=on")
        statements = [call.args[0] for call in cn.execute.call_args_list]
        self.assertEqual(statements[0], "BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        self.assertEqual(statements[-1], "ROLLBACK")
        return statements

    def test_snapshot_rejects_dml_create_escalation_before_corpus(self):
        meta = {"read_only": "on", "isolation": "repeatable read", "can_insert": False}
        good = {key: False for key in generator.RISKS}
        for risk in generator.RISKS:
            with self.subTest(risk=risk):
                statements = self.snapshot_rejection(meta, good | {risk: True},
                                                     "READ_ONLY_ROLE_HAS_DML_DDL_OR_ESCALATION")
                self.assertEqual(len(statements), 4)
                self.assertEqual(statements[2], generator.ROLE_SQL)

    def test_snapshot_independently_rejects_unsafe_transaction_or_insert(self):
        meta = {"read_only": "on", "isolation": "repeatable read", "can_insert": False}
        good = {key: False for key in generator.RISKS}
        for unsafe in ({"read_only": "off"}, {"isolation": "read committed"}, {"can_insert": True}):
            with self.subTest(unsafe=unsafe):
                statements = self.snapshot_rejection(meta | unsafe, good, "READ_ONLY_SNAPSHOT_NOT_PROVEN")
                self.assertEqual(len(statements), 3)
                self.assertNotIn(generator.ROLE_SQL, statements)


if __name__ == "__main__":
    unittest.main(verbosity=2)
