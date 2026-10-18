#!/usr/bin/env python3
"""No-side-effect, pinned-snapshot monitor ingestion parity and network-isolation proof."""
from __future__ import annotations

import hashlib
import json
import os
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import monitor_explosion_candidates as monitor
import apply_ukrainealarm_bridge as ua

ROOT = Path("/tmp/ukrainealarm-proof")
AT = datetime(2026, 10, 17, 16, 0, tzinfo=timezone.utc)


def canonical(rows):
    return json.dumps(rows, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


def fingerprint(rows):
    return hashlib.sha256(canonical(rows).encode()).hexdigest()


class ReadOnlyIngestionProof(unittest.TestCase):
    def test_cached_bridge_repeat_and_no_ukrainealarm_calls(self):
        self.assertNotIn("UKRAINEALARM_API_TOKEN", os.environ)
        with patch.object(ua, "UkraineAlarmClient", side_effect=AssertionError("API client instantiated")):
            with patch.object(ua, "history_rows", side_effect=AssertionError("API request attempted")):
                a,errors_a=monitor.poll_cached_bridge(
                    ROOT/"ukrainealarm_bridge.json", AT,
                    ROOT/"alerts_combined.json",ROOT/"sevastopol_events.json")
                b,errors_b=monitor.poll_cached_bridge(
                    ROOT/"ukrainealarm_bridge.json", AT,
                    ROOT/"alerts_combined.json",ROOT/"sevastopol_events.json")
        self.assertFalse(errors_a, errors_a)
        self.assertEqual(errors_a,errors_b)
        self.assertEqual(set(a),set(monitor.CITY_CONFIG))
        self.assertEqual(len(a),23)
        self.assertEqual(fingerprint(a), fingerprint(b))
        for city,eps in a.items():
            self.assertTrue(eps,city)
            self.assertEqual(len(eps),len(set(row["episode_id"] for row in eps)),city)
            for ep in eps:
                self.assertEqual(ep["episode_id"],monitor.event_id(city,ep["alert_start"],ep["alert_end"]))
                if monitor.is_raion_proxy_city(city):
                    self.assertEqual(ep["logical_grouping"],"apply_ukrainealarm_bridge.union_alerts")
                    self.assertGreaterEqual(ep["raw_interval_count"],1)
        self.assertTrue(all(ep["alert_source"]=="kyiv_combined_exact_city" for ep in a["kyiv"]))
        self.assertTrue(all(ep["alert_source"]=="sevastopol_verified_exact_city_pairs" for ep in a["sevastopol"]))
        self.assertEqual(sum(monitor.is_raion_proxy_city(k) for k in a),19)
        print(json.dumps(dict(mode="cached_bridge",city_count=23,
            raion_proxy_cities=19,sha256=fingerprint(a),region_errors=errors_a),
            indent=2))

if __name__=="__main__":
    unittest.main(verbosity=2)
