#!/usr/bin/env python3
"""Immutable read-only Kyiv source snapshot -> test-only unclosed alert metadata."""
import argparse
import base64
import hashlib
import io
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import zipfile
from bs4 import BeautifulSoup

BUNDLE_SHA256 = "3f822042ceaaea06746dca2683f5fcc7eabf1dc6539752db2069f9aaf464d641"
BODY_SHA256 = "4120f640571b152708ba6dff3e8da0ea18b3b5c2042392c74fa29e6530d8d9cf"
SOURCE = "https://kyiv.digital/storage/air-alert/stats.html"
RUN_ID = 44680696823
KYIV = ZoneInfo("Europe/Kyiv")
STAMP = re.compile(r"^(?P<hm>\d\d:\d\d)\s+(?P<day>\d\d\.\d\d\.\d\d)\b")

def derive(raw_zip):
    if hashlib.sha256(raw_zip).hexdigest() != BUNDLE_SHA256:
        raise ValueError("IMMUTABLE_C2_ZIP_SHA_MISMATCH")
    with zipfile.ZipFile(io.BytesIO(raw_zip)) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        if manifest.get("github_run_id") != RUN_ID or manifest.get("github_run_attempt") != 1:
            raise ValueError("C2_RUN_IDENTITY_MISMATCH")
        contents = archive.read("payload.json")
        if hashlib.sha256(contents).hexdigest() != manifest["files"]["payload.json"]:
            raise ValueError("C2_PAYLOAD_SHA_MISMATCH")
        payload = json.loads(contents)
    receipt = payload["historical_source_receipts"]["kyiv"]
    pages = receipt.get("pages", [])
    if (receipt.get("github_run_id") != RUN_ID or receipt.get("source_key") != "kyiv_digital"
        or receipt.get("continuity_verified") is not True
        or receipt.get("source_identity", {}).get("url") != SOURCE
        or len(pages) != 1 or pages[0].get("url") != SOURCE):
        raise ValueError("KYIV_SOURCE_RECEIPT_INVALID")
    page = pages[0]
    body = base64.b64decode(page["body_base64"], validate=True)
    if (hashlib.sha256(body).hexdigest() != BODY_SHA256
        or page.get("body_sha256") != BODY_SHA256
        or page.get("captured_at") != receipt.get("last_checked_at")):
        raise ValueError("KYIV_SOURCE_BYTES_OR_CLOCK_MISMATCH")
    captured = datetime.fromisoformat(page["captured_at"].replace("Z", "+00:00"))
    if captured.tzinfo is None:
        raise ValueError("KYIV_CAPTURE_CLOCK_UNAWARE")
    events = []
    for row in BeautifulSoup(body, "html.parser").find_all("tr"):
        text = " ".join(row.stripped_strings)
        match = STAMP.match(text)
        if not match:
            continue
        if "🔴 Повітряна тривога" in text and "відбій" not in text.lower():
            kind = "start"
        elif "🟢 Відбій тривоги" in text and "повітряна тривога" not in text.lower():
            kind = "end"
        else:
            continue
        naive = datetime.strptime(match["day"] + " " + match["hm"], "%d.%m.%y %H:%M")
        local = naive.replace(tzinfo=KYIV)
        if local.astimezone(timezone.utc).astimezone(KYIV).replace(tzinfo=None) != naive:
            raise ValueError("INVALID_LOCAL_SOURCE_TIMESTAMP")
        events.append((local.astimezone(timezone.utc), kind))
    if len(events) < 500 or len(events) != len(set(events)):
        raise ValueError("KYIV_EXACT_ROWS_INSUFFICIENT_OR_DUPLICATE")
    events.sort(key=lambda event: (event[0], 0 if event[1] == "end" else 1))
    start, kind = events[-1]
    if kind != "start" or not start < captured.astimezone(timezone.utc):
        raise ValueError("NO_UNPAIRED_START_AT_CAPTURE")
    if (captured - start).total_seconds() > 26 * 3600:
        raise ValueError("START_TOO_OLD")
    return {
        "schema": "kyiv-active-provisional-test-v1", "test_only": True,
        "city_key": "kyiv", "alert_type": "AIR", "source": "kyiv_digital_live",
        "status": "unclosed_at_source_capture",
        "date": start.astimezone(KYIV).date().isoformat(),
        "started_at": start.astimezone(KYIV).isoformat(timespec="seconds"),
        "ends_at": None, "captured_at": page["captured_at"],
        "source_body_sha256": BODY_SHA256, "github_run_id": RUN_ID,
        "github_run_attempt": 1,
        "meaning": "Elapsed interval between source-confirmed start and source captured_at only. No end known at capture. Not live status, final duration, or a completed-alert episode.",
        "archive_change": False, "neon_writes": 0, "publication_allowed": False,
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    proof = derive(args.bundle.read_bytes())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(proof, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("KYIV_TEST_CAPTURE_PROOF_PASS", proof["started_at"], proof["captured_at"])

if __name__ == "__main__":
    main()
