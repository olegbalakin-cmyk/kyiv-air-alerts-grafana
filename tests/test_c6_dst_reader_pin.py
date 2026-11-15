"""Offline exact-source regression for the C6 DST-UTC bridge compatibility pin.

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


def accepted_namespace(generated):
    """Execute only fixed literal dicts and two pure guard helpers from AST."""
    source = ast.parse(generated.decode("utf-8"))
    names = {
        "CAPTURE_HOOK_BLOBS", "C6_INTEGRATION_HOOK_BLOBS",
        "C6_SEVASTOPOL_CHECKPOINT_BLOBS", "C6_SEVASTOPOL_PR93_BLOBS",
        "C6_DST_UTC_BRIDGE_BLOBS",
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

    def test_wrong_same_run_bridge_fails_before_patching(self):
        with self.assertRaisesRegex(pin.PinBlocked, "DST_UTC_BRIDGE_BLOB_MISMATCH"):
            pin.patched_bytes(self.generator, self.parser, self.bridge + b"\n")

    def test_generator_and_parser_still_pinned(self):
        with self.assertRaisesRegex(pin.PinBlocked, "PINNED_GENERATOR_BLOB_MISMATCH"):
            pin.patched_bytes(self.generator + b"\n", self.parser, self.bridge)
        with self.assertRaisesRegex(pin.PinBlocked, "PR93_PARSER_BLOB_MISMATCH"):
            pin.patched_bytes(self.generator, self.parser + b"\n", self.bridge)

    def test_exact_existing_patch_remains_idempotence_guarded(self):
        updated = pin.patched_bytes(self.generator, self.parser, self.bridge)
        with self.assertRaises(pin.PinBlocked):
            pin.patched_bytes(updated, self.parser, self.bridge)


if __name__ == "__main__":
    unittest.main()
