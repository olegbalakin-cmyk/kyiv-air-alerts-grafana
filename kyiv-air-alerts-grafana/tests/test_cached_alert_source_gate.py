#!/usr/bin/env python3
"""Fail-closed source validation regression matrix. No live network or DB calls."""
import copy
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from cached_alert_source_gate import (
    SourceGateError, validate_cached_source_files, REQUIRED_REGIONS,
)

UTC = timezone.utc
NOW = datetime(2026, 10, 17, 16, 0, tzinfo=UTC)
CHECKPOINT = "2026-10-17T15:57:53Z"
T = "2026-10-17T15:30:00Z"


def fixture():
    regions = {
        city: dict(city_key=city, region_id=str(i+1), continuous=True,
                   poll_overlap_verified=True, last_error=None, last_checked_at=T)
        for i, city in enumerate(sorted(REQUIRED_REGIONS))
    }
    bridge = dict(schema_version=3, regions=regions,
                  events=[dict(city_key="kharkiv", alert_type="AIR",
                               start="2026-10-17T14:00:00Z",
                               end="2026-10-17T14:30:00Z")],
                  event_count=1, last_fetch_error=None,
                  last_successful_fetch_at=CHECKPOINT)
    qa = dict(ok=True, errors=[], production_rows=23,
              exact_city_rows=4, raion_proxy_rows=19,
              effective_freshness=dict(
                  source="official UkraineAlarm API regionHistory bridge",
                  fully_continuous=True, fresh=True, warning=False,
                  status="official_api_bridge_fresh",
                  last_successful_fetch_at=CHECKPOINT,
                  required_rows=sorted(REQUIRED_REGIONS),
                  covered_rows=sorted(REQUIRED_REGIONS), uncovered_rows=[]))
    pair = {"start":"2026-10-17T14:00:00+00:00",
            "end":"2026-10-17T14:30:00+00:00"}
    return dict(bridge=bridge,
                dashboard={"cities": {k:{} for k in REQUIRED_REGIONS|{"kyiv","sevastopol"}}},
                kyiv=[pair], sevastopol={"pairs":[pair]}, qa=qa)


class LocalSourceGateTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.TemporaryDirectory()
        self.addCleanup(self.root.cleanup)
        self.path = Path(self.root.name)
        self.data = fixture()
        self.paths = {k:self.path/(k+".json") for k in self.data}
        self.flush()

    def flush(self):
        for k,v in self.data.items():
            self.paths[k].write_text(json.dumps(v), encoding="utf-8")

    def check(self, now=NOW):
        return validate_cached_source_files(
            bridge_path=self.paths["bridge"], dashboard_path=self.paths["dashboard"],
            kyiv_alerts_path=self.paths["kyiv"],
            sevastopol_events_path=self.paths["sevastopol"],
            qa_path=self.paths["qa"], now=now,
            monitor_city_keys=REQUIRED_REGIONS|{"kyiv","sevastopol"})

    def test_valid_and_read_only(self):
        before = {k:p.read_bytes() for k,p in self.paths.items()}
        self.assertEqual(self.check()["mode"], "cached_bridge")
        self.assertEqual(self.check()["required_region_count"], 21)
        self.assertEqual(before,{k:p.read_bytes() for k,p in self.paths.items()})

    def test_rejections(self):
        cases = [
            ("unsupported_schema",lambda d:d["bridge"].update(schema_version=2)),
            ("missing_region",lambda d:d["bridge"]["regions"].pop("kharkiv")),
            ("missing_events",lambda d:d["bridge"].pop("events")),
            ("malformed_events",lambda d:d["bridge"].update(events={})),
            ("event_count",lambda d:d["bridge"].update(event_count=3)),
            ("not_continuous",lambda d:d["bridge"]["regions"]["kharkiv"].update(continuous=False)),
            ("no_overlap",lambda d:d["bridge"]["regions"]["kharkiv"].update(poll_overlap_verified=False)),
            ("region_error",lambda d:d["bridge"]["regions"]["kharkiv"].update(last_error="429")),
            ("top_error",lambda d:d["bridge"].update(last_fetch_error="429")),
            ("missing_checkpoint",lambda d:d["bridge"].pop("last_successful_fetch_at")),
            ("stale_checkpoint",lambda d:d["bridge"].update(last_successful_fetch_at="2026-10-16T03:00:00Z")),
            ("stale_region",lambda d:d["bridge"]["regions"]["kharkiv"].update(last_checked_at="2026-10-16T03:00:00Z")),
            ("bad_time",lambda d:d["bridge"]["regions"]["kharkiv"].update(last_checked_at="nonsense")),
            ("future_time",lambda d:d["bridge"]["regions"]["kharkiv"].update(last_checked_at="2026-10-18T00:00:00Z")),
            ("missing_kyiv",lambda d:d.update(kyiv=[])),
            ("corrupt_kyiv",lambda d:d.update(kyiv={"bad":1})),
            ("missing_sevastopol",lambda d:d.update(sevastopol={"pairs":[]})),
            ("corrupt_sevastopol",lambda d:d.update(sevastopol={"pairs":None})),
            ("bad_qa",lambda d:d["qa"].update(ok=False)),
            ("bad_qa_coverage",lambda d:d["qa"]["effective_freshness"].update(covered_rows=[])),
            ("bad_qa_checkpoint",lambda d:d["qa"]["effective_freshness"].update(last_successful_fetch_at=T)),
            ("bad_dashboard",lambda d:d["dashboard"]["cities"].pop("kyiv")),
            ("bad_event_interval",lambda d:d["bridge"]["events"][0].update(end="2026-10-17T13:00:00Z")),
        ]
        for name,mutate in cases:
            with self.subTest(name=name):
                self.data=fixture()
                mutate(self.data)
                self.flush()
                before={k:p.read_bytes() for k,p in self.paths.items()}
                with self.assertRaises(SourceGateError):
                    self.check()
                self.assertEqual(before,{k:p.read_bytes() for k,p in self.paths.items()})
        self.data=fixture()
        self.flush()
        for kind in ("bridge","kyiv","sevastopol","qa","dashboard"):
            with self.subTest(missing=kind):
                self.flush()
                self.paths[kind].unlink()
                with self.assertRaises(SourceGateError):
                    self.check()
                self.flush()
            with self.subTest(json=kind):
                self.paths[kind].write_text("{",encoding="utf-8")
                with self.assertRaises(SourceGateError):
                    self.check()
                self.flush()

    def test_exact_twelve_hour_boundary(self):
        self.data["bridge"]["last_successful_fetch_at"]=T
        self.data["qa"]["effective_freshness"]["last_successful_fetch_at"]=T
        self.flush()
        self.assertTrue(self.check(NOW)["ok"])
        with self.assertRaises(SourceGateError):
            self.check(NOW+timedelta(seconds=1))

    def test_zero_network_and_zero_external_connections(self):
        with patch("socket.socket", side_effect=AssertionError("network attempted")):
            self.assertTrue(self.check()["ok"])

if __name__=="__main__":
    unittest.main(verbosity=2)
