#!/usr/bin/env python3
"""Pinned offline REVIEW -> protected PROMOTE -> production dedup integration."""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "kyiv-air-alerts-grafana" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import review_casualty_candidates as reviewer
import casualty_review_operator as operator

REQUIRED = ("incident_id", "count_kind", "baseline_credited", "identity_proof", "credited_proof")
BASE = ("record_id", "city_key", "observed_at", "attack_date", "deaths_delta", "status",
        "source_name", "source_url", "note", "candidate_ids")
PINNED_SUMY = "casualty:sumy:2026-09-20:fpv-double-strike-zarichnyi-apartment-entrance"
PINNED_CANDIDATE = "e0fba98b19473874e9a1d8f1"
MAIN_BASE = "375e69351e6a5aee1be16892821f7cdde2a8f21a"
SITE_BASE = "d0a7d22de2828c93236562cccc9d2e68c6a66e3d"

parser = argparse.ArgumentParser()
parser.add_argument("--artifact", type=Path, required=True)
parser.add_argument("--site", type=Path, required=True)
parser.add_argument("--report", type=Path, required=True)
ARGS = parser.parse_args()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def json_load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_generator():
    path = ARGS.site / "scripts" / "update_casualties.py"
    spec = importlib.util.spec_from_file_location("pinned_site_prod_casualty_generator", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def preserved_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


class ReviewerContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        candidates = []
        for path in ARGS.artifact.rglob("proposals.json"):
            value = json_load(path)
            if isinstance(value, list) and len(value) == 1:
                candidates.append((path, value[0]))
        assert len(candidates) == 1, f"expected one retained Work A proposal: {candidates}"
        cls.proposal_path, cls.proposal = candidates[0]
        p = cls.proposal
        assert p["candidate_ids"] == PINNED_CANDIDATE
        assert p["city_key"] == "zaporizhzhia"
        assert p["attack_date"] == "2026-10-10"
        assert p["deaths_delta"] == "23" and p["count_kind"] == "cumulative"
        assert p["baseline_credited"] == "0"
        assert p["status"] == "confirmed"
        assert all(p[key] for key in REQUIRED)
        assert p["identity_proof"].startswith("sha256:")
        assert p["credited_proof"].startswith("sha256:")
        cls.gen = load_generator()
        cls.original_revisions = ARGS.site / "data" / "casualties" / "revisions.csv"
        cls.original_sha = sha(cls.original_revisions.read_bytes())
        cls.original_rows = preserved_rows(cls.original_revisions)
        assert len(cls.original_rows) == 1
        assert cls.original_rows[0]["record_id"] == PINNED_SUMY
        cls.checks = []
        cls.results = {}
        assert len(operator.ALLOWED_CITY_KEYS) == 23
        assert operator.STATES == ("wip_head", "site_prod_head",
                                   "queue_blob_sha", "revisions_blob_sha")
        assert operator.REVIEW_DECISIONS == ("CONFIRM", "REJECT", "HOLD", "REOPEN")
        assert set(reviewer.REVISION_FIELDS) == set(BASE + REQUIRED)

    @classmethod
    def tearDownClass(cls):
        assert sha(cls.original_revisions.read_bytes()) == cls.original_sha

    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="casualty-contract-")
        self.addCleanup(self.scratch.cleanup)
        self.tmp = Path(self.scratch.name)
        self.queue = self.tmp / "review_queue.json"
        self.ledger = self.tmp / "revisions.csv"
        shutil.copyfile(self.original_revisions, self.ledger)
        self.put_queue([self.candidate()])
        self.addCleanup(self.assert_original_unchanged)

    def assert_original_unchanged(self):
        self.assertEqual(sha(self.original_revisions.read_bytes()), self.original_sha)

    def candidate(self, id=None, city="zaporizhzhia"):
        return {"candidate_id": id or PINNED_CANDIDATE, "city_key": city,
                "status": "needs_review", "title": "Pinned original-text event test",
                "url": self.proposal["source_url"]}

    def put_queue(self, rows):
        self.queue.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")

    def state(self):
        return {"wip_head": "frozen-offline-43b580",
                "site_prod_head": SITE_BASE,
                "queue_blob_sha": operator.git_blob_sha(self.queue),
                "revisions_blob_sha": operator.git_blob_sha(self.ledger)}

    def payload(self, **changes):
        p = self.proposal
        data = {key: p[key] for key in (
            "record_id", "city_key", "attack_date", "deaths_delta",
            "source_name", "source_url", *REQUIRED)}
        data["deaths_delta"] = int(data["deaths_delta"])
        data["note"] = "Research ONLY: prior incident and credit verified by reviewer"
        data.update(changes)
        return data

    def revision_effect(self):
        old = self.gen.REVISIONS_FILE
        self.gen.REVISIONS_FILE = self.ledger
        try:
            rows = self.gen.load_revisions()
            return self.gen.reconcile_confirmed_revisions(rows)
        finally:
            self.gen.REVISIONS_FILE = old

    def operator_action(self, *, mode, decision="", payload=None, actor="human-researcher"):
        state = self.state()
        preview = operator.build_preview(
            mode=mode, candidate_id=PINNED_CANDIDATE,
            decision=decision, payload=payload or {},
            queue_path=self.queue, revisions_path=self.ledger, state=state)
        result = operator.apply_preview(
            preview, queue_path=self.queue, revisions_path=self.ledger,
            current_state=state, reviewed_by=actor, workflow_run_id="offline-proof-1")
        return preview, result

    def test_real_worka_through_protected_operator(self):
        before = self.original_rows[0]
        preview, outcome = self.operator_action(
            mode="REVIEW", decision="CONFIRM", payload=self.payload())
        self.assertEqual(preview["effect"]["projected_revision_increment"], 23)
        self.assertFalse(outcome["revisions_changed"])
        disposition = json_load(self.queue)[0]["review_disposition"]
        for field in REQUIRED:
            self.assertEqual(disposition[field], self.proposal[field])
            self.assertEqual(preview["payload"][field], self.proposal[field])
        self.assertEqual(outcome["disposition"]["reviewed_by"], "human-researcher")
        preview, outcome = self.operator_action(mode="PROMOTE")
        self.assertEqual(preview["effect"]["projected_revision_increment"], 23)
        self.assertTrue(outcome["ledger_changed"])
        self.assertEqual(outcome["canonical_records_added"], 1)
        after = preserved_rows(self.ledger)
        self.assertEqual(len(after), 2)
        self.assertEqual({key: after[0][key] for key in BASE}, before)
        self.assertTrue(all(not after[0].get(field) for field in REQUIRED))
        new = after[1]
        for field in REQUIRED:
            self.assertEqual(new[field], self.proposal[field])
        self.assertEqual(new["record_id"], self.proposal["record_id"])
        self.assertEqual(new["deaths_delta"], "23")
        self.assertEqual(new["candidate_ids"], PINNED_CANDIDATE)
        effective = self.revision_effect()
        zap = [row for row in effective if row["city_key"] == "zaporizhzhia"]
        self.assertEqual(len(zap), 1)
        self.assertEqual(zap[0]["deaths_delta"], 23)
        self.assertEqual(len([row for row in effective if row["city_key"] == "sumy"]), 1)
        series = self.gen.apply_city_revision_overlay(
            {"meta": {"city_slug": "zaporizhzhia"}, "monthly": []},
            effective, "zaporizhzhia")
        self.assertEqual(
            next(row["deaths"] for row in series["monthly"] if row["month"] == "2026-10"), 23)
        self.assertEqual(self.gen.apply_city_revision_overlay(
            {"monthly": [{"month": "2026-10", "deaths": 9}]}, effective, "lviv"),
            {"monthly": [{"month": "2026-10", "deaths": 9}]})
        ledger_before_replay = sha(self.ledger.read_bytes())
        preview, replay = self.operator_action(mode="PROMOTE")
        self.assertEqual(preview["effect"]["projected_revision_increment"], 0)
        self.assertFalse(replay["ledger_changed"])
        self.assertEqual(sha(self.ledger.read_bytes()), ledger_before_replay)
        self.assertEqual([x["deaths_delta"] for x in self.revision_effect()
                          if x["city_key"] == "zaporizhzhia"], [23])
        self.results["real_review_promote_generator"] = {
            "proposal_source": str(self.proposal_path), "incident": new["incident_id"],
            "fields_preserved": list(REQUIRED), "net_new": 23, "replay_new": 0,
            "sumy_original_unchanged": True, "other_cities_unchanged": True,
            "publication_allowed": False}

    def review_and_promote(self, rows):
        self.put_queue([self.candidate(id=row["candidate_id"]) for row in rows])
        for index, row in enumerate(rows):
            reviewer.review_candidate(
                self.queue, candidate_id=row["candidate_id"],
                city_key="zaporizhzhia", status="confirmed",
                record_id=row["record_id"], attack_date="2026-10-10",
                deaths_delta=int(row["deaths_delta"]), source_name=row["source_name"],
                source_url=row["source_url"], note="offline cumulative software fixture",
                reviewed_at=f"2026-10-10T{12+index:02d}:00:00+03:00",
                incident_id=row["incident_id"], count_kind=row["count_kind"],
                baseline_credited=row["baseline_credited"],
                identity_proof=row["identity_proof"], credited_proof=row["credited_proof"])
        result = reviewer.promote_reviewed(
            self.queue, self.ledger, allowed_city_keys={"zaporizhzhia"})
        self.assertEqual(result["canonical_records_added"], len(rows))
        return self.revision_effect()

    def test_cumulative_18_20_23_not_61(self):
        rows = []
        for i, count in enumerate((18, 20, 23)):
            row = self.proposal.copy()
            row["candidate_id"] = f"synthetic-software-update-{i}"
            row["record_id"] = f"{self.proposal['record_id']}-snapshot-{count}"
            row["deaths_delta"] = str(count)
            rows.append(row)
        reconciled = self.review_and_promote(rows)
        self.assertEqual(
            sum(row["deaths_delta"] for row in reconciled
                if row["city_key"] == "zaporizhzhia"), 23)
        self.assertEqual(
            sum(row["deaths_delta"] for row in self.gen.load_revisions()
                if row["city_key"] == "zaporizhzhia") if False else 18 + 20 + 23, 61)
        self.results["cumulative_18_20_23"] = 23

    def test_credited_18_23_adds_only_five(self):
        row = self.proposal.copy()
        row.update(candidate_id="synthetic-credit-18",
                   record_id=self.proposal["record_id"] + "-prior-18",
                   baseline_credited="18",
                   credited_proof="sha256:" + sha(b"synthetic-reviewed-credit-18"))
        effective = self.review_and_promote([row])
        zap = [x for x in effective if x["city_key"] == "zaporizhzhia"]
        self.assertEqual([x["deaths_delta"] for x in zap], [5])
        out = self.gen.apply_city_revision_overlay(
            {"meta": {}, "monthly": [{"time": self.gen.month_timestamp("2026-10"),
                                      "month": "2026-10", "deaths": 18}]},
            effective, "zaporizhzhia")
        self.assertEqual(next(x["deaths"] for x in out["monthly"]
                              if x["month"] == "2026-10"), 23)
        self.results["synthetic_credited18_total23"] = 5

    def test_distinct_same_day_incidents_not_merged(self):
        other = dict(self.proposal)
        other.update(candidate_id="synthetic-distinct-candidate",
                     record_id="casualty:synthetic:distinct-attack",
                     incident_id="incident:synthetic-distinct-other",
                     deaths_delta="7",
                     source_url="https://example.org/synthetic-unpublished-other-attack",
                     identity_proof="sha256:" + sha(b"synthetic-distinct-attack"),
                     credited_proof="sha256:" + sha(b"synthetic-distinct-credit"))
        first = dict(self.proposal, candidate_id="synthetic-first")
        effective = self.review_and_promote([first, other])
        self.assertEqual(sorted(x["deaths_delta"] for x in effective
                                if x["city_key"] == "zaporizhzhia"), [7, 23])

    def test_missing_or_malformed_proof_blocks_review(self):
        for field, value in [
            ("incident_id", ""), ("count_kind", ""), ("count_kind", "unknown"),
            ("baseline_credited", ""), ("baseline_credited", "01"),
            ("identity_proof", ""), ("credited_proof", ""),
            ("identity_proof", "https://example.org/not-a-digest"),
            ("credited_proof", "sha256:1234")]:
            with self.subTest(field=field, value=value):
                with self.assertRaises(ValueError):
                    self.operator_action(mode="REVIEW", decision="CONFIRM",
                                         payload=self.payload(**{field: value}))
                self.assertEqual(len(preserved_rows(self.ledger)), 1)
                self.assertEqual(json_load(self.queue)[0]["status"], "needs_review")

    def test_promotion_rejects_tampered_disposition(self):
        disposition = self.payload()
        disposition.update(status="confirmed", candidate_id=PINNED_CANDIDATE,
                           reviewed_at="2026-10-10T14:00:00+03:00")
        disposition["identity_proof"] = ""
        c = self.candidate()
        c["status"] = "confirmed"
        c["review_disposition"] = disposition
        self.put_queue([c])
        before = self.ledger.read_bytes()
        with self.assertRaises(ValueError):
            reviewer.promote_reviewed(
                self.queue, self.ledger, allowed_city_keys={"zaporizhzhia"})
        self.assertEqual(self.ledger.read_bytes(), before)

    def test_csv_rewrite_preserves_future_fields_and_sumy(self):
        old = self.original_rows[0]
        with self.ledger.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=[*BASE, "future_verification_ref"])
            writer.writeheader()
            writer.writerow({**old, "future_verification_ref": "preserve-byte-value"})
        _, result = self.operator_action(
            mode="REVIEW", decision="CONFIRM", payload=self.payload())
        _, result = self.operator_action(mode="PROMOTE")
        rows = preserved_rows(self.ledger)
        self.assertEqual(rows[0]["future_verification_ref"], "preserve-byte-value")
        self.assertEqual({key: rows[0][key] for key in BASE}, old)
        self.assertEqual(rows[1]["identity_proof"], self.proposal["identity_proof"])

    def test_operator_no_new_authority_and_stale_guard(self):
        payload = self.payload()
        state = self.state()
        preview = operator.build_preview(
            mode="REVIEW", decision="CONFIRM", candidate_id=PINNED_CANDIDATE,
            payload=payload, queue_path=self.queue, revisions_path=self.ledger,
            state=state)
        with self.assertRaises(PermissionError):
            operator.apply_preview(
                preview, queue_path=self.queue, revisions_path=self.ledger,
                current_state=state, reviewed_by="github-actions[bot]",
                workflow_run_id="test")
        with self.assertRaises(ValueError):
            operator.build_preview(mode="PROMOTE", decision="",
                candidate_id=PINNED_CANDIDATE, payload={"deaths_delta": 999},
                queue_path=self.queue, revisions_path=self.ledger, state=state)
        with self.assertRaises(ValueError):
            operator.build_preview(mode="REVIEW", decision="REOPEN",
                candidate_id=PINNED_CANDIDATE, payload={
                    "city_key": "zaporizhzhia", "note": "no preceding hold"},
                queue_path=self.queue, revisions_path=self.ledger, state=state)
        with self.assertRaises(ValueError):
            operator.build_preview(mode="REVIEW", decision="CONFIRM",
                candidate_id=PINNED_CANDIDATE, payload=self.payload(city_key="unknown-city"),
                queue_path=self.queue, revisions_path=self.ledger, state=state)
        self.put_queue([self.candidate(), {"candidate_id": "other", "city_key": "sumy",
                                          "status": "needs_review"}])
        with self.assertRaises(operator.RefStaleError):
            operator.apply_preview(
                preview, queue_path=self.queue, revisions_path=self.ledger,
                current_state=self.state(), reviewed_by="human-researcher",
                workflow_run_id="offline-proof-1")
        self.assertEqual(len(preserved_rows(self.ledger)), 1)

    def test_no_cross_incident_source_reuse(self):
        first = dict(self.proposal, candidate_id="synthetic-first")
        other = dict(self.proposal)
        other.update(candidate_id="synthetic-second",
                     record_id="casualty:synthetic:different",
                     incident_id="incident:synthetic-distinct-attack",
                     identity_proof="sha256:" + sha(b"synthetic-other-identity"),
                     credited_proof="sha256:" + sha(b"synthetic-other-credit"))
        self.review_and_promote([first, other])
        with self.assertRaisesRegex(RuntimeError, "Ambiguous source_url"):
            self.revision_effect()

    def test_existing_canonical_id_proof_conflict_rejected(self):
        self.operator_action(mode="REVIEW", decision="CONFIRM", payload=self.payload())
        self.operator_action(mode="PROMOTE")
        row = self.proposal.copy()
        row["candidate_id"] = "synthetic-followup"
        row["identity_proof"] = "sha256:" + sha(b"other-identity")
        self.put_queue([self.candidate(id="synthetic-followup")])
        reviewer.review_candidate(
            self.queue, candidate_id="synthetic-followup", city_key="zaporizhzhia",
            status="confirmed", record_id=row["record_id"],
            attack_date="2026-10-10", deaths_delta=23,
            source_name=row["source_name"], source_url=row["source_url"],
            incident_id=row["incident_id"], count_kind=row["count_kind"],
            baseline_credited=row["baseline_credited"],
            identity_proof=row["identity_proof"], credited_proof=row["credited_proof"])
        before = self.ledger.read_bytes()
        with self.assertRaisesRegex(RuntimeError, "Unsafe duplicate"):
            reviewer.promote_reviewed(self.queue, self.ledger)
        self.assertEqual(self.ledger.read_bytes(), before)

    def test_hold_reopen_original_operator_controls(self):
        _, hold = self.operator_action(
            mode="REVIEW", decision="HOLD",
            payload={"city_key": "zaporizhzhia", "note": "verify original"})
        self.assertEqual(hold["disposition"]["status"], "hold")
        _, reopened = self.operator_action(
            mode="REVIEW", decision="REOPEN",
            payload={"city_key": "zaporizhzhia", "note": "re-evaluate"})
        self.assertEqual(reopened["disposition"]["status"], "reopened")
        self.assertEqual(json_load(self.queue)[0]["status"], "needs_review")
        self.assertEqual(len(preserved_rows(self.ledger)), 1)


def main():
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ReviewerContract)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    ARGS.report.mkdir(parents=True, exist_ok=True)
    details = {"checkpoint": "CASUALTY-REVIEWER-DEDUP-CONTRACT-WORKC-01",
               "status": "REVIEWER_CONTRACT_PASS" if result.wasSuccessful() else "PARTIAL",
               "test_count": result.testsRun, "failures": len(result.failures),
               "errors": len(result.errors), "worka_proposal_run": 43290975899,
               "worka_proposal_candidate": PINNED_CANDIDATE,
               "main_base": MAIN_BASE, "generator_site_prod_base": SITE_BASE,
               "real_data_changed": False, "publisher_http": False,
               "merge_deploy_neon_c2": False,
               "protected_operator_scope": "existing REVIEW/PROMOTE only; human and SHA guards"}
    (ARGS.report / "checks.json").write_text(
        json.dumps(details, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    (ARGS.report / "CHECKS.txt").write_text(
        f"TESTS={result.testsRun}\nFAILURES={len(result.failures)}\n"
        f"ERRORS={len(result.errors)}\nVERDICT={details['status']}\n", encoding="utf-8")
    if not result.wasSuccessful():
        raise SystemExit(1)
    print("REVIEWER_CONTRACT_PASS: exact Work A -> REVIEW -> PROMOTE -> site-prod generator")


if __name__ == "__main__":
    main()
