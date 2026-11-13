# Changelog — recent accepted transitions

Newest first; current coordination lives in [PROJECT_STATE.md](PROJECT_STATE.md). Full historical text, SHA/Actions/artifact references and exact previous roots are preserved in the [archive index](docs/coordination-archive/README.md), verified by its manifest. Maintain 5–10 brief transitions; use the [archival CLI](docs/coordination-maintenance.md) before growth exceeds 12 KiB.

<!-- coordination:history:start -->
### CASUALTY-ONE-TIME-SOURCE-TRANSPORT-PASS-FACT-EXTRACTION-BLOCKED-01 — physical one-time transport PASS, facts BLOCKED (2026-11-13)

- [PR #118](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/118) live [Actions #43405970445](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43405970445) SUCCESS, head `fbc721e7`, ten T01–T10 HTTP 200, ten GET of ≤20, zero redirects/retries, 36/36 safety. ZIP [#14027391709](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43405970445/artifacts/14027391709) independently SHA256 `d43e81484c043d45a9ebee7435f041207303060590fb5ba0687bbaa1d9205bf3`. **Zero new structured fact reports, no source text/excerpts retained; no casualties credited/published. One-time grant consumed.** Next offline parser/retention diagnosis, no new HTTP without approval.

### CASUALTY-CURRENT-SITEPROD-FRONTEND-WORKH-01 — exact HEAD current frontend PASS (2026-11-13)

- [PR #114](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/114) `46728a37`, [CI #43397597547](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43397597547) 42+32 PASS, [ZIP #14023123111](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43397597547/artifacts/14023123111) independently SHA256 `c68ea1bc107a2d1a427ac57a7a086fc724998fd093ae37b4058098ddef753cc9`. Source→scratch PROMOTE→current frontend `INCOMPLETE/≥23`; 23 alert cities, Sumy +1, rollback intact. No live deployment or publication.

### CASUALTY-STRICT-REDIRECT-WORKI-OFFLINE-01 — exact redirect-path offline PASS (2026-11-13)

- [PR #115](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/115) `da49571a`, [CI #43397030680](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43397030680) 36/36; [ZIP #14023795533](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43397030680/artifacts/14023795533) independently SHA256 `e4780a0b3e19b8c4c45098751e5b36a58870b5b9f65fb6db9eb6f7057085c327`. Unknown redirects blocked before HTTP; authorization NOT_GRANTED, 0 source HTTP, production unchanged.

### CASUALTY-INTEGRATED-E2E-SHADOW-WORKF-01 — integrated saved-source E2E PASS only (2026-11-13)

- PR [#112](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/112) `2274276`, [CI #43387209190](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43387209190) SUCCESS; ZIP #14018663260 independently SHA256 `6416875ad6c618ff12fb3358392033e883085795e5e785d64525a8d42810a450`. 11+42 PASS, scratch REVIEW/PROMOTE→generator +23/replay 0→INCOMPLETE/≥23 chart. Current frontend untested; publication OFF.

### CASUALTY-CONTROLLED-CAPTURE-PREFLIGHT-OFFLINE-01 — bounded source-capture preflight PASS only (2026-11-13)

- PR [#111](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/111) `630c996`, [CI #43387015696](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43387015696) 12/12 PASS; ZIP #14019520132 independently SHA256 `a06147b9a566c372eca725fa083342e239ed229609c6c77939dbdd9021b7e71e`. 10 URLs/7 hosts/max 20 requests, 0 publisher HTTP; no owner consent. Same-host redirect-path guard must be fixed before pilot.

### CASUALTY-EVIDENCE-INGESTION-WORKE-01 — saved-source evidence ingestion offline PASS (2026-11-13)

- [PR #110](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/110) `6b44b976` [CI #43320351570](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43320351570) 10/10 PASS; [ZIP #13990550763](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43320351570/artifacts/13990550763) independently SHA256 `5d313e372e53f4afd9c2d9f412e0b30c9b9f41880fae94e6f404fd4a1126b7e5`. 3/1682 texts, 2 reports, 1 +23 shadow; 5 PR102 clusters blocked, source HTTP/regular capture OFF; no merge/live publish. Next joint offline E2E then separately approved bounded capture.

### CASUALTY-GENERATOR-DISPLAY-WORKD-01 — generator→INCOMPLETE chart/exports isolated PASS (2026-11-12)

- [PR #109](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/109) `62aef364`, [CI #43308531075](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43308531075) 42/42 PASS, [artifact #13985535590](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43308531075/artifacts/13985535590) ZIP SHA256 independently verified `86dff044fbe148fa4fe1d05eb24c3540f07e29d50a8d16f581527a59d2e7ca5a`. Real generator +23 -> qualified INCOMPLETE/≥23 chart, CSV/PNG/embed; rollback PASS; no live publication. Work E and joint release gate OPEN.

### CASUALTY-REVIEWER-DEDUP-CONTRACT-WORKC-01 — reviewer contract fixed in research, no adoption (2026-11-12)

- [PR #108](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/108) `fb3dcb7a`, [CI #43305347207](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43305347207) 11/11 PASS; [ZIP #13982783250](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43305347207/artifacts/13982783250) independently SHA256 verified `27e0f18fe97d0c150a6d9753784c53f483219ab85e2f1c59dc3cf3237c8c54e4`. Actual protected reviewer/promote → scratch ledger → pinned generator PASS. No merge, real writes or publication; Work D/E open.

<!-- coordination:history:end -->
