#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "dashboard_data.json"
OUT = ROOT / "data" / "grafana"


def write_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    cities = data.get("cities") or {}
    keys = data.get("multicity_meta", {}).get("production_city_keys") or list(cities)

    if len(keys) != 23:
        raise RuntimeError(f"Expected 23 production city rows, got {len(keys)}")

    city_dir = OUT / "cities"
    city_dir.mkdir(parents=True, exist_ok=True)

    for key in keys:
        city = cities.get(key)
        if not city:
            raise RuntimeError(f"Missing city data: {key}")
        feed = {
            "kpis": city.get("kpis") or [],
            "monthly": city.get("monthly") or [],
            "weekly": city.get("weekly") or [],
            "daily28": city.get("daily28") or [],
        }
        write_json(city_dir / f"{key}.json", feed)

    write_json(OUT / "comparison.json", {"comparison": data.get("comparison") or {}})
    write_json(
        OUT / "casualties.json",
        {"casualties_by_city": data.get("casualties_by_city") or {}},
    )

    sizes = {p.name: p.stat().st_size for p in city_dir.glob("*.json")}
    comparison_size = (OUT / "comparison.json").stat().st_size
    casualties_size = (OUT / "casualties.json").stat().st_size
    if max(sizes.values()) > 1_000_000:
        raise RuntimeError(f"City feed unexpectedly large: {max(sizes.values())}")
    if comparison_size > 1_500_000:
        raise RuntimeError(f"Comparison feed unexpectedly large: {comparison_size}")
    if casualties_size > 500_000:
        raise RuntimeError(f"Casualty feed unexpectedly large: {casualties_size}")

    print(
        "Built Grafana feeds:",
        f"{len(sizes)} city files, max={max(sizes.values())} bytes,",
        f"comparison={comparison_size} bytes, casualties={casualties_size} bytes",
    )


if __name__ == "__main__":
    main()
