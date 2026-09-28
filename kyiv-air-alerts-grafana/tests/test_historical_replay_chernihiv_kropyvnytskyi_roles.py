import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPLAY_PATH = ROOT / "scripts" / "replay_explosion_history.py"
SPEC = importlib.util.spec_from_file_location(
    "chernihiv_kropyvnytskyi_review_role_test", REPLAY_PATH
)
replay = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(replay)
monitor = replay.import_monitor(ROOT)


def roles(city, row):
    return replay.historical_review_roles(city, row, monitor)[0]


def episode(city, episode_id):
    return {
        "episode_id": episode_id,
        "city_key": city,
        "city": city,
        "alert_start": "2026-06-20T18:00:00Z",
        "alert_end": "2026-06-20T21:00:00Z",
        "alert_start_date_kyiv": "2026-06-20",
    }


def classify(city, row, bucket="strict_events", episode_id="ep-proof"):
    ep = episode(city, episode_id)
    candidate = replay.candidate_from_history(
        city,
        {**row, "matched_episode_id": episode_id},
        bucket,
        episode_id,
        monitor,
        ep,
    )
    return monitor.classify_candidate(
        candidate, city, [ep], replay.manual_matching(episode_id)
    )


def test_chernihiv_reviewed_attack_context_role_restored():
    row = {
        "evidence": (
            "О 14:31 у Чернігові пролунали вибухи під час російської атаки "
            "на об'єкти критичної інфраструктури."
        ),
        "decision": "strict: exact_city + aerial_war + time_match",
    }
    got = roles("chernihiv", row)
    assert got["exact_city_evidence"]["present"] is True
    assert got["explosion_evidence"]["present"] is True
    assert got["aerial_war_evidence"]["present"] is True
    assert got["same_attack_basis"]["present"] is True
    assert classify("chernihiv", row)["proposed_outcome"] == "approved_strict"


def test_chernihiv_reviewed_same_attack_linkage_restored():
    row = {
        "evidence": (
            "У Чернігові о 11:12 було чутно вибух; тривогу в Чернігівському "
            "районі оголосили о 10:59, ПС повідомляли про реактивний БпЛА РФ "
            "курсом на місто."
        ),
        "decision_basis": "strict: exact_city+aerial_context+matched_alert",
    }
    got = roles("chernihiv", row)
    assert got["same_attack_basis"]["present"] is True
    assert classify("chernihiv", row)["proposed_outcome"] == "approved_strict"


def test_chernihiv_reviewed_factual_role_adapter():
    row = {
        "evidence": (
            "The Chernihiv-district alert was followed by an AFU UAV warning "
            "toward Chernihiv and a reported UAV hit on an enterprise in the "
            "north of Chernihiv before the all-clear."
        ),
        "decision": "strict_exact_city_in_episode",
    }
    got = roles("chernihiv", row)
    assert got["exact_city_evidence"]["present"] is True
    assert got["explosion_evidence"]["event_types"] == ["impact"]
    assert got["aerial_war_evidence"]["present"] is True
    assert got["same_attack_basis"]["present"] is True


def test_chernihiv_reviewed_event_and_sensitivity_linkage():
    row = {
        "evidence": (
            "Увечері 29 листопада БпЛА атакував підприємство в Чернігові; "
            "contemporaneous city-council reporting falls within the earlier "
            "evening alert episode."
        ),
        "decision": "sensitivity_only",
        "basis": "inferred_same_attack",
    }
    got = roles("chernihiv", row)
    assert got["explosion_evidence"]["event_types"] == ["strike"]
    assert got["same_attack_basis"]["present"] is True
    decision = classify("chernihiv", row, bucket="sensitivity_only_events")
    assert decision["proposed_outcome"] == "approved_sensitivity"


def test_chernihiv_missing_review_contract_stays_unresolved():
    row = {
        "evidence": (
            "У Чернігові пролунав вибух під час атаки БпЛА; "
            "Повітряні сили попереджали про дрон."
        )
    }
    assert roles("chernihiv", row) == {}
    assert classify("chernihiv", row)["proposed_outcome"] == "needs_review"


def test_kropyvnytskyi_reviewed_same_attack_linkage_restored():
    row = {
        "evidence": (
            "О 01:17 у Кропивницькому пролунав вибух; перед цим Повітряні "
            "сили повідомили про дрони в напрямку міста під час тривоги."
        ),
        "basis": "exact_city_during_alert",
    }
    got = roles("kropyvnytskyi", row)
    assert got["same_attack_basis"]["present"] is True
    assert classify("kropyvnytskyi", row)["proposed_outcome"] == "approved_strict"


def test_kropyvnytskyi_reviewed_factual_role_adapter():
    row = {
        "evidence": (
            "Exact-city explosion at 15:55 during the 15:29-16:24 alert; "
            "the report places it in the context of the ongoing Russian drone attack."
        ),
        "basis": "exact_city_during_alert",
    }
    got = roles("kropyvnytskyi", row)
    assert got["exact_city_evidence"]["present"] is True
    assert got["explosion_evidence"]["event_types"] == ["explosion"]
    assert got["aerial_war_evidence"]["present"] is True
    assert got["same_attack_basis"]["present"] is True
    assert classify("kropyvnytskyi", row)["proposed_outcome"] == "approved_strict"


def test_absent_or_ambiguous_review_data_does_not_become_positive():
    controls = [
        {
            "evidence": "Exact-city explosion during an alert with a drone warning.",
        },
        {
            "evidence": "У Кіровоградській області було гучно через загрозу БпЛА.",
            "basis": "review_district_only_not_counted",
        },
        {
            "evidence": "Drone threat toward Kropyvnytskyi during the alert.",
            "basis": "exact_city_during_alert",
        },
    ]
    for row in controls:
        got = roles("kropyvnytskyi", row)
        assert not (
            (got.get("exact_city_evidence") or {}).get("present")
            and (got.get("explosion_evidence") or {}).get("present")
            and (got.get("same_attack_basis") or {}).get("present")
        ), row


def test_no_generic_text_inference_without_review_contract():
    row = {
        "evidence": (
            "Exact-city explosion in Kropyvnytskyi during a Russian drone attack."
        )
    }
    assert roles("kropyvnytskyi", row) == {}


def test_publication_timestamp_is_not_event_time():
    row = {
        "publication_time": "2026-06-20T19:30:00+03:00",
        "evidence": "Exact-city explosion during the alert.",
        "basis": "exact_city_during_alert",
    }
    assert replay.retained_event_datetimes(row, monitor) == []


def test_regional_evidence_is_not_exact_city_without_reviewed_exact_city_role():
    row = {
        "evidence": "У Кіровоградській області пролунали вибухи під час тривоги.",
        "basis": "review_district_only_not_counted",
    }
    assert roles("kropyvnytskyi", row) == {}


def test_review_row_without_event_fact_is_not_upgraded():
    row = {
        "evidence": "Drone threat toward Kropyvnytskyi during the alert.",
        "basis": "exact_city_during_alert",
    }
    got = roles("kropyvnytskyi", row)
    assert "explosion_evidence" not in got
    assert "same_attack_basis" not in got
    assert classify("kropyvnytskyi", row)["proposed_outcome"] == "needs_review"
