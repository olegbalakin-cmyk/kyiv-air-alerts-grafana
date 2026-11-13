# Changelog — recent accepted transitions

Newest first; current coordination lives in [PROJECT_STATE.md](PROJECT_STATE.md). Full historical text, SHA/Actions/artifact references and exact previous roots are preserved in the [archive index](docs/coordination-archive/README.md), verified by its manifest. Maintain 5–10 brief transitions; use the [archival CLI](docs/coordination-maintenance.md) before growth exceeds 12 KiB.

<!-- coordination:history:start -->
### CASUALTY-WORKN-FIRST-LAUNCH-PREHTTP-TEST-GATE-BLOCK-01 — separate PR #127 0-GET pre-HTTP failure; PR #128 live 3/3 proof stands (2026-11-13)

- [PR #127 run #43512279660](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43512279660) attempt 1 FAILURE, 66/68 pre-HTTP, capture SKIPPED, 0 GET, authorization consumed. This later run on `f18af39f` is separate from [PR #128 success #43510162714](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43510162714) (`5e5628a8`, 3 HTTP200/3 GET). #128 already fixed the launch-present test contradiction. System next task remains Work O offline evidence extraction; no new HTTP approval.

### CASUALTY-WORKN-T03T05-HTTP200-FACT-EXTRACTION-BLOCKED-01 — T03–T05 live capture 3/3 PASS; parsing BLOCKED (2026-11-13)

- Owner-approved [PR #128](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/128) launch `5e5628a8`, [run #43510162714](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43510162714) SUCCESS 3/3 HTTP200, 3 GET, 0 redirects, 68/68 safety. [ZIP #14076819100](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43510162714/artifacts/14076819100) SHA256 independently verified `dc7d1ba10d66e6b3e39f7f3a85fffbb7522e8930390117b139185e5eb6627da6`; all 4 JSON hashes match. 3 NEEDS_REVIEW cards, publisher parser reports 0 and no factual excerpts; police claims 3 without event link. 0 casualty credits/PROMOTE/publication. Single-use authorization consumed; no recapture until fresh owner approval.

### CASUALTY-WORKN-LAUNCH-STATE-FIX-OFFLINE-PASS-01 — Work N offline PASS and safety fix on independent branch (2026-11-13)

- [PR #127](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/127) `4ae85477`, [Actions #43507349125](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43507349125) 68/68 PASS, both artifact ZIP hashes independently checked. Live test/launch file contradiction fixed in [PR #128](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/128) `236d3d3a`, [CI #43508802671](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43508802671) 2/2 PASS incl 68/68 synthetic launch-present, ZIP #14076498074 SHA256 `2eb23ffc7fab82ee660f765becd147ca65609a24a1fc36f01a3b73d0ff3d5d84` checked. GET=0; new SHA-specific owner grant needed. No PROMOTE/production.

### CASUALTY-WORKM-PREHTTP-CI-FIX-OFFLINE-PASS-01 — Work M exact live-fixture pre-HTTP offline PASS (2026-11-13)

- [PR #125](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/125) `657fd705`, [CI #43504057015](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43504057015) 2 jobs SUCCESS, 68/68 PASS, 0 GET, 0 auto credits; [ZIP #14074633696](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43504057015/artifacts/14074633696) independently SHA256 `26e4b256a09d5f10d2307c2596c614cb1c12cca4dfe8a0e1f4c6e999c886016f`. Fixed `_pr102` and `_site` pinned fixture checkouts; new research-only code, no fresh launch. Earlier authorization consumed. New clean branch pin/preflight + owner GO still required before live T03–T05.

### CASUALTY-WORKL-FIRST-OWNER-LAUNCH-PREHTTP-CI-BLOCK-01 — real launch CI failure before HTTP (2026-11-13)

- Owner-approved Work L [run #43502247617](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43502247617) at `e1f9c3af` FAILED on missing `_pr102/.../capture_once.py` test fixture after owner-grant gate PASS; source capture SKIPPED, no artifact, 0 GET/0 casualty credit. One-time grant consumed, no retry; fix offline and seek fresh owner approval separately.

### CASUALTY-WORKL-THREE-SOURCE-LIVE-PREFLIGHT-OFFLINE-PASS-01 — Work L three-source pilot readiness PASS offline (2026-11-13)

- [PR #124](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/124) exact `78fd1472`, [Actions #43500434087](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43500434087) 68/68 PASS; [ZIP #14072718715](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43500434087/artifacts/14072718715) independently SHA256 `f3d8742828897bda7c102ce7a4d9cb985db18b784ad9ca94eb46c93a86feb2e0`; four inner JSON hashes MATCH. T03/T04/T05 one-shot trigger prepared; no source GET, no owner grant, special workflow availability pending; no automatic credits/publication.

### CASUALTY-WORKK-THREE-SOURCE-RUNNER-OFFLINE-PASS-01 — research-only three-source runner PASS (2026-11-13)

- [PR #122](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/122) `69e7d023`, [CI #43439055939](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43439055939) 59+10 PASS, [ZIP #14044811680](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43439055939/artifacts/14044811680) SHA256 independently verified `369c98cce533fe7e4fac0032d9f80b48b0c03cd86da578bce8f6bac2cfcbc766`. Three synthetic source cards and 4 hash manifest checks PASS. T03/T04/T05 HTTP not authorized; max 6 GET proposed, one-time only; no auto-credit or production publication.

### CASUALTY-PARSER-DIAGNOSTIC-WORKJ-OFFLINE-01 — research parser + bounded fact retention PASS offline (2026-11-13)

- PR [#121](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/121) `a92e2ddb`, [CI #43433677112](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43433677112) 45+10 PASS, [ZIP #14040641691](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43433677112/artifacts/14040641691) independently SHA256 `1d47ae01cb9395bc6c2de89ed55133eff8f0ec9c843b4712945e153c285aa595`. Proven retained +23 unchanged; new source facts need a separate 3-URL live permission after wiring cards into one-shot. Source GET 0, publication OFF.

### CASUALTY-ONE-TIME-SOURCE-TRANSPORT-PASS-FACT-EXTRACTION-BLOCKED-01 — physical one-time transport PASS, facts BLOCKED (2026-11-13)

- [PR #118](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/118) live [Actions #43405970445](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43405970445) SUCCESS, head `fbc721e7`, ten T01–T10 HTTP 200, ten GET of ≤20, zero redirects/retries, 36/36 safety. ZIP [#14027391709](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43405970445/artifacts/14027391709) independently SHA256 `d43e81484c043d45a9ebee7435f041207303060590fb5ba0687bbaa1d9205bf3`. **Zero new structured fact reports, no source text/excerpts retained; no casualties credited/published. One-time grant consumed.** Next offline parser/retention diagnosis, no new HTTP without approval.

### CASUALTY-CURRENT-SITEPROD-FRONTEND-WORKH-01 — exact HEAD current frontend PASS (2026-11-13)

- [PR #114](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/114) `46728a37`, [CI #43397597547](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43397597547) 42+32 PASS, [ZIP #14023123111](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43397597547/artifacts/14023123111) independently SHA256 `c68ea1bc107a2d1a427ac57a7a086fc724998fd093ae37b4058098ddef753cc9`. Source→scratch PROMOTE→current frontend `INCOMPLETE/≥23`; 23 alert cities, Sumy +1, rollback intact. No live deployment or publication.

### CASUALTY-STRICT-REDIRECT-WORKI-OFFLINE-01 — exact redirect-path offline PASS (2026-11-13)

- [PR #115](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/115) `da49571a`, [CI #43397030680](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43397030680) 36/36; [ZIP #14023795533](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43397030680/artifacts/14023795533) independently SHA256 `e4780a0b3e19b8c4c45098751e5b36a58870b5b9f65fb6db9eb6f7057085c327`. Unknown redirects blocked before HTTP; authorization NOT_GRANTED, 0 source HTTP, production unchanged.

<!-- coordination:history:end -->
