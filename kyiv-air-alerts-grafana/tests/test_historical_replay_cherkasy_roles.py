import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPLAY_PATH = ROOT / "scripts" / "replay_explosion_history.py"
SPEC = importlib.util.spec_from_file_location("cherkasy_systematic_rule_gap_test", REPLAY_PATH)
replay = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(replay)
monitor = replay.import_monitor(ROOT)


def roles(row):
    return replay.historical_review_roles("cherkasy", row, monitor)[0]


def classify(row, episode_id="ep-cherkasy"):
    episode = {
        "episode_id": episode_id,
        "city_key": "cherkasy",
        "city": "Черкаси",
        "alert_start": "2026-09-03T14:00:00Z",
        "alert_end": "2026-09-03T20:00:00Z",
        "alert_start_date_kyiv": "2026-09-03",
    }
    candidate = replay.candidate_from_history(
        "cherkasy", {**row, "matched_episode_id": episode_id}, "strict_events", episode_id, monitor
    )
    return monitor.classify_candidate(
        candidate, "cherkasy", [episode], replay.manual_matching(episode_id)
    )


def test_reviewed_role_persistence_positive():
    row = {
        "evidence": "Suspilne reported explosions heard in Cherkasy during the air alert on the night of 17 December, in a Russian drone attack context.",
        "decision": "strict: exact_city + aerial_war + explicit_during_alert",
    }
    got = roles(row)
    assert got["exact_city_evidence"]["present"] is True
    assert got["explosion_evidence"]["present"] is True
    assert got["aerial_war_evidence"]["present"] is True
    assert got["same_attack_basis"]["present"] is True


def test_reviewed_role_absence_negative():
    row = {"evidence": "Suspilne reported explosions heard in Cherkasy during the air alert on the night of 17 December, in a Russian drone attack context."}
    assert roles(row) == {}


def test_reviewed_cross_segment_same_attack_positive():
    positives = [
        {"evidence": "О 18:28 у Черкасах було чутно вибух під час російської атаки; Повітряні сили повідомляли про БпЛА курсом на Черкаси.", "basis": "exact_city_time_inside_alert"},
        {"evidence": "О 09:08 вибухи чули у Черкасах та на околицях; перед цим Повітряні сили попереджали про БпЛА в напрямку міста.", "basis": "exact_city_timed_inside_alert"},
        {"evidence": "Близько 03:15 у Черкасах було чутно вибухи; армія РФ атакувала балістичними ракетами.", "basis": "exact_city_timed_inside_alert"},
        {"evidence": "Близько 03:15 у Черкасах пролунали вибухи; місто атакували дрони.", "basis": "exact_city_timed_inside_alert"},
    ]
    for row in positives:
        got = roles(row)
        assert got["same_attack_basis"]["present"] is True, row
        assert got["same_attack_basis"]["basis"] == "reviewed_cherkasy_explicit_cross_segment_same_attack", row


def test_article_cooccurrence_without_relation_is_negative():
    row = {
        "evidence": "О 10:00 у Черкасах було чутно вибухи; Повітряні сили окремо повідомили про БпЛА над областю.",
        "basis": "exact_city_timed_inside_alert",
    }
    assert "same_attack_basis" not in roles(row)


def test_multi_incident_controls_stay_unlinked():
    controls = [
        {"episode_id": "58624e812ef70a85166d09c6", "evidence": "О 21:24 у Черкасах було чутно вибухи; о 21:11 Повітряні сили повідомляли про БпЛА на Черкаси зі сходу.", "basis": "exact_city_timed_inside_alert"},
        {"episode_id": "7dc902b97fda7ea1d146c907", "evidence": "О 09:20 у Черкасах було чутно вибух під час атаки РФ; на Черкащині знешкодили ракету та 11 БпЛА.", "basis": "exact_city_time_inside_alert"},
    ]
    for row in controls:
        assert "same_attack_basis" not in roles(row), row["episode_id"]
        assert classify(row, row["episode_id"])["proposed_outcome"] == "needs_review", row["episode_id"]


def test_cherkasy_genitive_positive_and_reviewed_relation():
    text = "Близько 23:55 жителі Черкас чули вибухи; у місті та на околицях працювала ППО під час загрози ударних БпЛА."
    row = {"evidence": text, "decision": "strict — exact-city aerial-war evidence and event time inside matched alert episode"}
    exact = monitor.exact_city_classification_evidence("cherkasy", {"title": text, "snippet": "", "publisher": "24 Канал"})
    assert exact["present"] is True
    assert roles(row)["same_attack_basis"]["present"] is True
    assert classify(row)["proposed_outcome"] == "approved_strict"


def test_cherkasy_genitive_regional_branding_and_origin_negatives():
    controls = [
        {"title": "На Черкащині оголосили тривогу, було гучно", "snippet": "", "publisher": ""},
        {"title": "У Черкаській області пролунали вибухи", "snippet": "", "publisher": ""},
        {"title": "В області було гучно - Новини Черкас", "snippet": "", "publisher": "Новини Черкас"},
        {"title": "Житель Черкас розповів, що у Києві пролунав вибух під час атаки БпЛА", "snippet": "", "publisher": ""},
    ]
    for row in controls:
        assert not monitor.exact_city_classification_evidence("cherkasy", row)["present"], row


def test_retained_evidence_gap_is_not_invented():
    controls = [
        {"evidence": "Суспільне описує наслідки нічної атаки БпЛА в Черкасах; власник за відеонаглядом датував подію 02:12 і свідок чув вибух.", "decision_basis": "strict: exact_city + aerial_attack + event_time_inside_episode"},
        {"evidence": "Факти ICTV повідомили, що орієнтовно о 06:09 в обласному центрі було гучно через ліквідацію крилатих ракет під час ракетно-дронової атаки.", "decision_basis": "strict: exact_city + aerial_attack + event_time_inside_episode"},
    ]
    for row in controls:
        assert roles(row) == {}, row
        assert classify(row)["proposed_outcome"] == "needs_review", row
