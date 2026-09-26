#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

USER_AGENT = "Mozilla/5.0 (compatible; historical-replay-source-retention-audit/1.0)"
STRIP_TAGS = ("script", "style", "noscript", "svg", "nav", "footer", "header", "form")
GENERIC_TOKENS = {
    "суми", "сумах", "сум", "місто", "міста", "місті", "обласного", "центру",
    "російський", "російські", "російська", "російського", "армія", "війська",
    "бпла", "дрон", "дрони", "безпілотник", "безпілотники", "шахед", "вибух",
    "вибухи", "удар", "удари", "атакував", "атакували", "влучив", "влучили",
    "близько", "після", "вранці", "увечері", "ввечері", "вночі", "вночі",
    "було", "були", "через", "під", "час", "один", "одного", "цього", "того",
}


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def import_monitor(repo_root: Path):
    path = repo_root / "scripts" / "monitor_explosion_candidates.py"
    spec = importlib.util.spec_from_file_location("source_retention_monitor", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import monitor from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(path.parent))
    spec.loader.exec_module(module)
    return module


def normalize(text: str | None) -> str:
    return " ".join((text or "").replace("\xa0", " ").split())


def content_tokens(text: str) -> set[str]:
    low = text.casefold().replace("’", "'")
    tokens = set(re.findall(r"[0-9A-Za-zА-Яа-яІіЇїЄєҐґ'-]{3,}", low))
    return {t.strip("'-") for t in tokens if t.strip("'-") and t.strip("'-") not in GENERIC_TOKENS}


def time_tokens(text: str) -> set[str]:
    return set(re.findall(r"(?<!\d)(?:[01]?\d|2[0-3]):[0-5]\d(?!\d)", text or ""))


def original_case_text(case: dict) -> str:
    parts = []
    for ev in case.get("evidence") or []:
        value = ev.get("evidence")
        if value:
            parts.append(str(value).split(" — ", 1)[0])
    return " ".join(parts)


def dedupe_chunks(chunks: list[str]) -> list[str]:
    out = []
    seen = set()
    for raw in chunks:
        text = normalize(raw)
        if len(text) < 30:
            continue
        if len(text) > 1800:
            text = text[:1800]
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


def html_chunks(url: str, raw_html: str) -> list[str]:
    soup = BeautifulSoup(raw_html or "", "html.parser")
    for tag in soup.find_all(STRIP_TAGS):
        tag.decompose()

    host = (urlparse(url).hostname or "").casefold()
    if host == "t.me" or host.endswith(".t.me"):
        chunks = [
            node.get_text(" ", strip=True)
            for node in soup.select(".tgme_widget_message_text")
        ]
        if chunks:
            return dedupe_chunks(chunks)

    container = soup.find("article") or soup.find("main") or soup
    chunks = []
    for node in container.find_all(["p", "li", "h1", "h2", "h3", "blockquote"]):
        text = node.get_text(" ", strip=True)
        if text:
            chunks.append(text)

    if not chunks:
        chunks.append(container.get_text(" ", strip=True))
    return dedupe_chunks(chunks)


def fetch_source(url: str) -> dict:
    try:
        response = requests.get(
            url,
            headers={"User-Agent": USER_AGENT, "Accept-Language": "uk,en;q=0.7"},
            timeout=35,
            allow_redirects=True,
        )
        response.raise_for_status()
        content_type = str(response.headers.get("Content-Type") or "").casefold()
        if "html" not in content_type:
            return {
                "status": "FETCH_UNSUPPORTED_CONTENT_TYPE",
                "http_status": response.status_code,
                "content_type": content_type,
                "resolved_url": str(response.url or url),
                "chunks": [],
            }
        chunks = html_chunks(str(response.url or url), response.text)
        normalized = "\n".join(chunks)
        return {
            "status": "OK" if chunks else "NO_TEXT_EXTRACTED",
            "http_status": response.status_code,
            "content_type": content_type,
            "resolved_url": str(response.url or url),
            "content_sha256": hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
            "chunk_count": len(chunks),
            "chunks": chunks,
        }
    except Exception as exc:
        return {
            "status": "FETCH_ERROR",
            "error": f"{type(exc).__name__}: {exc}",
            "chunks": [],
        }


def missing_roles(case: dict) -> list[str]:
    codes = set(case.get("reason_codes") or [])
    roles = []
    if "NO_EXACT_CITY_EVENT_TEXT" in codes:
        roles.append("exact_city")
    if "NO_STRICT_EXPLOSION_EVIDENCE" in codes:
        roles.append("strict_explosion")
    if "NO_AIR_MILITARY_CONTEXT" in codes:
        roles.append("air_military_context")
    if "AIR_CONTEXT_NOT_LINKED_TO_EVENT" in codes:
        roles.append("same_attack_context")
    return roles


def analyze_chunk(city: str, chunk: str, original: str, monitor) -> dict:
    exact = bool(monitor.city_mentioned(city, chunk))
    explosion = bool(monitor.strict_explosion_signal(chunk))
    air = bool(monitor.air_military_context(chunk))
    military_event = bool(monitor.military_strike_event_signal(chunk))
    complete = exact and explosion and air
    original_tokens = content_tokens(original)
    chunk_tokens = content_tokens(chunk)
    shared = sorted(original_tokens & chunk_tokens)
    original_times = time_tokens(original)
    chunk_times = time_tokens(chunk)
    shared_times = sorted(original_times & chunk_times)
    anchor_ok = bool(shared_times or len(shared) >= 2)
    return {
        "exact_city": exact,
        "strict_explosion": explosion,
        "air_military_context": air,
        "military_strike_event": military_event,
        "same_attack_context": complete,
        "complete_current_rule_roles": complete,
        "anchor_ok": anchor_ok,
        "shared_time_tokens": shared_times,
        "shared_content_tokens": shared[:12],
        "excerpt": chunk[:700],
    }


def case_audit(city: str, case: dict, source_cache: dict[str, dict], monitor) -> dict:
    original = original_case_text(case)
    required = missing_roles(case)
    urls = []
    for ev in case.get("evidence") or []:
        url = str(ev.get("source_url") or "").strip()
        if url and url not in urls:
            urls.append(url)

    candidates = []
    fetch_statuses = []
    for url in urls:
        src = source_cache[url]
        fetch_statuses.append({
            "url": url,
            "status": src.get("status"),
            "http_status": src.get("http_status"),
            "resolved_url": src.get("resolved_url"),
            "content_sha256": src.get("content_sha256"),
            "chunk_count": src.get("chunk_count", 0),
            "error": src.get("error"),
        })
        for idx, chunk in enumerate(src.get("chunks") or []):
            a = analyze_chunk(city, chunk, original, monitor)
            role_map = {
                "exact_city": a["exact_city"],
                "strict_explosion": a["strict_explosion"],
                "air_military_context": a["air_military_context"],
                "same_attack_context": a["same_attack_context"],
            }
            required_satisfied = all(role_map.get(role, False) for role in required)
            if required_satisfied or a["complete_current_rule_roles"]:
                candidates.append({
                    "url": url,
                    "chunk_index": idx,
                    **a,
                    "required_roles_satisfied": required_satisfied,
                })

    candidates.sort(
        key=lambda x: (
            bool(x.get("required_roles_satisfied") and x.get("anchor_ok")),
            bool(x.get("complete_current_rule_roles") and x.get("anchor_ok")),
            bool(x.get("required_roles_satisfied")),
            len(x.get("shared_time_tokens") or []),
            len(x.get("shared_content_tokens") or []),
        ),
        reverse=True,
    )
    best = candidates[0] if candidates else None

    any_ok = any(x.get("status") == "OK" for x in fetch_statuses)
    if best and best.get("required_roles_satisfied") and best.get("anchor_ok"):
        triage = "SOURCE_RETENTION_CANDIDATE"
    elif best and best.get("required_roles_satisfied"):
        triage = "SOURCE_CONTEXT_FOUND_WEAK_ANCHOR"
    elif any_ok:
        triage = "NO_COMPLETE_SOURCE_SEGMENT"
    else:
        triage = "FETCH_FAILED"

    return {
        "case_id": case.get("case_id"),
        "episode_id": case.get("episode_id"),
        "local_date": case.get("local_date"),
        "category": case.get("category"),
        "frozen_old_status": case.get("frozen_old_status"),
        "replayed_status": case.get("replayed_status"),
        "case_fingerprint": case.get("case_fingerprint"),
        "missing_roles": required,
        "triage": triage,
        "source_fetches": fetch_statuses,
        "best_candidate": best,
        "candidate_count": len(candidates),
    }


def audit(repo_root: Path, qa_path: Path, output: Path) -> None:
    qa = load_json(qa_path)
    city = str(qa.get("city_key") or "")
    if not city:
        raise ValueError("QA bundle missing city_key")
    monitor = import_monitor(repo_root)
    monitor.self_test()

    urls = []
    for case in qa.get("cases") or []:
        for ev in case.get("evidence") or []:
            url = str(ev.get("source_url") or "").strip()
            if url and url not in urls:
                urls.append(url)

    source_cache = {url: fetch_source(url) for url in urls}
    cases = [case_audit(city, case, source_cache, monitor) for case in qa.get("cases") or []]
    counts = Counter(row["triage"] for row in cases)
    fetch_counts = Counter(src.get("status") for src in source_cache.values())

    payload = {
        "schema_version": 1,
        "kind": "historical_replay_source_retention_audit",
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "city_key": city,
        "qa_bundle_path": str(qa_path),
        "qa_bundle_replay_input_head": qa.get("replay_input_head"),
        "qa_case_count": len(cases),
        "unique_source_url_count": len(urls),
        "triage_counts": dict(sorted(counts.items())),
        "source_fetch_counts": dict(sorted(fetch_counts.items())),
        "safe_mutation_performed": False,
        "methodology": {
            "purpose": "Detect likely source-retention misses without changing historical evidence or production data.",
            "source_scope": "Only source URLs already retained in the frozen QA bundle.",
            "role_logic": "Current monitor city/explosion/air-context functions applied to local source chunks.",
            "same_attack_gate": "Exact city + strict explosion + air context must co-occur in one extracted chunk.",
            "anchor_gate": "At least one shared clock time or at least two non-generic content tokens with retained evidence.",
            "automatic_repairs": "None. SOURCE_RETENTION_CANDIDATE is a reviewable candidate, not a mutation.",
        },
        "cases": cases,
    }
    dump_json(output, payload)


def self_test() -> None:
    assert "strict_explosion" in missing_roles({"reason_codes": ["NO_STRICT_EXPLOSION_EVIDENCE"]})
    assert time_tokens("о 14:30 та 15:00") == {"14:30", "15:00"}
    assert len(content_tokens("реактивний дрон атакував Мануфактуру у Сумах")) >= 2
    print("Source-retention auditor self-test OK")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path)
    parser.add_argument("--qa", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    if not args.repo_root or not args.qa or not args.output:
        parser.error("--repo-root, --qa and --output are required")
    audit(args.repo_root.resolve(), args.qa.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()
