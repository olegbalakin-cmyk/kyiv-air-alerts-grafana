"""PostgreSQL 18 exact-migration and independent process/Git-race checks. Isolated only."""
import concurrent.futures
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import psycopg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from db_phase1_core import CANONICALIZATION_VERSION, legacy_episode_id
from multicity_canonical_postgres import persist_canonical_episodes

DSN = os.environ.get("C2_TEST_DATABASE_URL", "")
MIGRATION = ROOT / "db/migrations/001_phase1_core.sql"


def corpus(start_index, count):
    t0 = datetime(2026, 10, 27, tzinfo=timezone.utc)
    result = []
    for j in range(start_index, start_index + count):
        a = t0 + timedelta(minutes=30 * j)
        b = a + timedelta(minutes=12)
        city = f"synthetic-city-{j % 23:02d}"
        result.append(dict(city_key=city, alert_type="AIR",
                           start_at=a, end_at=b, episode_state="closed",
                           canonicalization_version=CANONICALIZATION_VERSION,
                           legacy_episode_id=legacy_episode_id(city, a, b)))
    return result


def write_process(start_index, count, fail=False):
    import psycopg
    with psycopg.connect(DSN) as con:
        return persist_canonical_episodes(
            con, corpus(start_index, count),
            provenance={"run_kind": "multicity_canonical_shadow", "parameters": {}},
            db_branch="isolated-pg18-exact-migration",
            force_failure_after_new=2 if fail else None)


def run(*args, cwd=None, check=True):
    return subprocess.run(args, cwd=cwd, check=check, capture_output=True, text=True)


class ReleaseStage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        u = urlparse(DSN)
        if u.scheme not in ("postgresql", "postgres") or u.hostname != "127.0.0.1" or u.path != "/c2_test":
            raise AssertionError("only 127.0.0.1/c2_test is allowed")
        with psycopg.connect(DSN, autocommit=True) as con:
            con.execute("DROP VIEW IF EXISTS current_ingestion_checkpoints")
            con.execute("DROP TABLE IF EXISTS ingestion_checkpoints, alert_episode_sources, alert_episodes, ingestion_runs CASCADE")
            con.execute(MIGRATION.read_text(encoding="utf-8"))
            n = con.execute("""SELECT COUNT(*) FROM information_schema.tables
                WHERE table_schema='public' AND table_name IN
                ('ingestion_runs','alert_episodes','alert_episode_sources','ingestion_checkpoints')""").fetchone()[0]
            assert n == 4, n
            cls.server = con.execute("SHOW server_version_num").fetchone()[0]
            assert cls.server.startswith("18"), cls.server

    def setUp(self):
        with psycopg.connect(DSN, autocommit=True) as c:
            c.execute("TRUNCATE ingestion_checkpoints, alert_episode_sources, alert_episodes, ingestion_runs CASCADE")

    def counts(self):
        with psycopg.connect(DSN) as c:
            return (c.execute("SELECT count(*) FROM alert_episodes").fetchone()[0],
                    c.execute("SELECT count(*) FROM ingestion_runs WHERE status='succeeded'").fetchone()[0])

    def test_01_exact_migration_and_referential_integrity(self):
        result = write_process(0, 23)
        self.assertEqual(result["episodes_inserted"], 23)
        self.assertEqual(self.counts(), (23, 1))
        with psycopg.connect(DSN) as c:
            self.assertEqual(c.execute("""SELECT count(*) FROM alert_episodes a
                JOIN ingestion_runs i ON i.run_id=a.created_by_run_id
                WHERE i.status='succeeded'""").fetchone()[0], 23)

    def test_02_identical_concurrent_processes_are_idempotent(self):
        with concurrent.futures.ProcessPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(write_process, 0, 23) for _ in range(2)]
            receipts = [f.result(timeout=50) for f in futures]
        self.assertEqual(sorted(r["status"] for r in receipts), ["already_persisted", "persisted"])
        self.assertEqual(self.counts(), (23, 1))

    def test_03_partially_overlapping_batches(self):
        with concurrent.futures.ProcessPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(write_process, 0, 23), pool.submit(write_process, 10, 23)]
            receipts = [f.result(timeout=50) for f in futures]
        self.assertEqual(self.counts(), (33, 2))
        self.assertEqual(sum(r["episodes_inserted"] for r in receipts), 33)

    def test_04_interrupted_transaction_retry(self):
        with self.assertRaises(Exception):
            write_process(0, 23, fail=True)
        self.assertEqual(self.counts(), (0, 0))
        self.assertEqual(write_process(0, 23)["status"], "persisted")
        self.assertEqual(self.counts(), (23, 1))

    def test_05_lost_ack_exact_retry_after_commit(self):
        self.assertEqual(write_process(0, 23)["status"], "persisted")
        # Simulate the independent worker never receiving its committed reply.
        self.assertEqual(write_process(0, 23)["status"], "already_persisted")
        self.assertEqual(self.counts(), (23, 1))

    def test_06_git_race_rejection_rebase_retry_and_integrity(self):
        with tempfile.TemporaryDirectory(prefix="c2-bare-") as tmp:
            base = Path(tmp)
            bare, first, second = base/"remote.git", base/"first", base/"second"
            run("git", "init", "--bare", str(bare))
            run("git", "clone", str(bare), str(first))
            for work in (first,):
                run("git", "config", "user.email", "c2@example.invalid", cwd=work)
                run("git", "config", "user.name", "C2 test", cwd=work)
            (first/"data").mkdir()
            (first/"data/checkpoint").write_text("0\n")
            (first/"data/canonical.json").write_text('{"episodes":23}\n')
            run("git", "add", ".", cwd=first)
            run("git", "commit", "-m", "baseline", cwd=first)
            run("git", "push", "origin", "HEAD:refs/heads/site-prod", cwd=first)
            run("git", "clone", "-b", "site-prod", str(bare), str(second))
            run("git", "config", "user.email", "c2@example.invalid", cwd=second)
            run("git", "config", "user.name", "C2 test", cwd=second)
            # First writer prepares a distinct canonical+checkpoint update.
            (first/"data/checkpoint").write_text("1\n")
            (first/"data/canonical.json").write_text('{"episodes":23,"digest":"x"}\n')
            run("git", "add", ".", cwd=first)
            run("git", "commit", "-m", "writer-one", cwd=first)
            # A second writer wins the same remote while first has not fetched.
            (second/"unrelated").write_text("second\n")
            run("git", "add", ".", cwd=second)
            run("git", "commit", "-m", "writer-two", cwd=second)
            run("git", "push", "origin", "HEAD:site-prod", cwd=second)
            rejected = run("git", "push", "origin", "HEAD:site-prod", cwd=first, check=False)
            self.assertNotEqual(rejected.returncode, 0)
            run("git", "fetch", "origin", "site-prod", cwd=first)
            run("git", "rebase", "origin/site-prod", cwd=first)
            self.assertEqual((first/"data/checkpoint").read_text(), "1\n")
            self.assertEqual(json.loads((first/"data/canonical.json").read_text())["episodes"], 23)
            run("git", "push", "origin", "HEAD:site-prod", cwd=first)
            run("git", "fetch", "origin", "site-prod", cwd=second)
            self.assertEqual(run("git", "show", "origin/site-prod:data/checkpoint", cwd=second).stdout, "1\n")
            # A competing remote checkpoint advance must not be accepted silently.
            run("git", "reset", "--hard", "origin/site-prod", cwd=second)
            (second/"data/checkpoint").write_text("2\n")
            run("git", "add", ".", cwd=second)
            run("git", "commit", "-m", "remote-checkpoint-drift", cwd=second)
            run("git", "push", "origin", "HEAD:site-prod", cwd=second)
            run("git", "fetch", "origin", "site-prod", cwd=first)
            self.assertNotEqual(run("git", "show", "origin/site-prod:data/checkpoint", cwd=first).stdout,
                                (first/"data/checkpoint").read_text())
            print("GIT_RACE: rejected_push=YES; rebase_retry=PASS; remote_drift_detected=YES")


    def test_07_publication_snapshot_detects_post_rebase_mutation(self):
        from verify_c2_publication_snapshot import FILES, digest
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            for name in FILES:
                p = base / name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text("verified dataset", encoding="utf-8")
            baseline = digest(base)
            self.assertEqual(digest(base), baseline)
            (base / "data/dashboard_data.json").write_text("changed after rebase", encoding="utf-8")
            self.assertNotEqual(digest(base), baseline)

    def test_08_durable_pg_readback_detects_missing_canonical_parent(self):
        from db_phase1_core import canonical_json
        from verify_c2_release_dataset import verify
        import hashlib
        rows = [{**r, "start_at": r["start_at"].isoformat(),
                 "end_at": r["end_at"].isoformat()} for r in corpus(0, 23)]
        self.assertEqual(write_process(0, 23)["status"], "persisted")
        keys = [r["city_key"] for r in rows]
        # Canonical ordering is exact; one source episode per city.
        dashboard = {"multicity_meta": {"production_city_keys": keys}}
        serial = {
            "canonicalization_version": CANONICALIZATION_VERSION,
            "production_city_keys": keys, "episodes": rows,
        }
        digest_value = hashlib.sha256(canonical_json(serial).encode()).hexdigest()
        payload = {
            "canonicalization_version": CANONICALIZATION_VERSION,
            "cities": {r["city_key"]: {"episode_count": 1, "episodes": [r]} for r in rows},
        }
        receipt = {"status": "succeeded", "canonical_episode_count": 23,
                   "corpus_sha256": digest_value}
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            for name, value in (("payload", payload), ("dashboard", dashboard),
                                ("receipt", receipt)):
                (base / name).write_text(json.dumps(value, default=str), encoding="utf-8")
            with psycopg.connect(DSN) as c:
                self.assertEqual(verify(c, base/"payload", base/"dashboard",
                                        base/"receipt")["canonical_rows"], 23)
                c.execute("DELETE FROM alert_episodes WHERE legacy_episode_id=%s",
                          (rows[0]["legacy_episode_id"],))
                c.commit()
                with self.assertRaises(ValueError):
                    verify(c, base/"payload", base/"dashboard", base/"receipt")


if __name__ == "__main__":
    unittest.main()
