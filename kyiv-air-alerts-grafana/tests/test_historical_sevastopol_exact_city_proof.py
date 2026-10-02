from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKOUT_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / "scripts"))

import monitor_explosion_candidates as monitor
import run_historical_attack_event_backfill_batch as batch_runner


CASE18_ID = "6069b17ec096cae0912ad9bd"
CASE18_START = "2026-09-04T11:48:14Z"
CASE18_END = "2026-09-04T12:13:20Z"
CASE18_MESSAGE_ID = 23590
CASE18_TIMESTAMP = "2026-09-04T12:00:47Z"
CASE18_TEXT = (
    "В Севастополе военные отражают атаку ВСУ, работает ПВО и мобильные огневые группы. "
    "Уже сбит 1 БПЛА над акваторией в районе Парка Победы. "
    "Не пренебрегайте мерами безопасности! ⚡️ ⚡️ ⚡️ ⚡️ "
    "Покиньте открытые пространства и оставайтесь в безопасных местах. "
    "Наши военные ведут работу по уничтожению вражеских БПЛА из различных средств поражения, "
    "в том числе и из стрелкового оружия. Берегите себя!"
)
REGISTRY = CHECKOUT_ROOT / "research" / "historical_attack_event_source_registry.json"


def episode() -> dict:
    return {
        "episode_id": CASE18_ID,
        "city_key": "sevastopol",
        "city": monitor.CITY_CONFIG["sevastopol"]["label"],
        "alert_start": CASE18_START,
        "alert_end": CASE18_END,
    }


def source_family() -> dict:
    doc = json.loads(REGISTRY.read_text(encoding="utf-8"))
    return next(
        row
        for row in doc["cities"]["sevastopol"]["source_families"]
        if row["source_family"] == "telegram/razvozhaev"
    )


def case18_post() -> dict:
    return {
        "channel": "razvozhaev",
        "message_id": CASE18_MESSAGE_ID,
        "published_at": CASE18_TIMESTAMP,
        "text": CASE18_TEXT,
        "url": "https://t.me/razvozhaev/23590",
    }


def replay_case18() -> dict:
    ep = episode()
    fam = source_family()
    post = case18_post()
    row = batch_runner.telegram_candidate(
        "sevastopol", fam, post, "bounded_public_telegram_search"
    )
    obs = batch_runner.classify_row(
        "sevastopol",
        row,
        [ep],
        source_family=fam["source_family"],
        source_type="public_telegram",
        source_timestamp=post["published_at"],
        excerpt=post["text"],
        source_url=post["url"],
        telegram_channel=post["channel"],
        telegram_message_id=post["message_id"],
        retrieval_provenance={
            "adapter": "PublicTelegramAdapter",
            "proof_only": True,
            "replayed_from_accepted_step2_observation": True,
        },
    )
    target = next(
        row
        for row in batch_runner.episode_results("sevastopol", [ep], [obs], True)
        if row["episode_id"] == CASE18_ID
    )
    return {
        "exact_city_evidence": obs["exact_city_evidence"],
        "candidate_matching": obs["candidate_matching"],
        "temporal_binding": obs["temporal_binding"],
        "matched_episode": obs["classification_episode_id"],
        "air_defense_context": obs["air_defense_context"],
        "air_defense_action": obs["air_defense_action"],
        "interception_claim": obs["interception_claim"],
        "classifier_reason_codes": obs["classifier_reason_codes"],
        "classification_outcome": obs["classification_outcome"],
        "target_level_outcome": target["classifier_result"],
        "event_positive_strict": target["event_positive_strict"],
        "confirmed_event_types": target["confirmed_event_types"],
    }


def test_base_form() -> None:
    assert monitor.city_mentioned("sevastopol", "Севастополь")


def test_ukrainian_locative() -> None:
    assert monitor.city_mentioned("sevastopol", "у Севастополі")


def test_russian_locative() -> None:
    assert monitor.city_mentioned("sevastopol", "в Севастополе")


def test_false_positive_fragment_guard() -> None:
    assert not monitor.city_mentioned(
        "sevastopol",
        "У тексті трапився не-топонімічний токен севастопольськиймаркер.",
    )


def test_wrong_city_guard() -> None:
    ep = episode()
    row = {
        "source": "Telegram / control",
        "publisher": "control",
        "title": "В Ялте военные отражают атаку, работает ПВО.",
        "snippet": "Сбит БПЛА над акваторией.",
        "url": "https://example.invalid/wrong-city",
        "published_at": CASE18_TIMESTAMP,
        "discovery_basis": "bounded_public_telegram_search",
        "city_key": "sevastopol",
    }
    decision = monitor.classify_candidate(row, "sevastopol", [ep])
    assert decision["exact_city_classification_evidence"]["present"] is False
    assert decision["proposed_outcome"] not in {"approved_strict", "approved_sensitivity"}


def test_case18_exact_replay() -> None:
    result = replay_case18()
    print(json.dumps({"case18_after": result}, ensure_ascii=False, sort_keys=True))
    assert result["candidate_matching"]["outcome"] == "unique_match"
    assert result["candidate_matching"]["matched_episode_id"] == CASE18_ID
    assert result["exact_city_evidence"]["present"] is True
    assert result["air_defense_context"] is True
    assert result["air_defense_action"] is True
    assert result["interception_claim"] is True


if __name__ == "__main__":
    tests = [
        test_base_form,
        test_ukrainian_locative,
        test_russian_locative,
        test_case18_exact_replay,
        test_false_positive_fragment_guard,
        test_wrong_city_guard,
    ]
    for test in tests:
        test()
        print("PASS", test.__name__)

    print(
        json.dumps(
            {
                "tests_passed": len(tests),
                "case18": replay_case18(),
                "full_campaign_rerun": False,
                "recovery_scan": False,
                "incorporation": False,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
