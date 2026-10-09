#!/usr/bin/env python3
"""29 synthetic operator acceptance checks. No production refs or real data."""
import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from casualty_review_operator import (
    ALLOWED_CITY_KEYS, RefStaleError, apply_preview, build_preview, git_blob_sha,
    render_summary,
)
from review_casualty_candidates import REVISION_FIELDS, load_queue, load_revision_rows

C = "c-one"
OTHER = "c-two"
URL = "https://example.org/a"
# Frozen production route membership: site-prod at e71412503f27c3301d30bff841e449c901138e33.
# Authority: master_20cities_manifest.json (20) + cities/{kherson,odesa,zaporizhzhia}/manifest.json (3).
EXPECTED_PRODUCTION_CITY_KEYS = frozenset({
    "cherkasy", "chernihiv", "chernivtsi", "dnipro",
    "ivano-frankivsk", "kharkiv", "kherson", "khmelnytskyi",
    "kropyvnytskyi", "kyiv", "lutsk", "lviv",
    "mykolaiv", "odesa", "poltava", "rivne",
    "sevastopol", "sumy", "ternopil", "uzhhorod",
    "vinnytsia", "zaporizhzhia", "zhytomyr",
})
def candidate(cid=C, city="sumy", status="needs_review", title="S"):
    return dict(candidate_id=cid, city_key=city, status=status, url=URL, title=title,
                snippet="synthetic", source="test", published_at="2026-10-01")
def payload(record="casualty:sumy:2026-10-01:synth", delta=1):
    return dict(city_key="sumy", note="confirmed against source", record_id=record,
                attack_date="2026-10-01", deaths_delta=delta, source_name="Source",
                source_url=URL)

class OperatorAcceptance(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.queue = self.dir / "queue.json"
        self.rev = self.dir / "revisions.csv"
        self.dashboard = self.dir / "dashboard_data.json"
        self.baseline = self.dir / "baseline_monthly.csv"
        self.dashboard.write_text('{"protected":"unchanged"}', encoding="utf-8")
        self.baseline.write_text("month,deaths\n2026-09,20\n", encoding="utf-8")
        self.write_queue([candidate()])
        self.write_revisions([])
        self.immutable = (self.dashboard.read_bytes(), self.baseline.read_bytes())

    def write_queue(self, values):
        self.queue.write_text(json.dumps(values), encoding="utf-8")
    def write_revisions(self, rows):
        with self.rev.open("w", newline="", encoding="utf-8") as out:
            writer = csv.DictWriter(out, fieldnames=REVISION_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
    def state(self):
        return dict(wip_head="synthetic-wip-commit", site_prod_head="synthetic-prod-commit",
                    queue_blob_sha=git_blob_sha(self.queue),
                    revisions_blob_sha=git_blob_sha(self.rev))
    def preview(self, mode="REVIEW", decision="CONFIRM", value=None, cid=C):
        return build_preview(mode=mode, decision=decision, candidate_id=cid,
                             payload=payload() if value is None else value,
                             queue_path=self.queue, revisions_path=self.rev,
                             state=self.state())
    def apply(self, pre, state=None):
        return apply_preview(pre, queue_path=self.queue, revisions_path=self.rev,
                             current_state=state or self.state(),
                             reviewed_by="synthetic-human", workflow_run_id="synthetic-1")
    def confirmed(self, cid=C, record=None, **kwargs):
        p = payload(record=record) if record else payload()
        p.update(kwargs)
        self.apply(self.preview(value=p, cid=cid))
    def promote(self, cid=C):
        pre = self.preview(mode="PROMOTE", decision="", value={}, cid=cid)
        return self.apply(pre)
    def assert_unchanged(self):
        self.assertEqual(self.dashboard.read_bytes(), self.immutable[0])
        self.assertEqual(self.baseline.read_bytes(), self.immutable[1])

    def test_01_inspect_no_mutation(self):
        q, r = self.queue.read_bytes(), self.rev.read_bytes()
        p = self.preview(mode="INSPECT", decision="", value={})
        self.assertTrue(p["evidence"]); self.assertEqual(self.queue.read_bytes(), q)
        self.assertEqual(self.rev.read_bytes(), r)
    def test_02_confirm_one_disposition(self):
        self.confirmed()
        c = load_queue(self.queue)[0]
        self.assertEqual(c["status"], "confirmed")
        self.assertEqual(c["review_disposition"]["reviewed_by"], "synthetic-human")
        self.assertEqual(c["review_disposition"]["workflow_run_id"], "synthetic-1")
        self.assertEqual(load_revision_rows(self.rev), [])
    def test_03_reject_no_revision(self):
        self.apply(self.preview(decision="REJECT", value={"city_key":"sumy", "note":"wrong scope"}))
        self.assertEqual(load_queue(self.queue)[0]["status"],"rejected")
        self.assertEqual(load_revision_rows(self.rev), [])
    def test_04_hold_no_revision(self):
        self.apply(self.preview(decision="HOLD", value={"city_key":"sumy", "note":"insufficient evidence"}))
        self.assertEqual(load_queue(self.queue)[0]["status"],"hold")
        self.assertEqual(load_revision_rows(self.rev), [])
    def test_05_reopen_preserves_hold(self):
        self.apply(self.preview(decision="HOLD", value={"city_key":"sumy", "note":"hold reason"}))
        self.apply(self.preview(decision="REOPEN", value={"city_key":"sumy", "note":"new sources"}))
        c=load_queue(self.queue)[0]
        self.assertEqual(c["status"], "needs_review")
        self.assertEqual(c["review_history"][0]["note"], "hold reason")
    def test_06_confirmed_re_review_refused(self):
        self.confirmed()
        with self.assertRaises(ValueError): self.preview()
    def test_07_rejected_re_review_refused(self):
        self.apply(self.preview(decision="REJECT", value={"city_key":"sumy", "note":"reason"}))
        with self.assertRaises(ValueError): self.preview()
    def test_08_stale_queue_blob(self):
        pre=self.preview()
        self.write_queue([candidate(title="changed")])
        with self.assertRaises(RefStaleError): self.apply(pre, pre["state"])
    def test_09_candidate_status_changed(self):
        pre=self.preview()
        self.write_queue([candidate(status="hold")])
        with self.assertRaises(RefStaleError): self.apply(pre)
    def test_10_stale_revisions_blob(self):
        pre=self.preview()
        with self.rev.open("a") as out: out.write("\n")
        with self.assertRaises(RefStaleError): self.apply(pre, pre["state"])
    def test_11_invalid_city(self):
        with self.assertRaises(ValueError): self.preview(value={**payload(),"city_key":"fictional"})
        self.write_queue([candidate(city="fictional")])
        with self.assertRaisesRegex(ValueError, "Unknown production city_key"):
            self.preview(value={**payload(), "city_key": "fictional"})
    def test_12_invalid_attack_date(self):
        with self.assertRaises(ValueError): self.preview(value={**payload(),"attack_date":"2026-99-77"})
    def test_13_zero_deaths(self):
        with self.assertRaises(ValueError): self.preview(value={**payload(),"deaths_delta":0})
    def test_14_negative_deaths(self):
        with self.assertRaises(ValueError): self.preview(value={**payload(),"deaths_delta":-1})
    def test_15_missing_url(self):
        with self.assertRaises(ValueError): self.preview(value={**payload(),"source_url":""})
    def test_16_non_http_url(self):
        with self.assertRaises(ValueError): self.preview(value={**payload(),"source_url":"file:///tmp/a"})
    def test_17_duplicate_same_canonical_zero_second_death(self):
        self.write_queue([candidate(),candidate(cid=OTHER)])
        self.confirmed()
        self.confirmed(cid=OTHER)
        first=self.promote()
        second=self.promote(cid=OTHER)
        self.assertEqual(first["canonical_records_added"],1)
        self.assertEqual(second["canonical_records_added"],0)
        self.assertEqual(len(load_revision_rows(self.rev)),1)
    def test_18_conflicting_canonical_duplicate_refused(self):
        self.write_queue([candidate(),candidate(cid=OTHER)])
        self.confirmed()
        self.confirmed(cid=OTHER, deaths_delta=2)
        self.promote()
        with self.assertRaises(ValueError): self.preview(mode="PROMOTE",decision="",value={},cid=OTHER)
        self.assertEqual(len(load_revision_rows(self.rev)),1)
    def test_19_different_id_media_duplicate_warning(self):
        self.write_queue([candidate(),candidate(cid=OTHER)])
        self.confirmed()
        self.promote()
        pre=self.preview(value=payload(record="casualty:sumy:2026-10-01:other"),cid=OTHER)
        self.assertTrue(pre["warnings"])
        self.assertEqual(load_queue(self.queue)[1]["status"],"needs_review")
    def test_20_repeated_promote_idempotent(self):
        self.confirmed(); self.promote()
        repeat=self.promote()
        self.assertFalse(repeat["ledger_changed"])
        self.assertEqual(len(load_revision_rows(self.rev)),1)
    def test_21_retry_no_duplicate(self):
        pre=self.preview()
        self.apply(pre)
        with self.assertRaises((RefStaleError, ValueError)): self.apply(pre)
        self.promote()
        self.promote()
        self.assertEqual(len(load_revision_rows(self.rev)),1)
    def test_22_no_scheduled_confirmation(self):
        path=ROOT.parent/".github/workflows/casualty-review-operator.yml"
        text=path.read_text()
        self.assertIn("workflow_dispatch:",text)
        self.assertNotIn("  schedule:",text)
        self.assertNotIn("  push:",text)
        self.assertIn("casualty-review-approval",text)
    def test_23_no_dashboard_mutation(self):
        self.confirmed(); self.promote(); self.assert_unchanged()
    def test_24_no_historical_baseline_mutation(self):
        self.apply(self.preview(decision="HOLD",value={"city_key":"sumy","note":"hold"}))
        self.assert_unchanged()
    def test_25_untrusted_text_no_shell_execution(self):
        marker=self.dir/"shell-ran"
        nasty='"; touch '+str(marker)+'; $(id) <script>alert(1)</script>'
        c=candidate(title=nasty); c["snippet"]=nasty; c["note"]=nasty
        self.write_queue([c])
        pre=self.preview(mode="INSPECT", decision="", value={})
        summary=render_summary(pre)
        self.assertIn("&lt;script&gt;",summary)
        self.assertFalse(marker.exists())
    def test_26_branch_identity_stale(self):
        pre=self.preview()
        state={**self.state(),"wip_head":"concurrent-wip"}
        with self.assertRaises(RefStaleError): self.apply(pre,state)
    def test_27_bot_rejected(self):
        pre=self.preview()
        with self.assertRaises(PermissionError):
            apply_preview(pre,queue_path=self.queue,revisions_path=self.rev,
                          current_state=self.state(),reviewed_by="github-actions[bot]",
                          workflow_run_id="1")

    def test_28_all_authoritative_23_cities_accepted(self):
        self.assertEqual(len(EXPECTED_PRODUCTION_CITY_KEYS), 23)
        for city in sorted(EXPECTED_PRODUCTION_CITY_KEYS):
            with self.subTest(city=city):
                self.write_queue([candidate(city=city)])
                request = payload(record=f"casualty:{city}:2026-10-01:synthetic")
                request["city_key"] = city
                preview = self.preview(value=request)
                self.assertEqual(preview["payload"]["city_key"], city)
                self.assertEqual(preview["effect"]["projected_revision_increment"], 1)

    def test_29_exact_production_city_allowlist(self):
        self.assertEqual(len(EXPECTED_PRODUCTION_CITY_KEYS), 23)
        self.assertEqual(len(ALLOWED_CITY_KEYS), 23)
        self.assertEqual(EXPECTED_PRODUCTION_CITY_KEYS - ALLOWED_CITY_KEYS, set())
        self.assertEqual(ALLOWED_CITY_KEYS - EXPECTED_PRODUCTION_CITY_KEYS, set())
        self.assertEqual(ALLOWED_CITY_KEYS, EXPECTED_PRODUCTION_CITY_KEYS)

if __name__=="__main__":
    unittest.main(verbosity=2)
