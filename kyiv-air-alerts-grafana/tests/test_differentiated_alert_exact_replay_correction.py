import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from proof_differentiated_alert_exact_replay_correction import exact_replay_gate


class ExactReplayCorrectionGateTest(unittest.TestCase):
    def test_disabled_zero_zero_is_rejected(self):
        result = {
            "attempted": False,
            "status": "DISABLED",
            "inserted_snapshots": 0,
            "inserted_observations": 0,
            "store_counts": None,
        }
        self.assertFalse(
            exact_replay_gate(result, {"snapshots": 3, "observations": 3})
        )

    def test_valid_exact_replay_requires_unchanged_counts(self):
        result = {
            "attempted": True,
            "status": "SUCCEEDED",
            "inserted_snapshots": 0,
            "inserted_observations": 0,
            "store_counts": {"snapshots": 3, "observations": 3},
        }
        self.assertTrue(
            exact_replay_gate(result, {"snapshots": 3, "observations": 3})
        )
        self.assertFalse(
            exact_replay_gate(result, {"snapshots": 4, "observations": 3})
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
