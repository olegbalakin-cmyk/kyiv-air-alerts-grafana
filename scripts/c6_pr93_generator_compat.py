#!/usr/bin/env python3
"""Exact, local PR #93 collector-blob pin for the accepted C6 generator.

This changes only the generator's immutable allowlist in its isolated checkout.
It cannot fetch a source, run Neon, write site data, or publish Git.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

BASE_GENERATOR_GIT_BLOB = "34d8fa1dc0b25d0a88de2d6dcc73061cfe0771da"
MERGED_PR93_PARSER_GIT_BLOB = "d31c5ac43ac9e76491ee38033f9a46838c5abfbb"
ANCHOR = """C6_SEVASTOPOL_CHECKPOINT_BLOBS = {
 'scripts/add_sevastopol_exact.py': ('e4c091a677622eb28e504b0592a89e4d92d5fe02', '6698ec743b6efcd9aeb059dd81b51cc05ae93493'),
}
"""
EXTRA = """
# Exact owner-approved PR #93 blob at site-prod@6704c483; no wildcard drift.
C6_SEVASTOPOL_PR93_BLOBS = {
 'scripts/add_sevastopol_exact.py': ('e4c091a677622eb28e504b0592a89e4d92d5fe02', 'd31c5ac43ac9e76491ee38033f9a46838c5abfbb'),
}
"""
ORIGINAL_PREDICATE = "            C6_SEVASTOPOL_CHECKPOINT_BLOBS.get(path) == (expected, actual))"
PATCHED_PREDICATE = ("            C6_SEVASTOPOL_CHECKPOINT_BLOBS.get(path) == (expected, actual) or\n"
                     "            C6_SEVASTOPOL_PR93_BLOBS.get(path) == (expected, actual))")


class PinBlocked(ValueError):
    pass


def git_blob(raw: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def patched_bytes(raw: bytes, parser_raw: bytes) -> bytes:
    if git_blob(raw) != BASE_GENERATOR_GIT_BLOB:
        raise PinBlocked("PINNED_GENERATOR_BLOB_MISMATCH")
    if git_blob(parser_raw) != MERGED_PR93_PARSER_GIT_BLOB:
        raise PinBlocked("PR93_PARSER_BLOB_MISMATCH")
    original = raw.decode("utf-8")
    if original.count(ANCHOR) != 1 or original.count(ORIGINAL_PREDICATE) != 1:
        raise PinBlocked("PINNED_GENERATOR_CONTRACT_CHANGED")
    changed = original.replace(ANCHOR, ANCHOR + EXTRA).replace(
        ORIGINAL_PREDICATE, PATCHED_PREDICATE)
    compile(changed, "neon_json_shadow_generator.py", "exec")
    return changed.encode("utf-8")


def pin(generator: Path, parser: Path) -> str:
    modified = patched_bytes(generator.read_bytes(), parser.read_bytes())
    generator.write_bytes(modified)
    return hashlib.sha256(modified).hexdigest()


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--generator", type=Path, required=True)
    cli.add_argument("--site-parser", type=Path, required=True)
    args = cli.parse_args()
    try:
        digest = pin(args.generator, args.site_parser)
    except (PinBlocked, OSError, UnicodeError, SyntaxError):
        print("C6_GENERATOR_PIN_BLOCKED")
        return 2
    print("C6_PR93_EXACT_BLOB_PIN_PASS sha256=" + digest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
