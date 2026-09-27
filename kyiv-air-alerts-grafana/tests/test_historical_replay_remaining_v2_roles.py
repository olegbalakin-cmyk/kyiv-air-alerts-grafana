import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPLAY_PATH = ROOT / "scripts" / "replay_explosion_history.py"
SPEC = importlib.util.spec_from_file_location("historical_replay_remaining_v2_test", REPLAY_PATH)
replay = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(replay)
monitor = replay.import_monitor(ROOT)


TARGETS = {
    "2b3df2af5d1a6eb3a0a5b5e6": (
        "Близько 17:00 у Сумах був вибух; у Зарічному районі підтверджені "
        "два російські удари менш ніж за пів години."
    ),
    "57813e54f364c6ea1c31b79d": (
        "Уночі РФ атакувала у Сумах підприємство харчової промисловості, "
        "АЗС, СТО та вантажівку."
    ),
    "b350026329e2fb7dee324d0b": (
        "Жителі Сум повідомили про початок російської атаки близько 01:00 "
        "та три вибухи."
    ),
    "bc17e3913b1f9a7b78cf8af7": (
        "Близько 14:10 у середмісті Сум зафіксовано влучання; найближчий "
        "наступний frozen alert почався о 14:16."
    ),
    "d4ca36a6f8fdb93684f7b2c2": (
        "У Сумах близько 18:00 російський дрон упав біля дитячого майданчика."
    ),
}


def roles(text):
    return replay.historical_review_roles("sumy", {"evidence": text}, monitor)[0]


def assert_direct_event(text, event_type, basis):
    got = roles(text)
    assert got["exact_city_evidence"]["present"] is True
    assert got["explosion_evidence"]["present"] is True
    assert got["explosion_evidence"]["event_types"] == [event_type]
    assert got["aerial_war_evidence"]["present"] is True
    assert got["same_attack_basis"]["present"] is True
    assert got["same_attack_basis"]["basis"] == basis


def test_three_remaining_adversary_attack_wordings_are_v2_strikes():
    basis = "reviewed_direct_v2_strike_same_statement_exact_city_air_context"
    for episode_id in (
        "2b3df2af5d1a6eb3a0a5b5e6",
        "57813e54f364c6ea1c31b79d",
        "b350026329e2fb7dee324d0b",
    ):
        assert_direct_event(TARGETS[episode_id], "strike", basis)


def test_factual_impact_noun_is_v2_impact():
    assert_direct_event(
        TARGETS["bc17e3913b1f9a7b78cf8af7"],
        "impact",
        "reviewed_direct_v2_impact_noun_exact_city",
    )


def test_enemy_uav_physical_fall_is_v2_impact():
    assert_direct_event(
        TARGETS["d4ca36a6f8fdb93684f7b2c2"],
        "impact",
        "reviewed_enemy_uav_physical_fall_exact_city",
    )


def test_direct_impact_respects_existing_near_boundary_sensitivity_binding():
    episode = {
        "episode_id": "ep-impact",
        "alert_start": "2026-02-17T12:16:42Z",
        "alert_end": "2026-02-17T16:26:28Z",
        "alert_start_date_kyiv": "2026-02-17",
    }
    row = {
        "matched_episode_id": episode["episode_id"],
        "evidence": TARGETS["bc17e3913b1f9a7b78cf8af7"],
        "basis": "near_boundary",
        "source_url": "https://example.invalid/retained-impact",
    }
    candidate = replay.candidate_from_history(
        "sumy", row, "sensitivity_only_events", episode["episode_id"], monitor
    )
    decision = monitor.classify_candidate(
        candidate, "sumy", [episode], replay.manual_matching(episode["episode_id"])
    )
    assert decision["proposed_outcome"] == "approved_sensitivity"
    assert decision["sensitivity_basis"] == "near_boundary"
    assert decision["strict_explosion_evidence"]["event_types"] == ["impact"]


def test_enemy_uav_fall_reaches_strict_classifier_with_existing_binding():
    episode = {
        "episode_id": "ep-uav-fall",
        "alert_start": "2026-08-22T12:16:51Z",
        "alert_end": "2026-08-22T16:09:13Z",
        "alert_start_date_kyiv": "2026-08-22",
    }
    row = {
        "matched_episode_id": episode["episode_id"],
        "evidence": TARGETS["d4ca36a6f8fdb93684f7b2c2"],
        "source_url": "https://example.invalid/retained-uav-fall",
    }
    candidate = replay.candidate_from_history(
        "sumy", row, "strict_events", episode["episode_id"], monitor
    )
    decision = monitor.classify_candidate(
        candidate, "sumy", [episode], replay.manual_matching(episode["episode_id"])
    )
    assert decision["proposed_outcome"] == "approved_strict"
    assert decision["strict_explosion_evidence"]["event_types"] == ["impact"]


def test_future_possible_threat_and_generic_warning_are_not_direct_events():
    controls = [
        "РФ атакуватиме Суми завтра.",
        "РФ може атакувати Суми.",
        "Загроза російської атаки у Сумах.",
        "У Сумах повітряна тривога через загрозу БпЛА.",
    ]
    for text in controls:
        got = roles(text)
        assert "same_attack_basis" not in got
        assert not (
            (got.get("explosion_evidence") or {}).get("event_types") in (["strike"], ["impact"])
        )


def test_other_locality_and_oblast_only_are_not_direct_events():
    controls = [
        "У Сумах оголосили тривогу; РФ атакувала Харків.",
        "РФ атакувала Сумську область.",
        "У Сумах тривога; у Харкові зафіксовано влучання.",
    ]
    for text in controls:
        got = roles(text)
        assert "same_attack_basis" not in got


def test_negated_historical_nonmilitary_and_figurative_wording_are_not_promoted():
    controls = [
        "РФ не атакувала Суми; ударів не було.",
        "У Сумах влучання не зафіксовано.",
        "Торік РФ атакувала Суми.",
        "У Сумах зафіксували тепловий удар у спортсмена.",
        "У Сумах на турнірі зафіксовано влучання у десятку.",
    ]
    for text in controls:
        got = roles(text)
        assert "same_attack_basis" not in got


def test_generic_fall_and_signal_loss_are_not_enemy_uav_impacts():
    controls = [
        "У Сумах рекламний дрон упав біля сцени.",
        "У Сумах ворожий дрон втратив сигнал.",
        "У Сумах ворожий дрон може впасти біля майданчика.",
    ]
    for text in controls:
        got = roles(text)
        assert not (
            (got.get("explosion_evidence") or {}).get("event_types") == ["impact"]
            and (got.get("same_attack_basis") or {}).get("basis")
            == "reviewed_enemy_uav_physical_fall_exact_city"
        )


def test_missing_temporal_binding_is_rejected_before_candidate():
    episode = {
        "episode_id": "ep1",
        "alert_start": "2026-07-25T12:47:22Z",
        "alert_end": "2026-07-26T13:08:13Z",
        "alert_start_date_kyiv": "2026-07-25",
    }
    for text in (
        TARGETS["57813e54f364c6ea1c31b79d"],
        TARGETS["bc17e3913b1f9a7b78cf8af7"],
        TARGETS["d4ca36a6f8fdb93684f7b2c2"],
    ):
        binding = replay.bind_evidence_record({"evidence": text}, [episode], monitor)
        assert binding["episode_id"] is None
        assert binding["method"] == "missing_episode_binding"
