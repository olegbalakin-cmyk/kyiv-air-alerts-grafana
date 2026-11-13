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

**Pending exact-head physical GitHub Actions result.** Until the final workflow succeeds, verdict is **BLOCKED**; early CI failures are not evidence of a frontend defect. No claim of current-browser PASS or downloaded proof ZIP hash is made before exact-head verification.

## Release boundary

This test is not authorization to publish deaths. The 2026-10 Zaporizhzhia `≥23` remains a confirmed lower bound with incomplete source coverage. Five source-body-missing clusters remain blocked; historical credits and complete nationwide monitoring are not proven.

**Proposed checkpoint only after exact-head physical PASS:** `CASUALTY-CURRENT-SITEPROD-FRONTEND-WORKH-01`.
