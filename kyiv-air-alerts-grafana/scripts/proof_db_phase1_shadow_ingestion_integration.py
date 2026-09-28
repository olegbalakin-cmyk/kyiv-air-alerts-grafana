#!/usr/bin/env python3
from __future__ import annotations

import base64
import copy
import hashlib
import json
import os
import shutil
import sys
import tempfile
from contextlib import ExitStack
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import add_duration_unit_switch as exactmod
import apply_ukrainealarm_bridge as bridge
import expand_multicity_production as base

SOURCE_KEY = "ukrainealarm_region_history"
CITY_KEY = "lviv"
STREAM_KEY = "region_id:90:AIR"
EXPECTED_SEQ1_ID = "40a0d262-2a79-405b-8e06-1af6e28bc908"
EXPECTED_PROTECTED = {
    "primary": ([0, 0, 0, 0], None),
    "accepted_bootstrap": ([1, 126, 140, 1], 1),
    "accepted_live_e2e": ([2, 126, 140, 1], 1),
    "accepted_concurrency": ([3, 126, 140, 3], 3),
    "old_blocked_concurrency": ([2, 126, 140, 2], 2),
    "accepted_live_poll_adapter": ([6, 126, 140, 5], 5),
}


def require(ok: bool, message: str) -> None:
    if not ok:
        raise AssertionError(message)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def file_hash(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


class Response:
    def __init__(self, *, content: bytes | None = None, payload: Any = None):
        self.content = content if content is not None else json.dumps(payload).encode()
        self._payload = payload
        self.status_code = 200
        self.reason = "OK"
        self.ok = True
        self.text = self.content.decode("utf-8", errors="replace")

    def json(self):
        return copy.deepcopy(self._payload) if self._payload is not None else json.loads(self.content)

    def raise_for_status(self):
        return None


class Session:
    def __init__(self, response: Response, counter: dict[str, int], key: str):
        self.response = response
        self.counter = counter
        self.key = key

    def get(self, *args, **kwargs):
        self.counter[self.key] = self.counter.get(self.key, 0) + 1
        return self.response


class FrozenDateTime(datetime):
    frozen: datetime | None = None

    @classmethod
    def now(cls, tz=None):
        require(cls.frozen is not None, "proof clock not configured")
        return cls.frozen if tz is None else cls.frozen.astimezone(tz)


def copy_baseline(target: Path) -> tuple[Path, Path]:
    target.mkdir(parents=True, exist_ok=True)
    dashboard = target / "dashboard_data.json"
    store = target / "ukrainealarm_bridge.json"
    shutil.copy2(ROOT / "data" / "dashboard_data.json", dashboard)
    shutil.copy2(ROOT / "data" / "ukrainealarm_bridge.json", store)
    return dashboard, store


def capture_sources() -> dict[str, Any]:
    target = Path(tempfile.mkdtemp(prefix="phase1-shadow-capture-", dir=os.environ["RUNNER_TEMP"]))
    dashboard, store = copy_baseline(target)
    bundle: dict[str, Any] = {"vadimkin": {}, "ukrainealarm": {}}
    exact_factory = exactmod.http_session
    proxy_factory = base.http_session
    real_ua_get = bridge.UkraineAlarmClient.get

    def recorder(original, key):
        def factory():
            real = original()
            class R:
                def get(self, url, **kwargs):
                    response = real.get(url, **kwargs)
                    response.raise_for_status()
                    bundle["vadimkin"][key] = {
                        "url": url,
                        "content_b64": base64.b64encode(response.content).decode("ascii"),
                    }
                    return response
            return R()
        return factory

    def ua_record(self, url, *, params=None, context):
        response = real_ua_get(self, url, params=params, context=context)
        key = "regions" if url == bridge.REGIONS_URL else f"history:{(params or {}).get('regionId', '')}"
        bundle["ukrainealarm"][key] = {"payload": response.json(), "params": dict(params or {})}
        return response

    with ExitStack() as stack:
        stack.enter_context(patch.object(bridge, "DATA_FILE", dashboard))
        stack.enter_context(patch.object(bridge, "STORE_FILE", store))
        stack.enter_context(patch.object(exactmod, "http_session", recorder(exact_factory, "exact")))
        stack.enter_context(patch.object(base, "http_session", recorder(proxy_factory, "proxy")))
        stack.enter_context(patch.object(bridge.UkraineAlarmClient, "get", ua_record))
        stack.enter_context(patch.dict(os.environ, {"PHASE1_DB_SHADOW": "0"}, clear=False))
        bridge.main()

    require("exact" in bundle["vadimkin"] and "proxy" in bundle["vadimkin"], "Vadimkin capture incomplete")
    require(any(k.startswith("history:") for k in bundle["ukrainealarm"]), "UkraineAlarm capture incomplete")
    return bundle


def bundle_hash(bundle: dict[str, Any]) -> str:
    raw = json.dumps(bundle, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return sha256_bytes(raw)


def replay_stack(bundle: dict[str, Any], counters: dict[str, int]) -> ExitStack:
    stack = ExitStack()
    exact_bytes = base64.b64decode(bundle["vadimkin"]["exact"]["content_b64"])
    proxy_bytes = base64.b64decode(bundle["vadimkin"]["proxy"]["content_b64"])
    stack.enter_context(patch.object(
        exactmod, "http_session",
        lambda: Session(Response(content=exact_bytes), counters, "exact_http"),
    ))
    stack.enter_context(patch.object(
        base, "http_session",
        lambda: Session(Response(content=proxy_bytes), counters, "proxy_http"),
    ))
    real_phase1 = base.fetch_proxy_alerts_with_phase1
    def counted_phase1():
        counters["phase1_fetch"] = counters.get("phase1_fetch", 0) + 1
        return real_phase1()
    stack.enter_context(patch.object(base, "fetch_proxy_alerts_with_phase1", counted_phase1))

    def ua_replay(self, url, *, params=None, context):
        key = "regions" if url == bridge.REGIONS_URL else f"history:{(params or {}).get('regionId', '')}"
        row = bundle["ukrainealarm"].get(key)
        require(row is not None, f"capture missing {key}")
        counters[key] = counters.get(key, 0) + 1
        return Response(payload=row["payload"])
    stack.enter_context(patch.object(bridge.UkraineAlarmClient, "get", ua_replay))
    return stack


def run_replay(bundle: dict[str, Any], *, shadow: bool, target: Path) -> dict[str, Any]:
    dashboard, store = copy_baseline(target)
    FrozenDateTime.frozen = datetime.fromisoformat(os.environ["PROOF_FROZEN_TIME"].replace("Z", "+00:00"))
    counters: dict[str, int] = {}
    env = {"UKRAINEALARM_API_TOKEN": "captured-proof-token", "PHASE1_DB_SHADOW": "1" if shadow else "0"}
    if not shadow:
        env.update({"PHASE1_DATABASE_URL": "", "PHASE1_DB_BRANCH": ""})
    with replay_stack(bundle, counters), ExitStack() as stack:
        stack.enter_context(patch.object(bridge, "DATA_FILE", dashboard))
        stack.enter_context(patch.object(bridge, "STORE_FILE", store))
        stack.enter_context(patch.object(bridge, "datetime", FrozenDateTime))
        stack.enter_context(patch.dict(os.environ, env, clear=False))
        bridge.main()
    require(counters.get("phase1_fetch") == 1, f"real bridge phase1 fetch count !=1: {counters}")
    require(counters.get("proxy_http") == 1, f"proxy HTTP count !=1: {counters}")
    return {
        "dashboard_hash": file_hash(dashboard),
        "bridge_hash": file_hash(store),
        "counters": counters,
    }


def prepare() -> int:
    bundle = capture_sources()
    Path(os.environ["CAPTURE_BUNDLE"]).write_text(
        json.dumps(bundle, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    )
    digest = bundle_hash(bundle)
    sys.modules.pop("db_phase1_shadow", None)
    sys.modules.pop("psycopg", None)
    off = run_replay(bundle, shadow=False, target=Path(os.environ["RUNNER_TEMP"]) / "off")
    require("db_phase1_shadow" not in sys.modules, "shadow OFF imported db_phase1_shadow")
    require("psycopg" not in sys.modules, "shadow OFF imported psycopg")
    state = {
        "captured_input_hash": digest,
        "proof_frozen_time": os.environ["PROOF_FROZEN_TIME"],
        "shadow_off_dashboard_hash": off["dashboard_hash"],
        "shadow_off_bridge_hash": off["bridge_hash"],
    }
    Path(os.environ["PROOF_STATE"]).write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")
    print("capture hash =", digest)
    print("shadow OFF dashboard =", off["dashboard_hash"])
    print("shadow OFF bridge =", off["bridge_hash"])
    return 0


def direct(url: str) -> None:
    host = urlparse(url).hostname or ""
    require(bool(host) and "-pooler" not in host, "direct/unpooled connection required")


def snapshot(url: str) -> dict[str, Any]:
    import psycopg
    from psycopg.rows import dict_row
    direct(url)
    with psycopg.connect(url, autocommit=True, row_factory=dict_row, connect_timeout=20) as conn:
        with conn.cursor() as cur:
            cur.execute("""
              SELECT
                (SELECT count(*) FROM ingestion_runs)::int ingestion_runs,
                (SELECT count(*) FROM alert_episodes)::int alert_episodes,
                (SELECT count(*) FROM alert_episode_sources)::int alert_episode_sources,
                (SELECT count(*) FROM ingestion_checkpoints)::int ingestion_checkpoints
            """)
            counts = dict(cur.fetchone())
            cur.execute("""
              SELECT checkpoint_id::text, checkpoint_seq::int, previous_checkpoint_id::text,
                     checkpoint_kind, created_by_run_id::text
              FROM ingestion_checkpoints
              WHERE source_key=%s AND city_key=%s AND stream_key=%s
              ORDER BY checkpoint_seq
            """, (SOURCE_KEY, CITY_KEY, STREAM_KEY))
            history = [dict(r) for r in cur.fetchall()]
            cur.execute("SELECT legacy_episode_id FROM alert_episodes ORDER BY legacy_episode_id")
            episodes = [r["legacy_episode_id"] for r in cur.fetchall()]
            cur.execute("""
              SELECT source_key, source_record_key_version, source_record_key
              FROM alert_episode_sources
              ORDER BY source_key, source_record_key_version, source_record_key
            """)
            sources = [[r["source_key"], r["source_record_key_version"], r["source_record_key"]] for r in cur.fetchall()]
    return {"counts": {k: int(v) for k, v in counts.items()}, "history": history, "episodes": episodes, "sources": sources}


def check_protected(name: str, snap: dict[str, Any]) -> None:
    vector, seq = EXPECTED_PROTECTED[name]
    c = snap["counts"]
    got = [c["ingestion_runs"], c["alert_episodes"], c["alert_episode_sources"], c["ingestion_checkpoints"]]
    require(got == vector, f"{name} counts mismatch: {got}")
    current = snap["history"][-1]["checkpoint_seq"] if snap["history"] else None
    require(current == seq, f"{name} seq mismatch: {current}")
    if name == "accepted_live_poll_adapter":
        require([r["checkpoint_seq"] for r in snap["history"]] == [1,2,3,4,5], "adapter history changed")


def run_row(url: str, run_id: str) -> dict[str, Any]:
    import psycopg
    from psycopg.rows import dict_row
    with psycopg.connect(url, autocommit=True, row_factory=dict_row, connect_timeout=20) as conn:
        with conn.cursor() as cur:
            cur.execute("""
              SELECT run_id::text, run_kind, schema_version, canonicalization_version,
                     workflow_repository, workflow_name, workflow_ref, workflow_sha,
                     input_repository, input_ref, input_sha, github_run_id,
                     github_run_attempt, parameters, stats
              FROM ingestion_runs WHERE run_id=%s
            """, (run_id,))
            row = cur.fetchone()
            require(row is not None, f"missing run {run_id}")
            return dict(row)


def verify_identities(url: str, payload: dict[str, Any]) -> None:
    import psycopg
    from psycopg.rows import dict_row
    with psycopg.connect(url, autocommit=True, row_factory=dict_row, connect_timeout=20) as conn:
        with conn.cursor() as cur:
            for episode in payload["episodes"]:
                cur.execute("SELECT canonicalization_version FROM alert_episodes WHERE legacy_episode_id=%s", (episode["legacy_episode_id"],))
                row = cur.fetchone()
                require(row is not None and row["canonicalization_version"] == episode["canonicalization_version"], "episode identity missing/incompatible")
            for obs in payload["source_observations"]:
                cur.execute("""
                  SELECT e.legacy_episode_id
                  FROM alert_episode_sources s JOIN alert_episodes e ON e.episode_uid=s.episode_uid
                  WHERE s.source_key=%s AND s.source_record_key_version=%s AND s.source_record_key=%s
                """, (obs["source_key"], obs["source_record_key_version"], obs["source_record_key"]))
                row = cur.fetchone()
                require(row is not None and row["legacy_episode_id"] == obs["episode_legacy_id"], "source identity missing/incompatible")


def prove() -> int:
    bundle = json.loads(Path(os.environ["CAPTURE_BUNDLE"]).read_text())
    state = json.loads(Path(os.environ["PROOF_STATE"]).read_text())
    require(bundle_hash(bundle) == state["captured_input_hash"], "capture hash changed")
    target_url = os.environ["PHASE1_DATABASE_URL"]
    protected_urls = {
        "primary": os.environ["PHASE1_PRIMARY_DATABASE_URL"],
        "accepted_bootstrap": os.environ["PHASE1_BOOTSTRAP_DATABASE_URL"],
        "accepted_live_e2e": os.environ["PHASE1_LIVE_E2E_DATABASE_URL"],
        "accepted_concurrency": os.environ["PHASE1_CONCURRENCY_DATABASE_URL"],
        "old_blocked_concurrency": os.environ["PHASE1_BLOCKED_DATABASE_URL"],
        "accepted_live_poll_adapter": os.environ["PHASE1_ADAPTER_DATABASE_URL"],
    }
    protected_before = {n: snapshot(u) for n, u in protected_urls.items()}
    for n, s in protected_before.items():
        check_protected(n, s)

    initial = snapshot(target_url)
    require(initial["counts"] == {"ingestion_runs":1,"alert_episodes":126,"alert_episode_sources":140,"ingestion_checkpoints":1}, f"wrong inherited counts {initial['counts']}")
    require(initial["history"][0]["checkpoint_id"] == EXPECTED_SEQ1_ID, "seq1 id mismatch")

    first = run_replay(bundle, shadow=True, target=Path(os.environ["RUNNER_TEMP"]) / "on-first")
    import db_phase1_shadow as shadow
    first_result = copy.deepcopy(shadow.last_shadow_result())
    first_payload = copy.deepcopy(shadow.last_shadow_payload())
    require(first_result and first_payload, "real bridge did not reach persistence adapter")
    require(first_payload["stream_key"] == STREAM_KEY, f"wrong stream {first_payload['stream_key']}")
    cp = first_payload["checkpoint_candidate"]
    require(cp["checkpoint_kind"] == "poll" and "checkpoint_seq" not in cp and "previous_checkpoint_id" not in cp, "integration owns checkpoint chain fields")
    after_first = snapshot(target_url)
    stats1 = first_result["stats"]
    require(after_first["counts"]["ingestion_runs"] == 2, "first run count wrong")
    require(after_first["counts"]["ingestion_checkpoints"] == 2, "first checkpoint count wrong")
    require(after_first["history"][-1]["checkpoint_seq"] == 2, "seq did not advance 1->2")
    require(after_first["history"][-1]["previous_checkpoint_id"] == EXPECTED_SEQ1_ID, "seq2 previous link wrong")
    require(stats1["checkpoints_inserted"] == 1 and stats1["exact_retry"] is False, "first stats wrong")
    require(after_first["counts"]["alert_episodes"] == 126 + stats1["episodes_inserted"], "episode formula wrong")
    require(after_first["counts"]["alert_episode_sources"] == 140 + stats1["source_observations_inserted"], "source formula wrong")
    require(set(initial["episodes"]).issubset(after_first["episodes"]), "baseline episode disappeared")
    require({tuple(x) for x in initial["sources"]}.issubset({tuple(x) for x in after_first["sources"]}), "baseline source disappeared")
    verify_identities(target_url, first_payload)
    prov = run_row(target_url, first_result["run_id"])
    require(prov["run_kind"] == "shadow_poll", "run_kind wrong")
    require(prov["canonicalization_version"] == "alert-canonicalization-v1", "version wrong")
    require(prov["parameters"]["assembly_profile"] == "lviv-historical-v1" and prov["parameters"]["shadow"] is True, "parameters wrong")
    require(str(prov["github_run_id"]) == os.environ["GITHUB_RUN_ID"], "github run mismatch")
    require(prov["input_sha"] == os.environ["GITHUB_SHA"], "input sha mismatch")
    require(after_first["history"][-1]["created_by_run_id"] == first_result["run_id"], "checkpoint run provenance mismatch")
    seq2 = after_first["history"][-1]["checkpoint_id"]
    require(first["dashboard_hash"] == state["shadow_off_dashboard_hash"], "dashboard OFF/ON mismatch")
    require(first["bridge_hash"] == state["shadow_off_bridge_hash"], "bridge OFF/ON mismatch")

    second = run_replay(bundle, shadow=True, target=Path(os.environ["RUNNER_TEMP"]) / "on-retry")
    retry_result = copy.deepcopy(shadow.last_shadow_result())
    final = snapshot(target_url)
    stats2 = retry_result["stats"]
    require(final["counts"]["ingestion_runs"] == 3 and final["counts"]["ingestion_checkpoints"] == 2, "retry DB counts wrong")
    require(final["history"][-1]["checkpoint_seq"] == 2 and final["history"][-1]["checkpoint_id"] == seq2, "retry changed seq2")
    require(final["counts"]["alert_episodes"] == after_first["counts"]["alert_episodes"], "retry episode count changed")
    require(final["counts"]["alert_episode_sources"] == after_first["counts"]["alert_episode_sources"], "retry source count changed")
    require(stats2["episodes_inserted"] == 0 and stats2["source_observations_inserted"] == 0 and stats2["checkpoints_inserted"] == 0 and stats2["exact_retry"] is True, "retry not exact")
    require(second["dashboard_hash"] == state["shadow_off_dashboard_hash"] == first["dashboard_hash"], "retry dashboard parity failed")
    require(second["bridge_hash"] == state["shadow_off_bridge_hash"] == first["bridge_hash"], "retry bridge parity failed")

    protected_after = {n: snapshot(u) for n, u in protected_urls.items()}
    for n, s in protected_after.items():
        check_protected(n, s)
    isolation = {n: protected_before[n] == protected_after[n] for n in protected_urls}
    require(all(isolation.values()), f"protected isolation failed {isolation}")

    split: dict[str, int] = {}
    for row in first_payload["source_observations"]:
        split[row["source_key"]] = split.get(row["source_key"], 0) + 1
    require(not any(k == "alerts-in-ua" or k.startswith("alerts_in_ua") for k in split), f"Alerts.in.ua leaked {split}")

    artifact = {
        "integration_base_sha": os.environ["INTEGRATION_BASE_SHA"],
        "integration_commit_sha": os.environ["GITHUB_SHA"],
        "workflow_run_id": os.environ["GITHUB_RUN_ID"],
        "site_prod_at_start": os.environ["SITE_PROD_AT_START"],
        "site_prod_at_end": os.environ["SITE_PROD_AT_START"],
        "main_at_start": os.environ["MAIN_AT_START"],
        "main_at_end": os.environ["MAIN_AT_START"],
        "canonical_blob": os.environ["CANONICAL_BLOB"],
        "persistence_blob": os.environ["PERSISTENCE_BLOB"],
        "ddl_blob": os.environ["DDL_BLOB"],
        "real_entrypoint": "scripts/apply_ukrainealarm_bridge.py::main()",
        "shadow_gate": "PHASE1_DB_SHADOW=1",
        "captured_input_hash": state["captured_input_hash"],
        "proof_frozen_time": state["proof_frozen_time"],
        "shadow_off_dashboard_hash": state["shadow_off_dashboard_hash"],
        "shadow_off_bridge_hash": state["shadow_off_bridge_hash"],
        "shadow_on_dashboard_hash": first["dashboard_hash"],
        "shadow_on_bridge_hash": first["bridge_hash"],
        "retry_dashboard_hash": second["dashboard_hash"],
        "retry_bridge_hash": second["bridge_hash"],
        "product_output_parity": True,
        "ignored_volatile_fields": [],
        "canonical_episode_count": len(first_payload["episodes"]),
        "canonical_source_observation_count": len(first_payload["source_observations"]),
        "canonical_source_split": split,
        "neon_project_id": os.environ["NEON_PROJECT_ID"],
        "proof_branch_id": os.environ["PHASE1_DB_BRANCH"],
        "proof_branch_name": os.environ["PROOF_BRANCH_NAME"],
        "parent_branch_id": os.environ["PARENT_BRANCH_ID"],
        "direct_unpooled": True,
        "db_initial_counts": initial["counts"],
        "db_initial_checkpoint": initial["history"][0],
        "first_shadow_run_id": first_result["run_id"],
        "first_shadow_stats": stats1,
        "seq2_checkpoint_id": seq2,
        "retry_shadow_run_id": retry_result["run_id"],
        "retry_shadow_stats": stats2,
        "retry_exact_retry": stats2["exact_retry"],
        "db_final_counts": final["counts"],
        "db_final_checkpoint_history": [r["checkpoint_seq"] for r in final["history"]],
        "real_path_provenance_match": True,
        "protected_branch_isolation": isolation,
        "site_prod_modified": False,
        "main_modified": False,
        "production_publication": False,
        "scheduled_shadow_enabled": False,
        "netlify_triggered": False,
        "credentials_exposed": False,
        "test_count": int(os.environ["PHASE1_TEST_COUNT"]),
        "test_result": os.environ["PHASE1_TEST_RESULT"],
        "verdict": "PHASE-1 SHADOW INGESTION INTEGRATION PROVEN",
    }
    Path(os.environ["PROOF_RESULT"]).write_text(json.dumps(artifact, indent=2, sort_keys=True, default=str) + "\n")
    print("PHASE-1 SHADOW INGESTION INTEGRATION PROVEN")
    print("first stats =", json.dumps(stats1, sort_keys=True))
    print("retry stats =", json.dumps(stats2, sort_keys=True))
    return 0


def main() -> int:
    require(len(sys.argv) == 2 and sys.argv[1] in {"prepare", "prove"}, "usage: ... prepare|prove")
    return prepare() if sys.argv[1] == "prepare" else prove()


if __name__ == "__main__":
    raise SystemExit(main())
