"""Validate original archived inputs; no database or source requests."""
import base64
import hashlib
import io
import json
import zipfile
from pathlib import Path

root = Path(__file__).resolve().parent
raw = base64.b64decode((root / "input_snapshot.zip.b64").read_bytes(), validate=False)
assert hashlib.sha256(raw).hexdigest() == (root / "input_snapshot.sha256").read_text().strip()
out = Path("inputs")
with zipfile.ZipFile(io.BytesIO(raw)) as z:
    assert z.testzip() is None
    assert set(z.namelist()) == {"current-physical-rows.json", "current-physical-receipt.json", "class-snapshot.json", "http/entity_bytes.bin", "http_evidence.json", "dst_plan.json"}
    z.extractall(out)
accepted = root.parent / "c6_23city_integrated_shadow_2026_10_30/approved_22city_archive.b64"
raw = base64.b64decode(accepted.read_bytes())
assert hashlib.sha256(raw).hexdigest() == "f6dda060a0ed48b01b4726625b36c33b472955f687be6877aef918fc3c8bddf2"
with zipfile.ZipFile(io.BytesIO(raw)) as z:
    assert z.testzip() is None and len(z.namelist()) == 18
    prefix = "C6-22CITY-READER-01/"
    manifest = json.loads(z.read(prefix + "sha256_manifest.json"))["files"]
    assert len(manifest) == 17
    for name, sha in manifest.items():
        assert hashlib.sha256(z.read(prefix + name)).hexdigest() == sha
    z.extractall(out / "adapter")
http = json.loads((out / "http_evidence.json").read_text())
assert http["http_status"] == 200
assert hashlib.sha256((out / "http/entity_bytes.bin").read_bytes()).hexdigest() == http["entity_sha256"]
print("ARCHIVE_AND_ORIGINAL_HTTP_BYTES_VERIFIED; archived SQL readback, not a new live database connection")
