# WORK H — Current site-prod frontend integration QA

**Scope:** research-only, offline local Chromium. Do not merge, deploy, publish casualty data, touch WIP, production revisions, C2 or Neon.

## Pinned actual inputs

- Current site-prod: `f0cfcbc862ca3dbf1b853e72de07ffcf6042856f` (verified branch head on 2026-11-13).
- Historical site: `d0a7d22de2828c93236562cccc9d2e68c6a66e3d`.
- Work F: `2274276ebf962e3e9917d59024ea624fd3bdbb95`, Actions #43387209190 `INTEGRATED_SHADOW_PASS`, frozen original source archived externally in pinned Actions inputs.
- Work C: `fb3dcb7ad96f4265c7ee6455812ea53fdde0cf17`.
- Work D: `62aef3645c4bdc89940bc1ba05abe23c08d23142`.
- Work E: `6b44b9766fdbe2cd2d65a20413d08f4f5ca91916`.

## Narrow design

The CI takes original retained evidence and frozen WIP, reruns the **unchanged pinned Work F integrated chain** and Work D bridge on disposable scratch output, then qualifies only the verified 2026-10 Zaporizhzhia row into the *current site-prod dashboard*. No synthetic dashboard fixture is supplied. Source identity, Work C scratch PROMOTE, repeat +0, Work D source SHA, generated count 23 and the original Sumy revision +1 are fail-closed requirements.

Unlike Work F, the local preview and its rollback read actual **current** site-prod `pages-preview/` and `data/` files. The existing Work D overlay remains a separate research-only script, not a production frontend modification. The current dashboard’s alert series for all 23 cities, other 22 casualty cities, all unrelated keys and all original Zaporizhzhia months must be unchanged.

Actual Chromium checks reuse Work D’s 42 browser assertions (hatch, `≥23`, tooltip, CSV, PNG, embed, annual lower bound, 375 px, city switch, keyboard navigation and rollback) and add independent current-frontend checks for alert charts, current KPI, comparison, trend, period switches, errors, external requests and desktop/mobile screenshots.

The workflow is a restricted branch-push-only, read-only GitHub Actions job. Only `/tmp` is used for generated JSON, screenshots, downloads and test evidence; exact tracked checkouts are checked for unchanged state.

## Verification status

**Result: CURRENT_FRONTEND_INTEGRATION_PASS (SHADOW ONLY).** Physical GitHub Actions [#43397364341](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43397364341) completed **SUCCESS** at code HEAD `57120451716da26aa6d0291889b8929cbba3fcc0`. Work F physical 18→20→23, Work C scratch REVIEW/PROMOTE +23 and second PROMOTE +0, unchanged current generator, Work D bridge and current JSON rebase all PASS. Existing Work D browser suite **42/42 PASS** (with one explicit test-only absent-month rollback compatibility adjustment), additional current frontend regressions **32/32 PASS**. No JS page errors, no external publisher requests, 23/23 alert city records and other 22 casualty cities unchanged, Sumy +1 retained, original current dashboard/frontend rollback PASS. Desktop, mobile 375 px, CSV, PNG, embed screenshots and trace evidence uploaded.

Proof artifact [#14023477976](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43397364341/artifacts/14023477976), size 9,166,961 bytes. GitHub API reported ZIP SHA-256 `eb14f92eedcae31e37ce1679585e471ead4ab0acc525337a1bdba56956572971` (**API reported, ZIP not independently downloaded/rehashed**). Independent workflow manifest SHA-256 `d54e99167aa76c1ea8114cec1c81f145cdeb4823033d44c4770a9a07d0ee44ad`; screenshot concatenated proof digest `34b58c20766e34c63fddc60f23503317a3a20dfca567747a6558574206706f71`. The final report-only commit must also receive an exact-HEAD workflow PASS before coordinator acceptance.

Earlier physical failures diagnosed **test adapter assumptions**, not new production failures: the generator adds city provenance metadata; missing October can appear as null rather than zero; and original Work D test rollback absolute /data/ would fetch the preview dashboard. The Work H isolated rollback routing now fetches the actual original /rollback/data/, while all production frontend/data files stay untouched. The test-only copy of Work D's 42-assertion script changes only the missing-month null/zero rollback assertion.

## Release boundary

This test is not authorization to publish deaths. The 2026-10 Zaporizhzhia `≥23` remains a confirmed lower bound with incomplete source coverage. Five source-body-missing clusters remain blocked; historical credits and complete nationwide monitoring are not proven.

**Proposed coordinator checkpoint (subject to final exact-head Actions):** `CASUALTY-CURRENT-SITEPROD-FRONTEND-WORKH-01`.
