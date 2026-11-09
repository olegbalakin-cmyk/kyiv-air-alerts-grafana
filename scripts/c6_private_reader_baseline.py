"""Prepare private full-fidelity read-only rows for an independently approved DST baseline.

No HTTP, SQL, GitHub upload, or production code. Caller supplies an existing
read-only snapshot; this function must be invoked only by a separately approved
proof. Output is expressly forbidden inside the checkout or existing paths.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

TABLES = ("episodes", "observations", "checkpoints", "runs",
          "classifications", "source_links", "events")


def _serialize(value):
    # Match the research reader's snapshot hashing representation.
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), default=str, allow_nan=False) + "\n").encode("utf-8")


def _private_write(path: Path, raw: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def retain_private_baseline(snapshot: dict, destination: Path, *, checkout: Path,
                            approved: bool = False, artifact_output: Path | None = None) -> dict:
    """Retain all seven raw reader table arrays and their exact serialized hashes.

    Never pass the resulting directory to actions/upload-artifact, Git staging,
    logs, site JSON, or a public research proof. Secure owner-controlled
    transfer and deletion require separate authorization.
    """
    if approved is not True:
        raise ValueError("PRIVATE_BASELINE_APPROVAL_REQUIRED")
    destination = Path(destination).resolve()
    checkout = Path(checkout).resolve()
    if destination == checkout or destination.is_relative_to(checkout):
        raise ValueError("RAW_BASELINE_IN_CHECKOUT_FORBIDDEN")
    if artifact_output is not None:
        artifact_output = Path(artifact_output).resolve()
        if (destination == artifact_output or destination.is_relative_to(artifact_output)
                or artifact_output.is_relative_to(destination)):
            raise ValueError("RAW_BASELINE_IN_UPLOADED_ARTIFACT_FORBIDDEN")
    if destination.exists():
        raise ValueError("RAW_BASELINE_OUTPUT_EXISTS")
    if set(TABLES) - set(snapshot) or any(not isinstance(snapshot[k], list) for k in TABLES):
        raise ValueError("RAW_BASELINE_INCOMPLETE")
    meta = snapshot.get("meta", {})
    if meta.get("read_only") != "on" or meta.get("isolation") != "repeatable read":
        raise ValueError("RAW_BASELINE_READONLY_UNPROVEN")
    destination.mkdir(mode=0o700, parents=False)
    try:
        manifest = {"schema": "c6-private-raw-reader-baseline-v1",
                    "publication_allowed": False, "GLOBAL_CUTOVER": "NO",
                    "tables": {}}
        for key in TABLES:
            name = key + ".json"
            raw = _serialize(snapshot[key])
            _private_write(destination / name, raw)
            manifest["tables"][key] = {"file": name, "rows": len(snapshot[key]),
                                       "sha256": hashlib.sha256(raw).hexdigest()}
        _private_write(destination / "sha256_manifest.json", _serialize(manifest))
        return {"status": "PRIVATE_BASELINE_STAGED", "table_count": len(TABLES),
                "publication_allowed": False}
    except BaseException:
        # Incomplete data is not a reusable baseline.
        for file in destination.iterdir():
            if file.is_file():
                file.unlink()
        destination.rmdir()
        raise
