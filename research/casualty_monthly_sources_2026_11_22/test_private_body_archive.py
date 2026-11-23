#!/usr/bin/env python3
"""Synthetic full-body encryption regression, offline only. No publisher GET."""
import base64
import hashlib
import os
import stat
import tempfile
import unittest
from pathlib import Path

from private_body_archive import PrivateBodyArchive, ArchiveError


class PrivateArchiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="casualty-monthly-encryption-test-")
        self.root = Path(self.tmp.name) / "private"
        self.key = base64.b64encode(os.urandom(32)).decode()
        self.archive = PrivateBodyArchive(self.root, self.key,
                                          checkout_root=Path(__file__).parents[2])
        self.body = b"<html><article>Example of two people killed.</article></html>"

    def tearDown(self):
        self.tmp.cleanup()

    def store(self, target_id="s01"):
        return self.archive.store(target_id=target_id,
            url="https://kyiv.npu.gov.ua/news/example", content_type="text/html",
            raw=self.body, decoded=self.body, captured_at="2026-11-23T20:00:00Z")

    def test_exact_full_body_round_trip_and_no_plaintext_artifact(self):
        receipt = self.store()
        result = self.archive.verify(receipt)
        self.assertEqual(result["raw"], self.body)
        self.assertEqual(result["decoded"], self.body)
        self.assertEqual(receipt["decoded_sha256"], hashlib.sha256(self.body).hexdigest())
        self.assertEqual(self.archive.write_index()["count"], 1)
        for file in self.root.rglob("*"):
            if file.is_file():
                self.assertNotIn(self.body, file.read_bytes())
                self.assertNotIn(b"people killed", file.read_bytes())
                self.assertEqual(stat.S_IMODE(file.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.root.stat().st_mode), 0o700)

    def test_pdf_and_original_bytes_not_the_same_as_decoded(self):
        receipt = self.archive.store(
            target_id="pdf", url="https://kyiv.npu.gov.ua/news/sample-pdf",
            content_type="application/pdf", raw=b"%PDF-1.7 compressed-test",
            decoded=b"%PDF-1.7 decompressed-test",
            captured_at="2026-11-23T20:00:00+00:00")
        proof = self.archive.verify(receipt)
        self.assertNotEqual(proof["raw"], proof["decoded"])

    def test_missing_key_invalid_base64_or_short_key(self):
        for key in ("", "not-base64", base64.b64encode(b"short").decode()):
            with self.subTest(key=key), self.assertRaises(ArchiveError):
                PrivateBodyArchive(self.root, key,
                                   checkout_root=Path(__file__).parents[2])

    def test_ciphertext_tamper_and_wrong_key_fail_closed(self):
        receipt = self.store()
        target = self.root / receipt["sealed_file"]
        blob = bytearray(target.read_bytes())
        blob[-1] ^= 1
        target.write_bytes(blob)
        with self.assertRaisesRegex(ArchiveError, "SEALED_SHA256_MISMATCH"):
            self.archive.verify(receipt)
        blob[-1] ^= 1
        target.write_bytes(blob)
        alternate = PrivateBodyArchive(
            self.root, base64.b64encode(os.urandom(32)).decode(),
            checkout_root=Path(__file__).parents[2])
        with self.assertRaisesRegex(ArchiveError, "ARCHIVE_AUTHENTICATION_FAILED"):
            alternate.verify(receipt)

    def test_metadata_tamper_and_record_path_fail_closed(self):
        receipt = self.store()
        with self.assertRaisesRegex(ArchiveError, "ARCHIVE_AUTHENTICATION_FAILED"):
            self.archive.verify(dict(receipt, source_url="https://fake.test/change"))
        with self.assertRaisesRegex(ArchiveError, "ARCHIVE_RECORD_PATH_CHANGED"):
            self.archive.verify(dict(receipt, sealed_file="../../secret"))

    def test_duplicate_invalid_id_and_large_body_fail_closed(self):
        self.store()
        with self.assertRaisesRegex(ArchiveError, "DUPLICATE_EVIDENCE_ID"):
            self.store()
        with self.assertRaisesRegex(ArchiveError, "UNSAFE_TARGET_ID"):
            self.store("../escape")
        with self.assertRaisesRegex(ArchiveError, "BODY_MISSING_OR_OVERSIZE"):
            self.archive.store(target_id="big", url="https://kyiv.npu.gov.ua/news/big",
                content_type="text/html", raw=b"x" * (2 * 1024 * 1024 + 1),
                decoded=b"x", captured_at="2026-11-23T20:00:00Z")

    def test_directory_symlink_and_open_permissions_rejected(self):
        link = Path(self.tmp.name) / "linked"
        link.symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(ArchiveError, "ARCHIVE_SYMLINK_BLOCKED"):
            PrivateBodyArchive(link, self.key,
                               checkout_root=Path(__file__).parents[2])
        os.chmod(self.root, 0o755)
        with self.assertRaisesRegex(ArchiveError, "ARCHIVE_DIRECTORY_PERMISSIONS"):
            PrivateBodyArchive(self.root, self.key,
                               checkout_root=Path(__file__).parents[2])

    def test_index_not_overwritable(self):
        self.store()
        self.archive.write_index()
        with self.assertRaisesRegex(ArchiveError, "INDEX_ALREADY_EXISTS"):
            self.archive.write_index()


if __name__ == "__main__":
    unittest.main(verbosity=2)
