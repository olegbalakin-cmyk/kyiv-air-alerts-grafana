import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPLAY_PATH = ROOT / "scripts" / "replay_explosion_history.py"
SPEC = importlib.util.spec_from_file_location("historical_replay_test_module", REPLAY_PATH)
replay = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(replay)
monitor = replay.import_monitor(ROOT)


TARGET_CASES = [
    (
        "232eb0da4edf28c2d1c726ab",
        "Близько 04:30 російський ударний БпЛА атакував Ковпаківський район міста Суми.",
    ),
    (
        "6f22822eb67990654c28d3e8",
        "У ніч на 17 серпня, після 23:00, російські ударні БпЛА масовано атакували Суми.",
    ),
    (
        "71eded846a321cdc6188fed9",
        "Близько 08:00 ударні БпЛА атакували приватний сектор Сум.",
    ),
    (
        "88f59d26acd8ae4fd31c7511",
        "Близько 13:40 російський БпЛА атакував АЗС у Зарічному районі Сум.",
    ),
]


def roles(text):
    return replay.historical_review_roles("sumy", {"evidence": text}, monitor)[0]


def test_four_sumy_targets_are_direct_v2_strikes():
    for episode_id, text in TARGET_CASES:
        got = roles(text)
        assert got["exact_city_evidence"]["present"] is True, episode_id
        assert got["aerial_war_evidence"]["present"] is True, episode_id
        assert got["explosion_evidence"]["present"] is True, episode_id
        assert got["explosion_evidence"]["event_types"] == ["strike"], episode_id
        assert got["same_attack_basis"]["present"] is True, episode_id
        assert got["same_attack_basis"]["basis"] == (
            "reviewed_direct_v2_strike_same_statement_exact_city_air_context"
        ), episode_id


def test_direct_strike_reaches_current_classifier_without_second_statement():
    episode = {
        "episode_id": "ep-direct-strike",
        "alert_start": "2026-07-02T10:16:53Z",
        "alert_end": "2026-07-02T11:12:12Z",
        "alert_start_date_kyiv": "2026-07-02",
    }
    row = {
        "matched_episode_id": episode["episode_id"],
        "evidence": TARGET_CASES[-1][1],
        "source_url": "https://example.invalid/retained",
    }
    candidate = replay.candidate_from_history(
        "sumy", row, "strict_events", episode["episode_id"], monitor
    )
    decision = monitor.classify_candidate(
        candidate, "sumy", [episode], replay.manual_matching(episode["episode_id"])
    )
    assert decision["proposed_outcome"] == "approved_strict"
    assert decision["strict_explosion_evidence"]["present"] is True
    assert decision["strict_explosion_evidence"]["event_types"] == ["strike"]
    assert decision["same_attack_context"]["present"] is True


def test_prediction_threat_is_not_direct_strike():
    got = roles("Російський ударний БпЛА може атакувати Суми.")
    assert "explosion_evidence" not in got
    assert "same_attack_basis" not in got


def test_city_missing_is_not_direct_strike():
    got = roles("Близько 13:40 російський БпЛА атакував АЗС.")
    assert "exact_city_evidence" not in got
    assert "explosion_evidence" not in got
    assert "same_attack_basis" not in got


def test_region_only_attack_is_not_exact_city_strike():
    got = roles("Ударні БпЛА атакували Сумщину.")
    assert "exact_city_evidence" not in got
    assert "explosion_evidence" not in got
    assert "same_attack_basis" not in got


def test_generic_aerial_threat_is_not_event_positive():
    got = roles("Загроза атаки ударних БпЛА на Суми.")
    assert "explosion_evidence" not in got
    assert "same_attack_basis" not in got


def test_possible_ppo_activity_is_not_event_positive():
    got = roles("У Сумах можлива робота ППО через загрозу БпЛА.")
    assert "explosion_evidence" not in got
    assert "same_attack_basis" not in got


def test_missing_or_outside_temporal_binding_is_rejected_before_candidate():
    episode = {
        "episode_id": "ep1",
        "alert_start": "2026-07-02T10:16:53Z",
        "alert_end": "2026-07-02T11:12:12Z",
        "alert_start_date_kyiv": "2026-07-02",
    }
    text = TARGET_CASES[-1][1]
    missing = replay.bind_evidence_record({"evidence": text}, [episode], monitor)
    outside = replay.bind_evidence_record(
        {"evidence": text, "matched_alert_start": "2026-07-02T14:00:00Z"},
        [episode],
        monitor,
    )
    assert missing["episode_id"] is None
    assert missing["method"] == "missing_episode_binding"
    assert outside["episode_id"] is None
