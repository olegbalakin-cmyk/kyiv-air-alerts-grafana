#!/usr/bin/env python3
"""Offline-only pinned root corpus tests; no network, SQL, secrets or server."""
import hashlib
import re
import ssl
from pathlib import Path

p = Path(__file__).with_name("ISRG_ROOTS_PINNED.pem")
data = p.read_bytes()
assert hashlib.sha256(data).hexdigest() == "0cd98d2dd7a71afe5e2e93673933f15254c5a41a9be4682f27ec582e72c52ce0", "PINNED_CA_SHA256_MISMATCH"
assert data.count(b"-----BEGIN CERTIFICATE-----") == 2
assert data.count(b"-----END CERTIFICATE-----") == 2
blocks = re.findall(rb"-----BEGIN CERTIFICATE-----\s*([A-Za-z0-9+/=\s]+)-----END CERTIFICATE-----", data)
assert len(blocks) == 2
import base64
expected = ("96bcec06264976f37460779acf28c5a7cfe8a3c0aae11a8ffcee05c0bddf08c6",
            "69729b8e15a86efc177a57afb7171dfc64add28c2fca8cf1507e34453ccb1470")
for block, fp in zip(blocks, expected):
    assert hashlib.sha256(base64.b64decode(block)).hexdigest() == fp, "ROOT_FINGERPRINT_MISMATCH"
# The *original* PEM corpus must be the only trust input; simulated substitutions fail.
for altered in (data+b"x", data[:-1], data.replace(b"ISRG", b"BAD!", 1), b""):
    assert hashlib.sha256(altered).hexdigest() != "0cd98d2dd7a71afe5e2e93673933f15254c5a41a9be4682f27ec582e72c52ce0"
print("PINNED_ISRG_CA_OFFLINE_PASS count=2 der_fingerprints=2 tamper_negatives=4 / NO_TLS_HANDSHAKE")
