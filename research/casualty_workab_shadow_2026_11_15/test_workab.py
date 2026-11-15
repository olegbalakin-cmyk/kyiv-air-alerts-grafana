"""Work AB: run two actual monitor CLI cycles on scratch WIP snapshots with mocked RSS.
Fixtures and Work Z archives are not direct proof of real source availability.
No network calls to any publisher, no WIP writes or automatic casualty credits.
"""
import contextlib
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "kyiv-air-alerts-grafana" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import monitor_casualty_candidates as monitor
import casualty_workx_evidence as x
import casualty_workaa_context as aa
import casualty_workaa_offline as saved

UTC = timezone.utc
CITY = "zaporizhzhia"
BASE = datetime(2026, 11, 15, 0, 0, tzinfo=UTC)
RUN_DIR = Path(os.environ.get("WORKAB_OUT", "/tmp/workab"))
REPORTS = []

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def run_scratch(t, *, failed=None, live=False, prior=None):
    with tempfile.TemporaryDirectory(prefix="workab-shadow-") as d:
        dir = Path(d)
        source_dir = ROOT / "kyiv-air-alerts-grafana" / "data" / "casualties"
        sources = {name: source_dir / name for name in (
            "candidate_monitor_state.json", "multicity_review_queue.json",
            "candidate_monitor_last_run.json")}
        paths = {name: dir / name for name in sources}
        for name, src in sources.items():
            shutil.copyfile(src, paths[name])
        if prior:
            shutil.copyfile(prior[0], paths["candidate_monitor_state.json"])
            shutil.copyfile(prior[1], paths["multicity_review_queue.json"])
        queue_before = json.loads(paths["multicity_review_queue.json"].read_text())
        current = paths["candidate_monitor_state.json"]
        state_before = json.loads(current.read_text())
        fail = failed
        calls = []
        def fixture(city, earliest, now):
            calls.append(city)
            if city == fail:
                raise TimeoutError("FIXTURE_TIMEOUT_NO_HTTP")
            if city == CITY:
                title = ("У Запоріжжі загинули двоє після ракетного удару"
                         if now == BASE else
                         "У Запоріжжі уточнили повідомлення про загиблих після ракетного удару")
                rows = [{"url": "https://news.google.com/rss/articles/workab-simulated-only",
                         "title": title, "publisher": "synthetic",
                         "published_at": monitor.iso(now), "snippet": "Синтетичний тест."}]
                return rows, "fixture://offline-not-http"
            return [], "fixture://offline-not-http"
        args = ["monitor_casualty_candidates.py", "--independent-source-check"]
        if live:
            args.append("--source-http")
        with patch.object(monitor, "STATE_FILE", paths["candidate_monitor_state.json"]), \
             patch.object(monitor, "QUEUE_FILE", paths["multicity_review_queue.json"]), \
             patch.object(monitor, "LAST_RUN_FILE", paths["candidate_monitor_last_run.json"]), \
             patch.object(monitor, "now_utc", return_value=t), \
             patch.object(monitor, "poll_all", return_value=({}, {})), \
             patch.object(monitor, "search_city_news", side_effect=fixture), \
             patch.object(monitor.requests, "get", side_effect=AssertionError("NO_HTTP_ALLOWED")), \
             patch.object(sys, "argv", args), contextlib.redirect_stdout(open(os.devnull, "w")):
            monitor.main()
        state = json.loads(current.read_text())
        queue = json.loads(paths["multicity_review_queue.json"].read_text())
        report = json.loads(paths["candidate_monitor_last_run.json"].read_text())
        # The real WIP paths remain read-only by construction; temp outputs only.
        result = {
            "report": report, "state": state, "queue": queue,
            "calls": calls, "before": state_before, "queue_before": queue_before,
            "saved": (current.read_bytes(), paths["multicity_review_queue.json"].read_bytes())
        }
        return result

class WorkAB(unittest.TestCase):
    def test_01_plan_all_23_even_no_new_finished_alerts(self):
        plans = monitor.plan_source_scans({"cities": {}}, {}, BASE, independent=True)
        self.assertEqual(len(plans), 23)
        self.assertEqual(set(plans), set(monitor.CITY_CONFIG))
        self.assertTrue(all(a["earliest"] == BASE - timedelta(days=8) for a in plans.values()))
        self.assertEqual(monitor.plan_source_scans({}, {}, BASE, independent=False), {})

    def test_02_03_two_cycles_retry_overlap_dedup_and_no_HTTP(self):
        first = run_scratch(BASE, live=True)
        self.assertEqual(len(first["calls"]), 23)
        self.assertEqual(first["report"]["cities_successfully_fetched"], 23)
        self.assertEqual(first["report"]["rss_http_requests_this_run"], 0)
        self.assertEqual(first["report"]["new_review_candidates"], 1)
        self.assertEqual(first["report"]["automatic_credits"], 0)
        self.assertEqual(first["report"]["PROMOTE"], "OFF")
        self.assertTrue(all(first["state"]["cities"][city]["last_independent_source_scan_at"]
                            == monitor.iso(BASE) for city in monitor.CITY_CONFIG))
        with tempfile.TemporaryDirectory(prefix="workab-cycle-") as temp:
            p = [Path(temp) / "state.json", Path(temp) / "queue.json"]
            for file, content in zip(p, first["saved"]):
                file.write_bytes(content)
            second = run_scratch(BASE+timedelta(hours=4), failed=CITY, live=True, prior=p)
            self.assertEqual(second["report"]["cities_successfully_fetched"], 22)
            self.assertIn(CITY, second["report"]["cities_with_source_errors"])
            self.assertEqual(second["report"]["new_review_candidates"], 0)
            self.assertEqual(second["report"]["rss_http_requests_this_run"], 0)
            self.assertEqual(second["state"]["cities"][CITY]["last_independent_source_scan_at"], monitor.iso(BASE))
            self.assertEqual(len(second["queue"]), len(first["queue"]))
            self.assertEqual(second["report"]["automatic_credits"], 0)
            for file, content in zip(p, second["saved"]):
                file.write_bytes(content)
            recovery = run_scratch(BASE+timedelta(hours=8), live=True, prior=p)
            self.assertEqual(recovery["report"]["new_review_candidates"], 0)
            self.assertEqual(recovery["state"]["cities"][CITY]["last_independent_source_scan_at"],
                             monitor.iso(BASE+timedelta(hours=8)))
            self.assertEqual(len(recovery["queue"]), len(first["queue"]))
            reports = [first, second, recovery]
        RUN_DIR.mkdir(parents=True, exist_ok=True)
        summary = {
            "schema": "workab-offline-two-cycles-v1",
            "head_sha": os.environ.get("GITHUB_SHA", "LOCAL_UNPINNED"),
            "mode": "MOCKED_RSS_ON_WIP_SNAPSHOT_NO_SOURCE_HTTP",
            "cities_planned": 23,
            "cycles": [
                {"time": monitor.iso(BASE + timedelta(hours=4*i)),
                 "fixture_cities_retrieved": v["report"]["cities_successfully_fetched"],
                 "new_candidates": v["report"]["new_review_candidates"],
                 "unavailable_sources": v["report"]["cities_with_source_errors"],
                 "rss_http_requests": v["report"]["rss_http_requests_this_run"],
                 "new_death_credits": v["report"]["automatic_credits"],
                 "cursor_sample_zaporizhzhia": v["state"]["cities"][CITY].get("last_independent_source_scan_at")}
                for i,v in enumerate(reports)],
            "last_successful_fixture_check_by_city": {
                city: recovery["state"]["cities"][city].get("last_independent_source_scan_at")
                for city in monitor.CITY_CONFIG},
            "wip_snapshot_queue_size": len(first["queue_before"]),
            "wip_snapshot_state_cities": len(first["before"]["cities"]),
            "queue_size_after": len(recovery["queue"]),
            "candidate_total_added": 1,
            "replayed_new_candidates": 0,
            "actual_source_checks": 0,
            "external_source_http_requests": 0,
            "automatic_credits": 0, "PROMOTE": "OFF",
            "publication_allowed": False,
            "evidence_capture_http": "OFF_PENDING_OWNER_GO",
        }
        (RUN_DIR/"cycles.json").write_text(json.dumps(summary,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
        REPORTS.append(summary)

    def test_04_no_http_by_default_no_cursor_advance(self):
        run = run_scratch(BASE, live=False)
        self.assertEqual(run["calls"], [])
        self.assertEqual(run["report"]["cities_successfully_fetched"], 0)
        self.assertEqual(run["report"]["rss_http_requests_this_run"], 0)
        self.assertEqual(len(run["report"]["cities_planned"]), 23)
        self.assertTrue(all(v.get("last_independent_source_scan_at") ==
                            (run["before"].get("cities") or {}).get(k,{}).get("last_independent_source_scan_at")
                            for k,v in run["state"]["cities"].items()))

    def test_05_workaa_sentence_bounds_and_segments(self):
        text = ("Вранці ракета влучила у приватний будинок у Запоріжжі, загинули двоє людей. "
                "Увечері того ж дня інша ракета влучила у школу в Запоріжжі, загинула людина. "
                "Пізніше стало відомо про ще одного загиблого.")
        r = aa.retain_incident_review_clues(text)
        self.assertEqual(r["status"], "INSUFFICIENT_EVIDENCE")
        self.assertEqual(len({z["article_segment_hint"] for z in r["evidence_mentions"]}), 2)
        self.assertFalse(r["attack_identity_verified"])
        long = "Внаслідок атаки загинули " + "люди постраждали " * 50 + "."
        self.assertIn("CONTEXT_INCOMPLETE", [
            z["context_status"] for z in aa.retain_incident_review_clues(long)["evidence_mentions"]])
        self.assertEqual(aa._review_sentences("Розслідують (ч. 2 ст. 438 КК України)."),
                         ["Розслідують (ч. 2 ст. 438 КК України)."])

    def test_06_workx_index_no_accumulation_no_incident_link(self):
        def f(cid,url,n,kind="TOTAL"):
            t="Підтверджено загибель людей."
            return {"candidate_id":cid,"source_url":url,"source_role":"publisher",
                    "decision":"NEEDS_REVIEW","publication_allowed":False,
                    "document_sha256":str(n)*64,"extracted_text_sha256":"f"*64,
                    "claim_deaths":n,"count_kind":kind,"excerpts":[{"text":t,"excerpt_sha256":x._sha(t)}]}
        url="https://mig.com.ua/offline-test-no-real-article"
        progress=[]
        prior=None
        for count in (18,20,23):
            r=x.build_review_index({"facts":[f("sim-"+str(count),url,count)],
                                    "automatic_credits":0,"publication_allowed":False},
                                   previous=prior,include_unretained=False)
            progress.append(r["cards"][0])
            prior=r["cards"]
        self.assertEqual([z["fatal_total_claimed_not_credited"] for z in progress],[18,20,23])
        self.assertEqual(sum(z["automatic_credits"] for z in progress),0)
        self.assertIsNone(progress[-1]["incident_id"])
        self.assertIn("SAME_URL_POSSIBLE_UPDATED_REPORT_NOT_EVENT_PROOF",progress[-1]["reasons"])
        a,b=f("two-incidents-a","https://mig.com.ua/a",2),f("two-incidents-b","https://mig.com.ua/b",3)
        separate=x.build_review_index({"facts":[a,b],"publication_allowed":False,"automatic_credits":0},
                                     include_unretained=False)
        self.assertEqual(separate["summary"]["automatically_linked_incidents"],0)
        self.assertTrue(all(z["incident_id"] is None for z in separate["cards"]))
        late=f("late",url,1,"ADDITIONAL_DEATH_REPORTED")
        lateRow=x.build_review_index({"facts":[late],"publication_allowed":False,"automatic_credits":0},
                                    include_unretained=False)["cards"][0]
        self.assertIsNone(lateRow["fatal_total_claimed_not_credited"])

    def test_07_saved_workz_three_cards_no_full_html(self):
        base=os.getenv("WORKAB_WORKZ_DIR")
        if not base:
            self.skipTest("Immutable Work Z archive is available only in exact-head Actions")
        d=Path(base)
        manifest=json.loads((d/"manifest.json").read_text())
        for name,want in manifest["files_sha256"].items():
            self.assertEqual(digest(d/name),want,name)
        facts=json.loads((d/"minimal_capture_facts.json").read_text())
        receipt=json.loads((d/"capture_receipts.json").read_text())
        result=saved.compact_existing(facts,receipt)
        self.assertEqual(result["evidence_index"]["summary"]["total"],3)
        self.assertEqual(result["evidence_index"]["summary"]["automatic_credits"],0)
        self.assertEqual(result["pair_decisions"],{
          "T03-T04":"INSUFFICIENT_EVIDENCE",
          "T03-T05":"INSUFFICIENT_EVIDENCE",
          "T04-T05":"INSUFFICIENT_EVIDENCE"})
        self.assertTrue(all(z["decision"]=="NEEDS_REVIEW" for z in result["evidence_index"]["cards"]))
        self.assertTrue(all(z["incident_id"] is None for z in result["evidence_index"]["cards"]))
        self.assertTrue(any("CONTEXT_INCOMPLETE" in z["reasons"] for z in result["evidence_index"]["cards"]))
        self.assertTrue(all("html" not in z and "body" not in z for z in result["evidence_index"]["cards"]))
        RUN_DIR.mkdir(parents=True,exist_ok=True)
        safe={"target_ids":result["target_ids"],
              "source_index_summary":result["evidence_index"]["summary"],
              "pair_decisions":result["pair_decisions"],
              "reason_counts":{r:sum(r in z["reasons"] for z in result["evidence_index"]["cards"])
                               for r in sorted({q for z in result["evidence_index"]["cards"] for q in z["reasons"]})},
              "incident_id_proven":0,"automatic_credits":0,"PROMOTE":"OFF","original_zip_sha256":saved.EXPECTED_ZIP_SHA}
        (RUN_DIR/"saved_evidence_summary.json").write_text(json.dumps(safe,ensure_ascii=False,sort_keys=True,indent=2)+"\n")

    def test_08_legacy_promotion_guard_is_read_only(self):
        repo=ROOT
        def show(branch, path):
            return subprocess.check_output(["git","show",f"{branch}:{path}"],cwd=repo,text=True)
        guard=show("origin/main",".github/workflows/casualty-review-operator.yml")
        generator=show("origin/main","kyiv-air-alerts-grafana/scripts/update_casualties.py")
        self.assertIn("false &&",guard)
        self.assertIn("LEGACY_CASUALTY_GENERATOR_BLOCKED",generator)
        self.assertIn("incident_id",generator)
        self.assertNotIn("launch.json",str(ROOT/"kyiv-air-alerts-grafana/scripts/casualty_workx_evidence.py"))

if __name__=="__main__":
    unittest.main(verbosity=2)
