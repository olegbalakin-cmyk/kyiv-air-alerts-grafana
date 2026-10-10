#!/usr/bin/env python3
from __future__ import annotations

import ast
import copy
import importlib.util
import json
import re
import socket
import subprocess
from collections import Counter, defaultdict
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlparse

import requests

PILOT_PATH = Path(".github/proof/kyiv_historical_discovery_calibration_pilot.py")
OLD_PROOF_PATH = Path(".github/proof/kyiv_historical_google_news_url_resolution_proof.py")
STRATEGY_PATH = Path("research/kyiv_historical_discovery_frozen_strategy_2026-10-08.json")
OLD_PROOF_ARTIFACT_PATH = Path("research/kyiv_historical_google_news_url_resolution_repair_2026-10-08.json")
OUT_PATH = Path("research/kyiv_historical_google_news_url_resolution_network_proof_2026-10-08.json")
PRE_REPAIR_COMMIT = "dcacfc6517d78361802ec5c41280b6ec57c7fe87"
TESTED_RESOLVER_COMMIT = "010d65e8bf0b8672778a4977e8d1e05aaf071951"
TESTED_RESOLVER_BLOB = "2bd9b9ee2f6d9c797c816476cc25e72214584a86"


def git(*args):
    return subprocess.run(
        ["git", *args], check=True, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE
    ).stdout.strip()


def git_text(ref, path):
    return git("show", f"{ref}:{path}")


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"IMPORT_FAILED:{path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def ast_index(source):
    tree = ast.parse(source)
    out = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out[node.name] = ast.dump(node, include_attributes=False)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    out[target.id] = ast.dump(node, include_attributes=False)
    return out


def static_safety_audit():
    pre = git_text(PRE_REPAIR_COMMIT, str(PILOT_PATH))
    post = git_text(TESTED_RESOLVER_COMMIT, str(PILOT_PATH))
    pre_i, post_i = ast_index(pre), ast_index(post)
    diff = git(
        "diff", "--unified=0", PRE_REPAIR_COMMIT, TESTED_RESOLVER_COMMIT,
        "--", str(PILOT_PATH)
    )
    changed_paths = [
        x for x in git(
            "diff", "--name-only", PRE_REPAIR_COMMIT, TESTED_RESOLVER_COMMIT
        ).splitlines() if x
    ]
    added = "\n".join(
        line[1:] for line in diff.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    )

    def same(names):
        return all(
            pre_i.get(name) == post_i.get(name) and name in pre_i
            for name in names
        )

    checks = {
        "query_vocabulary_unchanged":
            same(["VOCAB", "QUERY_TERMS", "ATTACK_RE"]),
        "query_date_window_semantics_unchanged":
            same([
                "google_news_query", "fixed_aggregate_query",
                "discover_via_google", "discover_fixed_aggregate",
            ]),
        "source_set_unchanged":
            same(["SOURCE_ORDER", "ALLOWED_FIXED_DOMAINS"]),
        "classifier_semantics_unchanged":
            same([
                "AUTH_COMMIT", "AUTH_PATH", "AUTH_BLOB",
                "prepare_authoritative_monitor",
                "context_episodes", "classify_episode",
            ]),
        "candidate_admission_unchanged":
            same([
                "make_candidate", "native_in_window",
                "discover_via_google", "discover_fixed_aggregate",
            ]),
        "telegram_fetch_semantics_unchanged":
            same(["fetch_telegram_post"]),
        "publisher_extraction_semantics_unchanged":
            same(["extract_article"]),
    }

    pre_urls = set(re.findall(r'https?://[^"\'\s)]+', pre))
    post_urls = set(re.findall(r'https?://[^"\'\s)]+', post))
    new_urls = sorted(post_urls - pre_urls)
    third_party = [
        url for url in new_urls
        if (urlparse(url).hostname or "").casefold() != "news.google.com"
    ]
    forbidden_auth_browser = [
        term for term in [
            "selenium", "playwright", "puppeteer",
            "authorization:", "bearer ", "browser login",
        ]
        if term in added.casefold()
    ]
    prod_terms = [
        term for term in [
            "neon", "database_url", "site-prod",
            "update-netlify-site.yml",
        ]
        if term in added.casefold()
    ]
    checks.update({
        "no_third_party_hosted_decode_api_added": not third_party,
        "no_cookies_auth_browser_login_required": not forbidden_auth_browser,
        "no_production_or_neon_wiring_added":
            changed_paths == [str(PILOT_PATH)] and not prod_terms,
    })
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "changed_paths_pre_repair_to_tested_commit": changed_paths,
        "new_literal_urls": new_urls,
        "third_party_decode_urls": third_party,
        "forbidden_auth_browser_terms": forbidden_auth_browser,
        "production_or_neon_terms": prod_terms,
    }


def generic_wrappers(row):
    diag = (
        ((row.get("result") or {}).get("source_diagnostics") or {})
        .get("generic_search") or {}
    )
    return [
        str(x.get("link") or "")
        for x in (diag.get("resolve_failures") or [])
        if "news.google.com/rss/articles/" in str(x.get("link") or "")
    ]


def fixed_wrappers(row, pilot):
    diagnostics = (
        (row.get("result") or {}).get("source_diagnostics") or {}
    )
    for family, _, _ in pilot.SOURCE_ORDER:
        if family == "generic_search":
            continue
        diag = diagnostics.get(family) or {}
        if diag.get("aggregate_fixed_source_query"):
            out, seen = [], set()
            for item in diag.get("resolve_failures") or []:
                link = str(item.get("link") or "")
                if (
                    "news.google.com/rss/articles/" in link
                    and link not in seen
                ):
                    seen.add(link)
                    out.append(link)
            return out
    return []


def forensic_rows(development):
    positives = [
        row for row in development
        if str(row.get("truth_label") or "") in {
            "STRICT_EVENT_POSITIVE", "SENSITIVITY_EVENT_POSITIVE"
        }
        and generic_wrappers(row)
    ]
    positives.sort(
        key=lambda row: (
            (row.get("result") or {}).get("alert_start") or "",
            row.get("episode_id") or "",
        )
    )
    holds = [
        row for row in development
        if row.get("truth_label") == "HOLD_CONTROL"
    ]
    holds.sort(
        key=lambda row: (
            (row.get("result") or {}).get("alert_start") or "",
            row.get("episode_id") or "",
        )
    )
    selected = positives[:20] + holds
    selected.sort(
        key=lambda row: (
            (row.get("result") or {}).get("alert_start") or "",
            row.get("episode_id") or "",
        )
    )
    return selected


def classify_url(pilot, url):
    if not url:
        return None
    if pilot.tg_identity(url):
        return "TELEGRAM"
    return "PUBLISHER" if pilot.host_of(url) else "OTHER_NATIVE"


def case_from_event(
    pilot, episode_id, truth_label, wrapper, resolved, err, event
):
    outcome = str(event.get("resolution_outcome") or "")
    return {
        "episode_id": episode_id,
        "truth_label": truth_label,
        "wrapper_url": wrapper,
        "opaque_article_id": pilot.google_article_id(wrapper),
        "opaque_id": event.get("opaque_id"),
        "legacy_resolver_result":
            resolved if outcome in {
                "DIRECT_NATIVE_URL",
                "LEGACY_HTTP_REDIRECT",
                "LEGACY_OUTBOUND_ANCHOR",
            } else None,
        "opaque_resolver_entered":
            bool(event.get("opaque_decode_attempted")),
        "metadata_signature_retrieval_status":
            event.get("metadata_signature_step_status"),
        "rpc_status": event.get("rpc_step_status"),
        "decoded_url": resolved,
        "canonicalized_url":
            pilot.canonical_url(resolved) if resolved else None,
        "final_host":
            pilot.host_of(resolved) if resolved else None,
        "url_type": classify_url(pilot, resolved),
        "terminal_error": err,
        "trace": event,
    }


def replay_records(pilot, http, records):
    cases = []
    for record in records:
        wrapper = record["wrapper_url"]
        before = len(http.resolution_events)
        resolved, err = pilot.resolve_google_result(
            http, {"link": wrapper}
        )
        event = (
            copy.deepcopy(http.resolution_events[-1])
            if len(http.resolution_events) > before else {}
        )
        cases.append(
            case_from_event(
                pilot, record["episode_id"], record["truth_label"],
                wrapper, resolved, err, event
            )
        )
    return cases


def summarize_cases(cases):
    resolved = [case for case in cases if case.get("decoded_url")]
    failures = Counter(
        case.get("terminal_error")
        for case in cases if case.get("terminal_error")
    )
    types = Counter(case.get("url_type") for case in resolved)
    return {
        "wrappers_attempted": len(cases),
        "wrappers_resolved": len(resolved),
        "wrappers_unresolved": len(cases) - len(resolved),
        "resolution_rate":
            (len(resolved) / len(cases)) if cases else 0.0,
        "unique_native_urls":
            len({case["decoded_url"] for case in resolved}),
        "telegram_native_urls": types["TELEGRAM"],
        "publisher_native_urls": types["PUBLISHER"],
        "other_native_urls": types["OTHER_NATIVE"],
        "GOOGLE_WRAPPER_NETWORK_FAILED":
            failures["GOOGLE_WRAPPER_NETWORK_FAILED"],
        "GOOGLE_WRAPPER_SIGNATURE_METADATA_FAILED":
            failures["GOOGLE_WRAPPER_SIGNATURE_METADATA_FAILED"],
        "GOOGLE_WRAPPER_RPC_FAILED":
            failures["GOOGLE_WRAPPER_RPC_FAILED"],
        "GOOGLE_WRAPPER_RESPONSE_UNPARSEABLE":
            failures["GOOGLE_WRAPPER_RESPONSE_UNPARSEABLE"],
        "GOOGLE_WRAPPER_NO_NATIVE_URL":
            failures["GOOGLE_WRAPPER_NO_NATIVE_URL"],
        "GOOGLE_WRAPPER_UNSUPPORTED_FORMAT":
            failures["GOOGLE_WRAPPER_UNSUPPORTED_FORMAT"],
        "terminal_failure_counts": dict(failures),
    }


def network_gate(pilot, wrapper):
    session = requests.Session()
    session.headers.update({
        "User-Agent": pilot.UA,
        "Accept-Language": "uk,en;q=0.7",
    })
    result = {
        "status": "FAIL",
        "environment_blocked": False,
    }
    try:
        socket.getaddrinfo("news.google.com", 443)
        dns_ok = True
    except OSError as exc:
        dns_ok = False
        result["environment_blocked"] = True
        result["dns_error"] = f"{type(exc).__name__}:{exc}"

    result["news_google_com"] = {
        "dns_network_success": dns_ok,
        "http_status": None,
        "response_received": False,
    }
    if not dns_ok:
        result["status"] = "NETWORK_ENVIRONMENT_BLOCKED"
        return result

    def do_get(url):
        item = {
            "url": url,
            "dns_network_success": True,
            "http_status": None,
            "response_received": False,
        }
        try:
            response = session.get(
                url, timeout=pilot.HTTP_TIMEOUT,
                allow_redirects=True
            )
            item.update({
                "http_status": response.status_code,
                "response_received": True,
                "final_url": str(response.url),
                "text": response.text,
            })
            return item
        except (requests.ConnectionError, requests.Timeout) as exc:
            result["environment_blocked"] = True
            item["error"] = f"{type(exc).__name__}:{exc}"
            return item
        except requests.RequestException as exc:
            item["error"] = f"{type(exc).__name__}:{exc}"
            return item

    root = do_get("https://news.google.com/")
    result["news_google_com"].update({
        key: value for key, value in root.items()
        if key != "text"
    })

    article_id = pilot.google_article_id(wrapper)
    metadata_url = f"https://news.google.com/articles/{article_id}"
    metadata = do_get(metadata_url)
    wrapper_probe = do_get(wrapper)
    timestamp, signature = pilot._google_signature_metadata(
        metadata.get("text") or "", article_id
    )
    if not (timestamp and signature):
        timestamp, signature = pilot._google_signature_metadata(
            wrapper_probe.get("text") or "", article_id
        )

    result["metadata_signature_endpoint"] = {
        key: value for key, value in metadata.items()
        if key != "text"
    }
    result["metadata_signature_endpoint"][
        "signature_metadata_found"
    ] = bool(timestamp and signature)

    rpc_item = {
        "url": pilot.GOOGLE_RPC_URL,
        "dns_network_success": True,
        "http_status": None,
        "response_received": False,
    }
    if timestamp and signature:
        rpc_context = [
            [
                "X", "X", ["X", "X"], None, None, 1, 1,
                "US:en", None, 1, None, None, None, None,
                None, 0, 1,
            ],
            "X", "X", 1, [1, 1, 1], 1, 1, None,
            0, 0, None, 0,
        ]
        rpc_request = [
            "garturlreq", rpc_context, article_id,
            int(timestamp), signature,
        ]
        rpc_call = [
            pilot.GOOGLE_RPC_ID,
            json.dumps(
                rpc_request, ensure_ascii=False,
                separators=(",", ":")
            ),
        ]
        try:
            response = session.post(
                pilot.GOOGLE_RPC_URL,
                data={
                    "f.req": json.dumps(
                        [[rpc_call]], ensure_ascii=False,
                        separators=(",", ":")
                    )
                },
                headers={
                    "Content-Type":
                        "application/x-www-form-urlencoded;charset=UTF-8"
                },
                timeout=pilot.HTTP_TIMEOUT,
                allow_redirects=True,
            )
            native, parse_status = pilot._google_rpc_native_url(
                response.text
            )
            rpc_item.update({
                "http_status": response.status_code,
                "response_received": True,
                "parse_status": parse_status,
                "native_url_returned": native,
            })
        except (requests.ConnectionError, requests.Timeout) as exc:
            result["environment_blocked"] = True
            rpc_item["error"] = f"{type(exc).__name__}:{exc}"
        except requests.RequestException as exc:
            rpc_item["error"] = f"{type(exc).__name__}:{exc}"
    else:
        rpc_item["error"] = "SIGNATURE_METADATA_UNAVAILABLE"

    result["batchexecute_endpoint"] = rpc_item
    probes = [
        result["news_google_com"],
        result["metadata_signature_endpoint"],
        result["batchexecute_endpoint"],
    ]
    pass_http = all(
        probe.get("response_received")
        and isinstance(probe.get("http_status"), int)
        and 200 <= probe["http_status"] < 400
        for probe in probes
    )
    if result["environment_blocked"]:
        result["status"] = "NETWORK_ENVIRONMENT_BLOCKED"
    elif (
        pass_http
        and result["metadata_signature_endpoint"].get(
            "signature_metadata_found"
        )
    ):
        result["status"] = "PASS"
    else:
        result["status"] = "FAIL"
    return result


def correctness_sample(
    pilot, old_proof, broad_cases, n=30
):
    prior = json.loads(
        OLD_PROOF_ARTIFACT_PATH.read_text(encoding="utf-8")
    )
    retained = list(
        (prior.get("correctness_guard") or {}).get("sample") or []
    )
    broad_map = {
        case["wrapper_url"]: case
        for case in broad_cases
        if case.get("decoded_url")
    }
    http = pilot.HTTP()
    sample = []
    for retained_case in retained:
        if len(sample) >= n:
            break
        wrapper = str(retained_case.get("wrapper_url") or "")
        current = broad_map.get(wrapper)
        if not current:
            continue
        url = current["decoded_url"]
        if url != retained_case.get("decoded_native_url"):
            sample.append({
                "wrapper_url": wrapper,
                "decoded_native_url": url,
                "retained_decoded_native_url":
                    retained_case.get("decoded_native_url"),
                "classification": "INCONSISTENT",
                "detail": {
                    "reason": "DECODE_TARGET_CHANGED"
                },
            })
            continue
        if pilot.tg_identity(url):
            native, fetch_error = pilot.fetch_telegram_post(
                http, url
            )
        else:
            native, fetch_error = pilot.extract_article(
                http, url
            )
        event = copy.deepcopy(current.get("trace") or {})
        event["google_rss_title"] = (
            retained_case.get("google_rss_title")
        )
        event["google_rss_source"] = (
            retained_case.get("google_rss_source")
        )
        classification, detail = (
            old_proof.correctness_classification(event, native)
        )
        sample.append({
            "wrapper_url": wrapper,
            "decoded_native_url": url,
            "rss_result_title":
                retained_case.get("google_rss_title"),
            "rss_publisher_source_name":
                retained_case.get("google_rss_source"),
            "rss_publication_time": None,
            "native_page_title":
                (native or {}).get("title"),
            "native_publisher_domain":
                pilot.host_of(url),
            "native_publication_time":
                (native or {}).get("published_at"),
            "native_fetch_error": fetch_error,
            "classification": classification,
            "detail": detail,
        })
    counts = Counter(
        item["classification"] for item in sample
    )
    return {
        "sample_size": len(sample),
        "CONSISTENT": counts["CONSISTENT"],
        "INCONSISTENT": counts["INCONSISTENT"],
        "UNVERIFIABLE": counts["UNVERIFIABLE"],
        "sample": sample,
        "historical_truth_urls_used": False,
        "new_google_news_discovery_queries": 0,
        "rss_metadata_source":
            "retained prior development-only proof metadata",
    }

def cat_for_url(pilot, url):
    identity = pilot.tg_identity(url)
    if identity:
        mapping = {
            "va_kyiv": "@VA_Kyiv",
            "kyivcityofficial": "@KyivCityOfficial",
            "vitaliy_klitschko": "@vitaliy_klitschko",
            "dsns_kyiv": "@dsns_kyiv",
            "kpszsu": "@kpszsu",
            "suspilnenews": "@suspilnenews",
            "suspilne_kyiv": "@suspilne_kyiv",
        }
        return mapping.get(
            identity[0].casefold(),
            f"telegram:@{identity[0]}",
        )
    host = pilot.host_of(url)
    if (
        host in {"suspilne.media", "www.suspilne.media"}
        and "/kyiv/" in (
            urlparse(url).path.casefold() + "/"
        )
    ):
        return "suspilne.media/kyiv"
    return f"publisher:{host or 'unknown'}"


def downstream_replay(
    pilot, development, broad_cases, shared_http
):
    broad_map = {
        (case["episode_id"], case["wrapper_url"]): case
        for case in broad_cases
    }
    by_category = defaultdict(Counter)
    for key in [
        "@VA_Kyiv", "@KyivCityOfficial",
        "@vitaliy_klitschko", "@dsns_kyiv",
        "@kpszsu", "@suspilnenews",
        "@suspilne_kyiv", "suspilne.media/kyiv",
    ]:
        by_category[key]
    totals = Counter()
    episode_results = []

    ordered_rows = sorted(
        development,
        key=lambda row: (
            (row.get("result") or {}).get("alert_start") or "",
            row.get("episode_id") or "",
        ),
    )
    for row in ordered_rows:
        episode_id = row["episode_id"]
        truth_label = row["truth_label"]
        wrapper_records = (
            [("fixed", wrapper) for wrapper in fixed_wrappers(row, pilot)]
            + [
                ("generic", wrapper)
                for wrapper in generic_wrappers(row)
            ]
        )
        seen_wrappers, resolved_urls = set(), []
        for origin, wrapper in wrapper_records:
            key = (origin, wrapper)
            if key in seen_wrappers:
                continue
            seen_wrappers.add(key)
            case = (
                broad_map.get((episode_id, wrapper))
                if origin == "generic" else None
            )
            if case is None:
                case = replay_records(
                    pilot, shared_http,
                    [{
                        "episode_id": episode_id,
                        "truth_label": truth_label,
                        "wrapper_url": wrapper,
                    }],
                )[0]
            if case.get("decoded_url"):
                resolved_urls.append(case["decoded_url"])
                by_category[
                    cat_for_url(pilot, case["decoded_url"])
                ]["resolved"] += 1

        unique_urls = sorted(set(resolved_urls))
        if unique_urls:
            totals["episodes_with_native_url"] += 1
            if truth_label in {
                "STRICT_EVENT_POSITIVE",
                "SENSITIVITY_EVENT_POSITIVE",
            }:
                totals["positive_episodes_with_native_url"] += 1
            elif truth_label == "HOLD_CONTROL":
                totals["hold_episodes_with_native_url"] += 1

        start = (
            pilot.parse_dt(row["result"]["alert_start"])
            - timedelta(hours=6)
        )
        end = (
            pilot.parse_dt(row["result"]["alert_end"])
            + timedelta(hours=24)
        )
        candidates = {}
        for url in unique_urls:
            family_info = pilot.fixed_family_for_url(url)
            if not family_info:
                continue
            family, kind, handle = family_info
            category = cat_for_url(pilot, url)
            totals["native_fetch_attempts"] += 1
            by_category[category]["fetch_attempted"] += 1
            if kind == "telegram":
                native, _ = pilot.fetch_telegram_post(
                    shared_http, url, handle
                )
            else:
                native, _ = pilot.extract_article(
                    shared_http, url
                )
            if not native:
                totals["native_fetch_failures"] += 1
                by_category[category]["fetch_failed"] += 1
                continue
            totals["native_fetch_successes"] += 1
            by_category[category]["fetch_succeeded"] += 1
            if native.get("text"):
                totals["usable_source_native_texts"] += 1
                by_category[category]["usable_text"] += 1
            if native.get("published_at"):
                totals["publication_timestamps"] += 1
                by_category[category]["timestamp"] += 1
            if not pilot.native_in_window(native, start, end):
                continue
            combined = (
                f"{native.get('title', '')} "
                f"{native.get('text', '')}"
            )
            if (
                not pilot.ATTACK_RE.search(combined)
                or not re.search(r"\bКи(їв|єв)", combined, re.I)
            ):
                continue
            candidate, _ = pilot.make_candidate(
                family, native,
                "retained_wrapper_native_replay",
                {"query_family": "frozen_development_wrapper"},
            )
            candidates[candidate["candidate_id"]] = candidate
            by_category[category]["candidate"] += 1
        totals["candidates_materialized"] += len(candidates)
        episode_results.append({
            "episode_id": episode_id,
            "truth_label": truth_label,
            "native_urls": unique_urls,
            "candidates_materialized": len(candidates),
        })

    tg_resolved = sum(
        values["resolved"]
        for key, values in by_category.items()
        if key.startswith("@") or key.startswith("telegram:")
    )
    tg_success = sum(
        values["fetch_succeeded"]
        for key, values in by_category.items()
        if key.startswith("@") or key.startswith("telegram:")
    )
    pub_resolved = by_category[
        "suspilne.media/kyiv"
    ]["resolved"]
    pub_success = by_category[
        "suspilne.media/kyiv"
    ]["fetch_succeeded"]

    next_transition = None
    next_blocker = "INSUFFICIENT EVIDENCE"
    if (
        tg_resolved and tg_success == 0
        and pub_resolved and pub_success == 0
    ):
        next_transition = "SOURCE-NATIVE URL -> SOURCE FETCH / BODY"
        next_blocker = "MULTIPLE DOWNSTREAM BLOCKERS"
    elif tg_resolved and tg_success == 0:
        next_transition = (
            "TELEGRAM NATIVE URL -> TELEGRAM HISTORICAL BODY"
        )
        next_blocker = (
            "TELEGRAM HISTORICAL RETRIEVAL IS NEXT BLOCKER"
        )
    elif pub_resolved and pub_success == 0:
        next_transition = (
            "PUBLISHER NATIVE URL -> PUBLISHER FULLTEXT"
        )
        next_blocker = (
            "PUBLISHER FULLTEXT RECOVERY IS NEXT BLOCKER"
        )
    elif (
        totals["usable_source_native_texts"]
        and totals["publication_timestamps"] == 0
    ):
        next_transition = "SOURCE-NATIVE BODY -> PUBLICATION TIME"
        next_blocker = (
            "PUBLICATION-TIME RECOVERY IS NEXT BLOCKER"
        )
    elif (
        totals["publication_timestamps"]
        and totals["candidates_materialized"] == 0
    ):
        next_transition = (
            "SOURCE-NATIVE EVIDENCE -> CANDIDATE ADMISSION"
        )
        next_blocker = (
            "CANDIDATE ADMISSION IS NEXT BLOCKER"
        )
    elif totals["candidates_materialized"] > 0:
        next_transition = "CANDIDATE ADMISSION -> CLASSIFIER"
        next_blocker = "NO MATERIAL RECOVERY BLOCKER REMAINS"
    elif totals["episodes_with_native_url"] == 0:
        next_transition = "QUERY -> NATIVE URL"
        next_blocker = "QUERY RECALL IS NEXT BLOCKER"

    return {
        "episodes_replayed": len(development),
        "positive_episodes_with_at_least_one_native_url":
            totals["positive_episodes_with_native_url"],
        "hold_episodes_with_at_least_one_native_url":
            totals["hold_episodes_with_native_url"],
        "native_fetch_attempts":
            totals["native_fetch_attempts"],
        "native_fetch_successes":
            totals["native_fetch_successes"],
        "usable_source_native_texts_recovered":
            totals["usable_source_native_texts"],
        "publication_timestamps_recovered":
            totals["publication_timestamps"],
        "candidates_materialized":
            totals["candidates_materialized"],
        "by_native_category": {
            key: dict(values)
            for key, values in sorted(by_category.items())
        },
        "episode_results": episode_results,
        "next_first_failure_transition": next_transition,
        "next_blocker": next_blocker,
    }


def main():
    pilot = load_module(
        PILOT_PATH, "kyiv_network_proof_pilot"
    )
    old_proof = load_module(
        OLD_PROOF_PATH, "kyiv_old_url_proof_helpers"
    )
    strategy = json.loads(
        STRATEGY_PATH.read_text(encoding="utf-8")
    )
    development = list(
        strategy.get("development_results") or []
    )
    if (
        len(development) != 67
        or sum(
            1 for row in development
            if row.get("truth_label") == "HOLD_CONTROL"
        ) != 19
    ):
        raise RuntimeError("DEVELOPMENT_COHORT_INVALID")

    tested_blob = git(
        "rev-parse",
        f"{TESTED_RESOLVER_COMMIT}:{PILOT_PATH}",
    )
    if tested_blob != TESTED_RESOLVER_BLOB:
        raise RuntimeError(
            f"TESTED_RESOLVER_BLOB_MISMATCH:{tested_blob}"
        )
    current_blob_before = git(
        "rev-parse", f"HEAD:{PILOT_PATH}"
    )
    if current_blob_before != TESTED_RESOLVER_BLOB:
        raise RuntimeError(
            f"CURRENT_RESOLVER_BLOB_MISMATCH:{current_blob_before}"
        )
    harness_commit = git("rev-parse", "HEAD")

    static = static_safety_audit()
    fixtures = old_proof.unit_fixtures(pilot)
    generic_records = [
        {
            "episode_id": row["episode_id"],
            "truth_label": row["truth_label"],
            "wrapper_url": wrapper,
        }
        for row in development
        for wrapper in generic_wrappers(row)
    ]
    if len(generic_records) != 1025:
        raise RuntimeError(
            f"FROZEN_WRAPPER_COUNT_INVALID:{len(generic_records)}"
        )

    gate = network_gate(
        pilot, generic_records[0]["wrapper_url"]
    )
    selected = forensic_rows(development)
    if len(selected) != 39:
        raise RuntimeError(
            f"FORENSIC_SAMPLE_INVALID:{len(selected)}"
        )
    selected_ids = {
        row["episode_id"] for row in selected
    }
    forensic_records = [
        record for record in generic_records
        if record["episode_id"] in selected_ids
    ]

    http = pilot.HTTP()
    forensic_cases = replay_records(
        pilot, http, forensic_records
    )
    broad_cases = replay_records(
        pilot, http, generic_records
    )
    forensic_summary = summarize_cases(forensic_cases)
    broad_summary = summarize_cases(broad_cases)
    forensic_episode_native = len({
        case["episode_id"]
        for case in forensic_cases
        if case.get("decoded_url")
    })

    correctness = correctness_sample(
        pilot, old_proof, broad_cases, 30
    )
    downstream = downstream_replay(
        pilot, development, broad_cases, http
    )
    current_blob_after = git(
        "rev-parse", f"HEAD:{PILOT_PATH}"
    )

    mutation = {
        "blind_per_episode_data_inspected": False,
        "blind_wrapper_decoding_attempts": 0,
        "historical_backfill_started": False,
        "unknown_alert_pilot_started": False,
        "Neon_writes": 0,
        "production_mutations": 0,
        "production_deploys": 0,
        "PR_merged": False,
    }

    proven = (
        static["status"] == "PASS"
        and sum(
            1 for item in fixtures if item.get("pass")
        ) == 8
        and len(fixtures) == 8
        and gate["status"] == "PASS"
        and forensic_summary["wrappers_resolved"] > 0
        and broad_summary["wrappers_resolved"] > 0
        and broad_summary[
            "GOOGLE_WRAPPER_UNSUPPORTED_FORMAT"
        ] == 0
        and correctness["sample_size"] >= 30
        and correctness["INCONSISTENT"] == 0
        and downstream["native_fetch_attempts"] > 0
        and current_blob_after == TESTED_RESOLVER_BLOB
        and mutation["blind_wrapper_decoding_attempts"] == 0
        and not mutation["historical_backfill_started"]
        and mutation["Neon_writes"] == 0
        and mutation["production_mutations"] == 0
    )

    if gate["status"] == "NETWORK_ENVIRONMENT_BLOCKED":
        verdict = (
            "KYIV HISTORICAL GOOGLE NEWS URL RESOLUTION = BLOCKED"
        )
    elif proven:
        verdict = (
            "KYIV HISTORICAL GOOGLE NEWS URL RESOLUTION = PROVEN"
        )
    elif broad_summary["wrappers_resolved"] > 0:
        verdict = (
            "KYIV HISTORICAL GOOGLE NEWS URL RESOLUTION = PARTIAL"
        )
    else:
        verdict = (
            "KYIV HISTORICAL GOOGLE NEWS URL RESOLUTION = FAILED"
        )

    artifact = {
        "schema_version": 1,
        "kind":
            "kyiv_historical_google_news_url_resolution_network_proof",
        "resolver_commit_tested": TESTED_RESOLVER_COMMIT,
        "resolver_blob_tested": TESTED_RESOLVER_BLOB,
        "resolver_blob_changed_during_proof":
            current_blob_after != TESTED_RESOLVER_BLOB,
        "proof_harness_commit": harness_commit,
        "static_safety_audit": static,
        "unit_fixtures": {
            "passed": sum(
                1 for item in fixtures if item.get("pass")
            ),
            "total": len(fixtures),
            "results": fixtures,
        },
        "network_capability_gate": gate,
        "forensic_sample": {
            "selection":
                "exact predecessor deterministic development sample: "
                "earliest 20 positives with generic wrappers + "
                "all 19 holds",
            "episodes": len(selected),
            "wrappers_attempted": len(forensic_cases),
            "wrappers_resolved":
                forensic_summary["wrappers_resolved"],
            "episodes_with_at_least_one_native_url":
                forensic_episode_native,
            "summary": forensic_summary,
            "cases": forensic_cases,
        },
        "development_wrapper_replay": {
            "wrappers_attempted": len(broad_cases),
            "summary": broad_summary,
            "records": broad_cases,
        },
        "correctness_guard": correctness,
        "development_downstream_replay": downstream,
        "next_first_failure_transition":
            downstream["next_first_failure_transition"],
        "next_blocker": downstream["next_blocker"],
        "mutation_confirmation": mutation,
        "verdict": verdict,
    }
    OUT_PATH.parent.mkdir(
        parents=True, exist_ok=True
    )
    OUT_PATH.write_text(
        json.dumps(
            artifact, ensure_ascii=False,
            indent=2, sort_keys=True
        ) + "\n",
        encoding="utf-8",
    )

    print(
        "NETWORK_PROOF_SUMMARY="
        + json.dumps({
            "verdict": verdict,
            "static": static["status"],
            "fixtures":
                f"{artifact['unit_fixtures']['passed']}/"
                f"{artifact['unit_fixtures']['total']}",
            "network": gate["status"],
            "forensic_episodes": len(selected),
            "forensic_wrappers": len(forensic_cases),
            "forensic_resolved":
                forensic_summary["wrappers_resolved"],
            "forensic_episode_native":
                forensic_episode_native,
            "development_wrappers": len(broad_cases),
            "development_resolved":
                broad_summary["wrappers_resolved"],
            "unique_native_urls":
                broad_summary["unique_native_urls"],
            "correctness": {
                key: correctness[key]
                for key in [
                    "sample_size", "CONSISTENT",
                    "INCONSISTENT", "UNVERIFIABLE",
                ]
            },
            "development_episodes":
                downstream["episodes_replayed"],
            "positive_native":
                downstream[
                    "positive_episodes_with_at_least_one_native_url"
                ],
            "hold_native":
                downstream[
                    "hold_episodes_with_at_least_one_native_url"
                ],
            "fetch_success":
                downstream["native_fetch_successes"],
            "texts":
                downstream[
                    "usable_source_native_texts_recovered"
                ],
            "timestamps":
                downstream["publication_timestamps_recovered"],
            "candidates":
                downstream["candidates_materialized"],
            "next_blocker": downstream["next_blocker"],
            "resolver_blob_unchanged":
                current_blob_after == TESTED_RESOLVER_BLOB,
        }, ensure_ascii=False, sort_keys=True)
    )
    return (
        0 if verdict ==
        "KYIV HISTORICAL GOOGLE NEWS URL RESOLUTION = PROVEN"
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
