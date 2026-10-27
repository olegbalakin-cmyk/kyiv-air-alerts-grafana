#!/usr/bin/env python3
"""C2 research tests: real disposable local PostgreSQL; never contact Neon.

Requires C2_TEST_DATABASE_URL pointing to 127.0.0.1/c2_test. Intentionally
uses a reduced test schema, not a claim of exact Neon schema equivalence.
"""
from __future__ import annotations

import contextlib
import copy
import io
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock
from urllib.parse import urlparse

import psycopg
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import db_phase1_core as core
import multicity_canonical_postgres as writer
import multicity_canonical_shadow as shadow
import multicity_shadow_payload as payload_builder
from verify_multicity_canonical_receipt import CanonicalReceiptError, verify_receipt

REPO_ROOT = ROOT.parent
BLUEPRINT = REPO_ROOT / "research/c2_fail_closed_2026_10_27/update-netlify-site.candidate.yml"


class SyntheticAlert:
    def __init__(self, start: datetime, end: datetime) -> None:
        self.start = start
        self.end = end


class FailingCommitConnection:
    """Transparent adapter for deliberately interrupted local test transactions."""

    def __init__(self, real: psycopg.Connection, *, after_commit: bool) -> None:
        self.real = real
        self.after_commit = after_commit

    def cursor(self):
        return self.real.cursor()

    def commit(self):
        if self.after_commit:
            self.real.commit()  # Durable COMMIT, but client never sees ACK.
            raise RuntimeError("synthetic commit acknowledgement lost")
        raise RuntimeError("synthetic pre-commit failure")

    def rollback(self):
        return self.real.rollback()

    def close(self):
        return self.real.close()


class C2PostgresIsolation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.DSN = os.environ.get("C2_TEST_DATABASE_URL", "")
        u = urlparse(cls.DSN)
        if u.scheme not in {"postgresql", "postgres"} or u.hostname != "127.0.0.1" or u.path != "/c2_test":
            raise AssertionError("C2_TEST_DATABASE_URL must target only 127.0.0.1/c2_test")
        with psycopg.connect(cls.DSN, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS ingestion_runs (
                        run_id uuid PRIMARY KEY, run_kind text NOT NULL,
                        source_key text, city_key text, workflow_repository text,
                        workflow_name text, workflow_ref text, workflow_sha text,
                        input_repository text, input_ref text, input_sha text,
                        github_run_id bigint, github_run_attempt integer,
                        db_branch text NOT NULL, schema_version text,
                        canonicalization_version text, status text NOT NULL,
                        started_at timestamptz, parameters jsonb, stats jsonb,
                        ingest_committed_at timestamptz, finished_at timestamptz
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS alert_episodes (
                        episode_uid uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                        legacy_episode_id text NOT NULL UNIQUE,
                        city_key text NOT NULL, alert_type text NOT NULL,
                        start_at timestamptz NOT NULL, end_at timestamptz NOT NULL,
                        episode_state text NOT NULL, canonicalization_version text NOT NULL,
                        created_by_run_id uuid, updated_by_run_id uuid
                    )
                """)

    def setUp(self):
        with psycopg.connect(self.DSN, autocommit=True) as conn:
            conn.execute("TRUNCATE alert_episodes, ingestion_runs")
        self.temp = tempfile.TemporaryDirectory(prefix="c2-local-")
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.dashboard = self.path / "dashboard.json"
        self.payload = self.path / "payload.json"
        self.receipt = self.path / "canonical-receipt.json"
        self.keys = [f"synthetic-city-{i:02d}" for i in range(23)]
        self.dashboard.write_text(
            json.dumps({"multicity_meta": {"production_city_keys": self.keys}}),
            encoding="utf-8",
        )
        env = {
            shadow.FLAG_ENV: "1",
            shadow.DB_ENV: self.DSN,
            shadow.BRANCH_ENV: "disposable-postgres-local",
            shadow.FAILURE_ENV: "fail_closed",
            shadow.DIAGNOSTIC_ENV: str(self.receipt),
            shadow.PAYLOAD_ENV: str(self.payload),
            shadow.DASHBOARD_ENV: str(self.dashboard),
            shadow.INPUT_REPOSITORY_ENV: "synthetic/c2-only",
            shadow.INPUT_REF_ENV: "site-prod",
            shadow.INPUT_SHA_ENV: "b" * 40,
            "GITHUB_SHA": "a" * 40,
            "GITHUB_RUN_ID": "123",
            "GITHUB_RUN_ATTEMPT": "1",
        }
        self.env_patch = mock.patch.dict(os.environ, env)
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)
        for i, key in enumerate(self.keys):
            start = datetime(2026, 10, 1, tzinfo=timezone.utc) + timedelta(hours=i)
            payload_builder.record_city_alerts(
                key, [SyntheticAlert(start, start + timedelta(minutes=15))],
                producer="synthetic-c2-test",
            )
        self.rows, keys, corpus_sha = shadow._load_corpus()
        self.assertEqual(keys, self.keys)
        self.assertEqual(len(self.rows), 23)
        self.assertEqual(len(corpus_sha), 64)

    def counts(self):
        with psycopg.connect(self.DSN) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) FROM alert_episodes")
                episodes = cur.fetchone()[0]
                cur.execute("SELECT count(*) FROM ingestion_runs WHERE status='succeeded'")
                runs = cur.fetchone()[0]
        return episodes, runs

    def diagnostic(self):
        return json.loads(self.receipt.read_text(encoding="utf-8"))

    def test_01_successful_commit_and_exact_retry(self):
        first = shadow.execute()
        self.assertEqual(first["status"], "succeeded")
        self.assertEqual(first["persistence_status"], "persisted")
        self.assertEqual(first["episodes_inserted"], 23)
        self.assertEqual(self.counts(), (23, 1))
        self.assertEqual(verify_receipt(self.receipt)["status"], "succeeded")
        second = shadow.execute()
        self.assertEqual(second["status"], "succeeded")
        self.assertEqual(second["persistence_status"], "already_persisted")
        self.assertEqual(second["episodes_inserted"], 0)
        self.assertEqual(second["episodes_existing"], 23)
        self.assertEqual(second["writes"], 0)
        verify_receipt(self.receipt)
        self.assertEqual(self.counts(), (23, 1))

    def test_02_unavailable_database_fails_without_ack(self):
        with mock.patch.object(psycopg, "connect", side_effect=psycopg.OperationalError("synthetic connection refused")):
            with contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(shadow.main(), 1)
        self.assertNotIn(self.DSN, err.getvalue())
        self.assertEqual(self.diagnostic()["status"], "failed")
        with self.assertRaises(CanonicalReceiptError):
            verify_receipt(self.receipt)
        self.assertEqual(self.counts(), (0, 0))

    def test_03_transaction_error_rolls_back_entire_batch(self):
        with psycopg.connect(self.DSN) as conn:
            with self.assertRaises(writer.ForcedMulticityFailure):
                writer.persist_canonical_episodes(
                    conn, self.rows,
                    provenance={"run_kind": "multicity_canonical_shadow", "parameters": {}},
                    db_branch="disposable-postgres-local",
                    force_failure_after_new=2,
                )
        self.assertEqual(self.counts(), (0, 0))
        self.assertEqual(shadow.execute()["persistence_status"], "persisted")
        self.assertEqual(self.counts(), (23, 1))

    def test_04_commit_rejected_before_commit_then_retry(self):
        real_connect = psycopg.connect
        def broken_connect(url):
            return FailingCommitConnection(real_connect(url), after_commit=False)
        with mock.patch.object(psycopg, "connect", side_effect=broken_connect):
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(shadow.main(), 1)
        self.assertEqual(self.diagnostic()["status"], "failed")
        with self.assertRaises(CanonicalReceiptError):
            verify_receipt(self.receipt)
        self.assertEqual(self.counts(), (0, 0))
        self.assertEqual(shadow.execute()["persistence_status"], "persisted")
        self.assertEqual(self.counts(), (23, 1))

    def test_05_lost_commit_ack_retries_without_duplicates(self):
        real_connect = psycopg.connect
        def lost_ack(url):
            return FailingCommitConnection(real_connect(url), after_commit=True)
        with mock.patch.object(psycopg, "connect", side_effect=lost_ack):
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(shadow.main(), 1)
        self.assertEqual(self.diagnostic()["status"], "failed")
        with self.assertRaises(CanonicalReceiptError):
            verify_receipt(self.receipt)
        self.assertEqual(self.counts(), (23, 1))  # PostgreSQL committed before ACK was lost.
        self.assertEqual(shadow.execute()["persistence_status"], "already_persisted")
        self.assertEqual(self.counts(), (23, 1))
        verify_receipt(self.receipt)

    def test_06_unexpected_writer_return_not_success(self):
        with mock.patch.object(writer, "persist_canonical_episodes", return_value={
            "status": "failed", "episodes_inserted": 23,
            "episodes_existing": 0, "episodes_updated": 0, "writes": 25,
            "run_id": "incorrect-false-ack",
        }):
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(shadow.main(), 1)
        self.assertEqual(self.diagnostic()["status"], "failed")
        self.assertEqual(self.counts(), (0, 0))
        with self.assertRaises(CanonicalReceiptError):
            verify_receipt(self.receipt)

    def test_07_fail_open_policy_misconfiguration_is_rejected(self):
        os.environ[shadow.FAILURE_ENV] = "fail_open"
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(shadow.main(), 1)
        self.assertEqual(self.diagnostic()["status"], "failed")
        self.assertEqual(self.counts(), (0, 0))

    def test_08_receipt_rejects_false_success_and_disabled(self):
        shadow.execute()
        good = self.diagnostic()
        for delta in (
            {"status": "failed"},
            {"status": "disabled"},
            {"failure_policy": "fail_open"},
            {"persistence_status": "failed"},
            {"city_count": 22},
            {"episodes_existing": 23},
            {"episodes_inserted": True},
            {"run_id": None},
            {"corpus_sha256": None},
            {"workflow_sha": None},
            {"input_sha": None},
            {"production_output_mutation": True},
        ):
            bad = {**copy.deepcopy(good), **delta}
            self.receipt.write_text(json.dumps(bad), encoding="utf-8")
            with self.subTest(delta=delta):
                with self.assertRaises(CanonicalReceiptError):
                    verify_receipt(self.receipt)
        self.receipt.unlink()
        with self.assertRaises(FileNotFoundError):
            verify_receipt(self.receipt)

    def test_09_cli_success_codes_and_receipt(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(shadow.main(), 0)
        self.assertEqual(json.loads(out.getvalue())["status"], "succeeded")
        self.assertEqual(verify_receipt(self.receipt)["episodes_inserted"], 23)
        self.assertEqual(self.counts(), (23, 1))


class C2CandidateWorkflowGuard(unittest.TestCase):
    def test_10_canonical_gate_precedes_every_site_prod_push(self):
        w = yaml.safe_load(BLUEPRINT.read_text(encoding="utf-8"))
        steps = w["jobs"]["update-site"]["steps"]
        names = [x["name"] for x in steps]
        canonical = names.index("Run multicity canonical DB shadow")
        gate = names.index("Gate publication on committed canonical persistence receipt")
        qa = names.index("Verify production dataset")
        publish = names.index("Commit updated production data and verified UkraineAlarm bridge checkpoint")
        self.assertLess(canonical, gate)
        self.assertLess(gate, qa)
        self.assertLess(qa, publish)
        self.assertNotIn("Persist verified UkraineAlarm bridge checkpoint", names)
        self.assertEqual(steps[canonical]["env"][shadow.FAILURE_ENV], "fail_closed")
        bridge = names.index("Apply verified Alerts.in.ua and UkraineAlarm bridge")
        self.assertEqual(steps[bridge]["env"]["PHASE1_DB_SHADOW_FAILURE_POLICY"], "fail_open")
        self.assertIn("verify_multicity_canonical_receipt.py", steps[gate]["run"])
        pushes = [(i, s["name"]) for i, s in enumerate(steps) if "git push " in str(s.get("run", ""))]
        self.assertEqual(pushes, [(publish, names[publish])])
        script = steps[publish]["run"]
        self.assertIn("verify_remote_bridge", script)
        self.assertIn("git rebase origin/site-prod", script)
        self.assertIn("git add kyiv-air-alerts-grafana/data", script)
        self.assertIn("git push origin HEAD:site-prod", script)
        self.assertEqual(w["jobs"]["update-site"]["steps"][0]["with"]["ref"], "site-prod")


if __name__ == "__main__":
    unittest.main()
