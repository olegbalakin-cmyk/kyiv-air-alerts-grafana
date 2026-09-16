#!/usr/bin/env python3
from __future__ import annotations

import expand_multicity_production as base

# These cities remain deliberately deferred.  The historical investigation is
# kept in git, but none of them are added to production until their city/proxy
# geography and rollout date are externally validated.
ADDITIONAL_PROXIES: dict[str, dict] = {}


def explicit_proxy_label(city: str, raion: str) -> str:
    return f"{city} ({raion})"


def main() -> None:
    # Backwards-compatible no-op entry point.  Production is defined by
    # expand_multicity_production.PROXY_CONFIG only.
    print("No additional proxy cities enabled; using validated production set only")
    print("Validated proxy rows:", ", ".join(base.PROXY_CONFIG))


if __name__ == "__main__":
    main()
