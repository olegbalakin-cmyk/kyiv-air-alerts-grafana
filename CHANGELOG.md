# Changelog

<!-- coordination:history:start -->
### CASUALTY-MONTHLY-23CITY-WEB-AUDIT-PARTIAL-2026-11-22-01 — 23-city source audit partial (2026-11-22)

- [Draft PR #233](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/233) 23 October city rows (12 with leads, 11 unknown), 27 candidate URLs; monthly OVA/MVA/UN scope differs from air-only city metric. Direct DNS prevented physical <=50 GET collection: 0 collector GET/receipts. Web-search examples only, no production/WIP changes. Next: manual fail-closed GitHub research one-shot, proof and reconciliation; PROMOTE OFF.

### CASUALTY-WORKAH-LIVE-3HTTP200-1NUMERIC-REVIEWONLY-2026-11-22-01 (2026-11-22)

- [Run #45020948794](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/45020948794) 3 HTTP200, numeric T03/T04 UNKNOWN, T05=3. Artifact #14753224774 ZIP SHA256 `549a3fc4b9389d6f43f89621c821ac6bd9a6ab8d1bd1e728381c103e9e765140`, inner JSON `4c724125346fb55b20c72313be5a22c13b19646a27e78aa97d080a72e476788c`. Identity unresolved, credits/PROMOTE OFF.

### CASUALTY-WORKAI-ARTICLE-GO-APPROVED-NOT-DISPATCHED-2026-11-22-01 (2026-11-22)

- GO `workai-article-20261122-001`, AH `2b3b5799`, 3 article GET/0 RSS, expiry 2026-11-23T12Z, SHA256 `da6b11752c0b60f38900f5fc311313cd4876f88bb70ce56722c8631df68079d8`; later used once by #45020948794.

### CASUALTY-WORKAI-OFF-DISPATCH-VERIFIED-2026-11-18-01 — owner OFF-dispatch verified (2026-11-18)

- [Actions #44326207596](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/44326207596): owner `workflow_dispatch`, exact AH `2b3b57991d035168d737f40b2239c15b01945776`, attempt 1; seven jobs SKIPPED incl. network. No HTTP/artifacts/credits. PR #198 registration PASS, article GO pending; PROMOTE OFF.

### CASUALTY-WORKAI-PR198-MANUAL-REGISTRATION-MERGED-2026-11-18-01 — owner-approved registration merge; OFF-dispatch pending (2026-11-18)

- [PR #198](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/198) `afdd4e7b` merged main@`ddb58809`, manual-only workflow, no auto GET. OFF dispatch #44326207596 verified.

### CASUALTY-WORKAH-OFFLINE-PASS-EXPIRED-GO-DISPATCH-UNVERIFIED-2026-11-17-01 (2026-11-17)

- [PR #177](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/177) `2b3b5799`, [CI #43709216154](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43709216154) 29/29 offline PASS, artifact #14159263098 ZIP SHA256 `144150a679f947e81569729a87039bb3614109d0f0aa0072538046b1603a70aa`, 3/3 inner PASS. Grant expired; zero GET/credits.

### CASUALTY-WORKAG-ARTICLE-FIRST-OFFLINE-PASS-LIVE-BLOCKED-01 (2026-11-15)

- [PR #174](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/174) `4d20b5f0`, [CI #43706844061](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43706844061) 20/20 offline PASS, artifact #14159030801 ZIP SHA256 `c340d32fddf9cf4d4aafb01499e3e0c513718b11c41937b49119b7769038f15a`. Four synthetic HTML, real sites unverified.

### CASUALTY-WORKAF-FILTER-ALLOWLIST-GO-OFFLINE-PASS-LIVE-BLOCKED-01 (2026-11-15)

- [PR #173](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/173) `37cf0b19`, CI #43702948168 12/12 offline, artifact #14157426485 SHA256 `e8ee113162701a86a701d96d90c602bc715307b7e03e22b7b688065720b4964a`. Atomic GO proof, earlier older workflows unguarded.

### CASUALTY-WORKAE-DUAL-RSS-PILOTS-RECONCILED-BUDGET-EXCEEDED-2026-11-15-01 (2026-11-15)

- Two physical RSS runs #43700780104/#43700806130 used one 6-GET GO for 12 GET; each 5/6 HTTP200, 115 links. A artifact #14156356307 SHA256 `28ad8b5cc105c81d87d15d04912af1285bf4c1bd62e52cacbfb6d4226770041d`; B #14156048863 SHA in prior log. 0 article GET.

### CASUALTY-WORKAE-SIX-DIRECT-RSS-ONESHOT-5OF6-2026-11-15-01 — one of two RSS runs (2026-11-15)

- [PR #171](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/171) `53c48f0b`, #43700806130 5/6 RSS200, 115 links, artifact #14156048863 SHA in prior checkpoint; duplicate six-GET GO noted in dual-run entry.

### CASUALTY-WORKAD-URL-WORKJ-FACTS-OFFLINE-PASS-SHADOW-PARTIAL-01 (archived evidence)

- [PR #170](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/170) `a502616d`, [CI #43697942529](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43697942529) 34/34 offline PASS; artifact #14155356566 ZIP SHA256 `99fe9eaad0ca0941caf693fe0c7ee2bc801d46f2073bd5909251446f5acc9510`. Work J numeric claims PASS fixtures only, opaque Google News URL unresolved, PROMOTE OFF.

### CASUALTY-WORKAC-BOUNDED-CAPTURE-OFFLINE-PASS-LIVE-BLOCKED-01 (2026-11-15)

- [PR #169](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/169) `1cd3e85f`, CI #43696226023 17/17 offline, artifact #14154303167 ZIP SHA256 `c45ae98be3dd0ab4e5bd0ffc9b23d31777032d2bb9b39e150c635bbd531695d9`; mocked only, no GET/credits.

### CASUALTY-WORKAB-SHADOW-OFFLINE-PASS-LIVE-BLOCKED-01 (2026-11-15)

- [PR #163](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/163) #43646987342 7/7 offline PASS, artifact #14133897958 SHA in archived proof. Shadow only, 0 live HTTP/credits; PROMOTE OFF.

### CASUALTY-WORKAA-CONTEXT-OFFLINE-PASS-EVIDENCE-PARTIAL-01 — TECHNICAL PASS / EVIDENCE PARTIAL (2026-11-14)

- [PR #160](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/160) `38b444df`, [CI #43643850083](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43643850083) 183 PASS/1 SKIP, artifact #14132887476 ZIP SHA256 `3cb896fd323aabad663ba6955404b1c6930a40e03603a3a26b107f927d0cfc06`; 15/15 hashes PASS. T04 incomplete, T03–T05 unlinked, 0 credits.

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

### CASUALTY-WORKN-FIRST-LAUNCH-PREHTTP-TEST-GATE-BLOCK-01 (archived evidence)

- Earlier Work N launch blocked before HTTP; [PR #127](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/127), see subsequent accepted Work N fixes. No source GET, casualty credit or production release.

### CASUALTY-WORKN-T03T05-HTTP200-FACT-EXTRACTION-BLOCKED-01 (2026-11-13)

- [PR #128](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/128) `5e5628a8`, CI #43510162714, 3 HTTP200; ZIP #14076819100 SHA256 `dc7d1ba10d66e6b3e39f7f3a85fffbb7522e8930390117b139185e5eb6627da6`, independent/4 inner PASS. Original parser insufficient; T03–T05 NEEDS_REVIEW, 0 credits. Grant spent.

### CASUALTY-WORKN-LAUNCH-STATE-FIX-OFFLINE-PASS-01 (archived evidence)

- [PR #127](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/127) `4ae85477`, CI #43507349125 68 PASS; [PR #128](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/128) `236d3d3a`, CI #43508802671 2 PASS, ZIP #14076498074 SHA256 `2eb23ffc7fab82ee660f765becd147ca65609a24a1fc36f01a3b73d0ff3d5d84`. 0 GET/PROMOTE.

### CASUALTY-WORKM-PREHTTP-CI-FIX-OFFLINE-PASS-01 (archived evidence)

- [PR #125](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/125) `657fd705`, CI #43504057015 68 PASS/0 GET, ZIP #14074633696 SHA256 `26e4b256a09d5f10d2307c2596c614cb1c12cca4dfe8a0e1f4c6e999c886016f` independent PASS. Fixture pins fixed, live GO needed.

### CASUALTY-WORKL-FIRST-OWNER-LAUNCH-PREHTTP-CI-BLOCK-01 — real launch CI failure before HTTP (2026-11-13)

- Owner-approved Work L [run #43502247617](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43502247617) at `e1f9c3af` FAILED on missing `_pr102/.../capture_once.py` test fixture after owner-grant gate PASS; source capture SKIPPED, no artifact, 0 GET/0 casualty credit. One-time grant consumed, no retry; fix offline and seek fresh owner approval separately.

<!-- coordination:history:end -->
