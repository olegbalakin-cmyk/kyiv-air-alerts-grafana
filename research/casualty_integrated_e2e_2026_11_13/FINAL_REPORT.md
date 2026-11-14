# WORK F — integrated casualty shadow proof

**Mode: SHADOW ONLY. No merge, production deployment, real casualty revisions, WIP writes, publisher requests, C2 or Neon.**

## Decision

**INTEGRATED_SHADOW_PASS (physical offline integration verified).** The successful physical GitHub Actions job checked the newly generated Work E/A outputs through Work C scratch REVIEW/PROMOTE, then the real post-PROMOTE production generator and Work D browser QA. The status does **not** establish regular autonomous 23-city monitoring or production publication readiness. The verification script fails closed.

## Inputs and immutable versions

- Main coordination: `main:PROJECT_STATE.md`, `main:CHANGELOG.md`; casualty coordination Draft PR #71 (read-only).
- Work A #105 `6a0100b0937218c62c5c079fd46e80e5071783cb`.
- Work B #106 `5441bdaf60b96e8efbb5019182ac7cf6a3c76da1`, defect-finding reference only.
- Work C #108 `fb3dcb7ad96f4265c7ee6455812ea53fdde0cf17`.
- Work D #109 `62aef3645c4bdc89940bc1ba05abe23c08d23142`.
- Work E #110 `6b44b9766fdbe2cd2d65a20413d08f4f5ca91916` (includes pinned Work A).
- Frozen WIP `43b580491d54d1df3bd84a0ae59a6987f8ea4d03`.
- Historical generator/site `d0a7d22de2828c93236562cccc9d2e68c6a66e3d`.
- Current read-only `site-prod@f0cfcbc862ca3dbf1b853e72de07ffcf6042856f`, observed on 2026-11-13.
- Original text artifact #13870872313; evidence JSON SHA-256 `84ffea1315d41b8ec67b55a07273d6bbd7d6e8e14191801402168f7fddf4e5df`; 10 Oct original-text SHA-256 `011894b7c4bd906dcfd0c5d2f7cef07a932976ca313220fa9089999264feb259`.
- PR #102 original transport receipts artifact #13963708531; receipts JSON SHA-256 `4c21321b8a75d57f60efc97f581e89604eaa03289bb64bfba26e491ac83a203b`; receipts do not contain article bodies.
- PR #88 group matrix `34bc539d0c7abb8af4f699b2e2c9ecec4b668397`.

## Integration method

The single research-only GitHub workflow checks out each exact immutable component separately; it does **not** merge incompatible PR bases. All derived output is under `/tmp` of a disposable Actions runner.

1. Work E processes saved real original text and creates `fact_cards.json` and validated `work_a_reports.json`, with source hashes and a cumulative 18 → 20 → 23 claim.
2. Work A consumes those exact newly generated reports via `--ingested-reports`, reparses the archived original, and produces one `AUTO_READY` +23 proposal. Five clusters lacking stored source text must stay blocked.
3. The new minimal `promote_generator.py` takes **that same newly generated proposal**, verifies the fact card and real frozen WIP entry, then reuses the **unchanged Work C** `build_preview` and `apply_preview` functions against private scratch queue and revisions. Actor `human-researcher` is solely an isolated software-test identity, **not a human verification, real authorization, or invocation of the protected GitHub workflow**. Required five dedup fields must survive the reviewer and PROMOTE.
4. Work C's full 11 safety regression tests run separately with the newly generated Work A proposal artifact.
5. The exact historical `site-prod` generator loads the newly promoted *scratch revisions file*, runs the actual `reconcile_confirmed_revisions` and `apply_city_revision_overlay`, and produces `generator_probe_after_promote.json`. The replay PROMOTE must be +0. Sumy +1 must remain unchanged; scratch rollback must restore original bytes.
6. Work D's existing `bridge.py` receives the **post-PROMOTE generator probe**, not Work A's prior direct proposal-generator fixture. It produces `INCOMPLETE / confirmed_minimum=23 / complete_total=null`.
7. Work D's unmodified local preview and actual Chromium `browser_qa.js` exercise the existing chart, hatching, tooltip, desktop, 375 px mobile, CSV, ChartShare PNG, embed, city switching, keyboard focus and clean rollback. The acceptance gate requires all 42 assertions.
8. A separate final verifier inspects outputs from every stage and emits a SHA-256 manifest. No source HTTP to publisher, no remote write or production mutation is permitted.

## Historical baseline vs current production

**Read-only git blob checks established:** `update_casualties.py` is the *same blob* `f5840c201c850b5312db611896b491a69f10e6ec` at both historical and current site-prod. `revisions.csv` is the *same blob* `8d7a2e2540bf4bf0f8c6227023821390bf82ce13`. The current dashboard JSON **differs** (historical blob `7a395b54cbba65676250ab196b189e84f23222f9`; current `f0ccce4e127ebd72dcf0a48aebb9b919b519cdc3`); current frontend `pages-preview/app.js` also **differs** (historical `313a011ab9a1ed9f82a544be9af1479ebeb01a53`; current `bc869cb71b7ddb39489c989323b59fdb5b87d6b3`).

The workflow therefore validates numerical generator compatibility with current production *separately*, but the 42 Chromium checks certify **the frozen historical frontend and source data**, not a production deployment nor browser compatibility with the current frontend. This is an explicit remaining adoption check.

## Critical negative and safety checks

- 18 → 20 → 23 cumulative total **23, never 61**: current saved-source proof and Work C regression.
- Repeat PROMOTE **+0**: actual Work C guarded scratch replay.
- Already credited 18 then 23 **+5**, two distinct same-day attacks, duplicate/cross-incident proof reuse, stale refs, human-only guard, missing/malformed evidence: Work C's 11 software regression checks on the combined CI.
- Missing original text, September pre-credited baseline unknown and October 5 late death: Work E/A evidence gates; remain `NEEDS_REVIEW`.
- Sumy confirmed +1; all other cities and original alert series; incomplete month/year; rollback: integration and browser checks.
- Publisher HTTP **0**; no new evidence fabricated.

These software negative fixtures are not independently established real fatal attacks.

## Open requirements for routine autonomous operation

1. Owner-authorized original source-body capture and retention for the 1,680 candidates without stored original factual text, with exact URL/rate/budget scope, attributable official confirmation, no automatic inference from publisher HTTP receipts or titles.
2. Resolve the five currently blocked Zaporizhzhia attack clusters and incident-level attribution of September's existing monthly credits; independently verify the October 5 potential late death and its prior credit.
3. Separate human/approval policy for moving proposals beyond shadow, safeguards against stale official updates, evidence contradictions, same-event duplicates and reprints.
4. An authorized, default-off-to-on scheduled integration of Work E → reviewer → generator; no such autonomous or production run is established.
5. Independent current-site-prod frontend/browser compatibility and real controlled rollout/rollback validation after separate owner approval.
6. Demonstrate source completeness and recall for 23 cities across time; a single confirmed example is not sufficient for publication safety.

**Even a successful isolated Work F run does not authorize casualty publication, does not establish full city coverage and does not imply unattended monitoring.**

## Proof and checkpoint

Workflow: `.github/workflows/research-casualty-integrated-e2e.yml`.

Proposed checkpoint (only if exact-HEAD physical proof succeeds):
`CASUALTY-INTEGRATED-E2E-SHADOW-WORKF-01`.

### Physical proof (2026-11-13 UTC)

- First integrated full-path SUCCESS: [GitHub Actions #43387002997](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43387002997) at code/CI HEAD `2d9e733f89297acf7e31341799fc46c49ccb0ed8`. Its uploaded artifact is [#14018768361](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43387002997/artifacts/14018768361), 1,809,299 bytes; GitHub API and uploader logs both give ZIP SHA-256 `3e3279f2ac237f8e90b5d8b35794ce2e9620be16466755d93ee3716d905f5b6e` (**GitHub reported, not independently downloaded/rehashed**).
- Final integrated verification output: `INTEGRATED_SHADOW_PASS: 18->20->23 -> Work E/A -> guarded scratch Work C REVIEW/PROMOTE -> actual generator -> Work D INCOMPLETE >=23 -> 42 browser checks; NO PUBLISH`. The independent manifest `/tmp/workf-proof-manifest.json` SHA-256 is `093fcc1cb3fb8a4b42353096c9c094121ffa4b50266ac9942cc71b1252c838ba`; its content is uploaded in the artifact.
- Actual scratch Work C run: `WORKF_PROMOTED_GENERATOR_PASS`; net +23, replay +0, all five fields kept, Sumy +1 kept, scratch rollback PASS, and unchanged current production generator accepts the private promoted ledger. Work C 11/11 PASS.
- Work D: 42/42 Chromium PASS including desktop, 375px mobile, tooltip, hatching, ≥23 label, CSV, ChartShare PNG, embed, city switch, keyboard focus, and clean isolated rollback. Browser artifact SHA-256 over sorted evidence files `48e60217249b270d90de483b02a0f326eaf2be103e56713fc861dfc69e965e14`.
- The first preliminary run failed the *final tracked checkout cleanliness check* only because Python tests generated untracked cache files; all actual Work E/A/C/D integration and 42 browser checks had passed. The narrowly amended final workflow explicitly checks tracked source modifications with `--untracked-files=no`; it never treats generated test caches as production source drift. The subsequent exact-code run succeeded.
- The follow-up edit to this report only does not change integration code or workflow semantics. A fresh exact-HEAD workflow is required to certify the final documentation commit; use the PR's newest Actions checks for final exact HEAD.

**Decision: `INTEGRATED_SHADOW_PASS` strictly for this archived source and frozen historical frontend. Source completeness remains unknown; current frontend browser compatibility remains untested; routine automation remains unauthorized. No change to PR #71 or production.**
