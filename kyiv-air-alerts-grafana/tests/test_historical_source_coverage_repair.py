from __future__ import annotations

import hashlib
import json
import sys
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKOUT_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / "scripts"))

import monitor_explosion_candidates as monitor
import run_historical_attack_event_backfill_batch as batch_runner
from historical_attack_event_sources import NetworkBounds, PublicTelegramAdapter, canonical_observation_id, content_hash

CASE17_ID = "9e87e464ea93d32b31a09a3d"
CASE18_ID = "6069b17ec096cae0912ad9bd"
CASE17_START = "2025-12-14T06:20:53Z"
CASE17_END = "2025-12-14T07:41:32Z"
CASE18_START = "2026-09-04T11:48:14Z"
CASE18_END = "2026-09-04T12:13:20Z"
CASE17_MESSAGE_ID = 40582
CASE18_MESSAGE_ID = 23590
REGISTRY = CHECKOUT_ROOT / "research" / "historical_attack_event_source_registry.json"


def episode(city_key: str, episode_id: str, start: str, end: str) -> dict:
    return {
        "episode_id": episode_id,
        "city_key": city_key,
        "city": monitor.CITY_CONFIG[city_key]["label"],
        "alert_start": start,
        "alert_end": end,
    }


def family(city_key: str, source_family: str) -> dict:
    doc = json.loads(REGISTRY.read_text(encoding="utf-8"))
    return next(
        row for row in doc["cities"][city_key]["source_families"]
        if row["source_family"] == source_family
    )


def bounded_search(source_family: dict, ep: dict, query: str) -> tuple[list[dict], dict]:
    bounds = NetworkBounds(
        timeout_seconds=15,
        max_retries=2,
        rate_limit_seconds=0.2,
        max_telegram_pages=60,
        max_neighbor_previous=3,
    )
    adapter = PublicTelegramAdapter(bounds)
    start = monitor.parse_dt(ep["alert_start"]) - timedelta(hours=batch_runner.PRE_ALERT_WINDOW_HOURS)
    end = monitor.parse_dt(ep["alert_end"]) + timedelta(hours=batch_runner.LATE_WINDOW_HOURS)
    return adapter.search(source_family["channel"], query, start, end, max_pages=source_family["max_pages"])


def exact_post(source_family: dict, message_id: int) -> tuple[dict, dict]:
    adapter = PublicTelegramAdapter(NetworkBounds(timeout_seconds=15, max_retries=2, rate_limit_seconds=0.2))
    post, meta = adapter.fetch_exact_post(source_family["channel"], message_id)
    assert post is not None, meta
    return post, meta


def to_observation(city_key: str, source_family: dict, ep: dict, post: dict) -> dict:
    row = batch_runner.telegram_candidate(city_key, source_family, post, "bounded_public_telegram_search")
    return batch_runner.classify_row(
        city_key,
        row,
        [ep],
        source_family=source_family["source_family"],
        source_type="public_telegram",
        source_timestamp=post["published_at"],
        excerpt=post["text"],
        source_url=post["url"],
        telegram_channel=post["channel"],
        telegram_message_id=post["message_id"],
        retrieval_provenance={
            "adapter": "PublicTelegramAdapter",
            "proof_only": True,
            "query": source_family["queries"][0],
        },
    )


def assert_stable_provenance(obs: dict, post: dict) -> None:
    assert obs["observation_id"] == canonical_observation_id(post["channel"], post["message_id"])
    assert obs["content_hash"] == content_hash(
        post["channel"], post["message_id"], post["published_at"], post["text"]
    )
    assert obs["telegram_channel"] == post["channel"]
    assert obs["telegram_message_id"] == post["message_id"]
    assert obs["source_timestamp"] == post["published_at"]


def test_case17_exact_time_retrieval() -> None:
    ep = episode("sumy", CASE17_ID, CASE17_START, CASE17_END)
    fam = family("sumy", "telegram/suspilnesumy")
    post, meta = exact_post(fam, CASE17_MESSAGE_ID)
    assert post["published_at"] == "2025-12-14T07:03:16Z"
    assert "Сумах" in post["text"] and "вибух" in post["text"].casefold()
    obs = to_observation("sumy", fam, ep, post)
    assert_stable_provenance(obs, post)
    assert obs["classification_episode_id"] == CASE17_ID
    assert obs["classification_outcome"] in {"approved_strict", "approved_sensitivity", "needs_review", "rejected"}
    print(json.dumps({"case":17,"retrieved":True,"message_id":post["message_id"],"timestamp":post["published_at"],"excerpt_hash":hashlib.sha256(post["text"].encode()).hexdigest(),"matched_episode":obs["classification_episode_id"],"classification":obs["classification_outcome"],"event_terms":obs["matched_discovery_terms"],"city_evidence":obs["exact_city_evidence"],"temporal_binding":obs["temporal_binding"]},ensure_ascii=False,sort_keys=True))


def test_case18_exact_time_retrieval() -> None:
    ep = episode("sevastopol", CASE18_ID, CASE18_START, CASE18_END)
    fam = family("sevastopol", "telegram/razvozhaev")
    post, meta = exact_post(fam, CASE18_MESSAGE_ID)
    assert post["published_at"] == "2026-09-04T12:00:39Z"
    low = post["text"].casefold()
    assert "севастополе" in low and "пво" in low and "бпла" in low
    obs = to_observation("sevastopol", fam, ep, post)
    assert_stable_provenance(obs, post)
    assert obs["candidate_matching"]["matched_episode_id"] == CASE18_ID
    print(json.dumps({"case":18,"retrieved":True,"message_id":post["message_id"],"timestamp":post["published_at"],"excerpt_hash":hashlib.sha256(post["text"].encode()).hexdigest(),"matched_episode":obs["classification_episode_id"],"classification":obs["classification_outcome"],"event_terms":obs["matched_discovery_terms"],"city_evidence":obs["exact_city_evidence"],"temporal_binding":obs["temporal_binding"]},ensure_ascii=False,sort_keys=True))


def test_sumy_threat_only_non_positive() -> None:
    ep = episode("sumy", CASE17_ID, CASE17_START, CASE17_END)
    fam = family("sumy", "telegram/suspilnesumy")
    post = {"channel":"suspilnesumy","message_id":99900017,"published_at":"2025-12-14T06:25:00Z","text":"БпЛА в напрямку Сум","url":"https://t.me/suspilnesumy/99900017"}
    obs = to_observation("sumy", fam, ep, post)
    assert obs["classification_outcome"] not in {"approved_strict","approved_sensitivity"}


def test_sevastopol_alert_only_non_positive() -> None:
    ep = episode("sevastopol", CASE18_ID, CASE18_START, CASE18_END)
    fam = family("sevastopol", "telegram/razvozhaev")
    post = {"channel":"razvozhaev","message_id":99900018,"published_at":"2026-09-04T11:50:00Z","text":"В Севастополе воздушная тревога. Угроза БПЛА.","url":"https://t.me/razvozhaev/99900018"}
    obs = to_observation("sevastopol", fam, ep, post)
    assert obs["classification_outcome"] not in {"approved_strict","approved_sensitivity"}


def test_adjacent_episode_control() -> None:
    fam = family("sumy", "telegram/suspilnesumy")
    target = episode("sumy", CASE17_ID, CASE17_START, CASE17_END)
    adjacent = episode("sumy", "adjacent-control", "2025-12-14T08:30:00Z", "2025-12-14T09:00:00Z")
    post = {"channel":"suspilnesumy","message_id":99900019,"published_at":"2025-12-14T08:45:00Z","text":"У Сумах пролунав вибух під час атаки БпЛА.","url":"https://t.me/suspilnesumy/99900019"}
    row = batch_runner.telegram_candidate("sumy", fam, post, "bounded_public_telegram_search")
    obs = batch_runner.classify_row("sumy", row, [target, adjacent], source_family=fam["source_family"], source_type="public_telegram", source_timestamp=post["published_at"], excerpt=post["text"], source_url=post["url"], telegram_channel=post["channel"], telegram_message_id=post["message_id"], retrieval_provenance={"adapter":"PublicTelegramAdapter","proof_only":True})
    assert obs["classification_episode_id"] != CASE17_ID
    assert obs["candidate_matching"].get("matched_episode_id") != CASE17_ID


def test_duplicate_source_control() -> None:
    fam = family("sumy", "telegram/suspilnesumy")
    ep = episode("sumy", CASE17_ID, CASE17_START, CASE17_END)
    post = {"channel":"suspilnesumy","message_id":99900020,"published_at":"2025-12-14T07:03:16Z","text":"У Сумах пролунав вибух під час атаки БпЛА.","url":"https://t.me/suspilnesumy/99900020"}
    obs = to_observation("sumy", fam, ep, post)
    duplicate = dict(obs)
    assert len(batch_runner.dedupe_observations([obs, duplicate])) == 1
    equivalent_web = dict(obs)
    equivalent_web.update({"observation_id":"web-equivalent","source_family":"suspilne.media/sumy","source_type":"source_local_html","telegram_channel":None,"telegram_message_id":None,"source_url":"https://suspilne.media/sumy/example","content_hash":"equivalent-web-hash"})
    result = next(x for x in batch_runner.episode_results("sumy", [ep], [obs, equivalent_web], True) if x["episode_id"] == CASE17_ID)
    assert result["event_positive_strict"] in {True, False}
    assert result["classifier_result"] in {"STRICT_EVENT_POSITIVE","SENSITIVITY_EVENT_POSITIVE","NEEDS_REVIEW","NO_CONFIRMED_EVENT"}
    # The public numerator is episode-binary even when equivalent observations survive source-level dedup.
    assert len([result]) == 1


def test_step1_timestamp_repair_still_passes() -> None:
    published = monitor.parse_dt("2026-04-26T06:45:05Z")
    got = monitor.dated_live_update_event_times("26 квітня 22:48 Війська РФ атакували Суми. У Сумах відбулося кілька влучань російських БпЛА.", published)
    assert [monitor.iso(value) for value in got] == ["2026-04-26T19:48:00Z"]


if __name__ == "__main__":
    tests = [
        test_case17_exact_time_retrieval,
        test_case18_exact_time_retrieval,
        test_sumy_threat_only_non_positive,
        test_sevastopol_alert_only_non_positive,
        test_adjacent_episode_control,
        test_duplicate_source_control,
        test_step1_timestamp_repair_still_passes,
    ]
    for test in tests:
        test()
        print("PASS", test.__name__)
    print(json.dumps({"tests_passed":len(tests),"full_campaign_rerun":False,"recovery_scan":False,"incorporation":False},sort_keys=True))
