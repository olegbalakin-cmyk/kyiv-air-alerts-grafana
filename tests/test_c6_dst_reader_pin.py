"""Offline exact-source regression for the C6 DST-UTC and weekday builder pins.

Only immutable Git files are loaded; never connects to Neon, source APIs, or Git.
"""
import ast
import hashlib
import unittest
from pathlib import Path

from scripts import c6_pr93_generator_compat as pin


ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "reader" / "scripts" / "neon_json_shadow_generator.py"
PARSER = ROOT / "site-current" / "kyiv-air-alerts-grafana" / "scripts" / "add_sevastopol_exact.py"
BRIDGE = ROOT / "site-current" / "kyiv-air-alerts-grafana" / "scripts" / "apply_ukrainealarm_bridge.py"
PRIOR_BRIDGE = ROOT / "site-prior" / "kyiv-air-alerts-grafana" / "scripts" / "apply_ukrainealarm_bridge.py"
EXPECTED_SOURCE = "8b95c4b508b9a473240889603f593e399cf8815d"

WEEKDAY_OLD = ROOT / "site-weekday-prior" / "kyiv-air-alerts-grafana" / "scripts" / "build_time_of_day_heatmap.py"
WEEKDAY_NEW = ROOT / "site-weekday-current" / "kyiv-air-alerts-grafana" / "scripts" / "build_time_of_day_heatmap.py"
EXPECTED_OLD_WEEKDAY = "382e815dc95ec4e0d7cb3cb3619e3242aba823ce"
EXPECTED_NEW_WEEKDAY = "ad6c913ab7554eb59597702ee26a4b903b3d2c6f"


def accepted_namespace(generated):
    """Execute only fixed literal dicts and two pure guard helpers from AST."""
    source = ast.parse(generated.decode("utf-8"))
    names = {
        "CAPTURE_HOOK_BLOBS", "C6_INTEGRATION_HOOK_BLOBS",
        "C6_SEVASTOPOL_CHECKPOINT_BLOBS", "C6_SEVASTOPOL_PR93_BLOBS",
        "C6_DST_UTC_BRIDGE_BLOBS", "C6_WEEKDAY_HEATMAP_BLOBS",
        "C6_SEVASTOPOL_BOUNDARY_BLOBS",
    }
    nodes = []
    for node in source.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id in names for target in node.targets
        ):
            assert isinstance(node.value, ast.Dict)
            nodes.append(node)
        if isinstance(node, ast.FunctionDef) and node.name in ("blob", "accepted_builder_blob"):
            nodes.append(node)
    scope = {"hashlib": hashlib}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "<guard-only>", "exec"), scope)
    assert names <= scope.keys()
    assert "accepted_builder_blob" in scope and "blob" in scope
    return scope


class ExactDstBridgePinTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.generator = GENERATOR.read_bytes()
        cls.parser = PARSER.read_bytes()
        cls.bridge = BRIDGE.read_bytes()
        cls.prior = PRIOR_BRIDGE.read_bytes()
        cls.old_weekday = WEEKDAY_OLD.read_bytes()
        cls.new_weekday = WEEKDAY_NEW.read_bytes()

    def test_exact_immutable_inputs(self):
        self.assertEqual(pin.git_blob(self.generator), pin.BASE_GENERATOR_GIT_BLOB)
        self.assertEqual(pin.git_blob(self.parser), pin.MERGED_PR93_PARSER_GIT_BLOB)
        self.assertEqual(pin.git_blob(self.bridge), pin.MERGED_DST_UTC_BRIDGE_GIT_BLOB)
        self.assertEqual(pin.git_blob(self.prior), "aaedf36299bac69a76971d7e8399894e416d1643")

    def test_patch_accepts_exact_dst_bridge_and_old_bridge(self):
        updated = pin.patched_bytes(self.generator, self.parser, self.bridge)
        scope = accepted_namespace(updated)
        accepted = scope["accepted_builder_blob"]
        self.assertTrue(accepted("scripts/apply_ukrainealarm_bridge.py", self.bridge, EXPECTED_SOURCE))
        self.assertTrue(accepted("scripts/apply_ukrainealarm_bridge.py", self.prior, EXPECTED_SOURCE))
        self.assertTrue(accepted("scripts/add_sevastopol_exact.py", self.parser,
                                "e4c091a677622eb28e504b0592a89e4d92d5fe02"))

    def test_nonapproved_bridge_rejected_by_guard(self):
        updated = pin.patched_bytes(self.generator, self.parser, self.bridge)
        accepted = accepted_namespace(updated)["accepted_builder_blob"]
        self.assertFalse(accepted("scripts/apply_ukrainealarm_bridge.py",
                                  self.bridge + b"\n# unapproved drift\n", EXPECTED_SOURCE))
        self.assertFalse(accepted("scripts/apply_ukrainealarm_bridge.py",
                                  self.bridge, "different-expected-blob"))
        self.assertFalse(accepted("scripts/update_data.py", self.bridge, EXPECTED_SOURCE))

    def test_exact_weekday_heatmap_pin_and_negative_drift(self):
        self.assertEqual(pin.git_blob(self.old_weekday), EXPECTED_OLD_WEEKDAY)
        self.assertEqual(pin.git_blob(self.new_weekday), EXPECTED_NEW_WEEKDAY)
        updated = pin.patched_bytes(self.generator, self.parser, self.bridge)
        accepted = accepted_namespace(updated)["accepted_builder_blob"]
        path = "scripts/build_time_of_day_heatmap.py"
        self.assertTrue(accepted(path, self.old_weekday, EXPECTED_OLD_WEEKDAY))
        self.assertTrue(accepted(path, self.new_weekday, EXPECTED_OLD_WEEKDAY))
        self.assertFalse(accepted(path, self.new_weekday + b"\n# unexpected drift\n", EXPECTED_OLD_WEEKDAY))
        self.assertFalse(accepted(path, self.new_weekday, "wrong-expected-blob"))
        self.assertFalse(accepted("scripts/update_data.py", self.new_weekday, EXPECTED_OLD_WEEKDAY))

    def test_wrong_same_run_bridge_fails_before_patching(self):
        with self.assertRaisesRegex(pin.PinBlocked, "DST_UTC_BRIDGE_BLOB_MISMATCH"):
            pin.patched_bytes(self.generator, self.parser, self.bridge + b"\n")

    def test_generator_and_parser_still_pinned(self):
        with self.assertRaisesRegex(pin.PinBlocked, "PINNED_GENERATOR_BLOB_MISMATCH"):
            pin.patched_bytes(self.generator + b"\n", self.parser, self.bridge)
        with self.assertRaisesRegex(pin.PinBlocked, "PR93_PARSER_BLOB_MISMATCH"):
            pin.patched_bytes(self.generator, self.parser + b"\n", self.bridge)

    def test_exact_boundary_parser_pin_and_negative_drift(self):
        candidate = (ROOT / "site-boundary-candidate" / "kyiv-air-alerts-grafana" /
                     "scripts" / "add_sevastopol_exact.py").read_bytes()
        self.assertEqual(pin.git_blob(candidate), pin.SEVASTOPOL_BOUNDARY_PARSER_GIT_BLOB)
        expected = "e4c091a677622eb28e504b0592a89e4d92d5fe02"
        for parser in (self.parser, candidate):
            updated = pin.patched_bytes(self.generator, parser, self.bridge)
            accepted = accepted_namespace(updated)["accepted_builder_blob"]
            self.assertTrue(accepted("scripts/add_sevastopol_exact.py", self.parser, expected))
            self.assertTrue(accepted("scripts/add_sevastopol_exact.py", candidate, expected))
            self.assertFalse(accepted("scripts/add_sevastopol_exact.py", candidate + b"\n", expected))
            self.assertFalse(accepted("scripts/add_sevastopol_exact.py", candidate, "wrong"))
            self.assertFalse(accepted("scripts/update_data.py", candidate, expected))
        with self.assertRaises(pin.PinBlocked):
            pin.patched_bytes(self.generator, candidate + b"\n", self.bridge)

    def test_exact_existing_patch_remains_idempotence_guarded(self):
        updated = pin.patched_bytes(self.generator, self.parser, self.bridge)
        with self.assertRaises(pin.PinBlocked):
            pin.patched_bytes(updated, self.parser, self.bridge)


if __name__ == "__main__":
    unittest.main()
