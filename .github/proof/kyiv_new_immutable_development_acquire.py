#!/usr/bin/env python3
"""Proof-only: immutable new development evidence acquisition on a GitHub runner."""
from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import os
import re
import sys
import time
import zlib
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[2]
PILOT = ROOT / ".github/proof/kyiv_historical_discovery_calibration_pilot.py"
INPUT = ROOT / "research/kyiv_historical_discovery_development_classifier_input_2026-10-08.json"
EXPECTED_INPUT_BLOB = "6e3d4e878e9b8258c3bdbba709fb34958f391263"
STAMP = "2026-10-09"
UTC = timezone.utc
ORIGINAL = {
    "VA_Kyiv", "KyivCityOfficial", "vitaliy_klitschko", "dsns_kyiv",
    "kpszsu", "suspilnenews", "suspilne_kyiv", "suspilne.media/kyiv",
}
VARIANT_A = {
    "bbc.com": "BBC_Ukrainian",
    "radiosvoboda.org": "Radio_Svoboda",
    "suspilne.media": "Suspilne_National",
}
STAGE2 = {
    "24tv.ua": "24_Kanal",
    "5.ua": "5.ua",
    "fakty.com.ua": "Fakty_ICTV",
    "focus.ua": "Focus",
    "kyiv24.news": "Kyiv24",
    "bigkyiv.com.ua": "bigkyiv.com.ua",
    "kyiv.novyny.live": "kyiv.novyny.live",
    "vikna.tv": "vikna.tv",
    "war.telegraf.com.ua": "war.telegraf.com.ua",
    "glavcom.ua": "Glavcom",
    "novynarnia.com": "Novynarnia",
    "zaxid.net": "zaxid.net",
    "ye.ua": "ye.ua",
}
TRANSIENT = (408, 425, 429, 500, 502, 503, 504)


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical_bytes(obj):
    return (json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def freeze(path, payload):
    payload["payload_sha256"] = digest(canonical_bytes(payload))
    path.write_bytes(canonical_bytes(payload))
    return payload["payload_sha256"]


def now():
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def assert_no_db_credentials():
    flagged = [
        name for name, value in os.environ.items()
        if value and (
            name in {"DATABASE_URL", "DIRECT_URL", "PGHOST", "PGUSER", "PGPASSWORD", "PGDATABASE"}
            or name.startswith(("NEON_", "POSTGRES_", "SUPABASE_DB_"))
        )
    ]
    if flagged:
        raise RuntimeError("DB_CREDENTIAL_PRESENT:" + ",".join(sorted(flagged)))


def host_of(url):
    return (urlparse(str(url or "")).hostname or "").lower().removeprefix("www.")


def family_for(p, url):
    fixed = p.fixed_family_for_url(url)
    if fixed:
        return fixed[0]
    h = host_of(url)
    path = urlparse(str(url or "")).path.lower()
    if h == "suspilne.media" and path.startswith("/kyiv/"):
        return "suspilne.media/kyiv"
    return VARIANT_A.get(h) or STAGE2.get(h) or ("OUTSIDE:" + h)


def development_cohort():
    import subprocess
    actual = subprocess.check_output(
        ["git", "rev-parse", "HEAD:research/kyiv_historical_discovery_development_classifier_input_2026-10-08.json"],
        cwd=ROOT, text=True,
    ).strip()
    if actual != EXPECTED_INPUT_BLOB:
        raise RuntimeError("FROZEN_DEVELOPMENT_INPUT_BLOB_MISMATCH:" + actual)
    doc = json.loads(INPUT.read_text(encoding="utf-8"))
    if doc.get("blind_data_used") is not False:
        raise RuntimeError("DEVELOPMENT_INPUT_BLINDNESS_ASSERTION_FAILED")
    rows = doc.get("episodes") or []
    if len(rows) != 67 or len({r["episode_id"] for r in rows}) != 67:
        raise RuntimeError("DEVELOPMENT_COHORT_NOT_67")
    labels = Counter(r.get("truth_label") for r in rows)
    if labels["HOLD_CONTROL"] != 19 or sum(v for k, v in labels.items() if k in (
        "STRICT_EVENT_POSITIVE", "SENSITIVITY_EVENT_POSITIVE"
    )) != 48:
        raise RuntimeError("DEVELOPMENT_LABEL_COUNTS_MISMATCH")
    # Deliberately project only sanitized timing/identity fields; no old URLs/text.
    return [{k: r[k] for k in ("episode_id", "city_key", "alert_start", "alert_end")} for r in rows]


class NativeHTTP:
    """Original extraction receives a requests-compatible .get, with bounded retries."""
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; kyiv-historical-discovery-calibration/1.0)",
            "Accept-Language": "uk,en;q=0.7",
        })
        self.responses = []
        self.retry_count = 0

    def get(self, url, *, timeout=20):
        last = None
        for attempt in range(2):
            response = None
            try:
                response = self.session.get(url, timeout=timeout, allow_redirects=True)
                raw = response.content
                record = {
                    "requested_url": url,
                    "final_url": response.url,
                    "http_status": response.status_code,
                    "retrieved_at_utc": now(),
                    "content_type": response.headers.get("content-type"),
                    "response_identity_headers": {
                        k: response.headers.get(k) for k in (
                            "etag", "last-modified", "content-length", "content-location"
                        ) if response.headers.get(k) is not None
                    },
                    "raw_response_sha256": digest(raw),
                    "raw_response_bytes": len(raw),
                    "retry_index": attempt,
                    "raw_zlib_base64": (
                        base64.b64encode(zlib.compress(raw, 6)).decode("ascii")
                        if len(raw) <= 250000 else None
                    ),
                    "raw_bytes_omission_reason": "SIZE_LIMIT" if len(raw) > 250000 else None,
                }
                self.responses.append(record)
                if response.status_code in TRANSIENT and attempt == 0:
                    self.retry_count += 1
                    time.sleep(0.5)
                    continue
                response.raise_for_status()
                return response
            except (requests.ConnectionError, requests.Timeout) as exc:
                last = exc
                self.responses.append({
                    "requested_url": url, "retrieved_at_utc": now(),
                    "retry_index": attempt, "technical_error": f"{type(exc).__name__}:{exc}",
                })
                if attempt == 0:
                    self.retry_count += 1
                    time.sleep(0.5)
                    continue
                raise
            except requests.RequestException:
                raise
        raise RuntimeError(f"NATIVE_HTTP_FAILED:{url}:{last}")


def acquire_native(p, url):
    session = NativeHTTP()
    family = family_for(p, url)
    try:
        if p.tg_identity(url):
            native, error = p.fetch_telegram_post(session, url)
            method = "unchanged:fetch_telegram_post"
        else:
            native, error = p.extract_article(session, url)
            method = "unchanged:extract_article"
    except Exception as exc:
        native, error, method = None, f"NATIVE_EXCEPTION:{type(exc).__name__}:{exc}", "exception"
    final = (native or {}).get("url")
    if native and family_for(p, final) != family:
        error = "SOURCE_FAMILY_CHANGED_ON_REDIRECT"
        native = None
    if native and not native.get("text"):
        error = "NATIVE_TEXT_EMPTY"
        native = None
    text_value = str((native or {}).get("text") or "")
    return {
        "requested_native_url": url,
        "normalized_source_family": family,
        "final_native_url": (native or {}).get("url"),
        "method": method,
        "extraction_version": "frozen_calibration_pilot:2bd9b9ee2f6d9c797c816476cc25e72214584a86",
        "native": native,
        "exact_extracted_text": text_value if native else None,
        "extracted_text_sha256": digest(text_value.encode("utf-8")) if native else None,
        "publication_timestamp": (native or {}).get("published_at"),
        "update_timestamp": None,
        "error": error,
        "http_responses": session.responses,
        "native_retry_count": session.retry_count,
    }


def run(outdir):
    assert_no_db_credentials()
    outdir.mkdir(parents=True, exist_ok=True)
    p = load(PILOT, "immutable_discovery_calibration")
    cohort = development_cohort()
    print("JOB_A_DEVELOPMENT_EPISODES=" + str(len(cohort)), flush=True)
    http = p.HTTP()
    hits = []
    queries = []
    failures = Counter()
    for index, ep in enumerate(cohort, 1):
        start = p.parse_dt(ep["alert_start"]) - timedelta(hours=6)
        end = p.parse_dt(ep["alert_end"]) + timedelta(hours=24)
        query_specs = [
            ("fixed_aggregate", p.fixed_aggregate_query(start, end)),
            ("generic_search", p.google_news_query(None, start, end)),
        ]
        for query_family, query_url in query_specs:
            query = {
                "episode_id": ep["episode_id"],
                "query_family": query_family,
                "exact_query": parse_qs(urlparse(query_url).query).get("q", [""])[0],
                "query_url": query_url,
                "search_window_start_utc": p.iso(start),
                "search_window_end_utc": p.iso(end),
                "discovery_timestamp_utc": now(),
                "hit_count": 0,
                "error": None,
            }
            try:
                rss = http.get(query_url)
                items = p.parse_google_rss(rss.content)
            except Exception as exc:
                items = []
                query["error"] = f"{type(exc).__name__}:{exc}"
                failures["discovery"] += 1
            query["hit_count"] = len(items)
            queries.append(query)
            for rank, item in enumerate(items, 1):
                hits.append({
                    "episode_id": ep["episode_id"],
                    "query_family": query_family,
                    "exact_query": query["exact_query"],
                    "search_window_start_utc": query["search_window_start_utc"],
                    "search_window_end_utc": query["search_window_end_utc"],
                    "result_rank": rank,
                    "result_title": item.get("title"),
                    "result_snippet": item.get("description"),
                    "wrapper_url": item.get("link"),
                    "publisher_metadata": {
                        "name": item.get("source"), "pubDate": item.get("pubDate")
                    },
                    "discovery_timestamp_utc": query["discovery_timestamp_utc"],
                    "native_url": None,
                    "resolver_method": None,
                    "resolver_error": None,
                })
        print(f"JOB_A_QUERY_PROGRESS={index}/67 queries={len(queries)} hits={len(hits)}", flush=True)

    print("JOB_A_DISCOVERY_QUERIES=" + str(len(queries)), flush=True)
    print("JOB_A_SEARCH_HITS=" + str(len(hits)), flush=True)
    # Resolve only fresh development RSS results. The existing Google resolver
    # is invoked without changes; no truth URL or historical text participates.
    resolved_wrappers = {}
    for index, hit in enumerate(hits, 1):
        wrapper = hit["wrapper_url"]
        if wrapper in resolved_wrappers:
            native_url, error, trace = resolved_wrappers[wrapper]
        else:
            item = {
                "link": wrapper,
                "title": hit["result_title"],
                "description": hit["result_snippet"],
                "source": hit["publisher_metadata"]["name"],
                "pubDate": hit["publisher_metadata"]["pubDate"],
            }
            before = len(http.resolution_events)
            native_url, error = p.resolve_google_result(http, item)
            trace = http.resolution_events[-1] if len(http.resolution_events) > before else {}
            resolved_wrappers[wrapper] = (native_url, error, trace)
        hit["native_url"] = p.canonical_url(native_url) if native_url else None
        hit["resolver_method"] = trace.get("resolution_outcome")
        hit["resolver_path"] = {
            k: trace.get(k) for k in (
                "legacy_resolution_attempted", "opaque_decode_attempted",
                "metadata_signature_step_status", "rpc_step_status"
            )
        }
        hit["native_domain"] = p.host_of(native_url) if native_url else None
        hit["normalized_source_family_candidate"] = family_for(p, native_url) if native_url else None
        hit["resolver_error"] = error
        if index % 100 == 0:
            print(f"JOB_A_RESOLVE_PROGRESS={index}/{len(hits)} resolved={sum(bool(x[0]) for x in resolved_wrappers.values())}", flush=True)

    native_urls = sorted({x["native_url"] for x in hits if x["native_url"]})
    print("JOB_A_NATIVE_URLS_RESOLVED=" + str(len(native_urls)), flush=True)
    native_records = {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        tasks = {pool.submit(acquire_native, p, url): url for url in native_urls}
        for index, future in enumerate(as_completed(tasks), 1):
            url = tasks[future]
            try:
                native_records[url] = future.result()
            except Exception as exc:
                native_records[url] = {
                    "requested_native_url": url,
                    "native": None,
                    "exact_extracted_text": None,
                    "error": f"FUTURE_EXCEPTION:{type(exc).__name__}:{exc}",
                    "http_responses": [],
                }
            if index % 25 == 0:
                ok = sum(bool(x.get("exact_extracted_text")) for x in native_records.values())
                print(f"JOB_A_NATIVE_PROGRESS={index}/{len(native_urls)} succeeded={ok}", flush=True)

    normalized = []
    for url, record in sorted(native_records.items()):
        native = record.get("native")
        if not native or not native.get("text"):
            continue
        family = family_for(p, native["url"])
        normalized.append({
            "requested_native_url": url,
            "canonical_native_url": native["url"],
            "source_family": family,
            "title": native.get("title"),
            "publication_timestamp": native.get("published_at"),
            "exact_normalized_text": native["text"],
            "normalized_text_sha256": digest(native["text"].encode("utf-8")),
            "extraction_provenance": {
                "method": record["method"],
                "version": record["extraction_version"],
                "native_response_sha256": (
                    next((x.get("raw_response_sha256") for x in record["http_responses"]
                          if x.get("raw_response_sha256")), None)
                ),
            },
        })
    document_a = {
        "schema": "kyiv-new-immutable-runner-discovery-v1",
        "source": "NEW_DEVELOPMENT_DISCOVERY",
        "created_at_utc": now(),
        "development_episodes": cohort,
        "queries": queries,
        "search_hits": hits,
        "counts": {
            "discovery_queries_executed": len(queries),
            "search_hits_frozen": len(hits),
            "native_urls_resolved": len(native_urls),
            "query_failures": failures["discovery"],
        },
        "blind_per_episode_data_inspected": False,
        "blind_wrapper_decode_attempts": 0,
    }
    document_b = {
        "schema": "kyiv-new-immutable-runner-native-corpus-v1",
        "created_at_utc": now(),
        "records": [native_records[u] for u in sorted(native_records)],
        "counts": {
            "attempted": len(native_urls),
            "succeeded": sum(bool(x.get("exact_extracted_text")) for x in native_records.values()),
            "failed": sum(not bool(x.get("exact_extracted_text")) for x in native_records.values()),
            "exact_text_records_frozen": len(normalized),
        },
        "native_urls_acquired_at_most_once_logically": len(native_records) == len(native_urls),
    }
    document_c = {
        "schema": "kyiv-new-immutable-runner-normalized-evidence-v1",
        "created_at_utc": now(),
        "records": normalized,
        "counts": {"exact_text_records": len(normalized)},
        "source_native_extraction_semantics_changed": False,
    }
    hashes = {
        "discovery_corpus_sha256": freeze(outdir / f"kyiv_historical_runner_discovery_snapshot_{STAMP}.json", document_a),
        "native_corpus_sha256": freeze(outdir / f"kyiv_historical_runner_native_corpus_{STAMP}.json", document_b),
        "normalized_evidence_sha256": freeze(outdir / f"kyiv_historical_runner_normalized_evidence_{STAMP}.json", document_c),
    }
    (outdir / "job_a_summary.json").write_bytes(canonical_bytes({
        "schema": "kyiv-runner-acquire-summary-v1",
        "metrics": {**document_a["counts"], **document_b["counts"], **document_c["counts"]},
        "hashes": hashes,
        "authorized_classifier_commit": "71cb6f6fbe856cc7b96759310fe9cc9c71cc0453",
        "authorized_classifier_blob": "778469b74c2aa807d851cf2c2ee35cf4aa785589",
        "blind_per_episode_data_inspected": False,
        "blind_wrapper_decode_attempts": 0,
        "neon_writes": 0,
        "production_mutations": 0,
    }))
    print("JOB_A_FINAL_SUMMARY=" + json.dumps({
        "queries": len(queries), "hits": len(hits), "resolved": len(native_urls),
        "attempted": len(native_urls), "succeeded": document_b["counts"]["succeeded"],
        "text_records": len(normalized), **hashes,
    }, sort_keys=True), flush=True)
    if not queries:
        raise RuntimeError("JOB_A_DISCOVERY_QUERIES_ZERO")
    if not hits:
        raise RuntimeError("JOB_A_SEARCH_RESULTS_ZERO")
    if not native_urls:
        raise RuntimeError("JOB_A_NATIVE_URLS_ZERO")
    if not native_records:
        raise RuntimeError("JOB_A_NATIVE_ACQUISITION_NEVER_STARTED")
    if not normalized or not all(hashes.values()):
        raise RuntimeError("JOB_A_EXACT_EVIDENCE_NOT_PERSISTED")
    print("JOB_A_ACCEPTANCE=PASS", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    try:
        run(arguments.output_dir)
    except Exception as exc:
        print(f"JOB_A_FAILURE={type(exc).__name__}:{exc}", file=sys.stderr, flush=True)
        raise
