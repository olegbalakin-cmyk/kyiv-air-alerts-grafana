# C6-KD-API1 — Owner review (2026-10-29)

**Disposition: ACCESS_BLOCKED for live origin HTTP capture; keep HTML as the operational live source.** Research-only and no deployment.

## Preflight
Verified current `main=ae25e2413a307d7aed74a2035a897e6409b42135`, `site-prod=e08cc7da8cf29fc8603f199c85f0964610a850a7`, operational `multicity-wip-2026-09-16=92011e2cd6a0ce515cd048a4c298c0f0a7bfdf98`; inspected current PROJECT_STATE.md, CHANGELOG.md, and site-prod parser. C6-R3 Actions 40867099080 success on 0cc4d4b5, C6-R4 PG16 Actions 40881999530 success on df384305. Neither is a live API proof. Prior C6=PARTIAL, 184 old identities unproven, Oct 184 municipal +14 fresh HTML, 55 classifications/223 memberships protected.

## API contract
Official documentation: https://kyiv.digital/open-api/docs/air-alert.html ; an archived public OpenAPI schema is preserved at https://github.com/Oleksandr-Hlushchenko/KSE-AI-Agentic-School-Stage2/blob/f2b81a7410078d0c919b1b9013dadf954b6f9a6f/data/raw/kyiv_digital/api_schema.yaml . The archived schema lacks an explicit `servers` entry. Independently existing clients use `https://kyiv.digital/open-api` with `GET /air-alert/history` and `GET /air-alert/state`. Required Accept: application/json or application/xml; no security requirement declared for these GETs. A Bearer token issued by Kyiv Digital is required for webhook *management*, not documented for these GETs. Pagination and numeric rate limits are not declared; 429 is listed. See api_contract.json.

History returns `items` with `state` (1 ON, 0 OFF), `causes` (zero or more simultaneous threat categories), and `created_at` (seconds, no timezone suffix). State returns `current` including `last_cause`, plus stats. No event ID is declared, and no native ID appeared in 5,384 archived records. There is no evidence of millisecond precision. Changing `causes` while state remains ON must never add a second general AIR episode. OpenAPI notes that threat-only changes do not trigger webhooks.

## Origin HTTP capture
A direct GET from the execution container failed DNS resolution. Web retrieval for history/state encountered an XML content-type restriction without a way to set the documented JSON Accept header; HTTP origin status, headers, response bytes, and SHA of a fresh origin capture are **NOT PROVEN**. This is an execution-environment/transport blocker, **not proof that Kyiv Digital requires an API token or that the endpoints are down**. No repeated scraping, credentials, polling or bypass.

## Secondary historical evidence (important new finding)
A public GitHub repository contains a pinned **2026-10-15** copy of the API history: 5,384 events, 319,775 raw UTF-8 bytes, independently recomputed SHA-256 `417e4024d258163c9ead52f80542d2566da0ea0a700bba70d933bbd616df1b3d`. https://github.com/Oleksandr-Hlushchenko/KSE-AI-Agentic-School-Stage2/blob/f2b81a7410078d0c919b1b9013dadf954b6f9a6f/data/raw/kyiv_digital/history_2026-10-15.json

For the frozen October 184 candidate pairs, **113 were within this archive's temporal coverage; 113/113 match both official municipal start and end timestamps to the exact second**, and the corresponding minute-side HTML-derived representations match by minute. The remaining **71/184** are out of the archive's coverage; **0/184 old physical identities are certified** without a source-native event identity or exact same-publisher raw upstream proof. The **latest 14 fresh HTML alerts (Oct 26–29)** cannot be checked against the Oct 15 archive; API parity is **NOT PROVEN**. See timestamp_comparison.json (184 individual rows and latest 14 rows).

The Oct 15 archived history includes 2,713 ON and 2,671 OFF records. Diagnostic chronological pairing yields 2,665 candidate completed intervals, 47 repeated ON, six orphan OFF, an open final alert. Those candidate intervals are **NOT** an authoritative count: repeated starts can indicate missing OFF. No origin-side native event IDs observed. Timezone is not encoded; October 1–15 exact-second parity supports Europe/Kyiv +03:00 in that bounded window, not a blanket DST policy.

## Reader and tests
Current production HTML `_parse_live_dt()` uses only HH:MM and `parse_live_history()` sorts/de-duplicates rows into completed alerts. `parse_official()` retains seconds from `dateTimeStart`/`dateTimeEnd`. `merge_sources()` appends live starts after latest historical *start*. No production parser was modified. A separate local, research-only conservative Python adapter and 21 synthetic tests were executed successfully (21/21) using Python 3.13.5. It quarantines repeated ON, missing/ambiguous OFF, conflicting same-clock events, and ambiguous DST; it treats threat changes as no additional general AIR; 429/outage fails closed. **The runnable adapter and tests are distributed in the companion local research package rather than asserted as CI-tested repository code**. No GitHub Actions proof was run.

## Release boundary and next action
Before switching any operational reader, separately run exactly one bounded unauthenticated GET with `Accept: application/json` to history and state from a network-capable, approved runner, record real HTTP status/headers and SHA-256 raw response, verify DST/timezone, extract the last 14, test Monday municipal transition and validate against protected reader. If 401/403 actually appears, obtain precise read-only entitlement from Kyiv Digital; do not presume token requirement now.

```ini
KYIV_DIGITAL_HISTORY_API_ACCESS = BLOCKED
API_TIMESTAMP_PRECISION = SECONDS_IN_ARCHIVED_2026_10_15; CURRENT_NOT_PROVEN
SOURCE_NATIVE_EVENT_ID = ABSENT_IN_ARCHIVE
GENERAL_AIR_SEMANTICS = PARTIAL
LATEST_COMPLETED_ALERT_PARITY = 0/14_VERIFIED; ACCESS_BLOCKED
HISTORICAL_184_IDENTITY_PROOF = NOT_PROVEN; 113/184_EXACT_TIME_PARITY_ONLY
RESEARCH_ADAPTER_TESTS = 21/21_PASS_LOCAL_SYNTHETIC; 0_LIVE
PRODUCTION_INTEGRATION_AUTHORIZED = NO
```

**Decision: leave HTML as the operational live source until independent bounded JSON-GET capture and owner review.** This does not change C6-OCT184-B1, C6-R4, Neon, WIP or production. No other project checkpoint acceptance is claimed.
