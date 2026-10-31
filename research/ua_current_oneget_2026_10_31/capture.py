#!/usr/bin/env python3
"""Exactly one authorized UkraineAlarm /api/v3/alerts HTTP GET; no Neon, no publication.

Full raw body is AES-256-GCM encrypted with a per-capture key derived by HKDF
from the existing UKRAINEALARM_API_TOKEN; the token/key never enter an artifact.
The public repository never receives plaintext API response bytes.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
from datetime import datetime, timezone

import requests
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

BRANCH = "research-ua-current-oneget-2026-10-31"
URL = "https://api.ukrainealarm.com/api/v3/alerts"
REF_SHA = "bf5f0a1edcfa0930942c9ecc462a73af7d9644ac"
MAX_BYTES = 8 * 1024 * 1024
INFO = b"ua-current-oneget-2026-10-31-raw-body-v1"
AAD = b"olegbalakin-cmyk/kyiv-air-alerts-grafana:/api/v3/alerts:oneget-2026-10-31"

class Blocked(Exception):
    pass

def need(condition, code):
    if not condition:
        raise Blocked(code)

def sha(data):
    return hashlib.sha256(data).hexdigest()

def git_blob_sha(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()

def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True, default=str) + "\n", encoding="utf-8")

def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")

def encrypt_body(raw, token, out):
    salt = os.urandom(16)
    nonce = os.urandom(12)
    key = HKDF(algorithm=hashes.SHA256(), length=32, salt=salt, info=INFO).derive(token.encode("utf-8"))
    ciphertext = AESGCM(key).encrypt(nonce, raw, AAD)
    (out / "api_response.aes256gcm").write_bytes(ciphertext)
    save_json(out / "encryption.json", {
        "algorithm": "AES-256-GCM",
        "kdf": "HKDF-SHA256",
        "key_material": "existing UKRAINEALARM_API_TOKEN (never stored)",
        "kdf_info_utf8": INFO.decode(),
        "salt_b64": base64.b64encode(salt).decode(),
        "nonce_b64": base64.b64encode(nonce).decode(),
        "aad_utf8": AAD.decode(),
        "raw_sha256": sha(raw),
        "encrypted_sha256": sha(ciphertext),
        "raw_bytes": len(raw),
        "encrypted_bytes": len(ciphertext),
        "archive_confidentiality": "encrypted even if a public GitHub Actions artifact is downloaded",
    })
    return ciphertext

def summarize(rows, matrix, captured_at):
    all_ids = [str(r.get("regionId")) for r in rows if isinstance(r, dict) and r.get("regionId") is not None]
    result = {}
    for city, spec in sorted(matrix.items()):
        if spec.get("provider") != "ukrainealarm":
            continue
        wanted = str(spec["region_id"])
        direct = [r for r in rows if isinstance(r, dict) and str(r.get("regionId")) == wanted]
        nested_host_ids = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            for alert in (row.get("activeAlerts") if isinstance(row.get("activeAlerts"), list) else []):
                if isinstance(alert, dict) and str(alert.get("regionId")) == wanted:
                    host = row.get("regionId")
                    if host is not None and str(host) != wanted:
                        nested_host_ids.append(str(host))
        alert_items = []
        for row in direct:
            aa = row.get("activeAlerts")
            if isinstance(aa, list):
                alert_items.extend(a for a in aa if isinstance(a, dict))
        types = sorted(set(str(a.get("type", a.get("alertType", "UNSPECIFIED"))) for a in alert_items))
        air_count = sum(str(a.get("type", a.get("alertType", ""))).upper() == "AIR" for a in alert_items)
        parent_fields = sorted({
            k for r in direct for k in ("parentRegionId", "parentId", "regionParentId")
            if k in r
        })
        result[city] = {
            "region_id": wanted,
            "source_type": spec.get("source_type"),
            "proxy_raion": spec.get("proxy_raion"),
            "direct_top_level_entries": len(direct),
            "direct_entry_found": len(direct) == 1,
            "direct_air_alert_objects_observed": air_count,
            "direct_alert_types_observed": types,
            "lastUpdate_values_in_direct_rows": [r.get("lastUpdate") for r in direct],
            "nested_under_other_top_level_ids": sorted(set(nested_host_ids)),
            "parent_reference_field_names_in_direct_rows": parent_fields,
            "ancestor_status_certified": False,
            "absent_direct_entry_interpretation": "UNKNOWN_NOT_PROVEN_INACTIVE" if not direct else None,
            "air_negative_status_certified": False,
        }
    need(len(result) == 21, "INVALID_MATRIX_CITY_COUNT")
    direct_count = sum(x["direct_entry_found"] for x in result.values())
    return {
        "captured_at_utc": captured_at,
        "schema": "c6-ua-current-oneget-2026-10-31-v1",
        "top_level_rows": len(rows),
        "top_level_rows_with_region_id": len(all_ids),
        "duplicate_top_level_region_ids": sorted({x for x in all_ids if all_ids.count(x) > 1}),
        "full_response_top_level_region_ids": sorted(set(all_ids)),
        "required_21": len(result),
        "required_21_direct_rows_unique": direct_count,
        "required_21_missing_or_ambiguous_direct_rows": sorted(c for c, x in result.items() if not x["direct_entry_found"]),
        "cities": result,
        "current_source_currency_certified": False,
        "ancestor_region_interpretation_certified": False,
        "negative_air_status_certified": False,
        "lastUpdate_is_not_proven_startDate": True,
        "notes": "Top-level missing region does not prove no alert. Nested AIR and inherited region semantics require independently supported contracts.",
    }

def main():
    args = argparse.ArgumentParser()
    args.add_argument("--matrix", type=Path, required=True)
    args.add_argument("--output", type=Path, required=True)
    cfg = args.parse_args()
    out = cfg.output
    out.mkdir(parents=True, exist_ok=True)
    verdict = {
        "checkpoint": "C6-UA-CURRENT-ONEGET-01",
        "scope": "research_only_one_authorized_get",
        "status": "BLOCKED",
        "endpoint": URL,
        "http_attempts": 0,
        "http_redirects": 0,
        "http_retries": 0,
        "neon_operations": 0,
        "production_mutations": 0,
        "publication_allowed": False,
        "C6": "PARTIAL",
        "C3": "PARTIAL",
        "GLOBAL_CUTOVER": "NO",
        "github_sha": os.environ.get("GITHUB_SHA"),
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "raw_plaintext_in_git_or_artifact": False,
    }
    code = 1
    try:
        need(os.environ.get("GITHUB_REF") == "refs/heads/" + BRANCH, "RESEARCH_BRANCH_GUARD")
        need(os.environ.get("GITHUB_RUN_ATTEMPT") == "1", "RERUN_NOT_AUTHORIZED")
        matrix_bytes = cfg.matrix.read_bytes()
        need(git_blob_sha(matrix_bytes) == REF_SHA, "PINNED_23CITY_SOURCE_MATRIX_MISMATCH")
        matrix = json.loads(matrix_bytes)
        ua = [x for x in matrix.values() if x.get("provider") == "ukrainealarm"]
        need(len(matrix) == 23 and len(ua) == 21, "MAPPING_CARDINALITY_MISMATCH")
        need(sum(x.get("source_type") == "exact_city" for x in ua) == 2, "EXACT_CITY_MAPPING_MISMATCH")
        token = os.environ.get("UKRAINEALARM_API_TOKEN", "").strip()
        need(len(token) >= 8, "TOKEN_NOT_AVAILABLE")

        # One physical attempt, no redirect and no retry. No Swagger/history/regions requests.
        session = requests.Session()
        session.mount("https://", requests.adapters.HTTPAdapter(max_retries=0))
        verdict["http_attempts"] = 1
        try:
            with session.get(
                URL,
                headers={"Authorization": token, "Accept": "application/json",
                         "Accept-Encoding": "identity",
                         "User-Agent": "kyiv-air-alerts-grafana/research-oneget-current-20261031"},
                timeout=(10, 30), stream=True, allow_redirects=False,
            ) as response:
                received_status = response.status_code
                safe_headers = {
                    k: response.headers.get(k) for k in
                    ("Date", "Content-Type", "Cache-Control", "Last-Modified", "ETag", "Retry-After")
                }
                body = response.raw.read(MAX_BYTES + 1, decode_content=True)
                captured_at = now_iso()
        finally:
            session.close()
        need(len(body) <= MAX_BYTES, "API_ENTITY_EXCEEDS_8MIB_LIMIT")
        ciphertext = encrypt_body(body, token, out)
        verdict["api_response_encrypted"] = True
        save_json(out / "http_receipt.json", {
            "method": "GET",
            "url": URL,
            "http_status": received_status,
            "safe_response_headers": safe_headers,
            "captured_at_utc": captured_at,
            "raw_sha256": sha(body),
            "ciphertext_sha256": sha(ciphertext),
            "raw_length_bytes": len(body),
            "no_retry": True,
            "no_redirect": True,
            "authorization_secret_omitted": True,
        })
        verdict["http_status"] = received_status
        need(received_status == 200, "DATA_API_HTTP_" + str(received_status))
        need("json" in str(safe_headers.get("Content-Type", "")).lower(), "DATA_API_CONTENT_TYPE_NOT_JSON")
        payload = json.loads(body.decode("utf-8", "strict"))
        if isinstance(payload, list):
            rows = payload
            verdict["response_top_level_type"] = "list"
        elif isinstance(payload, dict) and isinstance(payload.get("raw"), list):
            rows = payload["raw"]
            verdict["response_top_level_type"] = "object.raw"
        else:
            raise Blocked("UNKNOWN_CURRENT_API_ARRAY_CONTRACT")
        matrix_result = summarize(rows, matrix, captured_at)
        save_json(out / "region_matrix.json", matrix_result)
        verdict.update({
            "status": "PASS_BOUNDED_CURRENT_API_ACCESS",
            "verdict": "ACCESS_PASS_21_CITY_SEMANTICS_PARTIAL",
            "response_sha256": sha(body),
            "top_level_rows": len(rows),
            "required_21_direct_rows_unique": matrix_result["required_21_direct_rows_unique"],
            "current_active_complete": False,
            "full_active_status_contract": "NOT_PROVEN",
            "history_api_called": False,
        })
        code = 0
    except Exception as exc:
        verdict["failure_code"] = str(exc) if isinstance(exc, Blocked) else type(exc).__name__
        verdict["verdict"] = "BLOCKED_FAIL_CLOSED"
    finally:
        verdict["evaluated_at_utc"] = now_iso()
        save_json(out / "machine_verdict.json", verdict)
        save_json(out / "sha256_manifest.json", {
            "schema": "c6-ua-current-oneget-2026-10-31-manifest-v1",
            "files": {str(p.relative_to(out)): sha(p.read_bytes())
                      for p in sorted(out.rglob("*")) if p.is_file() and p.name != "sha256_manifest.json"},
        })
        print(json.dumps({
            k: verdict.get(k) for k in
            ("checkpoint", "status", "verdict", "http_attempts", "http_status",
             "required_21_direct_rows_unique", "failure_code", "publication_allowed")
        }, sort_keys=True))
    return code

if __name__ == "__main__":
    raise SystemExit(main())
