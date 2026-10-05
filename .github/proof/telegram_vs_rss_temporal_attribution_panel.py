#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

PRODUCTION_CODE_COMMIT = "c26307efcea065813870dc27901dbd225f4f3e33"
PREDECESSOR_PROOF_HEAD = "636840bf255cdb54d3dae346bb7ef65897405c6b"
PREDECESSOR_ACTIONS_RUN = 37269355479
PREDECESSOR_JSON_SHA256 = "c14080a70f465cf353ccc300450cb8a11c6f38ff39e5635a633c5e499a1a3f48"
PANEL_START_DATE = "2026-10-05"
PANEL_DAYS = 7
UTC_SLOTS = ((8, 45, "45 8 * * *"), (20, 45, "45 20 * * *"))
KYIV_OFFSET = timedelta(hours=3)

MIN_VALID_WINDOWS = 12
MIN_MATCHED_CLUSTERS = 20
MIN_TEMPORAL_SUCCESS_CLUSTERS = 5

MUTATION_KEYS = (
    "production_code_mutations",
    "classifier_mutations",
    "temporal_parser_policy_mutations",
    "discovery_mutations",
    "source_adapter_mutations",
    "persisted_evidence_mutations",
    "historical_state_queue_mutations",
    "review_queue_mutations",
    "canonical_alerts_mutations",
    "neon_db_mutations",
    "deployments",
)

REPRESENTATIONS = ("telegram", "rss_title_snippet", "rss_publisher_fulltext")


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def read_json(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: str | Path, payload: dict) -> str:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path.write_text(raw, encoding="utf-8")
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def sha256_file(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def panel_schedule() -> list[dict]:
    start = datetime.fromisoformat(PANEL_START_DATE).replace(tzinfo=timezone.utc)
    out = []
    index = 1
    for day in range(PANEL_DAYS):
        base = start + timedelta(days=day)
        for hour, minute, cron in UTC_SLOTS:
            scheduled = base.replace(hour=hour, minute=minute, second=0, microsecond=0)
            local = scheduled + KYIV_OFFSET
            out.append(
                {
                    "window_index": index,
                    "window_id": f"W{index:02d}",
                    "scheduled_at_utc": iso(scheduled),
                    "scheduled_at_kyiv": local.replace(tzinfo=timezone(KYIV_OFFSET)).isoformat(),
                    "cron": cron,
                }
            )
            index += 1
    return out


SCHEDULE = panel_schedule()


def resolve_window(now: datetime, cron: str) -> dict:
    compatible = [row for row in SCHEDULE if row["cron"] == cron]
    if not compatible:
        return {"in_panel": False, "reason": "UNREGISTERED_CRON"}
    ranked = []
    for row in compatible:
        when = parse_dt(row["scheduled_at_utc"])
        assert when is not None
        ranked.append((abs((now - when).total_seconds()), row))
    delta, row = min(ranked, key=lambda item: item[0])
    if delta > 6 * 3600:
        return {
            "in_panel": False,
            "reason": "OUTSIDE_REGISTERED_PANEL_WINDOW",
            "nearest_window": row,
            "distance_seconds": delta,
        }
    return {"in_panel": True, **row, "distance_seconds": delta}


def normalize_url(url: str | None) -> str:
    raw = str(url or "").strip()
    if not raw:
        return ""
    try:
        parts = urlsplit(raw)
    except ValueError:
        return raw
    scheme = (parts.scheme or "https").lower()
    host = (parts.hostname or "").casefold()
    if host.startswith("www."):
        host = host[4:]
    port = parts.port
    netloc = host + (f":{port}" if port else "")
    path = parts.path or "/"
    while "//" in path:
        path = path.replace("//", "/")
    if path != "/":
        path = path.rstrip("/")
    if host.endswith("news.google.com"):
        query = ""
    else:
        keep = []
        for key, value in parse_qsl(parts.query, keep_blank_values=True):
            low = key.casefold()
            if low.startswith("utm_") or low in {
                "fbclid", "gclid", "mc_cid", "mc_eid", "ref", "referrer", "source"
            }:
                continue
            keep.append((key, value))
        query = urlencode(sorted(keep))
    return urlunsplit((scheme, netloc, path, query, ""))


def source_native_identity(entry: dict) -> str:
    family = str(entry.get("source_family") or "")
    url = normalize_url(entry.get("resolved_url") or entry.get("url"))
    publisher = str(entry.get("publisher_or_channel") or entry.get("source") or "unknown").strip()
    published = str(entry.get("published_at") or "").strip()
    text_hash = str(entry.get("source_text_hash") or "").strip()
    if family == "telegram":
        if url:
            return f"telegram_url|{url}"
        return f"telegram_fallback|{publisher}|{published}|{text_hash}"
    if url:
        return f"rss_url|{url}"
    return f"rss_fallback|{publisher}|{published}|{text_hash}"


def evidence_id(identity: str) -> str:
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]


def family_name(entry: dict) -> str:
    return "telegram" if entry.get("source_family") == "telegram" else "rss"


def semantic_strong(entry: dict) -> bool:
    return bool((entry.get("semantic_gates") or {}).get("semantically_strong"))


def strict_binding(entry: dict) -> bool:
    return bool(entry.get("strict_episode_specific_binding"))


def feature(entry: dict, key: str) -> bool:
    return bool((entry.get("temporal_features") or {}).get(key))


def temporal_rank(entry: dict) -> tuple:
    temporal = entry.get("current_temporal_binding") or {}
    code = str(temporal.get("code") or "")
    return (
        int(strict_binding(entry)),
        int(temporal.get("evidence_type") == "explicit_event_time"),
        int(code == "TEMPORAL_CONTEMPORANEOUS_LIVE_WORDING"),
        int(bool(temporal.get("present"))),
        code,
    )


def wilson(k: int, n: int, z: float = 1.959963984540054) -> dict:
    if n <= 0:
        return {"low": None, "high": None}
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n) / den
    return {"low": max(0.0, centre - half), "high": min(1.0, centre + half)}


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    xs = sorted(values)
    if len(xs) == 1:
        return xs[0]
    pos = (len(xs) - 1) * q
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(xs) - 1)
    frac = pos - lo
    return xs[lo] * (1 - frac) + xs[hi] * frac


def lag_summary(values: list[float]) -> dict:
    if not values:
        return {
            "n": 0,
            "median_seconds": None,
            "p25_seconds": None,
            "p75_seconds": None,
            "min_seconds": None,
            "max_seconds": None,
        }
    xs = sorted(values)
    return {
        "n": len(xs),
        "median_seconds": statistics.median(xs),
        "p25_seconds": percentile(xs, 0.25),
        "p75_seconds": percentile(xs, 0.75),
        "min_seconds": min(xs),
        "max_seconds": max(xs),
    }


def exact_paired_binomial(tg_only: int, rss_only: int) -> dict:
    n = tg_only + rss_only
    if n == 0:
        return {"discordant_n": 0, "two_sided_exact_p": None}
    tail = min(tg_only, rss_only)
    numerator = sum(math.comb(n, k) for k in range(tail + 1))
    p = min(1.0, 2.0 * numerator / (2 ** n))
    return {"discordant_n": n, "two_sided_exact_p": p}


def mutation_all_zero(proof: dict) -> bool:
    return all(int(proof.get(key, 0) or 0) == 0 for key in MUTATION_KEYS)


def build_window(args: argparse.Namespace) -> dict:
    raw_path = Path(args.raw_audit)
    mutation_path = Path(args.mutation_proof)
    identity_path = Path(args.code_identity)

    raw = read_json(raw_path) if raw_path.exists() else None
    mutation = read_json(mutation_path) if mutation_path.exists() else {}
    identity = read_json(identity_path) if identity_path.exists() else {}

    valid = (
        int(args.observation_exit_code) == 0
        and raw is not None
        and mutation_all_zero(mutation)
        and bool(identity.get("production_code_byte_identical"))
        and str((raw.get("execution") or {}).get("production_code_commit") or "") == PRODUCTION_CODE_COMMIT
    )
    status = "VALID" if valid else "INVALID"

    raw_sha = sha256_file(raw_path) if raw_path.exists() else None
    raw_metrics = None
    if raw:
        raw_metrics = {
            "raw_observations": raw.get("raw_observations"),
            "source_availability": raw.get("source_availability"),
            "per_source_aggregate_metrics": raw.get("per_source_aggregate_metrics"),
            "telegram_temporal_decomposition": raw.get("telegram_temporal_decomposition"),
            "matched_alert_cluster_comparison": raw.get("matched_alert_cluster_comparison"),
            "explicit_time_lag_analysis": raw.get("explicit_time_lag_analysis"),
            "telegram_channel_breakdown": raw.get("telegram_channel_breakdown"),
            "rss_publisher_breakdown": raw.get("rss_publisher_breakdown"),
            "rss_search_errors": raw.get("rss_search_errors"),
            "telegram_errors": raw.get("telegram_errors"),
        }

    payload = {
        "schema": "telegram_vs_rss_temporal_attribution_panel_window_v1",
        "pre_registration": {
            "schedule": SCHEDULE,
            "production_code_commit": PRODUCTION_CODE_COMMIT,
            "accepted_predecessor": {
                "verdict": "TELEGRAM VS RSS TEMPORAL ATTRIBUTION = INSUFFICIENT SAMPLE",
                "actions_run": PREDECESSOR_ACTIONS_RUN,
                "proof_tooling_head": PREDECESSOR_PROOF_HEAD,
                "proof_json_sha256": PREDECESSOR_JSON_SHA256,
            },
            "decision_thresholds": {
                "minimum_valid_windows": MIN_VALID_WINDOWS,
                "minimum_matched_clusters": MIN_MATCHED_CLUSTERS,
                "minimum_clusters_with_any_strict_binding": MIN_TEMPORAL_SUCCESS_CLUSTERS,
            },
        },
        "window": {
            "window_index": int(args.window_index),
            "window_id": f"W{int(args.window_index):02d}",
            "scheduled_at_utc": args.scheduled_utc,
            "scheduled_at_kyiv": args.scheduled_local,
            "cron": args.cron,
            "status": status,
            "observation_exit_code": int(args.observation_exit_code),
            "failure_reason": None if valid else str(args.failure_reason or "INVALID_OBSERVATION"),
            "actions_run_id": int(args.actions_run_id),
            "run_attempt": int(args.run_attempt),
            "workflow_sha": args.workflow_sha,
            "proof_tooling_commit": args.proof_tooling_commit,
            "actual_started_at": ((raw or {}).get("execution") or {}).get("started_at"),
            "actual_finished_at": ((raw or {}).get("execution") or {}).get("finished_at"),
        },
        "production_code_identity": identity,
        "mutation_proof": mutation,
        "raw_audit_sha256": raw_sha,
        "raw_per_run_metrics": raw_metrics,
        "raw_audit": raw,
    }
    digest = write_json(args.out, payload)
    Path(args.out + ".sha256").write_text(
        f"{digest}  {Path(args.out).name}\n", encoding="utf-8"
    )
    return payload


def select_attempts(manifests: list[dict]) -> tuple[dict[int, dict], dict[int, list[dict]]]:
    attempts: dict[int, list[dict]] = defaultdict(list)
    for item in manifests:
        idx = int((item.get("window") or {}).get("window_index") or 0)
        if idx:
            attempts[idx].append(item)
    selected = {}
    for idx, rows in attempts.items():
        rows.sort(
            key=lambda row: (
                int((row.get("window") or {}).get("actions_run_id") or 0),
                int((row.get("window") or {}).get("run_attempt") or 0),
            )
        )
        valid_rows = [r for r in rows if (r.get("window") or {}).get("status") == "VALID"]
        selected[idx] = valid_rows[0] if valid_rows else rows[-1]
    return selected, attempts


def aggregate_occurrences(entries: list[dict]) -> dict:
    out = Counter()
    for entry in entries:
        out["candidate_occurrences"] += 1
        if not semantic_strong(entry):
            continue
        out["semantically_strong_candidates"] += 1
        out["any_temporal_language"] += int(feature(entry, "any_temporal_language"))
        out["explicit_event_clocks"] += int(feature(entry, "explicit_clock"))
        out["explicit_intervals"] += int(feature(entry, "explicit_interval"))
        out["accepted_contemporaneous_live_forms"] += int(
            feature(entry, "accepted_contemporaneous_live_wording")
        )
        completed_no_safe = feature(entry, "retrospective_or_completed") and not strict_binding(entry)
        out["completed_event_no_safe_message_time"] += int(completed_no_safe)
        broad_combo = (
            feature(entry, "broad_daypart_or_date_only")
            or feature(entry, "retrospective_or_completed")
            or feature(entry, "cumulative_or_summary")
        )
        out["broad_retrospective_cumulative_forms"] += int(broad_combo)
        out["strict_episode_specific_bindings"] += int(strict_binding(entry))
        temporal = entry.get("current_temporal_binding") or {}
        if strict_binding(entry) and temporal.get("evidence_type") == "explicit_event_time":
            out["strict_EXPLICIT_EVENT_TIME"] += 1
        if strict_binding(entry) and temporal.get("code") == "TEMPORAL_CONTEMPORANEOUS_LIVE_WORDING":
            out["strict_CONTEMPORANEOUS_LIVE_WORDING"] += 1
    sem = int(out["semantically_strong_candidates"])
    strict = int(out["strict_episode_specific_bindings"])
    result = {k: int(v) for k, v in sorted(out.items())}
    result["binding_rate"] = strict / sem if sem else None
    result["binding_rate_ci95_wilson"] = wilson(strict, sem)
    return result


def group_unique_candidates(entries: list[dict], *, combine_rss_representations: bool) -> list[dict]:
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for occurrence in entries:
        entry = occurrence["entry"]
        identity = source_native_identity(entry)
        rep = entry.get("representation")
        rep_key = family_name(entry) if combine_rss_representations else rep
        key = (rep_key, evidence_id(identity), str(entry.get("city") or ""))
        groups[key].append(occurrence)

    result = []
    for (rep_key, eid, city), rows in groups.items():
        rows.sort(key=lambda x: (x["window_index"], x["entry"].get("published_at") or ""))
        entries_only = [x["entry"] for x in rows]
        base = max(entries_only, key=temporal_rank)
        identities = sorted(set(source_native_identity(x) for x in entries_only))
        representations = sorted(set(str(x.get("representation") or "") for x in entries_only))
        windows = sorted(set(int(x["window_index"]) for x in rows))
        clusters = sorted(
            set(
                str(x.get("analysis_logical_alert_cluster"))
                for x in entries_only
                if x.get("analysis_logical_alert_cluster")
            )
        )
        lags = sorted(
            set(
                float(x.get("explicit_event_time_lag_seconds"))
                for x in entries_only
                if x.get("explicit_event_time_lag_seconds") is not None
            )
        )
        result.append(
            {
                "panel_key": f"{rep_key}|{eid}|{city}",
                "source_item_id": eid,
                "source_native_identity": identities[0] if identities else "",
                "source_family": family_name(base),
                "representations": representations,
                "city": city,
                "publisher_or_channel": base.get("publisher_or_channel"),
                "source": base.get("source"),
                "url": base.get("url"),
                "resolved_url": base.get("resolved_url"),
                "published_at": base.get("published_at"),
                "source_text_excerpt": base.get("source_text_excerpt"),
                "source_text_hash": base.get("source_text_hash"),
                "semantic_strong": any(semantic_strong(x) for x in entries_only),
                "temporal_features": {
                    key: any(feature(x, key) for x in entries_only)
                    for key in (
                        "any_temporal_language",
                        "explicit_clock",
                        "explicit_interval",
                        "accepted_contemporaneous_live_wording",
                        "broad_daypart_or_date_only",
                        "retrospective_or_completed",
                        "cumulative_or_summary",
                    )
                },
                "strict_episode_specific_binding": any(strict_binding(x) for x in entries_only),
                "best_current_temporal_binding": base.get("current_temporal_binding"),
                "analysis_logical_alert_clusters": clusters,
                "explicit_event_time_lag_seconds_values": lags,
                "observed_windows": windows,
                "first_window": min(windows),
                "last_window": max(windows),
                "rediscovery_occurrences": len(rows),
                "candidate_ids": sorted(set(str(x.get("candidate_id") or "") for x in entries_only)),
            }
        )
    result.sort(key=lambda x: (x["source_family"], x["city"], x["source_item_id"]))
    return result


def metrics_from_unique(groups: list[dict]) -> dict:
    out = Counter()
    source_items = set()
    for row in groups:
        source_items.add(row["source_item_id"])
        out["unique_candidate_evaluations"] += 1
        if not row["semantic_strong"]:
            continue
        out["unique_semantically_strong_candidates"] += 1
        features = row["temporal_features"]
        out["any_temporal_language"] += int(features["any_temporal_language"])
        out["explicit_event_clocks"] += int(features["explicit_clock"])
        out["explicit_intervals"] += int(features["explicit_interval"])
        out["accepted_contemporaneous_live_forms"] += int(
            features["accepted_contemporaneous_live_wording"]
        )
        strict = bool(row["strict_episode_specific_binding"])
        out["completed_event_no_safe_message_time"] += int(
            features["retrospective_or_completed"] and not strict
        )
        out["broad_retrospective_cumulative_forms"] += int(
            features["broad_daypart_or_date_only"]
            or features["retrospective_or_completed"]
            or features["cumulative_or_summary"]
        )
        out["strict_episode_specific_bindings"] += int(strict)
        temporal = row.get("best_current_temporal_binding") or {}
        if strict and temporal.get("evidence_type") == "explicit_event_time":
            out["strict_EXPLICIT_EVENT_TIME"] += 1
        if strict and temporal.get("code") == "TEMPORAL_CONTEMPORANEOUS_LIVE_WORDING":
            out["strict_CONTEMPORANEOUS_LIVE_WORDING"] += 1
    sem = int(out["unique_semantically_strong_candidates"])
    strict = int(out["strict_episode_specific_bindings"])
    result = {k: int(v) for k, v in sorted(out.items())}
    result["unique_source_observations"] = len(source_items)
    result["binding_rate"] = strict / sem if sem else None
    result["binding_rate_ci95_wilson"] = wilson(strict, sem)
    return result


def build_source_item_ledger(entries: list[dict]) -> list[dict]:
    by_item: dict[tuple, list[dict]] = defaultdict(list)
    for occurrence in entries:
        entry = occurrence["entry"]
        identity = source_native_identity(entry)
        key = (family_name(entry), evidence_id(identity))
        by_item[key].append(occurrence)
    out = []
    for (family, eid), rows in by_item.items():
        rows.sort(key=lambda x: x["window_index"])
        first = rows[0]["entry"]
        out.append(
            {
                "source_family": family,
                "source_item_id": eid,
                "source_native_identity": source_native_identity(first),
                "publisher_or_channel": first.get("publisher_or_channel"),
                "representations": sorted(
                    set(str(x["entry"].get("representation") or "") for x in rows)
                ),
                "cities": sorted(set(str(x["entry"].get("city") or "") for x in rows)),
                "observed_windows": sorted(set(int(x["window_index"]) for x in rows)),
                "occurrence_count": len(rows),
                "source_text_hashes": sorted(
                    set(str(x["entry"].get("source_text_hash") or "") for x in rows)
                ),
            }
        )
    out.sort(key=lambda x: (x["source_family"], x["source_item_id"]))
    return out


def matched_cluster_ledger(entries: list[dict]) -> list[dict]:
    clusters = defaultdict(
        lambda: {
            "telegram_semantic": set(),
            "rss_semantic": set(),
            "telegram_strict": set(),
            "rss_strict": set(),
            "telegram_representations": set(),
            "rss_representations": set(),
            "windows": set(),
        }
    )
    meta = {}
    for occurrence in entries:
        entry = occurrence["entry"]
        if not semantic_strong(entry):
            continue
        cluster = entry.get("analysis_logical_alert_cluster")
        if not cluster:
            continue
        city = str(entry.get("city") or "")
        key = f"{city}|{cluster}"
        item_id = evidence_id(source_native_identity(entry))
        fam = family_name(entry)
        rec = clusters[key]
        rec[f"{fam}_semantic"].add(item_id)
        rec[f"{fam}_representations"].add(str(entry.get("representation") or ""))
        if strict_binding(entry):
            rec[f"{fam}_strict"].add(item_id)
        rec["windows"].add(int(occurrence["window_index"]))
        meta[key] = {"city": city, "logical_alert_cluster": cluster}

    out = []
    for key, rec in sorted(clusters.items()):
        if not rec["telegram_semantic"] or not rec["rss_semantic"]:
            continue
        tg = bool(rec["telegram_strict"])
        rss = bool(rec["rss_strict"])
        if tg and rss:
            outcome = "BOTH_TEMPORAL_BINDING"
        elif tg:
            outcome = "TELEGRAM_ONLY_TEMPORAL_BINDING"
        elif rss:
            outcome = "RSS_ONLY_TEMPORAL_BINDING"
        else:
            outcome = "NEITHER_TEMPORAL_BINDING"
        out.append(
            {
                **meta[key],
                "outcome": outcome,
                "telegram_strict_episode_binding": tg,
                "rss_strict_episode_binding": rss,
                "telegram_unique_semantically_strong_source_items": len(rec["telegram_semantic"]),
                "rss_unique_semantically_strong_source_items": len(rec["rss_semantic"]),
                "telegram_source_item_ids": sorted(rec["telegram_semantic"]),
                "rss_source_item_ids": sorted(rec["rss_semantic"]),
                "telegram_strict_source_item_ids": sorted(rec["telegram_strict"]),
                "rss_strict_source_item_ids": sorted(rec["rss_strict"]),
                "telegram_representations": sorted(rec["telegram_representations"]),
                "rss_representations": sorted(rec["rss_representations"]),
                "observed_windows": sorted(rec["windows"]),
            }
        )
    return out


def matched_summary(ledger: list[dict]) -> dict:
    counts = Counter(row["outcome"] for row in ledger)
    total = len(ledger)
    tg_bound = sum(int(row["telegram_strict_episode_binding"]) for row in ledger)
    rss_bound = sum(int(row["rss_strict_episode_binding"]) for row in ledger)
    outcomes = {}
    for name in (
        "TELEGRAM_ONLY_TEMPORAL_BINDING",
        "RSS_ONLY_TEMPORAL_BINDING",
        "BOTH_TEMPORAL_BINDING",
        "NEITHER_TEMPORAL_BINDING",
    ):
        count = int(counts[name])
        outcomes[name] = {"count": count, "share": count / total if total else None}
    return {
        "matched_logical_alert_clusters": total,
        "unique_cities": sorted(set(row["city"] for row in ledger)),
        "outcomes": outcomes,
        "telegram_cluster_binding_rate": tg_bound / total if total else None,
        "telegram_cluster_binding_rate_ci95_wilson": wilson(tg_bound, total),
        "rss_cluster_binding_rate": rss_bound / total if total else None,
        "rss_cluster_binding_rate_ci95_wilson": wilson(rss_bound, total),
        "paired_discordant_exact_test": exact_paired_binomial(
            counts["TELEGRAM_ONLY_TEMPORAL_BINDING"],
            counts["RSS_ONLY_TEMPORAL_BINDING"],
        ),
        "clusters_with_any_strict_binding": sum(
            1
            for row in ledger
            if row["telegram_strict_episode_binding"] or row["rss_strict_episode_binding"]
        ),
    }


def group_breakdowns(
    tg_groups: list[dict],
    rep_groups: dict[str, list[dict]],
    cluster_ledger: list[dict],
) -> tuple[dict, dict, dict]:
    by_city = defaultdict(list)
    by_channel = defaultdict(list)
    for row in tg_groups:
        if not row["semantic_strong"]:
            continue
        by_city[row["city"]].append(row)
        by_channel[str(row.get("publisher_or_channel") or "unknown")].append(row)

    city_out = {}
    for city, rows in sorted(by_city.items()):
        if len(rows) < 10:
            continue
        strict = sum(int(r["strict_episode_specific_binding"]) for r in rows)
        clusters = [x for x in cluster_ledger if x["city"] == city]
        counts = Counter(x["outcome"] for x in clusters)
        city_out[city] = {
            "telegram_denominator": len(rows),
            "telegram_strict_bindings": strict,
            "telegram_binding_rate": strict / len(rows),
            "telegram_binding_rate_ci95_wilson": wilson(strict, len(rows)),
            "rss_matched_cluster_results": {
                "matched_clusters": len(clusters),
                "TELEGRAM_ONLY_TEMPORAL_BINDING": int(counts["TELEGRAM_ONLY_TEMPORAL_BINDING"]),
                "RSS_ONLY_TEMPORAL_BINDING": int(counts["RSS_ONLY_TEMPORAL_BINDING"]),
                "BOTH_TEMPORAL_BINDING": int(counts["BOTH_TEMPORAL_BINDING"]),
                "NEITHER_TEMPORAL_BINDING": int(counts["NEITHER_TEMPORAL_BINDING"]),
            },
        }

    channel_out = {}
    for channel, rows in sorted(by_channel.items()):
        if len(rows) < 10:
            continue
        strict = sum(int(r["strict_episode_specific_binding"]) for r in rows)
        live_cases = sum(
            int(r["temporal_features"]["accepted_contemporaneous_live_wording"]) for r in rows
        )
        live_strict = sum(
            int(
                r["strict_episode_specific_binding"]
                and (r.get("best_current_temporal_binding") or {}).get("code")
                == "TEMPORAL_CONTEMPORANEOUS_LIVE_WORDING"
            )
            for r in rows
        )
        channel_out[channel] = {
            "denominator": len(rows),
            "contemporaneous_live_cases": live_cases,
            "strict_temporal_bindings": strict,
            "strict_contemporaneous_live_bindings": live_strict,
            "binding_rate": strict / len(rows),
            "binding_rate_ci95_wilson": wilson(strict, len(rows)),
        }

    publisher_out = {}
    for rep in ("rss_title_snippet", "rss_publisher_fulltext"):
        by_pub = defaultdict(list)
        for row in rep_groups.get(rep, []):
            if row["semantic_strong"]:
                by_pub[str(row.get("publisher_or_channel") or "unknown")].append(row)
        rows_out = {}
        for publisher, rows in sorted(by_pub.items(), key=lambda kv: (-len(kv[1]), kv[0])):
            strict = sum(int(r["strict_episode_specific_binding"]) for r in rows)
            rows_out[publisher] = {
                "semantically_strong_candidates": len(rows),
                "strict_temporal_bindings": strict,
                "binding_rate": strict / len(rows),
                "binding_rate_ci95_wilson": wilson(strict, len(rows)),
                "major_publisher": len(rows) >= 10,
            }
        publisher_out[rep] = rows_out
    return city_out, channel_out, publisher_out


def explicit_lag(unique_by_rep: dict[str, list[dict]], family_groups: dict[str, list[dict]]) -> dict:
    out = {}
    for rep, groups in unique_by_rep.items():
        values = []
        for row in groups:
            if not row["semantic_strong"] or not row["strict_episode_specific_binding"]:
                continue
            temporal = row.get("best_current_temporal_binding") or {}
            if temporal.get("evidence_type") != "explicit_event_time":
                continue
            lags = row.get("explicit_event_time_lag_seconds_values") or []
            if lags:
                values.append(float(lags[0]))
        out[rep] = lag_summary(values)
    for family, groups in family_groups.items():
        values = []
        for row in groups:
            if not row["semantic_strong"] or not row["strict_episode_specific_binding"]:
                continue
            temporal = row.get("best_current_temporal_binding") or {}
            if temporal.get("evidence_type") != "explicit_event_time":
                continue
            lags = row.get("explicit_event_time_lag_seconds_values") or []
            if lags:
                values.append(float(lags[0]))
        out[f"{family}_official_combined"] = lag_summary(values)
    return out


def decide(
    *,
    panel_complete: bool,
    valid_windows: int,
    matched: dict,
    tg_groups: list[dict],
) -> dict:
    thresholds = {
        "minimum_valid_windows": MIN_VALID_WINDOWS,
        "minimum_matched_clusters": MIN_MATCHED_CLUSTERS,
        "minimum_clusters_with_any_strict_binding": MIN_TEMPORAL_SUCCESS_CLUSTERS,
    }
    if not panel_complete:
        return {
            "verdict": "PENDING",
            "strategic_recommendation": "PENDING",
            "thresholds": thresholds,
            "reason": "PRE_REGISTERED_PANEL_NOT_COMPLETE",
        }

    sample_sufficient = (
        valid_windows >= MIN_VALID_WINDOWS
        and matched["matched_logical_alert_clusters"] >= MIN_MATCHED_CLUSTERS
        and matched["clusters_with_any_strict_binding"] >= MIN_TEMPORAL_SUCCESS_CLUSTERS
    )

    strict_cities = sorted(
        set(r["city"] for r in tg_groups if r["semantic_strong"] and r["strict_episode_specific_binding"])
    )
    strict_channels = sorted(
        set(
            str(r.get("publisher_or_channel") or "unknown")
            for r in tg_groups
            if r["semantic_strong"] and r["strict_episode_specific_binding"]
        )
    )
    cross_city = len(strict_cities) >= 2 and any(city != "kyiv" for city in strict_cities)
    cross_channel = len(strict_channels) >= 2

    tg_only = matched["outcomes"]["TELEGRAM_ONLY_TEMPORAL_BINDING"]["count"]
    rss_only = matched["outcomes"]["RSS_ONLY_TEMPORAL_BINDING"]["count"]
    tg_cluster_bound = sum(
        1
        for _ in range(matched["matched_logical_alert_clusters"])
    ) * 0
    tg_rate = matched["telegram_cluster_binding_rate"] or 0.0
    rss_rate = matched["rss_cluster_binding_rate"] or 0.0

    if not sample_sufficient:
        verdict = "TELEGRAM VS RSS TEMPORAL ATTRIBUTION = INSUFFICIENT SAMPLE"
    elif tg_only > rss_only and tg_rate > rss_rate:
        if cross_city and cross_channel and (tg_only - rss_only) >= 2:
            verdict = "TELEGRAM TEMPORAL ATTRIBUTION = CLEARLY STRONGER"
        else:
            verdict = "TELEGRAM TEMPORAL ATTRIBUTION = MODESTLY STRONGER"
    elif rss_only > tg_only and rss_rate > tg_rate and (rss_only - tg_only) >= 2:
        verdict = "RSS TEMPORAL ATTRIBUTION = STRONGER"
    else:
        verdict = "TELEGRAM AND RSS TEMPORAL ATTRIBUTION = COMPARABLE"

    recommendation = {
        "TELEGRAM TEMPORAL ATTRIBUTION = CLEARLY STRONGER": "PRIORITIZE TELEGRAM COVERAGE AUDIT",
        "TELEGRAM TEMPORAL ATTRIBUTION = MODESTLY STRONGER": "PURSUE BOTH",
        "TELEGRAM AND RSS TEMPORAL ATTRIBUTION = COMPARABLE": "PURSUE BOTH",
        "RSS TEMPORAL ATTRIBUTION = STRONGER": "PRIORITIZE RSS TEMPORAL PARSER WORK",
        "TELEGRAM VS RSS TEMPORAL ATTRIBUTION = INSUFFICIENT SAMPLE": "GATHER MORE COMPARABLE DATA",
    }[verdict]

    return {
        "verdict": verdict,
        "strategic_recommendation": recommendation,
        "thresholds": thresholds,
        "sample_sufficient": sample_sufficient,
        "telegram_strict_success_cities": strict_cities,
        "telegram_strict_success_channels": strict_channels,
        "cross_city_replication": cross_city,
        "cross_channel_replication": cross_channel,
        "channel_replication_answer": (
            "MULTIPLE_CHANNELS"
            if len(strict_channels) >= 2
            else ("ONLY_ONE_CHANNEL" if len(strict_channels) == 1 else "NO_STRICT_TELEGRAM_SUCCESS")
        ),
    }


def aggregate_panel(args: argparse.Namespace) -> dict:
    root = Path(args.input_dir)
    manifests = []
    for path in sorted(root.rglob("window_*.json")):
        try:
            item = read_json(path)
        except Exception:
            continue
        if item.get("schema") == "telegram_vs_rss_temporal_attribution_panel_window_v1":
            manifests.append(item)

    selected, attempts = select_attempts(manifests)
    as_of = parse_dt(args.as_of) or datetime.now(timezone.utc)

    schedule_status = []
    panel_complete = True
    for row in SCHEDULE:
        idx = row["window_index"]
        scheduled = parse_dt(row["scheduled_at_utc"])
        assert scheduled is not None
        attempt_rows = attempts.get(idx, [])
        valid_attempts = [
            a for a in attempt_rows if (a.get("window") or {}).get("status") == "VALID"
        ]
        if valid_attempts:
            status = "VALID"
        elif attempt_rows:
            status = "INVALID"
        elif as_of >= scheduled:
            status = "MISSING"
        else:
            status = "PENDING"
            panel_complete = False
        schedule_status.append(
            {
                **row,
                "status": status,
                "attempt_count": len(attempt_rows),
                "valid_attempt_count": len(valid_attempts),
                "selected_actions_run_id": (
                    int((selected.get(idx, {}).get("window") or {}).get("actions_run_id") or 0)
                    if idx in selected
                    else None
                ),
            }
        )

    valid_selected = {
        idx: item
        for idx, item in selected.items()
        if (item.get("window") or {}).get("status") == "VALID"
    }

    occurrences = []
    per_run = []
    for idx, item in sorted(valid_selected.items()):
        raw = item.get("raw_audit") or {}
        for entry in raw.get("candidate_level_ledger") or []:
            occurrences.append({"window_index": idx, "entry": entry})
        per_run.append(
            {
                "window_index": idx,
                "window": item.get("window"),
                "production_code_identity": item.get("production_code_identity"),
                "raw_audit_sha256": item.get("raw_audit_sha256"),
                "raw_per_run_metrics": item.get("raw_per_run_metrics"),
            }
        )

    observation_metrics = {}
    for rep in REPRESENTATIONS:
        rep_entries = [x["entry"] for x in occurrences if x["entry"].get("representation") == rep]
        observation_metrics[rep] = aggregate_occurrences(rep_entries)
    observation_metrics["telegram_family"] = aggregate_occurrences(
        [x["entry"] for x in occurrences if family_name(x["entry"]) == "telegram"]
    )
    observation_metrics["rss_official_family"] = aggregate_occurrences(
        [x["entry"] for x in occurrences if family_name(x["entry"]) == "rss"]
    )

    rep_unique = {}
    for rep in REPRESENTATIONS:
        rep_unique[rep] = group_unique_candidates(
            [x for x in occurrences if x["entry"].get("representation") == rep],
            combine_rss_representations=False,
        )

    family_unique = {
        "telegram": group_unique_candidates(
            [x for x in occurrences if family_name(x["entry"]) == "telegram"],
            combine_rss_representations=True,
        ),
        "rss": group_unique_candidates(
            [x for x in occurrences if family_name(x["entry"]) == "rss"],
            combine_rss_representations=True,
        ),
    }

    unique_metrics = {
        "by_representation": {rep: metrics_from_unique(rows) for rep, rows in rep_unique.items()},
        "by_source_family": {
            "telegram": metrics_from_unique(family_unique["telegram"]),
            "rss_official": metrics_from_unique(family_unique["rss"]),
        },
    }

    clusters = matched_cluster_ledger(occurrences)
    matched = matched_summary(clusters)
    city_breakdown, channel_breakdown, publisher_breakdown = group_breakdowns(
        family_unique["telegram"], rep_unique, clusters
    )

    lag = explicit_lag(
        rep_unique,
        {"telegram": family_unique["telegram"], "rss": family_unique["rss"]},
    )

    source_items = build_source_item_ledger(occurrences)
    unique_candidate_ledger = []
    for rep in REPRESENTATIONS:
        unique_candidate_ledger.extend(rep_unique[rep])

    mutation_attempts = []
    all_zero = True
    for idx, rows in sorted(attempts.items()):
        for item in rows:
            proof = item.get("mutation_proof") or {}
            zero = mutation_all_zero(proof)
            all_zero = all_zero and zero
            mutation_attempts.append(
                {
                    "window_index": idx,
                    "actions_run_id": int((item.get("window") or {}).get("actions_run_id") or 0),
                    "run_attempt": int((item.get("window") or {}).get("run_attempt") or 0),
                    "status": (item.get("window") or {}).get("status"),
                    "all_required_mutations_zero": zero,
                    "mutation_proof": proof,
                }
            )

    decision = decide(
        panel_complete=panel_complete,
        valid_windows=len(valid_selected),
        matched=matched,
        tg_groups=family_unique["telegram"],
    )

    payload = {
        "schema": "telegram_vs_rss_temporal_attribution_multiwindow_panel_v1",
        "generated_at": iso(as_of),
        "pre_registration": {
            "schedule": SCHEDULE,
            "sampling_plan": {
                "planned_windows": 14,
                "calendar_days": 7,
                "observations_per_day": 2,
                "spacing": "12 hours",
                "timezone": "Europe/Kyiv",
                "no_early_stop": True,
                "no_outcome_driven_extra_runs": True,
                "retry_rule": "only genuine execution failure with no valid observation",
            },
            "production_code_commit": PRODUCTION_CODE_COMMIT,
            "accepted_predecessor": {
                "verdict": "TELEGRAM VS RSS TEMPORAL ATTRIBUTION = INSUFFICIENT SAMPLE",
                "actions_run": PREDECESSOR_ACTIONS_RUN,
                "proof_tooling_head": PREDECESSOR_PROOF_HEAD,
                "proof_json_sha256": PREDECESSOR_JSON_SHA256,
            },
            "decision_thresholds": {
                "minimum_valid_windows": MIN_VALID_WINDOWS,
                "minimum_matched_clusters": MIN_MATCHED_CLUSTERS,
                "minimum_clusters_with_any_strict_binding": MIN_TEMPORAL_SUCCESS_CLUSTERS,
            },
        },
        "observation_windows": schedule_status,
        "panel_complete": panel_complete,
        "valid_window_count": len(valid_selected),
        "invalid_or_missing_window_count": sum(
            1 for x in schedule_status if x["status"] in {"INVALID", "MISSING"}
        ),
        "raw_per_run_metrics": per_run,
        "observation_panel": {
            "definition": "every candidate occurrence in every selected valid scheduled run",
            "metrics": observation_metrics,
        },
        "unique_evidence_panel": {
            "definition": "global cross-run deduplication by source-native source item identity; candidate evaluations are source item x city, with RSS representations kept separate where reported",
            "metrics": unique_metrics,
            "source_item_ledger": source_items,
            "candidate_evaluation_ledger": unique_candidate_ledger,
        },
        "matched_alert_cluster_analysis": {
            "summary": matched,
            "ledger": clusters,
        },
        "city_replication": {
            "reporting_threshold": "at least 10 unique semantically strong Telegram candidates",
            "cities": city_breakdown,
        },
        "telegram_channel_replication": {
            "reporting_threshold": "at least 10 unique semantically strong candidates",
            "channels": channel_breakdown,
            "strict_success_channels": decision.get("telegram_strict_success_channels", []),
            "replication_answer": decision.get("channel_replication_answer"),
        },
        "rss_publisher_context": {
            "major_publisher_threshold": "at least 10 unique semantically strong candidates",
            "by_representation": publisher_breakdown,
        },
        "explicit_time_lag_analysis": lag,
        "uncertainty_and_statistics": {
            "source_family_binding_rate_intervals": {
                "telegram": unique_metrics["by_source_family"]["telegram"].get(
                    "binding_rate_ci95_wilson"
                ),
                "rss_official": unique_metrics["by_source_family"]["rss_official"].get(
                    "binding_rate_ci95_wilson"
                ),
            },
            "matched_cluster_paired_test": matched["paired_discordant_exact_test"],
            "note": "candidate-level independence is not assumed; paired cluster discordance is descriptive support only",
        },
        "decision": decision,
        "mutation_proof": {
            "per_attempt": mutation_attempts,
            "cumulative_all_required_mutations_zero": all_zero,
            "required_zero_fields": list(MUTATION_KEYS),
        },
    }

    digest = write_json(args.out, payload)
    Path(args.out + ".sha256").write_text(
        f"{digest}  {Path(args.out).name}\n", encoding="utf-8"
    )
    summary = {
        "schema": payload["schema"],
        "generated_at": payload["generated_at"],
        "panel_complete": panel_complete,
        "valid_window_count": len(valid_selected),
        "observation_windows": schedule_status,
        "unique_evidence_metrics": unique_metrics,
        "matched_alert_cluster_summary": matched,
        "city_replication": city_breakdown,
        "telegram_channel_replication": payload["telegram_channel_replication"],
        "rss_publisher_context": payload["rss_publisher_context"],
        "explicit_time_lag_analysis": lag,
        "uncertainty_and_statistics": payload["uncertainty_and_statistics"],
        "decision": decision,
        "cumulative_mutation_zero": all_zero,
        "json_sha256": digest,
    }
    write_json(args.summary_out, summary)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    p_resolve = sub.add_parser("resolve")
    p_resolve.add_argument("--now", required=True)
    p_resolve.add_argument("--cron", required=True)
    p_resolve.add_argument("--github-output")

    p_window = sub.add_parser("window")
    p_window.add_argument("--window-index", required=True, type=int)
    p_window.add_argument("--scheduled-utc", required=True)
    p_window.add_argument("--scheduled-local", required=True)
    p_window.add_argument("--cron", required=True)
    p_window.add_argument("--raw-audit", required=True)
    p_window.add_argument("--mutation-proof", required=True)
    p_window.add_argument("--code-identity", required=True)
    p_window.add_argument("--observation-exit-code", required=True, type=int)
    p_window.add_argument("--failure-reason", default="")
    p_window.add_argument("--actions-run-id", required=True, type=int)
    p_window.add_argument("--run-attempt", required=True, type=int)
    p_window.add_argument("--workflow-sha", required=True)
    p_window.add_argument("--proof-tooling-commit", required=True)
    p_window.add_argument("--out", required=True)

    p_agg = sub.add_parser("aggregate")
    p_agg.add_argument("--input-dir", required=True)
    p_agg.add_argument("--as-of", required=True)
    p_agg.add_argument("--out", required=True)
    p_agg.add_argument("--summary-out", required=True)

    args = parser.parse_args()

    if args.command == "resolve":
        now = parse_dt(args.now)
        if now is None:
            raise SystemExit("INVALID_NOW")
        result = resolve_window(now, args.cron)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        if args.github_output:
            with Path(args.github_output).open("a", encoding="utf-8") as fh:
                fh.write(f"in_panel={'true' if result.get('in_panel') else 'false'}\n")
                if result.get("in_panel"):
                    fh.write(f"window_index={result['window_index']}\n")
                    fh.write(f"window_id={result['window_id']}\n")
                    fh.write(f"scheduled_utc={result['scheduled_at_utc']}\n")
                    fh.write(f"scheduled_local={result['scheduled_at_kyiv']}\n")
                    fh.write(f"cron={result['cron']}\n")
        return

    if args.command == "window":
        result = build_window(args)
        print(
            json.dumps(
                {
                    "window": result["window"],
                    "raw_audit_sha256": result["raw_audit_sha256"],
                    "mutation_zero": mutation_all_zero(result["mutation_proof"]),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return

    if args.command == "aggregate":
        result = aggregate_panel(args)
        print(
            json.dumps(
                {
                    "panel_complete": result["panel_complete"],
                    "valid_window_count": result["valid_window_count"],
                    "matched_alert_cluster_summary": result["matched_alert_cluster_analysis"]["summary"],
                    "decision": result["decision"],
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return


if __name__ == "__main__":
    main()
