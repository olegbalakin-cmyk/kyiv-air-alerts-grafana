import csv
import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import review_casualty_candidates as review
import update_casualties as update


REVISION_HEADER = ",".join(review.REVISION_FIELDS) + "\n"
EXPECTED_CITY_KEYS = {
    "kyiv", "kharkiv", "sevastopol", "cherkasy", "zhytomyr", "dnipro",
    "khmelnytskyi", "poltava", "rivne", "sumy", "vinnytsia",
    "kropyvnytskyi", "lviv", "chernihiv", "mykolaiv", "lutsk",
    "uzhhorod", "ivano-frankivsk", "ternopil", "chernivtsi",
    "odesa", "zaporizhzhia", "kherson",
}


def candidate(candidate_id: str, city_key: str, url: str = "https://media.example/item") -> dict:
    return {
        "candidate_id": candidate_id,
        "city_key": city_key,
        "city": city_key,
        "status": "needs_review",
        "url": url,
        "title": f"Synthetic candidate {candidate_id}",
        "snippet": "Synthetic fixture only; no real casualty candidate.",
        "first_discovered_at": "2026-10-08T10:00:00Z",
        "last_seen_at": "2026-10-08T10:00:00Z",
        "trigger_episode_ids": ["synthetic-episode"],
        "trigger_check_labels": ["24h"],
    }


def write_queue(path: Path, items: list[dict]) -> None:
    path.write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_revision_rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def configure_builder(monkeypatch, tmp_path: Path) -> tuple[Path, Path]:
    casualty_src = ROOT / "data" / "casualties"
    casualty_tmp = tmp_path / "casualties"
    casualty_tmp.mkdir()
    for name in (
        "baseline_monthly.csv",
        "master_20cities_manifest.json",
        "master_20cities_monthly_wide.csv",
    ):
        shutil.copy2(casualty_src / name, casualty_tmp / name)
    shutil.copytree(casualty_src / "cities", casualty_tmp / "cities")

    revisions = casualty_tmp / "revisions.csv"
    revisions.write_text(REVISION_HEADER, encoding="utf-8")
    legacy_queue = casualty_tmp / "review_queue.json"
    legacy_queue.write_text("[]\n", encoding="utf-8")
    dashboard = tmp_path / "dashboard_data.json"
    dashboard.write_text("{}\n", encoding="utf-8")

    monkeypatch.setattr(update, "DATA_FILE", dashboard)
    monkeypatch.setattr(update, "CASUALTY_DIR", casualty_tmp)
    monkeypatch.setattr(update, "BASELINE_FILE", casualty_tmp / "baseline_monthly.csv")
    monkeypatch.setattr(update, "REVISIONS_FILE", revisions)
    monkeypatch.setattr(update, "REVIEW_QUEUE_FILE", legacy_queue)
    monkeypatch.setattr(update, "SOURCE_STATE_FILE", casualty_tmp / "source_state.json")
    monkeypatch.setattr(update, "CITY_SERIES_DIR", casualty_tmp / "cities")
    monkeypatch.setattr(update, "MASTER_WIDE_FILE", casualty_tmp / "master_20cities_monthly_wide.csv")
    monkeypatch.setattr(update, "MASTER_MANIFEST_FILE", casualty_tmp / "master_20cities_manifest.json")
    return revisions, dashboard


def month_deaths(dashboard: dict, city_key: str, month: str) -> int:
    rows = dashboard["casualties_by_city"][city_key]["monthly"]
    return next(int(row["deaths"]) for row in rows if row["month"] == month)


def expected_historical_months() -> dict[str, dict[str, int]]:
    out = {}
    baseline = update.load_baseline()
    out["kyiv"] = {row["month"]: int(row["deaths"]) for row in baseline}

    with update.MASTER_WIDE_FILE.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    master_cities = [
        city for city, family in update.city_baseline_routes().items()
        if family == "master_20cities"
    ]
    for city in master_cities:
        out[city] = {row["month"]: int(row[city]) for row in rows}

    for city in ("odesa", "zaporizhzhia", "kherson"):
        series = update.load_validated_city_series()[city]["monthly"]
        out[city] = {row["month"]: int(row["deaths"]) for row in series}
    return out


def test_rejected_disposition_is_durable_and_writes_no_delta(monkeypatch, tmp_path):
    revisions, dashboard_path = configure_builder(monkeypatch, tmp_path)
    queue = tmp_path / "queue.json"
    original = candidate("cand-rejected", "odesa")
    write_queue(queue, [original])

    review.review_candidate(
        queue,
        candidate_id="cand-rejected",
        city_key="odesa",
        status="rejected",
        note="synthetic rejection",
        reviewed_at="2026-10-08T12:00:00+03:00",
    )
    summary = review.promote_reviewed(queue, revisions, allowed_city_keys=EXPECTED_CITY_KEYS)
    update.update_dashboard_data(no_network=True)

    stored = json.loads(queue.read_text(encoding="utf-8"))[0]
    assert stored["status"] == "rejected"
    assert stored["review_disposition"]["status"] == "rejected"
    assert stored["url"] == original["url"]
    assert stored["trigger_episode_ids"] == original["trigger_episode_ids"]
    assert summary["revision_rows"] == 0
    assert read_revision_rows(revisions) == []
    dashboard = json.loads(dashboard_path.read_text(encoding="utf-8"))
    assert month_deaths(dashboard, "odesa", "2026-09") == 3


def test_confirmed_candidate_reaches_city_month_and_fixture_dashboard(monkeypatch, tmp_path):
    revisions, dashboard_path = configure_builder(monkeypatch, tmp_path)
    queue = tmp_path / "queue.json"
    write_queue(queue, [candidate("cand-confirmed", "odesa")])

    review.review_candidate(
        queue,
        candidate_id="cand-confirmed",
        city_key="odesa",
        status="confirmed",
        record_id="synthetic:odesa:2026-09-20:aerial-deaths",
        attack_date="2026-09-20",
        deaths_delta=2,
        source_name="Synthetic official confirmation fixture",
        source_url="https://official.example/odesa-fixture",
        note="test fixture only",
        reviewed_at="2026-10-08T12:05:00+03:00",
    )
    summary = review.promote_reviewed(queue, revisions, allowed_city_keys=EXPECTED_CITY_KEYS)
    update.update_dashboard_data(no_network=True)

    rows = read_revision_rows(revisions)
    assert summary["canonical_records_added"] == 1
    assert len(rows) == 1
    assert rows[0]["record_id"] == "synthetic:odesa:2026-09-20:aerial-deaths"
    assert rows[0]["candidate_ids"] == "cand-confirmed"
    dashboard = json.loads(dashboard_path.read_text(encoding="utf-8"))
    assert month_deaths(dashboard, "odesa", "2026-09") == 5
    affected = next(
        row for row in dashboard["casualties_by_city"]["odesa"]["monthly"]
        if row["month"] == "2026-09"
    )
    assert affected["baseline_deaths"] == 3
    assert affected["revision_delta"] == 2


def test_promotion_is_idempotent(monkeypatch, tmp_path):
    revisions, _ = configure_builder(monkeypatch, tmp_path)
    queue = tmp_path / "queue.json"
    write_queue(queue, [candidate("cand-idempotent", "dnipro")])
    review.review_candidate(
        queue,
        candidate_id="cand-idempotent",
        city_key="dnipro",
        status="confirmed",
        record_id="synthetic:dnipro:2026-09-21",
        attack_date="2026-09-21",
        deaths_delta=3,
        source_name="Synthetic official confirmation fixture",
        source_url="https://official.example/dnipro-fixture",
        reviewed_at="2026-10-08T12:10:00+03:00",
    )

    first = review.promote_reviewed(queue, revisions, allowed_city_keys=EXPECTED_CITY_KEYS)
    second = review.promote_reviewed(queue, revisions, allowed_city_keys=EXPECTED_CITY_KEYS)
    rows = read_revision_rows(revisions)
    assert first["canonical_records_added"] == 1
    assert second["canonical_records_added"] == 0
    assert second["ledger_changed"] is False
    assert len(rows) == 1
    assert rows[0]["deaths_delta"] == "3"


def test_duplicate_media_candidates_share_one_canonical_delta(monkeypatch, tmp_path):
    revisions, dashboard_path = configure_builder(monkeypatch, tmp_path)
    queue = tmp_path / "queue.json"
    write_queue(
        queue,
        [
            candidate("cand-media-a", "sumy", "https://media-a.example/item"),
            candidate("cand-media-b", "sumy", "https://media-b.example/item"),
        ],
    )
    for cid, source_url in (
        ("cand-media-a", "https://official-a.example/sumy"),
        ("cand-media-b", "https://official-b.example/sumy"),
    ):
        review.review_candidate(
            queue,
            candidate_id=cid,
            city_key="sumy",
            status="confirmed",
            record_id="synthetic:sumy:2026-09-22",
            attack_date="2026-09-22",
            deaths_delta=2,
            source_name=f"Synthetic confirmation {cid}",
            source_url=source_url,
            reviewed_at="2026-10-08T12:15:00+03:00",
        )

    review.promote_reviewed(queue, revisions, allowed_city_keys=EXPECTED_CITY_KEYS)
    rows = read_revision_rows(revisions)
    assert len(rows) == 1
    assert set(rows[0]["candidate_ids"].split("|")) == {"cand-media-a", "cand-media-b"}
    update.update_dashboard_data(no_network=True)
    dashboard = json.loads(dashboard_path.read_text(encoding="utf-8"))
    assert month_deaths(dashboard, "sumy", "2026-09") == 5


def test_needs_review_cannot_enter_revisions_or_totals(monkeypatch, tmp_path):
    revisions, dashboard_path = configure_builder(monkeypatch, tmp_path)
    queue = tmp_path / "queue.json"
    item = candidate("cand-pending", "kharkiv")
    item.update(
        {
            "record_id": "unsafe-inferred-record",
            "attack_date": "2026-09-20",
            "deaths_delta": 99,
        }
    )
    write_queue(queue, [item])

    summary = review.promote_reviewed(queue, revisions, allowed_city_keys=EXPECTED_CITY_KEYS)
    assert summary["revision_rows"] == 0
    update.update_dashboard_data(no_network=True)
    dashboard = json.loads(dashboard_path.read_text(encoding="utf-8"))
    assert month_deaths(dashboard, "kharkiv", "2026-09") == 1


def test_all_23_city_keys_route_to_expected_baseline_family():
    routes = update.city_baseline_routes()
    assert set(routes) == EXPECTED_CITY_KEYS
    assert routes["kyiv"] == "kyiv_baseline"
    assert {city for city, family in routes.items() if family == "validated_city"} == {
        "odesa", "zaporizhzhia", "kherson"
    }
    master_only = {city for city, family in routes.items() if family == "master_20cities"}
    assert len(master_only) == 19


def test_historical_regression_zero_deltas_preserves_every_city_month(monkeypatch, tmp_path, capsys):
    revisions, dashboard_path = configure_builder(monkeypatch, tmp_path)
    expected = expected_historical_months()
    assert read_revision_rows(revisions) == []

    update.update_dashboard_data(no_network=True)
    dashboard = json.loads(dashboard_path.read_text(encoding="utf-8"))
    actual = {
        city: {row["month"]: int(row["deaths"]) for row in dashboard["casualties_by_city"][city]["monthly"]}
        for city in EXPECTED_CITY_KEYS
    }
    assert actual == expected
    compared_cells = sum(len(months) for months in expected.values())
    print(f"HISTORICAL_REGRESSION cities={len(expected)} city_month_cells={compared_cells} mismatches=0")
    capsys.readouterr()


def test_confirmed_review_requires_all_explicit_fields(tmp_path):
    queue = tmp_path / "queue.json"
    write_queue(queue, [candidate("cand-missing", "kyiv")])
    with pytest.raises(ValueError, match="source_name"):
        review.review_candidate(
            queue,
            candidate_id="cand-missing",
            city_key="kyiv",
            status="confirmed",
            record_id="synthetic:kyiv:2026-09-25",
            attack_date="2026-09-25",
            deaths_delta=1,
            source_url="https://official.example/kyiv",
        )
    stored = json.loads(queue.read_text(encoding="utf-8"))[0]
    assert stored["status"] == "needs_review"


def test_legacy_kyiv_review_queue_is_not_used_by_promotion(tmp_path):
    multicity = tmp_path / "multicity_review_queue.json"
    legacy = tmp_path / "review_queue.json"
    revisions = tmp_path / "revisions.csv"
    revisions.write_text(REVISION_HEADER, encoding="utf-8")
    write_queue(multicity, [candidate("cand-multicity-pending", "kyiv")])
    legacy_payload = [candidate("legacy-candidate", "kyiv")]
    legacy_payload[0]["status"] = "confirmed"
    write_queue(legacy, legacy_payload)
    legacy_before = legacy.read_bytes()

    review.promote_reviewed(multicity, revisions, allowed_city_keys=EXPECTED_CITY_KEYS)
    assert legacy.read_bytes() == legacy_before
    assert read_revision_rows(revisions) == []
    assert review.DEFAULT_QUEUE_FILE.name == "multicity_review_queue.json"
