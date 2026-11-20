#!/usr/bin/env python3
"""Exact PR #93, DST-UTC and weekday builder blob pins for the C6 generator.

This changes only the generator's immutable allowlist in its isolated checkout.
It cannot fetch a source, run Neon, write site data, or publish Git.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

BASE_GENERATOR_GIT_BLOB = "34d8fa1dc0b25d0a88de2d6dcc73061cfe0771da"
MERGED_PR93_PARSER_GIT_BLOB = "d31c5ac43ac9e76491ee38033f9a46838c5abfbb"
MERGED_DST_UTC_BRIDGE_GIT_BLOB = "1e3860df58d229b566ff0383409dd7527ad25576"
ANCHOR = """C6_SEVASTOPOL_CHECKPOINT_BLOBS = {
 'scripts/add_sevastopol_exact.py': ('e4c091a677622eb28e504b0592a89e4d92d5fe02', '6698ec743b6efcd9aeb059dd81b51cc05ae93493'),
}
"""
EXTRA = """
# Exact owner-approved PR #93 blob at site-prod@6704c483; no wildcard drift.
C6_SEVASTOPOL_PR93_BLOBS = {
 'scripts/add_sevastopol_exact.py': ('e4c091a677622eb28e504b0592a89e4d92d5fe02', 'd31c5ac43ac9e76491ee38033f9a46838c5abfbb'),
}

# Exact source union-only UTC fix: site-prod@66a5120a (Actions #43645246989 PASS).
# Preserve every existing accepted hash; do not permit arbitrary collector drift.
C6_DST_UTC_BRIDGE_BLOBS = {
 'scripts/apply_ukrainealarm_bridge.py': ('8b95c4b508b9a473240889603f593e399cf8815d', '1e3860df58d229b566ff0383409dd7527ad25576'),
}
# Exact owner-approved additive weekday dayparts builder (PR #201).
# Previous site-prod@148c545d and new site-prod@ae650fea only; keep all other pins.
C6_WEEKDAY_HEATMAP_BLOBS = {
 'scripts/build_time_of_day_heatmap.py': ('382e815dc95ec4e0d7cb3cb3619e3242aba823ce', 'ad6c913ab7554eb59597702ee26a4b903b3d2c6f'),
}
"""
ORIGINAL_PREDICATE = "            C6_SEVASTOPOL_CHECKPOINT_BLOBS.get(path) == (expected, actual))"
PATCHED_PREDICATE = ("            C6_SEVASTOPOL_CHECKPOINT_BLOBS.get(path) == (expected, actual) or\n"
                     "            C6_SEVASTOPOL_PR93_BLOBS.get(path) == (expected, actual) or\n"
                     "            C6_DST_UTC_BRIDGE_BLOBS.get(path) == (expected, actual) or\n"
                     "            C6_WEEKDAY_HEATMAP_BLOBS.get(path) == (expected, actual))")


class PinBlocked(ValueError):
    pass


def git_blob(raw: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def patched_bytes(raw: bytes, parser_raw: bytes,
                  bridge_raw: bytes | None = None) -> bytes:
    if git_blob(raw) != BASE_GENERATOR_GIT_BLOB:
        raise PinBlocked("PINNED_GENERATOR_BLOB_MISMATCH")
    if git_blob(parser_raw) != MERGED_PR93_PARSER_GIT_BLOB:
        raise PinBlocked("PR93_PARSER_BLOB_MISMATCH")
    if bridge_raw is not None and git_blob(bridge_raw) != MERGED_DST_UTC_BRIDGE_GIT_BLOB:
        raise PinBlocked("DST_UTC_BRIDGE_BLOB_MISMATCH")
    original = raw.decode("utf-8")
    if original.count(ANCHOR) != 1 or original.count(ORIGINAL_PREDICATE) != 1:
        raise PinBlocked("PINNED_GENERATOR_CONTRACT_CHANGED")
    changed = original.replace(ANCHOR, ANCHOR + EXTRA).replace(
        ORIGINAL_PREDICATE, PATCHED_PREDICATE)
    compile(changed, "neon_json_shadow_generator.py", "exec")
    return changed.encode("utf-8")


def pin(generator: Path, parser: Path, bridge: Path | None = None) -> str:
    modified = patched_bytes(generator.read_bytes(), parser.read_bytes(),
                             bridge.read_bytes() if bridge is not None else None)
    generator.write_bytes(modified)
    return hashlib.sha256(modified).hexdigest()


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--generator", type=Path, required=True)
    cli.add_argument("--site-parser", type=Path, required=True)
    cli.add_argument("--site-bridge", type=Path,
                     help="Exact same-run site-prod UTC bridge (required by live C6 workflow)")
    args = cli.parse_args()
    try:
        digest = pin(args.generator, args.site_parser, args.site_bridge)
    except (PinBlocked, OSError, UnicodeError, SyntaxError):
        print("C6_GENERATOR_PIN_BLOCKED")
        return 2
    print("C6_PR93_EXACT_BLOB_PIN_PASS sha256=" + digest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
