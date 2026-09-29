import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPLAY_PATH = ROOT / "scripts" / "replay_explosion_history.py"
SPEC = importlib.util.spec_from_file_location("historical_replay_dnipro_roles_test", REPLAY_PATH)
replay = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(replay)
monitor = replay.import_monitor(ROOT)


def row(evidence, *, basis="exact_city; confirmed_air_war; timed_inside_alert", decision="strict", event_time="2026-01-01 12:10"):
    out = {
        "evidence": evidence,
        "basis": basis,
        "decision": decision,
        "alert_episode_start": "2026-01-01 12:00",
        "source_url": "https://example.test/dnipro",
    }
    if event_time is not None:
        out["event_time"] = event_time
    return out


def roles(item):
    return replay.historical_review_roles("dnipro", item, monitor)[0]


def episode():
    return {
        "episode_id": "dnipro-target",
        "city_key": "dnipro",
        "city": "Дніпро",
        "alert_start": "2026-01-01T10:00:00Z",
        "alert_end": "2026-01-01T11:00:00Z",
        "alert_start_date_kyiv": "2026-01-01",
    }


def classify(item, bucket="strict_events"):
    ep = episode()
    candidate = replay.candidate_from_history(
        "dnipro", item, bucket, ep["episode_id"], monitor, ep
    )
    decision = monitor.classify_candidate(
        candidate, "dnipro", [ep], replay.manual_matching(ep["episode_id"])
    )
    return candidate, decision


def test_reviewed_fact_role_requires_actual_event_fact():
    good = roles(row("У Дніпрі під час атаки БпЛА пролунали вибухи."))
    assert good["explosion_evidence"]["present"] is True
    bad = roles(row("У Дніпрі оголосили загрозу БпЛА; можливі вибухи."))
    assert "explosion_evidence" not in bad


def test_exact_city_role_comes_from_review_contract_not_oblast_name():
    exact = roles(row("Під час атаки БпЛА пролунали вибухи.", basis="exact_city; confirmed_air_war; timed_inside_alert"))
    assert exact["exact_city_evidence"]["present"] is True
    oblast = roles(row("У Дніпропетровській області під час атаки БпЛА пролунали вибухи.", basis="confirmed_air_war; timed_inside_alert"))
    assert "exact_city_evidence" not in oblast


def test_same_attack_requires_retained_reviewed_episode_relation():
    linked = roles(row("У Дніпрі під час атаки БпЛА пролунали вибухи."))
    assert linked["same_attack_basis"]["present"] is True
    proximity_only = roles(row("У Дніпрі під час атаки БпЛА пролунали вибухи.", basis="exact_city; confirmed_air_war"))
    assert "same_attack_basis" not in proximity_only


def test_attack_context_requires_explicit_reviewed_air_context_not_generic_alert():
    explicit = roles(row("У Дніпрі пролунали вибухи.", basis="exact_city; confirmed_air_war; timed_inside_alert"))
    assert explicit["aerial_war_evidence"]["present"] is True
    generic = roles(row("У Дніпрі пролунали вибухи під час тривоги.", basis="strict_exact_city_event_inside_episode"))
    assert "aerial_war_evidence" not in generic
    assert "same_attack_basis" not in generic


def test_reviewed_loud_fact_is_gated_by_exact_city_air_and_episode_contract():
    good = roles(row("У Дніпрі було гучно на тлі атаки БпЛА."))
    assert good["explosion_evidence"]["event_types"] == ["explosion"]
    bad = roles(row("У Дніпрі було гучно.", basis="exact_city; timed_inside_alert"))
    assert "explosion_evidence" not in bad


def test_sensitivity_inferred_same_attack_stays_sensitivity_without_exact_minute():
    item = row(
        "У Дніпрі чули вибухи на тлі ракетної атаки.",
        basis="strong inferred_same_attack: exact-city hearing + missile context, but only broad overnight timing",
        decision="sensitivity_only",
        event_time=None,
    )
    candidate, decision = classify(item, "sensitivity_only_events")
    assert decision["proposed_outcome"] == "approved_sensitivity"
    assert decision["proposed_outcome"] != "approved_strict"
    assert "temporal" not in candidate["review_provenance"]
    assert candidate["review_provenance"]["sensitivity_binding"]["basis"] == "inferred_same_attack"


def test_actual_confirmed_air_defense_action_may_be_retained():
    r = roles(row("У Дніпрі під час атаки БпЛА працювала ППО та збила ворожий дрон."))
    assert "air_defense_action" in r["explosion_evidence"]["event_types"]


def test_preliminary_pvo_is_not_promoted_to_air_defense_action():
    r = roles(row("У Дніпрі пролунав вибух під час атаки БпЛА; попередньо, могла працювати ППО."))
    assert r["explosion_evidence"]["present"] is True
    assert "air_defense_action" not in r["explosion_evidence"]["event_types"]


def test_city_name_alone_does_not_create_roles():
    r = roles(row("Дніпро.", basis="", decision=""))
    assert r == {}


def test_publication_metadata_does_not_create_roles():
    item = row("У Дніпрі оголосили повітряну тривогу.", basis="", decision="")
    item["published_at"] = "2026-01-01T10:05:00Z"
    assert roles(item) == {}
