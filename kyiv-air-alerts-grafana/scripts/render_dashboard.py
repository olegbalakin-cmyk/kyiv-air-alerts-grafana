#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "grafana" / "dashboard.template.json"
OUTPUT = ROOT / "grafana" / "dashboard.json"


def replace(obj, marker: str, value: str):
    if isinstance(obj, str):
        return obj.replace(marker, value)
    if isinstance(obj, list):
        return [replace(x, marker, value) for x in obj]
    if isinstance(obj, dict):
        return {k: replace(v, marker, value) for k, v in obj.items()}
    return obj


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repository", required=True, help="OWNER/REPO")
    ap.add_argument("--branch", default="main")
    args = ap.parse_args()
    raw = f"https://raw.githubusercontent.com/{args.repository}/{args.branch}/data/dashboard_data.json"
    obj = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    obj = replace(obj, "__RAW_DATA_URL__", raw)
    OUTPUT.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Rendered {OUTPUT} -> {raw}")


if __name__ == "__main__":
    main()
