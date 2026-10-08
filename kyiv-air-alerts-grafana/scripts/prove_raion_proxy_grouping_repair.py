#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

import apply_ukrainealarm_bridge as ua
import monitor_explosion_candidates as monitor

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "data" / "ukrainealarm_bridge.json"
ACTIVATION = ROOT / "config" / "live_persistence_activation.json"


def key(ep: dict) -> tuple[str, str, str]:
    return (ep["alert_start"], ep["alert_end"], ep["episode_id"])


def canonical_episode(city_key: str, alert) -> dict:
    return monitor.make_episode(
        city_key,
        alert.start.astimezone(monitor.UTC),
        alert.end.astimezone(monitor.UTC),
        source="canonical-parity",
    )


def main() -> None:
    bridge = json.loads(BRIDGE.read_text(encoding="utf-8"))
    activation = json.loads(ACTIVATION.read_text(encoding="utf-8"))
    cutoff = monitor.parse_dt(activation["activation_cutoff_utc"])
    assert cutoff is not None

    proxy_cfg = ua.extended.configure_all_proxies()
    static, _ = ua.load_static_bridge()
    proxy_base = ua.base.fetch_proxy_alerts()

    rows = []
    mismatches = []
    for city_key in sorted(proxy_cfg):
        api_alerts = ua.api_store_alerts(bridge, city_key)
        canonical = ua.union_alerts(
            [*proxy_base[city_key], *static[city_key], *api_alerts],
            "historical_proxy_plus_alertsinua_plus_ukrainealarm",
        )
        live = monitor.raion_proxy_logical_episodes(
            city_key,
            bridge,
            [],
            source="parity-live",
        )
        canonical_recent = [
            canonical_episode(city_key, alert)
            for alert in canonical
            if alert.end.astimezone(monitor.UTC) >= cutoff
        ]
        live_recent = [
            ep
            for ep in live
            if monitor.parse_dt(ep["alert_end"]) >= cutoff
        ]
        canonical_keys = [key(ep) for ep in canonical_recent]
        live_keys = [key(ep) for ep in live_recent]
        exact = canonical_keys == live_keys
        rows.append(
            {
                "city": city_key,
                "canonical_recent": len(canonical_recent),
                "live_recent": len(live_recent),
                "exact": exact,
                "canonical": canonical_keys,
                "live": live_keys,
            }
        )
        if not exact:
            mismatches.append(rows[-1])

    proof = monitor.raion_proxy_grouping_self_test()
    compared = sum(row["canonical_recent"] for row in rows)
    exact_rows = sum(
        len(row["canonical"])
        for row in rows
        if row["exact"]
    )
    out = {
        "raion_proxy_cities": sorted(proxy_cfg),
        "city_count": len(proxy_cfg),
        "activation_cutoff": activation["activation_cutoff_utc"],
        "logical_episodes_compared": compared,
        "exact_boundary_matches": exact_rows,
        "exact_episode_id_matches": exact_rows,
        "identity_mismatches": len(mismatches),
        "mismatches": mismatches,
        "grouping_self_test": proof,
        "per_city": rows,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    if mismatches:
        raise SystemExit("raion-proxy recent parity mismatches remain")


if __name__ == "__main__":
    main()
