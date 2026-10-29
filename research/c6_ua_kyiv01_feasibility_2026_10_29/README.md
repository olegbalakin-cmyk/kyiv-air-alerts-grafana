# C6-UA-KYIV-01 — research-only audit (2026-10-29)

## Scope / actual evidence
- Base main: b5e094b391ecad699580239f40549368f34b4120; site-prod: e08cc7da8cf29fc8603f199c85f0964610a850a7; operational WIP: 92011e2cd6a0ce515cd048a4c298c0f0a7bfdf98.
- Official SDK: `UkraineAlarm/UkraineAlarm-javascript` master files `docs/RegionViewModel.md`, `docs/RegionsViewModel.md`, `docs/AlertRegionModel.md`, `docs/Alert.md`, `docs/RegionAlarmModel.md`, `docs/RegionAlarmsHistory.md`, `docs/V2RegionType.md`, `docs/AlertType.md`, `docs/RegionsApi.md`. This SDK contract exposes `regionChildIds`, `State/District/Community`, and v3 history `regionId/startDate/endDate/alertType/isContinue`; **it does not describe reason fields in RegionAlarmModel**. An older/particular generated SDK is NOT proof of the current raw wire payload.
- Third-party `UkraineAlarm.Sdk/1.1.0` metadata cites `ActiveAlertLevels / AlertLevel / Reason`. Distinguish **client data model**, **documented current wire contract**, **observed actual response**, and **historical persisted reason transitions**. No latter proof in this task.
- Current production `site-prod` files: `kyiv-air-alerts-grafana/scripts/apply_ukrainealarm_bridge.py` Git blob `8b95c4b508b9a473240889603f593e399cf8815d`, `ukrainealarm_request_policy.py` `6fe5429a0abf93dbfb3bae009a9f0de4ef4f86b4`, `differentiated_alert_source_capture.py` `d406bb87360a85abe6ad58d0fe9c99aa64d23bee`; `data/ukrainealarm_bridge.json` Git blob `bb5e0a7f2068d098761fc449fe58b0180f5c54d2`; `data/kyiv_threat_mix.json` `d8b8b5f18ca523c54297497fb37cdc21e35a7efd`.
- Production `history_rows()` selects only `AIR`, `startDate`, `endDate` and does not persist original `Reason` (even if it exists). Bridge keeps bounded completed events and is not a full Kyiv city historical archive. Separate differentiated capture selects `regionId=147`, but this code does NOT establish `147` as Kyiv. Do not assume city scope.
- Kyiv Digital comparison baseline from accepted **different source** checkpoint: archived 113/113 exact-second interval matches; 71 outside archive; newest 14 (Oct 26–29) not confirmed against publisher API. These figures are NOT UkraineAlarm matches.
- Current `kyiv_threat_mix.json` meta: source Kyiv Digital `/air-alert/history`, 2026-10-01..28, episode-level causes assigned for whole alert; **intra-alert changes not reconstructed**.
- Official UkraineAlarm v3 `/alerts/regionHistory` retains at most **25 most recent region alarms**, and current UTC precision or exact Kyiv mapping have not been captured. Missing earlier events beyond the window = OUT_OF_COVERAGE, not absent.
- Token presence in available local executor = **false**. No protected token-capable shared-budget runner was available to this executor; CI intentionally has **no secrets**. Zero UkraineAlarm HTTP requests; HTTP status and body hash: null, `NOT_OBSERVED`. No production request budget risk.
- No observed `/regions` publisher body was available: `KYIV_CITY_REGION_ID=NOT_PROVEN`; `KYIV_CITY_SCOPE=NOT_PROVEN`; `HISTORY_DEPTH=DOCUMENTED_25_NOT_OBSERVED`; 0 eligible UkraineAlarm-vs-city timestamp comparisons.
- Neither municipal JSON nor Kyiv Digital API is evidence that current UkraineAlarm identifies Kyiv with equal geographic scope, timestamps or reason semantics.

## Isolated source & tests
`ua_kyiv_research_adapter.py`: strictly fixture-driven region mapping gate requiring independently established city territory parity and a primary capture hash; timestamp-aware completed AIR; fail-closed missing state; raw reason retention in hypothetical `activeAlertLevels`; current-poll change journal (observed time, NOT original publisher time); 25-item window classification, UTC/DST, 401/429/network guard placeholders and request spacing helper. No token or HTTP code; the production 70-second throttled client remains unchanged. This does **not** prove the SDK-shaped fixture matches live API.
`test_ua_kyiv_research_adapter.py`: synthetic scenarios only. Unique synthetic `synthetic-city-9001` is NOT a real Kyiv ID. Exact-SHA execution proof is Actions workflow `.github/workflows/c6-ua-kyiv01-offline.yml` and its log/artifact if completed. Never count fixtures as observed UkraineAlarm values or parity.

## Decision
**C (retain municipal-history + Kyiv Digital fresh completed tail)** is the only immediately defensible **operational** choice, pending new evidence; this is not a conclusion that UkraineAlarm is inaccurate. Future **B** becomes plausible only after primary `/regions` exact Kyiv city mapping, one coordinated GET `/alerts/{verifiedId}`, one `/alerts/regionHistory?regionId={verifiedId}`, 25-window exact-second comparison versus municipal+Kyiv Digital, and reason semantics at current-state. **A** requires stronger primary multi-cause semantics and history/transition retention (or an independently durable snapshot collection that meets the requirement), plus adequate coverage.
No branch promotion or change to site-prod/WIP, operational ingestion, Neon, data, mappings, casualty or persistence tracks. `PRODUCTION_INTEGRATION_AUTHORIZED=NO`, `NEON_WRITES=0`.

## Residual blockers
1. Secure, owner-coordinated shared-token runner / budget and 70-second spacing; no concurrent production updater.
2. Raw primary `/regions` with SHA-256 and complete city/oblast hierarchy; city-scope corroboration with municipal official JSON.
3. Real current-state and last-25 history raw-body hashes, status, headers (sanitized), timestamps, provenance and schema / precise cause values.
4. Exact same-region second-level parity for eligible October alarms; others `OUT_OF_COVERAGE`.
5. Distinguish `AIR` from flight/strike threat reasons; verify multi-reason state, reason changes and persistence after OFF.
6. Controlled live fixture replay/proof and source-specific review before any optional owner decision.
