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
    ]
    for row in controls:
        assert "same_attack_basis" not in roles(row), row["episode_id"]
        assert classify(row, row["episode_id"])["proposed_outcome"] == "needs_review", row["episode_id"]


def test_explicit_during_attack_event_links_adjacent_aerial_context():
    row = {
        "evidence": (
            "О 09:20 у Черкасах було чутно вибух під час атаки РФ; "
            "на Черкащині знешкодили ракету та 11 БпЛА."
        ),
        "basis": "exact_city_time_inside_alert",
    }
    got = roles(row)
    assert got["same_attack_basis"]["present"] is True
    assert got["same_attack_basis"]["basis"] == (
        "reviewed_cherkasy_explicit_cross_segment_same_attack"
    )
    assert classify(row)["proposed_outcome"] == "approved_strict"


def test_explicit_during_attack_does_not_borrow_other_city_context():
    row = {
        "evidence": (
            "О 09:20 у Черкасах було чутно вибух під час атаки РФ; "
            "у Києві ППО знешкодила ударний БпЛА."
        ),
        "basis": "exact_city_time_inside_alert",
    }
    assert "same_attack_basis" not in roles(row)


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


def classify_sensitivity(row, episode):
    candidate = replay.candidate_from_history(
        "cherkasy",
        {**row, "matched_episode_id": episode["episode_id"]},
        "sensitivity_only_events",
        episode["episode_id"],
        monitor,
    )
    return monitor.classify_candidate(
        candidate,
        "cherkasy",
        [episode],
        replay.manual_matching(episode["episode_id"]),
    )


def test_confirmed_exact_city_air_defense_clock_can_supply_reviewed_strict_time():
    cases = [
        (
            {
                "episode_id": "ep-ppo-cross-midnight",
                "alert_start": "2025-02-13T20:28:36Z",
                "alert_end": "2025-02-14T00:22:00Z",
                "alert_start_date_kyiv": "2025-02-13",
            },
            {
                "event_time_kyiv": "2025-02-14 ~01:42",
                "publication_time": "2025-02-14T01:47:00+02:00",
                "evidence": (
                    "О 01:43 під час атаки Shahed у Черкасах Суспільне "
                    "повідомило про фактичну роботу ППО."
                ),
                "decision_basis": "sensitivity: near_boundary",
            },
        ),
        (
            {
                "episode_id": "ep-ppo-daytime",
                "alert_start": "2026-03-24T09:17:43Z",
                "alert_end": "2026-03-24T15:53:27Z",
                "alert_start_date_kyiv": "2026-03-24",
            },
            {
                "event_time_kyiv": "2026-03-24 14:46 and 15:31",
                "evidence": (
                    "О 14:46 у Черкасах кореспонденти Суспільного повідомили "
                    "про фактичну роботу ППО під час атаки ударних БпЛА; "
                    "повторно роботу ППО у Черкасах було чутно о 15:31."
                ),
                "decision": "sensitivity_only: inferred_same_attack",
            },
        ),
    ]
    for episode, row in cases:
        decision = classify_sensitivity(row, episode)
        assert decision["proposed_outcome"] == "approved_strict", (episode, decision)
        assert decision["temporal_binding"]["present"] is True
        assert decision["temporal_binding"]["episode_specific"] is True
        assert decision["temporal_binding"]["episode_id"] == episode["episode_id"]
        assert "air_defense_action" in decision["event_types"]


def test_possible_air_defense_clock_is_not_promoted():
    episode = {
        "episode_id": "ep-possible-ppo",
        "alert_start": "2026-03-24T09:17:43Z",
        "alert_end": "2026-03-24T15:53:27Z",
        "alert_start_date_kyiv": "2026-03-24",
    }
    row = {
        "event_time_kyiv": "2026-03-24 14:46",
        "evidence": "О 14:46 у Черкасах можлива робота ППО через загрозу БпЛА.",
        "decision": "sensitivity_only: inferred_same_attack",
    }
    decision = classify_sensitivity(row, episode)
    assert decision["proposed_outcome"] != "approved_strict"
    assert decision["strict_explosion_evidence"]["present"] is False


def test_untimed_exact_city_explosion_remains_sensitivity_only():
    episode = {
        "episode_id": "ep-untimed-explosion",
        "alert_start": "2026-07-01T19:16:29Z",
        "alert_end": "2026-07-02T01:59:03Z",
        "alert_start_date_kyiv": "2026-07-01",
    }
    row = {
        "matched_episode_start": "2026-07-01T22:16:29+03:00",
        "evidence": (
            "У Черкасах у ніч на 2 липня було чутно вибух під час тієї самої "
            "російської ракетно-дронової атаки. Точного часу міської події немає."
        ),
        "basis": "inferred_same_attack",
    }
    decision = classify_sensitivity(row, episode)
    assert decision["proposed_outcome"] == "approved_sensitivity"
    assert decision["temporal_binding"]["present"] is False


def _strict_upgrade_fixture(target_id="ep-upgrade"):
    row = {
        "episode_id": target_id,
        "category": "SENSITIVITY_TO_STRICT",
        "candidate_contributor_ids": ["candidate-upgrade"],
    }
    decisions = {
        "candidate-upgrade": {
            "proposed_outcome": "approved_strict",
            "proposed_matched_episode_id": target_id,
            "reason_codes": [
                "MATCH_UNIQUE",
                "EXACT_CITY_EVENT_TEXT",
                "STRICT_EXPLOSION_EVIDENCE",
                "AIR_MILITARY_CONTEXT",
                "SAME_ATTACK_CONTEXT_SUPPORTED",
                "TEMPORAL_EXPLICIT_ALERT_RELATION",
                "REVIEW_PROVENANCE_USABLE",
            ],
            "temporal_binding": {
                "present": True,
                "episode_specific": True,
                "episode_id": target_id,
            },
            "provenance_basis": {
                "present": True,
                "usable": True,
                "target_episode_id": target_id,
            },
        }
    }
    return row, decisions


def test_generic_evidence_backed_sensitivity_to_strict_upgrade_is_not_qa():
    row, decisions = _strict_upgrade_fixture()
    assert replay.evidence_backed_sensitivity_to_strict_upgrade(row, decisions) is True


def test_unsafe_or_unexplained_sensitivity_to_strict_transition_stays_qa():
    row, decisions = _strict_upgrade_fixture()
    decisions["candidate-upgrade"]["provenance_basis"]["usable"] = False
    assert replay.evidence_backed_sensitivity_to_strict_upgrade(row, decisions) is False

    row, decisions = _strict_upgrade_fixture()
    decisions["candidate-upgrade"]["temporal_binding"]["present"] = False
    assert replay.evidence_backed_sensitivity_to_strict_upgrade(row, decisions) is False
