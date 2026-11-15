# Changelog

<!-- coordination:history:start -->
### CASUALTY-WORKAE-SIX-DIRECT-RSS-ONESHOT-5OF6-2026-11-15-01 — real RSS proof, no casualty publication (2026-11-15)

- [Work AE PR #171](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/171) `53c48f0b`, offline CI #43699168963 40/40 PASS; isolated owner-GO commit `1ee89a1180425c09f669d1f4abb6cf68fb4fd569`, [Actions #43700806130](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43700806130) SUCCESS, [artifact #14156048863](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43700806130/artifacts/14156048863), uploader ZIP SHA256 `95898566c9dba46bf83a5f2c8711698078d9c3a4b5f55737f61306261423e41f` (not independently rehashed). 6 GET: Ukrinform 30/0, Radio Svoboda 20/3, Pravda 20/1, Interfax 25/0, Hromadske Radio 20/2 HTTP200; Espreso 403 (items/keyword candidates). 115 direct publisher-site HTTPS URLs; no article GET, retries, redirects or credits. Google News incremental coverage unknown. No WIP/prod changes.

### CASUALTY-WORKAD-URL-WORKJ-FACTS-OFFLINE-PASS-SHADOW-PARTIAL-01 — technical PASS / readiness PARTIAL (2026-11-15)

- [Draft PR #170](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/170) `a502616d5264d7fd5dfe649d6a256f1a984e67cb`; [CI #43697942529](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43697942529) SUCCESS 34/34 (AB7/AC10/AD17), [artifact #14155356566](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43697942529/artifacts/14155356566), ZIP SHA256 from uploader `99fe9eaad0ca0941caf693fe0c7ee2bc801d46f2073bd5909251446f5acc9510` (no independent ZIP rehash); 4/4 inner PASS. Synthetic URLs: 2 resolved, 1 unresolved, 1 blocked. Work J cumulative/delta/scope, dedup, HTTP security budgets PASS offline. No real Google News direct-link coverage proof; T03–T05 unlinked. Zero live HTTP/WIP writes/credits/PROMOTE; owner GO required for bounded pilot.

### CASUALTY-WORKAC-BOUNDED-CAPTURE-OFFLINE-PASS-LIVE-BLOCKED-01 (2026-11-15)

- [PR #169](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/169) `1cd3e85f`, [Actions #43696226023](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43696226023) 17/17 PASS, artifact #14154303167 uploader ZIP SHA256 `c45ae98be3dd0ab4e5bd0ffc9b23d31777032d2bb9b39e150c635bbd531695d9`, 3/3 inner PASS. Mock secure article capture/budgets PASS, 0 source GET/WIP credits; opaque links unresolved. Work AD adds Work J counts in research only.

### CASUALTY-WORKAB-SHADOW-OFFLINE-PASS-LIVE-BLOCKED-01 (2026-11-15)

- [PR #163](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/163) `4604004b`, [Actions #43646987342](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43646987342) 7/7 PASS, artifact #14133897958 ZIP SHA256 `7e7e1474f1dfd6c40ae336fead3045fd818413b0eaff8109f11fa52a5349c818` independently verified. Three mocked 23→22→23 city cycles, cursor recovery, replay +0, 3 T03–T05 NEEDS_REVIEW. No real HTTP, credits, live GO.

### CASUALTY-WORKAA-CONTEXT-OFFLINE-PASS-EVIDENCE-PARTIAL-01 — TECHNICAL PASS / EVIDENCE PARTIAL (2026-11-14)

- [Draft PR #160](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/160) `38b444dff0e9f1e363593aaa42dec4dc278743e0`; [Actions #43643850083](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43643850083) SUCCESS, 183 executed/1 expected skip, artifact #14132887476 SHA256 `3cb896fd323aabad663ba6955404b1c6930a40e03603a3a26b107f927d0cfc06` (independently rehashed by executor, 15/15 inner PASS). Index 1,683→3; incomplete T04 flagged; all T03–T05 pairs unlinked, 0 HTTP/credits. No AA merge or PROMOTE.

### CASUALTY-WORKZ-HTTP200-EVIDENCE-PARTIAL-01 (2026-11-14)

- [PR #145](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/145), [run #43609731091](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43609731091) PASS, artifact #14119860789 independently verified ZIP SHA `ea32abf6eaab69656608b891b272eef6f54ee286844d1f9f2fba217e64e117b8`. 3 HTTP200, all 3 pairs unlinked, 0 credits. One-shot owner grant spent.

### CASUALTY-WORKW-INTEGRATION-OFFLINE-PASS-01 (2026-11-14)

- [PR #141](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/141) `4e083db7`, [Actions #43589692637](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43589692637) PASS, artifact #14111553746 (SHA in PR). Offline 18→20→23=23/replay 0, operator hard-OFF, no credit. Work Y PR #147 later merged code to main, PROMOTE still OFF.

### CASUALTY-WORKX-INDEPENDENT-SCAN-EVIDENCE-OFFLINE-PASS-01 (2026-11-14)

- [PR #142](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/142) `b07a5957cb57ab8cf008d14373b15fa1db47b3af`; [Actions #43589727392](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43589727392) SUCCESS, 169 PASS/1 SKIP; artifact #14111089895 (SHA in PR). Independent 23-city 48h source discovery and excerpts offline-tested, 3 T03–T05 NEEDS_REVIEW, 0 credits, source HTTP OFF.

### CASUALTY-WORKV-REVIEWER-OPERATOR-OFFLINE-E2E-PASS-01 (2026-11-14)

- [PR #140](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/140) `663f3eebf300485e1fcf5ff8499629f0c3986719`; [Actions #43587369075](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43587369075) SUCCESS, artifact #14110980955 (SHA in PR). Offline reviewer→operator→generator: 18→20→23=23, replay +0, unknown proofs blocked, Sumy +1/22 cities unchanged, T03–T05 NEEDS_REVIEW. 0 live credits or PROMOTE.

### CASUALTY-WORKTU-CONTRACT-AND-LIVE-JSON-GATES-01 (2026-11-14)

- Work T: old main reviewer/operator contract mismatched production generator `f5840c20`; PR #105 shadow CI #43290975899 is not a live operator proof. Work V/Y later fixed this. Work U: Git Zaporizhzhia total 316, last validated September; live Netlify casualty JSON parity UNVERIFIED. T03–T05 no credits.

### CASUALTY-WORKR-OWNER-ONE-SHOT-HTTP200-CONTEXT-CAPTURE-PASS-IDENTITY-REVIEW-01 (2026-11-14)

- [PR #137](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/137), [Actions #43574791160](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43574791160) PASS, ZIP #14105343291 SHA256 `8248b426baa23d822b0ba92332137ab59c63146b648b22271c41af7ff0a3177b` independent/4 inner PASS. 3 GET/HTTP200, T03 2, T04 later +1 aged 69, T05 3 aged 37/38/69. Incident identity unverified, 0 credits; owner grant spent.

### CASUALTY-WORKR-IDENTITY-REVIEW-PREFLIGHT-SOURCE-REVIEW-REQUIRED-01 (2026-11-14)

- [PR #137](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/137) `f2f3a922`, CI #43573408615 153 PASS/1 SKIP, ZIP #14104883690 SHA256 `6ab3d7ec12d6973f8ea3f63bc6fe572364dba0c48eb514ff39b7e3ecfba8d76b`, independent/11 PASS; T03–T05 unlinked, 0 credits.

### CASUALTY-WORKQ-REAL-EXCERPTS-AUXCI-OFFLINE-PARTIAL-01 (2026-11-14)

- [PR #135](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/135), [Actions #43571952329](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43571952329) 145 PASS/1 SKIP, ZIP #14104761484 SHA256 `90ec4ef12c967facc743914316da41e99b6d9d0237350b16437cd820bad451d5`, independent/10 inner PASS. T03 2, T04 additional age 69, T05 3 unbound; 18→20→23 PASS, 0 credits or new HTTP.

### CASUALTY-WORKP-T03T05-HTTP200-EXCERPTS-PASS-TOTALS-PARTIAL-01 (2026-11-14)

- [PR #132](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/132) `e0be1f3d`, run #43521321878 3 HTTP200; ZIP #14082589637 SHA256 `67133a7b2e94fdcdf8c1a4bf3871788b691e35b3666430b976e082355675b99f` independent/4 hashes PASS. T03/T04 totals NULL, T05 3 unmatched, 0 credits. Grant consumed, auxiliary CI #43521321898 failed.

### CASUALTY-WORKO-PARSER-EVIDENCE-PARTIAL-REAL-HTML-REQUIRED-01 (2026-11-13)

- [PR #129](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/129), [Actions #43513881396](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43513881396) 133 PASS/1 SKIP, ZIP #14079821808 SHA256 `adf9cbc56c52e4c0f102035160a6ed10cddc2e3229a1e4dc3e7ddbf97326f8ff`, independent/7 inner PASS. Parser fixes; T03/T04 raw HTML missing, T05 identity unverified. No live HTTP or publication.

### CASUALTY-WORKN-FIRST-LAUNCH-PREHTTP-TEST-GATE-BLOCK-01 — separate PR #127 0-GET pre-HTTP failure; PR #128 live 3/3 proof stands (2026-11-13)

- [PR #127 run #43512279660](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43512279660) attempt 1 FAILURE, 66/68 pre-HTTP, capture SKIPPED, 0 GET, authorization consumed. This later run on `f18af39f` is separate from [PR #128 success #43510162714](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43510162714) (`5e5628a8`, 3 HTTP200/3 GET). #128 already fixed the launch-present test contradiction. System next task remains Work O offline evidence extraction; no new HTTP approval.

### CASUALTY-WORKN-T03T05-HTTP200-FACT-EXTRACTION-BLOCKED-01 (2026-11-13)

- [PR #128](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/128) `5e5628a8`, CI #43510162714, 3 HTTP200; ZIP #14076819100 SHA256 `dc7d1ba10d66e6b3e39f7f3a85fffbb7522e8930390117b139185e5eb6627da6`, independent/4 inner PASS. Original parser insufficient; T03–T05 NEEDS_REVIEW, 0 credits. Grant spent.

### CASUALTY-WORKN-LAUNCH-STATE-FIX-OFFLINE-PASS-01 — Work N offline PASS and safety fix on independent branch (2026-11-13)

- [PR #127](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/127) `4ae85477`, [Actions #43507349125](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43507349125) 68/68 PASS, both artifact ZIP hashes independently checked. Live test/launch file contradiction fixed in [PR #128](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/128) `236d3d3a`, [CI #43508802671](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43508802671) 2/2 PASS incl 68/68 synthetic launch-present, ZIP #14076498074 SHA256 `2eb23ffc7fab82ee660f765becd147ca65609a24a1fc36f01a3b73d0ff3d5d84` checked. GET=0; new SHA-specific owner grant needed. No PROMOTE/production.

### CASUALTY-WORKM-PREHTTP-CI-FIX-OFFLINE-PASS-01 — Work M exact live-fixture pre-HTTP offline PASS (2026-11-13)

- [PR #125](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/125) `657fd705`, [CI #43504057015](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43504057015) 2 jobs SUCCESS, 68/68 PASS, 0 GET, 0 auto credits; [ZIP #14074633696](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43504057015/artifacts/14074633696) independently SHA256 `26e4b256a09d5f10d2307c2596c614cb1c12cca4dfe8a0e1f4c6e999c886016f`. Fixed `_pr102` and `_site` pinned fixture checkouts; new research-only code, no fresh launch. Earlier authorization consumed. New clean branch pin/preflight + owner GO still required before live T03–T05.

### CASUALTY-WORKL-FIRST-OWNER-LAUNCH-PREHTTP-CI-BLOCK-01 — real launch CI failure before HTTP (2026-11-13)

- Owner-approved Work L [run #43502247617](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43502247617) at `e1f9c3af` FAILED on missing `_pr102/.../capture_once.py` test fixture after owner-grant gate PASS; source capture SKIPPED, no artifact, 0 GET/0 casualty credit. One-time grant consumed, no retry; fix offline and seek fresh owner approval separately.

<!-- coordination:history:end -->
