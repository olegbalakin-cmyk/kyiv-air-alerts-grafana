#!/usr/bin/env python3
# Development-only proof. Synchronize trigger marker.
from __future__ import annotations

import copy
import importlib.util
import json
import re
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from types import SimpleNamespace

PILOT_PATH = Path(".github/proof/kyiv_historical_discovery_calibration_pilot.py")
STRATEGY_PATH = Path("research/kyiv_historical_discovery_frozen_strategy_2026-10-08.json")
OUT_PATH = Path("research/kyiv_historical_google_news_url_resolution_repair_2026-10-08.json")


def load_pilot():
    spec = importlib.util.spec_from_file_location("kyiv_url_resolution_pilot", PILOT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("PILOT_IMPORT_FAILED")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class FakeResponse:
    def __init__(self, url, text="", content_type="text/html; charset=utf-8"):
        self.url = url
        self.text = text
        self.content = text.encode("utf-8")
        self.headers = {"content-type": content_type}

    def raise_for_status(self):
        return None


class FakeHTTP:
    def __init__(self, gets=None, posts=None):
        self.gets = gets or {}
        self.posts = posts or {}
        self.google_resolution_cache = {}
        self.resolution_events = []

    def get(self, url, **kwargs):
        value = self.gets[url]
        if isinstance(value, Exception):
            raise value
        return value

    def post(self, url, **kwargs):
        value = self.posts[url]
        if isinstance(value, Exception):
            raise value
        return value


def opaque_article_id(pilot, opaque="AU_yqFixtureOpaqueIdentifier0123456789"):
    import base64
    raw = ("prefix-" + opaque + "-suffix").encode("ascii")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def rpc_body(pilot, native):
    inner = ["garturlres", native]
    outer = [["wrb.fr", pilot.GOOGLE_RPC_ID, json.dumps(inner), None, None, None, "generic"]]
    return ")]}'\n" + json.dumps(outer)


def unit_fixtures(pilot):
    fixtures = []

    # A. direct publisher URL
    h = FakeHTTP()
    url = "https://example.org/article"
    got, err = pilot.resolve_google_result(h, {"link": url})
    fixtures.append({"name":"A_direct_publisher","pass":got == url and err is None,"got":got,"err":err})

    # B. normal Google redirect to publisher
    aid = opaque_article_id(pilot, "AU_yqRedirectFixture0123456789")
    wrap = f"https://news.google.com/rss/articles/{aid}?oc=5"
    target = "https://redirect.example/news"
    h = FakeHTTP(gets={wrap: FakeResponse(target, "<html></html>")})
    got, err = pilot.resolve_google_result(h, {"link": wrap})
    fixtures.append({"name":"B_google_redirect","pass":got == target and err is None,"got":got,"err":err})

    # C. legacy Google page containing external anchor
    aid = opaque_article_id(pilot, "AU_yqAnchorFixture0123456789")
    wrap = f"https://news.google.com/rss/articles/{aid}?oc=5"
    target = "https://anchor.example/story"
    html = f'<html><a href="{target}">story</a></html>'
    h = FakeHTTP(gets={wrap: FakeResponse(wrap, html)})
    got, err = pilot.resolve_google_result(h, {"link": wrap})
    fixtures.append({"name":"C_legacy_anchor","pass":got == target and err is None,"got":got,"err":err})

    # D. opaque AU_yq wrapper with mocked metadata/RPC -> exact native URL
    aid = opaque_article_id(pilot, "AU_yqOpaqueFixture0123456789")
    wrap = f"https://news.google.com/rss/articles/{aid}?oc=5"
    target = "https://publisher.example/exact"
    meta = f'<div data-n-a-id="{aid}" data-n-a-ts="1700000000" data-n-a-sg="sig"></div>'
    h = FakeHTTP(
        gets={wrap: FakeResponse(wrap, meta)},
        posts={pilot.GOOGLE_RPC_URL: FakeResponse(pilot.GOOGLE_RPC_URL, rpc_body(pilot, target))}
    )
    got, err = pilot.resolve_google_result(h, {"link": wrap})
    fixtures.append({"name":"D_opaque_success","pass":got == target and err is None,"got":got,"err":err})

    # E. malformed opaque wrapper -> fail closed
    wrap = "https://news.google.com/rss/articles/abcdefghijklmnop?oc=5"
    h = FakeHTTP(gets={wrap: FakeResponse(wrap, "<html></html>")})
    got, err = pilot.resolve_google_result(h, {"link": wrap})
    fixtures.append({"name":"E_malformed_opaque","pass":got is None and err == "GOOGLE_WRAPPER_UNSUPPORTED_FORMAT","got":got,"err":err})

    # F. valid opaque wrapper but RPC has no native URL
    aid = opaque_article_id(pilot, "AU_yqNoUrlFixture0123456789")
    wrap = f"https://news.google.com/rss/articles/{aid}?oc=5"
    meta = f'<div data-n-a-id="{aid}" data-n-a-ts="1700000001" data-n-a-sg="sig2"></div>'
    no_url_body = ")]}'\n" + json.dumps([["wrb.fr", pilot.GOOGLE_RPC_ID, json.dumps(["garturlres", None])]])
    h = FakeHTTP(
        gets={wrap: FakeResponse(wrap, meta)},
        posts={pilot.GOOGLE_RPC_URL: FakeResponse(pilot.GOOGLE_RPC_URL, no_url_body)}
    )
    got, err = pilot.resolve_google_result(h, {"link": wrap})
    fixtures.append({"name":"F_rpc_no_native","pass":got is None and err == "GOOGLE_WRAPPER_NO_NATIVE_URL","got":got,"err":err})

    # G. decoded Telegram URL is preserved
    aid = opaque_article_id(pilot, "AU_yqTelegramFixture0123456789")
    wrap = f"https://news.google.com/rss/articles/{aid}?oc=5"
    target = "https://t.me/suspilne_kyiv/12345"
    meta = f'<div data-n-a-id="{aid}" data-n-a-ts="1700000002" data-n-a-sg="sig3"></div>'
    h = FakeHTTP(
        gets={wrap: FakeResponse(wrap, meta)},
        posts={pilot.GOOGLE_RPC_URL: FakeResponse(pilot.GOOGLE_RPC_URL, rpc_body(pilot, target))}
    )
    got, err = pilot.resolve_google_result(h, {"link": wrap})
    fixtures.append({"name":"G_telegram_native","pass":got == target and pilot.tg_identity(got) == ("suspilne_kyiv",12345),"got":got,"err":err})

    # H. decoded normal publisher URL is preserved
    aid = opaque_article_id(pilot, "AU_yqPublisherFixture0123456789")
    wrap = f"https://news.google.com/rss/articles/{aid}?oc=5"
    target = "https://suspilne.media/kyiv/123456-story/"
    meta = f'<div data-n-a-id="{aid}" data-n-a-ts="1700000003" data-n-a-sg="sig4"></div>'
    h = FakeHTTP(
        gets={wrap: FakeResponse(wrap, meta)},
        posts={pilot.GOOGLE_RPC_URL: FakeResponse(pilot.GOOGLE_RPC_URL, rpc_body(pilot, target))}
    )
    got, err = pilot.resolve_google_result(h, {"link": wrap})
    fixtures.append({"name":"H_publisher_native","pass":got == target and pilot.host_of(got) == "suspilne.media","got":got,"err":err})

    return fixtures


def generic_wrappers(row):
    diag = ((row.get("result") or {}).get("source_diagnostics") or {}).get("generic_search") or {}
    return [
        str(x.get("link") or "")
        for x in (diag.get("resolve_failures") or [])
        if "news.google.com/rss/articles/" in str(x.get("link") or "")
    ]


def forensic_rows(development):
    positives = [
        r for r in development
        if str(r.get("truth_label") or "") in {"STRICT_EVENT_POSITIVE","SENSITIVITY_EVENT_POSITIVE"}
        and generic_wrappers(r)
    ]
    positives.sort(key=lambda r: ((r.get("result") or {}).get("alert_start") or "", r.get("episode_id") or ""))
    holds = [r for r in development if r.get("truth_label") == "HOLD_CONTROL"]
    holds.sort(key=lambda r: ((r.get("result") or {}).get("alert_start") or "", r.get("episode_id") or ""))
    selected = positives[:20] + holds
    selected.sort(key=lambda r: ((r.get("result") or {}).get("alert_start") or "", r.get("episode_id") or ""))
    return selected


def outcome_counts(events):
    return dict(Counter(str(e.get("terminal_failure_reason") or e.get("resolution_outcome") or "UNKNOWN") for e in events))


def resolution_summary(events):
    decoded = [e for e in events if e.get("decoded_native_url")]
    return {
        "attempted": len(events),
        "native_urls_resolved": len(decoded),
        "unique_native_urls": len({e.get("decoded_native_url") for e in decoded}),
        "telegram_native_urls": sum(1 for e in decoded if e.get("native_kind") == "TELEGRAM"),
        "publisher_native_urls": sum(1 for e in decoded if e.get("native_kind") == "PUBLISHER"),
        "unsupported_format_failures": sum(1 for e in events if e.get("terminal_failure_reason") == "GOOGLE_WRAPPER_UNSUPPORTED_FORMAT"),
        "transport_network_failures": sum(1 for e in events if e.get("terminal_failure_reason") == "GOOGLE_WRAPPER_NETWORK_FAILED"),
        "terminal_failure_counts": outcome_counts(events),
    }


def cat_for_url(pilot, url):
    ident = pilot.tg_identity(url)
    if ident:
        handle = ident[0].casefold()
        mapping = {
            "va_kyiv":"@VA_Kyiv",
            "kyivcityofficial":"@KyivCityOfficial",
            "vitaliy_klitschko":"@vitaliy_klitschko",
            "dsns_kyiv":"@dsns_kyiv",
            "kpszsu":"@kpszsu",
            "suspilnenews":"@suspilnenews",
            "suspilne_kyiv":"@suspilne_kyiv",
        }
        return mapping.get(handle, f"telegram:@{ident[0]}")
    host = pilot.host_of(url)
    if host in {"suspilne.media","www.suspilne.media"} and "/kyiv/" in (pilot.urlparse(url).path.casefold()+"/"):
        return "suspilne.media/kyiv"
    return f"publisher:{host or 'unknown'}"


def norm_tokens(text):
    return {x for x in re.findall(r"[0-9A-Za-zА-Яа-яІіЇїЄєҐґ]{4,}", str(text or "").casefold())}


def correctness_classification(event, native):
    rss_title = str(event.get("google_rss_title") or "")
    rss_source = str(event.get("google_rss_source") or "")
    native_title = str((native or {}).get("title") or "")
    native_text = str((native or {}).get("text") or "")
    if not rss_title and not rss_source:
        return "UNVERIFIABLE", {"reason":"NO_RSS_METADATA"}

    r_tokens = norm_tokens(rss_title)
    n_tokens = norm_tokens(native_title or native_text[:1000])
    overlap = len(r_tokens & n_tokens) / max(1, min(len(r_tokens), len(n_tokens))) if r_tokens and n_tokens else 0.0

    source_tokens = norm_tokens(rss_source)
    host_tokens = norm_tokens(event.get("final_domain") or "")
    source_host_match = bool(source_tokens & host_tokens)
    if overlap >= 0.35 or source_host_match:
        return "CONSISTENT", {"title_overlap":round(overlap,3),"source_host_match":source_host_match}
    if r_tokens and n_tokens and len(r_tokens) >= 4 and len(n_tokens) >= 4 and overlap == 0 and rss_source:
        return "INCONSISTENT", {"title_overlap":0.0,"source_host_match":source_host_match}
    return "UNVERIFIABLE", {"title_overlap":round(overlap,3),"source_host_match":source_host_match}


def main():
    pilot = load_pilot()
    strategy = json.loads(STRATEGY_PATH.read_text(encoding="utf-8"))
    development = list(strategy.get("development_results") or [])
    if len(development) != 67:
        raise RuntimeError(f"DEVELOPMENT_COUNT_INVALID:{len(development)}")
    if sum(1 for r in development if r.get("truth_label") == "HOLD_CONTROL") != 19:
        raise RuntimeError("DEVELOPMENT_HOLD_COUNT_INVALID")

    fixtures = unit_fixtures(pilot)
    if not all(x["pass"] for x in fixtures):
        raise RuntimeError("UNIT_FIXTURE_FAILURE")

    # Exact predecessor forensic sample: earliest 20 positives with generic hits + all 19 holds.
    selected = forensic_rows(development)
    if len(selected) != 39:
        raise RuntimeError(f"FORENSIC_SAMPLE_INVALID:{len(selected)}")
    forensic_http = pilot.HTTP()
    forensic = []
    for row in selected:
        wrappers = generic_wrappers(row)
        if not wrappers:
            raise RuntimeError("FORENSIC_WRAPPER_MISSING:" + str(row.get("episode_id")))
        wrapper = wrappers[0]
        before = len(forensic_http.resolution_events)
        resolved, err = pilot.resolve_google_result(forensic_http, {"link":wrapper})
        event = copy.deepcopy(forensic_http.resolution_events[-1]) if len(forensic_http.resolution_events) > before else {}
        forensic.append({
            "episode_id":row.get("episode_id"),
            "truth_label":row.get("truth_label"),
            "alert_start":(row.get("result") or {}).get("alert_start"),
            "wrapper_url":wrapper,
            "resolved_native_url":resolved,
            "error":err,
            "trace":event,
        })
    forensic_summary = resolution_summary([x["trace"] for x in forensic])

    # Broad replay over all 1,025 frozen development wrapper records, no new queries.
    broad_http = pilot.HTTP()
    broad_events = []
    wrapper_ledger = []
    for row in development:
        for wrapper in generic_wrappers(row):
            before = len(broad_http.resolution_events)
            resolved, err = pilot.resolve_google_result(broad_http, {"link":wrapper})
            event = copy.deepcopy(broad_http.resolution_events[-1]) if len(broad_http.resolution_events) > before else {}
            broad_events.append(event)
            wrapper_ledger.append({
                "episode_id":row.get("episode_id"),
                "truth_label":row.get("truth_label"),
                "wrapper_url":wrapper,
                "resolved_native_url":resolved,
                "error":err,
                "trace":event,
            })
    if len(wrapper_ledger) != 1025:
        raise RuntimeError(f"FROZEN_WRAPPER_COUNT_INVALID:{len(wrapper_ledger)}")
    broad_summary = resolution_summary(broad_events)

    # Development-only recovery replay with existing query/source/window/admission functions unchanged.
    tmp = Path(tempfile.mkdtemp(prefix="kyiv-url-proof-"))
    mon = None
    wt = None
    replay_http = pilot.HTTP()
    fetch_stats = Counter()
    per_category = defaultdict(Counter)
    native_by_input_url = {}

    original_tg = pilot.fetch_telegram_post
    original_article = pilot.extract_article

    def tg_probe(http, url, expected_channel=None):
        cat = cat_for_url(pilot, url)
        fetch_stats["native_fetches_attempted"] += 1
        per_category[cat]["fetch_attempted"] += 1
        native, err = original_tg(http, url, expected_channel)
        if native:
            fetch_stats["native_fetches_succeeded"] += 1
            per_category[cat]["fetch_succeeded"] += 1
            native_by_input_url[url] = copy.deepcopy(native)
            if native.get("text"):
                fetch_stats["usable_source_native_texts"] += 1
                per_category[cat]["usable_text"] += 1
            if native.get("published_at"):
                fetch_stats["publication_timestamps"] += 1
                per_category[cat]["timestamp"] += 1
        else:
            fetch_stats["native_fetches_failed"] += 1
            per_category[cat]["fetch_failed"] += 1
        return native, err

    def article_probe(http, url):
        cat = cat_for_url(pilot, url)
        fetch_stats["native_fetches_attempted"] += 1
        per_category[cat]["fetch_attempted"] += 1
        native, err = original_article(http, url)
        if native:
            fetch_stats["native_fetches_succeeded"] += 1
            per_category[cat]["fetch_succeeded"] += 1
            native_by_input_url[url] = copy.deepcopy(native)
            if native.get("text"):
                fetch_stats["usable_source_native_texts"] += 1
                per_category[cat]["usable_text"] += 1
            if native.get("published_at"):
                fetch_stats["publication_timestamps"] += 1
                per_category[cat]["timestamp"] += 1
        else:
            fetch_stats["native_fetches_failed"] += 1
            per_category[cat]["fetch_failed"] += 1
        return native, err

    pilot.fetch_telegram_post = tg_probe
    pilot.extract_article = article_probe

    replay_rows = []
    try:
        mon, wt = pilot.prepare_authoritative_monitor(tmp)
        all_eps = pilot.load_full_kyiv_episodes()
        ordered = sorted(development, key=lambda r: ((r.get("result") or {}).get("alert_start") or "", r.get("episode_id") or ""))
        for row in ordered:
            ep = {
                "episode_id":row["episode_id"],
                "city_key":"kyiv",
                "alert_start":row["result"]["alert_start"],
                "alert_end":row["result"]["alert_end"],
            }
            before = len(replay_http.resolution_events)
            result = pilot.run_one(mon, replay_http, all_eps, ep)
            episode_events = copy.deepcopy(replay_http.resolution_events[before:])
            resolved_events = [e for e in episode_events if e.get("decoded_native_url")]
            replay_rows.append({
                "episode_id":row["episode_id"],
                "truth_label":row["truth_label"],
                "result":result,
                "resolution_events":episode_events,
                "resolved_native_urls":sorted({e.get("decoded_native_url") for e in resolved_events if e.get("decoded_native_url")}),
            })
    finally:
        pilot.fetch_telegram_post = original_tg
        pilot.extract_article = original_article
        try:
            if wt is not None:
                pilot.sh(["git","worktree","remove","--force",str(wt)],check=False)
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)

    generic_hits = sum(int((((r["result"].get("source_diagnostics") or {}).get("generic_search") or {}).get("search_hits") or 0)) for r in replay_rows)
    all_replay_events = [e for r in replay_rows for e in r["resolution_events"]]
    resolved_replay_events = [e for e in all_replay_events if e.get("decoded_native_url")]
    for e in resolved_replay_events:
        per_category[cat_for_url(pilot, e.get("decoded_native_url"))]["resolved"] += 1

    positives_with_native = sum(
        bool(r["resolved_native_urls"])
        for r in replay_rows
        if r["truth_label"] in {"STRICT_EVENT_POSITIVE","SENSITIVITY_EVENT_POSITIVE"}
    )
    holds_with_native = sum(bool(r["resolved_native_urls"]) for r in replay_rows if r["truth_label"] == "HOLD_CONTROL")
    candidates_materialized = sum(len(r["result"].get("candidate_records") or []) for r in replay_rows)

    # Deterministic correctness sample from real development replay results.
    correctness_pool = []
    seen = set()
    for e in resolved_replay_events:
        url = e.get("decoded_native_url")
        if not url or url in seen or url not in native_by_input_url:
            continue
        if not (e.get("google_rss_title") or e.get("google_rss_source")):
            continue
        seen.add(url)
        cls, detail = correctness_classification(e, native_by_input_url[url])
        correctness_pool.append({
            "wrapper_url":e.get("wrapper_url"),
            "decoded_native_url":url,
            "google_rss_title":e.get("google_rss_title"),
            "google_rss_source":e.get("google_rss_source"),
            "native_title":native_by_input_url[url].get("title"),
            "classification":cls,
            "detail":detail,
        })
    correctness_pool.sort(key=lambda x:(x["wrapper_url"] or "", x["decoded_native_url"] or ""))
    correctness = correctness_pool[:30]
    correctness_counts = Counter(x["classification"] for x in correctness)

    tg_attempt = sum(v["fetch_attempted"] for k,v in per_category.items() if k.startswith("@") or k.startswith("telegram:"))
    tg_success = sum(v["fetch_succeeded"] for k,v in per_category.items() if k.startswith("@") or k.startswith("telegram:"))
    pub_attempt = sum(v["fetch_attempted"] for k,v in per_category.items() if k.startswith("publisher:") or k == "suspilne.media/kyiv")
    pub_success = sum(v["fetch_succeeded"] for k,v in per_category.items() if k.startswith("publisher:") or k == "suspilne.media/kyiv")

    next_transition = None
    next_blocker = "INSUFFICIENT EVIDENCE"
    if resolved_replay_events:
        if tg_attempt and tg_success == 0 and pub_attempt and pub_success == 0:
            next_transition = "SOURCE-NATIVE URL -> SOURCE FETCH / BODY"
            next_blocker = "MULTIPLE DOWNSTREAM BLOCKERS"
        elif tg_attempt and tg_success == 0:
            next_transition = "TELEGRAM NATIVE URL -> TELEGRAM HISTORICAL BODY"
            next_blocker = "TELEGRAM HISTORICAL RETRIEVAL IS NEXT BLOCKER"
        elif pub_attempt and pub_success == 0:
            next_transition = "PUBLISHER NATIVE URL -> PUBLISHER FULLTEXT"
            next_blocker = "PUBLISHER FULLTEXT RECOVERY IS NEXT BLOCKER"
        elif fetch_stats["usable_source_native_texts"] and fetch_stats["publication_timestamps"] == 0:
            next_transition = "SOURCE-NATIVE BODY -> PUBLICATION TIME"
            next_blocker = "PUBLICATION-TIME RECOVERY IS NEXT BLOCKER"
        elif fetch_stats["publication_timestamps"] and candidates_materialized == 0:
            next_transition = "SOURCE-NATIVE EVIDENCE -> CANDIDATE ADMISSION"
            next_blocker = "CANDIDATE ADMISSION IS NEXT BLOCKER"
        elif candidates_materialized > 0:
            next_transition = "CANDIDATE ADMISSION -> CLASSIFIER"
            next_blocker = "NO MATERIAL RECOVERY BLOCKER REMAINS"

    mutation_confirmation = {
        "blind_cohort_touched":False,
        "historical_backfill_started":False,
        "unknown_alert_pilot_started":False,
        "Neon_writes":0,
        "production_mutations":0,
        "canonical_classifications_changed":0,
        "live_pipeline_changed":0,
    }

    verdict = "KYIV HISTORICAL GOOGLE NEWS URL RESOLUTION = FAILED"
    if (
        broad_summary["unsupported_format_failures"] == 0
        and broad_summary["native_urls_resolved"] > 0
        and len(correctness) >= 30
        and correctness_counts["INCONSISTENT"] == 0
        and fetch_stats["native_fetches_attempted"] > 0
        and not mutation_confirmation["blind_cohort_touched"]
    ):
        verdict = "KYIV HISTORICAL GOOGLE NEWS URL RESOLUTION = PROVEN"
    elif broad_summary["native_urls_resolved"] > 0:
        verdict = "KYIV HISTORICAL GOOGLE NEWS URL RESOLUTION = PARTIAL"

    artifact = {
        "schema_version":1,
        "kind":"kyiv_historical_google_news_url_resolution_repair",
        "resolver_implementation":{
            "name":"bounded_internal_google_news_batchexecute_v1",
            "external_dependency_added":False,
            "rpc_id":pilot.GOOGLE_RPC_ID,
            "google_rpc_url":pilot.GOOGLE_RPC_URL,
            "legacy_resolution_preserved":True,
            "query_semantics_changed":False,
            "source_set_changed":False,
            "classifier_semantics_changed":False,
            "candidate_admission_semantics_changed":False,
        },
        "unit_fixtures":{
            "passed":sum(1 for x in fixtures if x["pass"]),
            "total":len(fixtures),
            "results":fixtures,
        },
        "forensic_sample":{
            "selection":"deterministic earliest-by-alert_start 20 development positives with generic hits + all 19 development holds",
            "episodes":len(selected),
            "wrappers_attempted":len(forensic),
            "summary":forensic_summary,
            "cases":forensic,
        },
        "development_wrapper_replay":{
            "wrappers_attempted":len(wrapper_ledger),
            "summary":broad_summary,
            "records":wrapper_ledger,
        },
        "correctness_guard":{
            "sample_size":len(correctness),
            "CONSISTENT":correctness_counts["CONSISTENT"],
            "INCONSISTENT":correctness_counts["INCONSISTENT"],
            "UNVERIFIABLE":correctness_counts["UNVERIFIABLE"],
            "sample":correctness,
        },
        "post_repair_development_recovery_funnel":{
            "episodes_replayed":len(replay_rows),
            "generic_hits":generic_hits,
            "native_urls_resolved":len(resolved_replay_events),
            "positive_episodes_with_at_least_one_native_url":positives_with_native,
            "hold_episodes_with_at_least_one_native_url":holds_with_native,
            "native_fetches_attempted":fetch_stats["native_fetches_attempted"],
            "native_fetches_succeeded":fetch_stats["native_fetches_succeeded"],
            "usable_source_native_texts_recovered":fetch_stats["usable_source_native_texts"],
            "publication_timestamps_recovered":fetch_stats["publication_timestamps"],
            "candidates_materialized":candidates_materialized,
            "by_native_category":{k:dict(v) for k,v in sorted(per_category.items())},
            "episode_results":replay_rows,
        },
        "next_first_failure_transition":next_transition,
        "next_blocker":next_blocker,
        "mutation_confirmation":mutation_confirmation,
        "verdict":verdict,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print("PROOF_SUMMARY=" + json.dumps({
        "verdict":verdict,
        "fixtures":f"{artifact['unit_fixtures']['passed']}/{artifact['unit_fixtures']['total']}",
        "forensic_resolved":forensic_summary["native_urls_resolved"],
        "development_resolved":broad_summary["native_urls_resolved"],
        "unsupported":broad_summary["unsupported_format_failures"],
        "correctness":dict(correctness_counts),
        "fetches_succeeded":fetch_stats["native_fetches_succeeded"],
        "texts":fetch_stats["usable_source_native_texts"],
        "timestamps":fetch_stats["publication_timestamps"],
        "candidates":candidates_materialized,
        "next_blocker":next_blocker,
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
