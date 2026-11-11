"""Frozen B2 history: retain 382 exact read-only parents solely as evidence.

No live DB/source calls, no changes to C2 stats, no publication.
"""
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "scripts" / "neon_shadow_c6_assets"
def module(filename, name):
    spec = importlib.util.spec_from_file_location(name, filename)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj

gen = module(ROOT / "scripts" / "neon_json_shadow_generator.py", "c6_generator_frozen_b2")
b2 = module(ASSETS / "source_priority_reader.py", "c6_accepted_frozen_b2")
bundle = json.loads((ASSETS / "frozen_october_382_198_bundle.json").read_text())
overrides = {rule["live_uid"] for rule in bundle["display_overrides"]}

def full_evidence():
    raw = [{ "uid": row["uid"], "start_at": row["start"], "end_at": row["end"],
        "city_key": "kyiv", "alert_type": "AIR", "episode_state": "closed"}
        for row in bundle["source_rows"]]
    expected = bundle["expected_relationships"]
    snap = {"episodes": raw, "classifications": expected["classifications_rows"],
        "source_links": expected["source_link_rows"], "events": expected["event_rows"]}
    # Independently verified old Kiev live parents (184) must NEVER go into
    # the current C2 statistics. Other 198 frozen parents are canonical.
    canon = [row for row in raw if row["uid"] not in overrides]
    return snap, canon

class FrozenB2EvidenceTests(unittest.TestCase):
    def test_exact_382_physical_parents_yield_198_canonical_display(self):
        snap, canonical = full_evidence()
        self.assertEqual(len(snap["episodes"]), 382)
        self.assertEqual(len(overrides), 184)
        self.assertEqual(len(canonical), 198)
        selected = gen.frozen_b2_display_selection(snap, canonical, bundle, b2)
        self.assertEqual(len(selected["display_alerts"]), 198)
        self.assertEqual(len(selected["view_only_suppressed"]), 184)
        self.assertTrue({r["uid"] for r in selected["display_alerts"]} <=
                        {r["uid"] for r in canonical})
        self.assertFalse({r["uid"] for r in selected["display_alerts"]} & overrides)
        self.assertEqual(len(snap["episodes"]), 382)

    def test_missing_frozen_historical_parent_fails_closed(self):
        snap, canonical = full_evidence()
        snap["episodes"].pop()
        with self.assertRaisesRegex(Exception, "FROZEN_B2_EVIDENCE_PARENTS_MISSING"):
            gen.frozen_b2_display_selection(snap, canonical, bundle, b2)

    def test_stale_frozen_display_parent_fails_closed(self):
        snap, canonical = full_evidence()
        canonical.pop()
        with self.assertRaisesRegex(Exception, "FROZEN_B2_DISPLAY_PARENT_NOT_C2_CANONICAL"):
            gen.frozen_b2_display_selection(snap, canonical, bundle, b2)

    def test_malformed_historical_parent_fails_closed(self):
        snap, canonical = full_evidence()
        snap["episodes"][0]["episode_state"] = "open"
        with self.assertRaisesRegex(Exception, "FROZEN_B2_EVIDENCE_PARENTS_MISSING"):
            gen.frozen_b2_display_selection(snap, canonical, bundle, b2)

if __name__ == "__main__":
    unittest.main()
