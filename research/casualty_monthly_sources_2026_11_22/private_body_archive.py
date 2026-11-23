"""Private encrypted publisher-body archive for casualty research (no automatic GET).

Encrypted record stores exact raw response bytes AND decoded bytes in an
authenticated in-memory ZIP. Nothing plaintext is written to disk, to log,
to GitHub source, or to the unencrypted capture_report.json.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import io
import json
import os
import re
import secrets
import stat
import zipfile
from datetime import datetime, timezone
from pathlib import Path

try:
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except ImportError as exc:
    raise RuntimeError("cryptography is required for encrypted evidence archiving") from exc

MAX_BODY = 2 * 1024 * 1024
MAGIC = b"CASUALTY_EVIDENCE_V1\x00"
SCHEMA = "casualty-private-fullbody-v1"
MIME_TYPES = {"text/html", "application/xhtml+xml", "application/pdf"}


class ArchiveError(RuntimeError):
    pass


def _canonical(data: dict) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _mode_guard(path: Path) -> None:
    if path.is_symlink():
        raise ArchiveError("ARCHIVE_SYMLINK_BLOCKED")
    if not path.is_dir():
        raise ArchiveError("ARCHIVE_NOT_DIRECTORY")
    if stat.S_IMODE(path.stat().st_mode) != 0o700:
        raise ArchiveError("ARCHIVE_DIRECTORY_PERMISSIONS")


def _private_dir(directory: Path, checkout_root: Path) -> Path:
    if not directory.is_absolute():
        raise ArchiveError("ARCHIVE_PATH_NOT_ABSOLUTE")
    path = directory
    checkout = checkout_root.resolve()
    resolved = path.resolve()
    if resolved == checkout or checkout in resolved.parents:
        raise ArchiveError("ARCHIVE_INSIDE_CHECKOUT")
    if path.exists():
        _mode_guard(path)
    else:
        if path.parent.exists() and path.parent.is_symlink():
            raise ArchiveError("ARCHIVE_SYMLINK_PARENT")
        path.mkdir(mode=0o700, parents=True, exist_ok=False)
        os.chmod(path, 0o700)
    return path


def _key(key_b64: str) -> bytes:
    if not key_b64 or not isinstance(key_b64, str):
        raise ArchiveError("ARCHIVE_KEY_MISSING")
    try:
        binary = base64.b64decode(key_b64, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ArchiveError("ARCHIVE_KEY_BAD_BASE64") from exc
    if len(binary) != 32:
        raise ArchiveError("ARCHIVE_KEY_NEEDS_32_BYTES")
    return binary


def _write_exclusive(path: Path, data: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


class PrivateBodyArchive:
    """AES-256-GCM sealed records with in-memory verification only.

    The redacted index includes only public URL, hashes, sizes, MIME, timestamps
    and ciphertext filenames; never published text. The key stays outside Git.
    """

    def __init__(self, directory: Path, key_b64: str, *, checkout_root: Path):
        self.key = _key(key_b64)
        self.root = _private_dir(Path(directory), checkout_root)
        self.records = self.root / "sealed"
        if self.records.exists():
            _mode_guard(self.records)
        else:
            self.records.mkdir(mode=0o700)
        self.index = []

    def store(self, *, target_id: str, url: str, content_type: str,
              raw: bytes, decoded: bytes, captured_at: str) -> dict:
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}", target_id):
            raise ArchiveError("UNSAFE_TARGET_ID")
        if not url.startswith("https://") or len(url) > 2048:
            raise ArchiveError("UNSAFE_SOURCE_URL")
        if content_type not in MIME_TYPES:
            raise ArchiveError("UNSUPPORTED_CONTENT_TYPE")
        if (not isinstance(raw, bytes) or not isinstance(decoded, bytes)
                or not raw or not decoded or len(raw) > MAX_BODY
                or len(decoded) > MAX_BODY):
            raise ArchiveError("BODY_MISSING_OR_OVERSIZE")
        try:
            d = datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
            if d.tzinfo is None:
                raise ValueError("naive timestamp")
        except (TypeError, ValueError, AttributeError) as exc:
            raise ArchiveError("CAPTURE_TIME_INVALID") from exc
        filename = target_id + ".sealed"
        dest = self.records / filename
        if dest.exists() or any(item["target_id"] == target_id for item in self.index):
            raise ArchiveError("DUPLICATE_EVIDENCE_ID")
        metadata = {
            "schema": SCHEMA,
            "target_id": target_id,
            "source_url": url,
            "content_type": content_type,
            "captured_at": d.astimezone(timezone.utc).isoformat(),
            "raw_sha256": _digest(raw),
            "decoded_sha256": _digest(decoded),
            "raw_bytes": len(raw),
            "decoded_bytes": len(decoded),
        }
        memory = io.BytesIO()
        with zipfile.ZipFile(memory, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("metadata.json", _canonical(metadata))
            z.writestr("raw.body", raw)
            z.writestr("decoded.body", decoded)
        nonce = secrets.token_bytes(12)
        sealed = MAGIC + nonce + AESGCM(self.key).encrypt(nonce, memory.getvalue(), _canonical(metadata))
        _write_exclusive(dest, sealed)
        receipt = dict(metadata, sealed_file="sealed/" + filename,
                       sealed_sha256=_digest(sealed), encryption="AES-256-GCM")
        self.index.append(receipt)
        return receipt

    def write_index(self) -> dict:
        path = self.root / "evidence_index.json"
        if path.exists():
            raise ArchiveError("INDEX_ALREADY_EXISTS")
        report = {"schema": SCHEMA, "encrypted_only": True,
                  "record_count": len(self.index), "records": self.index}
        _write_exclusive(path, _canonical(report) + b"\n")
        return {"index_sha256": _digest(path.read_bytes()),
                "count": len(self.index), "path": "evidence_index.json"}

    def verify(self, receipt: dict) -> dict:
        """Verify/recover in memory only; no plaintext console or disk writes."""
        meta = {k: receipt[k] for k in (
            "schema", "target_id", "source_url", "content_type", "captured_at",
            "raw_sha256", "decoded_sha256", "raw_bytes", "decoded_bytes")}
        fname = "sealed/" + meta["target_id"] + ".sealed"
        if receipt.get("sealed_file") != fname:
            raise ArchiveError("ARCHIVE_RECORD_PATH_CHANGED")
        path = self.root / fname
        if path.is_symlink() or not path.is_file():
            raise ArchiveError("SEALED_FILE_MISSING_OR_SYMLINK")
        blob = path.read_bytes()
        if _digest(blob) != receipt.get("sealed_sha256") or not blob.startswith(MAGIC):
            raise ArchiveError("SEALED_SHA256_MISMATCH")
        nonce, ciphertext = blob[len(MAGIC):len(MAGIC)+12], blob[len(MAGIC)+12:]
        try:
            clear = AESGCM(self.key).decrypt(nonce, ciphertext, _canonical(meta))
        except InvalidTag as exc:
            raise ArchiveError("ARCHIVE_AUTHENTICATION_FAILED") from exc
        with zipfile.ZipFile(io.BytesIO(clear)) as z:
            if set(z.namelist()) != {"metadata.json", "raw.body", "decoded.body"}:
                raise ArchiveError("ARCHIVE_PAYLOAD_INVALID")
            if z.read("metadata.json") != _canonical(meta):
                raise ArchiveError("ARCHIVE_METADATA_MISMATCH")
            raw, decoded = z.read("raw.body"), z.read("decoded.body")
        if (_digest(raw) != meta["raw_sha256"] or _digest(decoded) != meta["decoded_sha256"]
                or len(raw) != meta["raw_bytes"] or len(decoded) != meta["decoded_bytes"]):
            raise ArchiveError("ARCHIVE_BODY_MISMATCH")
        return {"raw": raw, "decoded": decoded, "metadata": meta}
