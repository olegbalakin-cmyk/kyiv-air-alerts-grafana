#!/usr/bin/env python3
"""Single bounded BBC publisher GET. Never writes or logs publisher bytes publicly."""
import hashlib
import http.client
import json
import os
import ssl
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

URL = "https://www.bbc.com/ukrainian/articles/ck9dzex1zp3qo"
HOST = "www.bbc.com"
PATH = "/ukrainian/articles/ck9dzex1zp3qo"
MAX_RESPONSE_BYTES = 8_000_000
MAX_ELAPSED_SECONDS = 45.0
SOCKET_TIMEOUT_SECONDS = 12.0
PROOF_DIR = Path("research/bbc_publisher_http_2026_10_12/proof")
PRIVATE_DIR = Path(os.environ.get("RUNNER_TEMP", "/tmp")) / "bbc-single-publisher-private-20261012"
RAW_FILE = PRIVATE_DIR / "response.entity.bin"
HEADER_KEYS = (
    "Content-Type", "Content-Encoding", "Content-Length", "Date", "ETag",
    "Last-Modified", "Location", "Transfer-Encoding"
)


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def file_digest(path):
    h = hashlib.sha256()
    count = 0
    with path.open("rb") as f:
        for part in iter(lambda: f.read(65536), b""):
            count += len(part)
            h.update(part)
    return count, h.hexdigest()


def safe_header(key, value):
    if value is None:
        return None
    if key == "Location":
        parsed = urlsplit(value)
        if parsed.query or parsed.fragment or len(value) > 400:
            return {"value": "REDACTED_LOCATION_QUERY_OR_FRAGMENT", "sha256": hashlib.sha256(value.encode()).hexdigest()}
    if len(value) > 400:
        return {"value": "REDACTED_OVERSIZED_HEADER", "sha256": hashlib.sha256(value.encode()).hexdigest()}
    return value


def run_capture():
    assert URL == f"https://{HOST}{PATH}"
    assert not PRIVATE_DIR.exists(), "Existing private directory: refusing reuse or a second GET"
    PRIVATE_DIR.mkdir(mode=0o700, parents=True)
    os.chmod(PRIVATE_DIR, 0o700)
    PROOF_DIR.mkdir(parents=True, exist_ok=True)
    started = utc_now()
    start_ns = time.monotonic_ns()
    response = None
    conn = None
    status = None
    headers = {key.lower().replace("-", "_"): None for key in HEADER_KEYS}
    read_complete = False
    truncated = False
    bytes_received = 0
    error_phase = None
    error_class = None
    request_attempted = False
    completion = None
    duration_ms = None
    fd = os.open(str(RAW_FILE), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as f:
            try:
                conn = http.client.HTTPSConnection(
                    HOST, port=443, timeout=SOCKET_TIMEOUT_SECONDS,
                    context=ssl.create_default_context())
                error_phase = "https_request"
                # Exactly one request, no cookie/auth headers; http.client never follows redirects.
                request_attempted = True
                conn.request("GET", PATH, headers={
                    "Accept": "text/html",
                    "Accept-Encoding": "gzip",
                    "User-Agent": "BBC-single-article-research-proof/1.0",
                    "Connection": "close",
                })
                response = conn.getresponse()
                status = int(response.status)
                for key in HEADER_KEYS:
                    headers[key.lower().replace("-", "_")] = safe_header(key, response.getheader(key))
                error_phase = "read_entity"
                while True:
                    if (time.monotonic_ns() - start_ns) / 1e9 > MAX_ELAPSED_SECONDS:
                        error_class = "TotalElapsedLimitExceeded"
                        break
                    allowance = MAX_RESPONSE_BYTES + 1 - bytes_received
                    if allowance <= 0:
                        truncated = True
                        break
                    part = response.read(min(65536, allowance))
                    if not part:
                        read_complete = True
                        break
                    f.write(part)
                    bytes_received += len(part)
                    if bytes_received > MAX_RESPONSE_BYTES:
                        truncated = True
                        break
            except Exception as exc:
                error_class = type(exc).__name__
            finally:
                completion = utc_now()
                duration_ms = round((time.monotonic_ns() - start_ns) / 1e6, 3)
                f.flush()
                os.fsync(f.fileno())
    finally:
        if conn is not None:
            conn.close()
    exact_length_match = None
    advertised_length = headers.get("content_length")
    if isinstance(advertised_length, str) and advertised_length.isdigit():
        exact_length_match = int(advertised_length) == bytes_received
        if not exact_length_match:
            read_complete = False
    if truncated or error_class is not None:
        read_complete = False
    size, digest = file_digest(RAW_FILE)
    assert size == bytes_received, "Internal raw file byte count differs"
    output = {
        "schema": "single_bbc_publisher_http_observation_v1",
        "target_url": URL,
        "method": "GET",
        "requested_hostname": HOST,
        "https_tls_verification": "stdlib_default_ssl_hostname_and_certificate_verification",
        "request_attempts": 1 if request_attempted else 0,
        "redirect_policy": "do_not_follow",
        "redirect_followed": False,
        "cookies_and_authorization_sent_by_script": False,
        "automatic_retries": False,
        "accept_encoding_requested": "gzip",
        "response_size_limit_bytes": MAX_RESPONSE_BYTES,
        "socket_timeout_seconds": SOCKET_TIMEOUT_SECONDS,
        "elapsed_limit_seconds": MAX_ELAPSED_SECONDS,
        "utc_request_start_client_observed": started,
        "utc_response_completion_client_observed": completion,
        "monotonic_elapsed_ms": duration_ms,
        "client_clock_independently_calibrated": False,
        "http_status": status,
        "final_url_no_redirect": URL if status is not None else None,
        "response_headers_selected": headers,
        "raw_received_entity_size_bytes": size,
        "raw_received_entity_sha256": digest,
        "reading_finished_normally": read_complete,
        "response_size_truncated": truncated,
        "content_length_matches_entity_bytes": exact_length_match,
        "error_phase": error_phase if error_class else None,
        "error_class": error_class,
        "body_storage": "GitHub-hosted runner temporary private directory, 0700; file 0600; removed after job",
        "durable_restricted_raw_preservation": False,
        "restricted_durable_readback": False,
        "raw_body_uploaded_or_committed": False,
        "entity_semantics": "HTTP entity bytes after transfer framing removal, before Content-Encoding decompression",
    }
    (PROOF_DIR / "observation.json").write_text(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"observation_saved": True, "http_status": status,
                      "raw_entity_size_bytes": size, "raw_sha256": digest,
                      "complete": read_complete, "error_class": error_class}, sort_keys=True))


if __name__ == "__main__":
    run_capture()