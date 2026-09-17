#!/usr/bin/env python3
from __future__ import annotations

import configure_compact_dashboard as compact
import expand_multicity_production as production
import extend_remaining_proxies as extended


def main() -> None:
    # configure_compact_dashboard validates its expected set against
    # expand_multicity_production.CITY_KEYS. Extend that runtime expectation
    # with the seven cross-source-validated proxy rows before configuring UI.
    production.CITY_KEYS = [
        *production.EXACT_KEYS,
        *production.PROXY_KEYS,
        *extended.ADDITIONAL_PROXIES.keys(),
    ]
    compact.main()


if __name__ == "__main__":
    main()
