import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPLAY_PATH = ROOT / "scripts" / "replay_explosion_history.py"
SPEC = importlib.util.spec_from_file_location("kmo_review_role_test", REPLAY_PATH)
replay = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(replay)
monitor = replay.import_monitor(ROOT)


def roles(city, row):
    return replay.historical_review_roles(city, row, monitor)[0]


def episode(city="mykolaiv", episode_id="ep-proof"):
    return {
        "episode_id": episode_id,
        "city_key": city,
        "city": city,
        "alert_start": "2026-07-09T10:00:00Z",
        "alert_end": "2026-07-09T12:00:00Z",
        "alert_start_date_kyiv": "2026-07-09",
    }


def classify(city, row, bucket="strict_events", episode_id="ep-proof"):
    ep = episode(city, episode_id)
    candidate = replay.candidate_from_history(
        city, {**row, "matched_episode_id": episode_id}, bucket,
        episode_id, monitor, ep,
    )
    return candidate, monitor.classify_candidate(
        candidate, city, [ep], replay.manual_matching(episode_id)
    )


def test_each_reviewed_role_family_can_be_recovered():
    rows = [
        {"evidence": "Exact-city explosion in Mykolaiv during a Russian-drone alert.",
         "decision": "strict: exact time inside matched alert episode"},
        {"evidence": "У Миколаєві РФ ударила дроном по об'єкту.",
         "decision_basis": "strict: exact_city + confirmed_drone_strike + inside_matched_alert"},
        {"evidence": "О 15:21 у Херсоні повідомили про вибухи; КАБ ішов на місто.",
         "decision": "strict: exact-city explosion inside the same aerial-alert episode"},
        {"evidence": "An exact-city explosion in Mykolaiv during a Shahed attack.",
         "decision": "strict: exact time inside matched alert episode"},
        {"evidence": "У Миколаєві повідомили про вибух під час російської атаки.",
         "basis": "near_boundary"},
    ]
    for city, row in zip(
        ["mykolaiv", "mykolaiv", "kherson", "mykolaiv", "mykolaiv"], rows
    ):
        got = roles(city, row)
        assert got["exact_city_evidence"]["present"] is True
        assert got["explosion_evidence"]["present"] is True
        assert got["aerial_war_evidence"]["present"] is True
        assert got["same_attack_basis"]["present"] is True


def test_strict_review_contract_recovers_strict():
    _, decision = classify(
        "mykolaiv",
        {
            "evidence": "Suspilne reports an exact-city explosion at 13:59 during the drone alert.",
            "decision": "strict: exact time inside matched alert episode",
        },
    )
    assert decision["proposed_outcome"] == "approved_strict"


def test_sensitivity_review_contract_stays_sensitivity_without_synthetic_minute():
    row = {
        "evidence": (
            "Exact-city explosion is linked to a reactive-drone threat, "
            "but the event time is not stated."
        ),
        "decision": "sensitivity: inferred_same_attack",
    }
    candidate, decision = classify("mykolaiv", row, "sensitivity_only_events")
    assert decision["proposed_outcome"] == "approved_sensitivity"
    provenance = candidate["review_provenance"]
    assert "temporal" not in provenance
    assert provenance["sensitivity_binding"]["basis"] == "inferred_same_attack"


def test_sole_evidence_insufficient_case_does_not_gain_exact_city_role():
    row = {
        "evidence": (
            "Суспільне підтверджує другу ранкову тривогу о 08:04 та друге "
            "збиття під час ранкової Shahed-атаки, але не дає окремої хвилини "
            "вибуху для цього episode."
        ),
        "decision_basis": (
            "sensitivity_only: strong_inferred_same_attack; "
            "exact explosion time not published"
        ),
    }
    got = roles("mykolaiv", row)
    assert "exact_city_evidence" not in got
    assert "same_attack_basis" not in got
    _, decision = classify(
        "mykolaiv", row, "sensitivity_only_events",
        "05992c5cdaa538ec9552236b",
    )
    assert decision["proposed_outcome"] == "needs_review"


def test_negative_role_controls_do_not_invent_missing_roles():
    no_exact = roles(
        "mykolaiv",
        {
            "evidence": "У Миколаївській області повідомили про вибух під час атаки дронів.",
            "basis": "inferred_same_attack",
        },
    )
    assert "exact_city_evidence" not in no_exact

    no_fact = roles(
        "mykolaiv",
        {
            "evidence": "Exact-city warning: possible explosion during a drone threat.",
            "basis": "sensitivity: inferred_same_attack",
        },
    )
    assert "explosion_evidence" not in no_fact

    no_link = roles(
        "mykolaiv",
        {
            "evidence": "Exact-city explosion in Mykolaiv during a drone attack.",
            "basis": "exact_city",
        },
    )
    assert "same_attack_basis" not in no_link

    no_context = roles(
        "mykolaiv",
        {
            "evidence": "Exact-city explosion in Mykolaiv.",
            "basis": "exact_city",
        },
    )
    assert "aerial_war_evidence" not in no_context


def test_five_ppo_structural_examples_keep_actual_action_semantics():
    cases = [
        ("mykolaiv", "The report links exact-city explosions and air-defense activity to UAVs heading toward Mykolaiv after the 13:56 alert.",
         "strict: exact-city explosions explicitly within alert attack sequence", "strict_events"),
        ("mykolaiv", "Exact-city explosions and air-defense activity were reported as UAVs approached Mykolaiv, but no event time is stated.",
         "sensitivity: inferred_same_attack", "sensitivity_only_events"),
        ("mykolaiv", "Об 11:46 у Миколаєві було чути вибухи; тривога тривала, над містом були дрони та працювала ППО.",
         "strict: exact-city time inside matched alert", "strict_events"),
        ("odesa", "Під час тривоги 00:20–00:49 група Shahed атакувала Одесу з моря; у місті було чутно ППО та вибухи.",
         "strict: source explicitly places exact-city explosions during matched UAV alert", "strict_events"),
        ("odesa", "Під час тривоги в Одесі тривала атака дронів; очевидці описали вибухи в місті, а близько 11:55 кореспонденти чули дрон і роботу ППО.",
         "exact_city_during_alert", "strict_events"),
    ]
    outcomes = []
    ppo_types = []
    for city, evidence, basis, bucket in cases:
        row = {"evidence": evidence, "basis": basis}
        got = roles(city, row)
        outcomes.append(classify(city, row, bucket)[1]["proposed_outcome"])
        ppo_types.append("air_defense_action" in got["explosion_evidence"]["event_types"])
    assert outcomes == [
        "approved_strict", "approved_sensitivity", "approved_strict",
        "approved_strict", "approved_strict",
    ]
    assert any(ppo_types)


def test_ppo_warning_readiness_and_possibility_do_not_become_action():
    for phrase in (
        "можлива робота ППО",
        "очікується робота ППО",
        "попереджають про роботу ППО",
        "ППО готова до роботи",
    ):
        got = roles(
            "mykolaiv",
            {
                "evidence": f"У Миколаєві {phrase}; загроза БпЛА.",
                "basis": "exact_city; matched_alert",
            },
        )
        event_types = got.get("explosion_evidence", {}).get("event_types", [])
        assert "air_defense_action" not in event_types


def test_retired_rows_are_not_in_counted_positive_buckets():
    expected = {
        "kherson": {
            "8237340ab735032f39db197c", "aea1ffbdace229409cec0c16",
            "e7b33cc9d7a37efc3ad2a51c", "283fdd8775dd3f46a54c2e2c",
            "8e7ef06ae0a9fa2e019fb17d", "8aa162150ee5a23c622c8532",
            "79fa40f617d42897a5dbba14",
        },
        "odesa": {
            "c9170f2906d0e18731a81fa2", "503a0c99d1b5f9fe9c447c0e",
            "0c2c1c3a0cbbbea7b7d2ccde",
        },
    }
    for city, retired in expected.items():
        data = json.loads(
            (ROOT / "data" / "explosion_research" / city / "final_evidence.json").read_text()
        )
        counted = {
            str(row.get("record_id") or "")
            for bucket in ("strict_events", "sensitivity_only_events")
            for row in data.get(bucket, [])
        }
        assert retired.isdisjoint(counted)
        assert set(data["normalization_provenance"]["retired_record_ids"]) == retired


def test_three_repaired_mykolaiv_targets_remain_counted_and_bound():
    target_ids = {
        "63ec7dd62617f94945546a5b",
        "7e7ada38d112e78babb90844",
        "90e3489c770ee84f88d5c4cf",
    }
    data = json.loads(
        (ROOT / "data" / "explosion_research" / "mykolaiv" / "final_evidence.json").read_text()
    )
    found = {}
    for row in data["strict_events"]:
        eid = row.get("matched_episode_id")
        if eid in target_ids:
            found[eid] = row
    assert set(found) == target_ids
    assert all(row["normalization_provenance"]["current_counted"] is True for row in found.values())


def test_adapter_is_city_gated():
    row = {
        "evidence": "Exact-city explosion during a Russian-drone alert.",
        "decision": "strict: exact time inside matched alert episode",
    }
    assert roles("kyiv", row) == {}
    dnipro = roles("dnipro", row)
    assert "exact_city_evidence" not in dnipro
    assert "same_attack_basis" not in dnipro
