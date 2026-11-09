"""Narrow no-network checks for separate owner-approved private DST baseline."""
import hashlib
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path

from scripts.c6_private_reader_baseline import TABLES, retain_private_baseline


class PrivateBaselineTests(unittest.TestCase):
    def snapshot(self):
        return {"meta": {"read_only": "on", "isolation": "repeatable read"},
                **{name: [{"example": name}] for name in TABLES}}

    def test_missing_explicit_approval_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            with self.assertRaisesRegex(ValueError, "APPROVAL_REQUIRED"):
                retain_private_baseline(self.snapshot(), root / "private",
                                        checkout=root / "checkout")

    def test_checkout_destination_forbidden(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "checkout").mkdir()
            with self.assertRaisesRegex(ValueError, "IN_CHECKOUT_FORBIDDEN"):
                retain_private_baseline(self.snapshot(), root / "checkout" / "raw",
                                        checkout=root / "checkout", approved=True)

    def test_read_only_required(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            s = self.snapshot()
            s["meta"]["read_only"] = "off"
            with self.assertRaisesRegex(ValueError, "READONLY_UNPROVEN"):
                retain_private_baseline(s, root / "private",
                                        checkout=root / "checkout", approved=True)

    def test_retains_full_raw_rows_with_verified_hashes(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "private"
            verdict = retain_private_baseline(self.snapshot(), out,
                                              checkout=root / "checkout", approved=True)
            self.assertEqual(verdict["status"], "PRIVATE_BASELINE_STAGED")
            self.assertFalse(verdict["publication_allowed"])
            manifest = json.loads((out / "sha256_manifest.json").read_text())
            self.assertEqual(set(manifest["tables"]), set(TABLES))
            self.assertEqual({p.name for p in out.iterdir()},
                             {"sha256_manifest.json"} | {t + ".json" for t in TABLES})
            for t in TABLES:
                raw = (out / (t + ".json")).read_bytes()
                self.assertEqual(json.loads(raw), self.snapshot()[t])
                self.assertEqual(manifest["tables"][t]["sha256"], hashlib.sha256(raw).hexdigest())
                if os.name == "posix":
                    self.assertEqual(stat.S_IMODE((out / (t + ".json")).stat().st_mode), 0o600)

    def test_refuses_existing_output(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "private"
            out.mkdir()
            with self.assertRaisesRegex(ValueError, "OUTPUT_EXISTS"):
                retain_private_baseline(self.snapshot(), out,
                                        checkout=root / "checkout", approved=True)


    def test_uploaded_artifact_destination_forbidden(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            checkout = root / "research"
            checkout.mkdir()
            artifact = root / "research-evidence"
            artifact.mkdir()
            with self.assertRaisesRegex(ValueError, "UPLOADED_ARTIFACT_FORBIDDEN"):
                retain_private_baseline(self.snapshot(), artifact / "raw",
                                        checkout=checkout, artifact_output=artifact,
                                        approved=True)
            self.assertFalse((artifact / "raw").exists())



if __name__ == "__main__":
    unittest.main()
