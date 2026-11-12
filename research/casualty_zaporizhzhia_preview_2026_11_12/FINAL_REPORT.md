# CASUALTY-ZAPORIZHZHIA-PLUS23-OFFLINE-PREVIEW-01

**Decision: `PREVIEW_BLOCKED` — 2026-11-12.** Full isolated preview on frozen `site-prod@fc7261660bdee75ee59296ee94cc1189be6b1a22`. **No publication approval.**

- Verified exact-head preview: [GitHub Actions #43194939504](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43194939504), research HEAD `fceae84fd138eeca8ebab193f54249963d4c4d17`, runner **SUCCESS** (the diagnostic test intentionally records domain-level failures rather than concealing them).
- Domain test results: **19 PASS / 3 FAIL** (three failures are duplicate-event protection).
- [Immutable CI proof artifact #13932621688](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43194939504/artifacts/13932621688): ZIP SHA-256 **`ac81ada5acc493d309755becb4ddb0660b520d5ca8e746313fa031de5ec89735`**, 4,665,679 bytes.
- Earlier diagnostic [#43194680914](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43194680914): 18 PASS / 4 FAIL; one frontend probe false failure caused by cross-realm JavaScript array comparison. Research probe corrected before the final run. Frozen production code unchanged.
- Latest `main@375e69351e6a5aee1be16892821f7cdde2a8f21a`; `site-prod@fc7261660bdee75ee59296ee94cc1189be6b1a22` matched the frozen source at start. Production branch HEAD and pinned immutable Git input SHA-256 were compared before and after the isolated generator runs.

## Actual control and +23 diff

| Check | Physical result | Verdict |
|---|---|---|
| Existing generator creates previously missing October 2026 | New `2026-10` monthly row | PASS |
| October deaths | 23 | PASS |
| Date attribution | `attack_date=2026-10-10` creates October row, not November observation month | PASS |
| Zaporizhzhia total | 316 → 339 = **+23** | PASS |
| Zaporizhzhia meta confirmed_deaths | 316 → 339 | PASS |
| Previous 56 months | Bytewise-equivalent structured rows | PASS |
| Other city casualty series | Unchanged (excluding generated Kyiv timestamp only) | PASS |
| Air alerts and independent top-level series | Unchanged | PASS |
| Month order | Chronological, no duplicates | PASS |
| Repeat generator run, one unchanged revision row | No new deaths | PASS |
| Rollback: remove staged revision and regenerate | Baseline semantics restored, 316 deaths | PASS |
| Exact frontend `renderCasualties` monthly and annual functions | Node VM chart values PASS; monthly October=23, note total 339 | PASS |
| Real browser rendering / independent Netlify preview | Not executed; no deployment requested or allowed | NOT EXECUTED |
| Production inputs and site-prod branch | Original SHA-256 and HEAD unchanged | PASS |

The read-only trace is: `revisions.csv` → `load_revisions()` → `city_baseline_routes()` (`zaporizhzhia` as `validated_city`) → `apply_city_revision_overlay()` → `dashboard_data.json` → `casualties_by_city.zaporizhzhia.monthly` → frontend `renderCasualties()`. No production-code change is needed merely to create a previously missing month. The existing overlay creates it.

## Duplicate-event scenarios — blocking defect

These fixtures explicitly represent **the same original 10 October morning KAB strike**, with the same source candidate identity; they are **not unrelated deaths from the same date**.

| Already credited for the SAME strike | Expected newly added | Actual newly added | Verdict |
|---|---:|---:|---|
| 0 | +23 | +23 | PASS |
| 18 | +5 | +23 | **FAIL** |
| 23 | +0 | +23 | **FAIL** |
| Repeat same single CSV revision (regenerate) | +0 | +0 | PASS |
| Distinct confirmed rows containing cumulative 18, 20, 23 for same attack | final 23, not 61 | October 61 | **FAIL** |
| Duplicate `record_id` | Reject | Rejected by loader | PASS |
| Separately identified unrelated attack on same date (+7) plus original +23 | 30 | 30 | PASS |

**Precise defect:** `load_revisions()` checks only unique `record_id`. `apply_city_revision_overlay()` adds every confirmed `deaths_delta` by city and attack month. Neither recognizes a canonical incident identity across different `record_id` values or treats official totals 18 → 20 → 23 as snapshots, so duplicate reports for one attack accumulate.

**Smallest safe later fix:** before overlay, group confirmed records by provably canonical incident identity, distinguish cumulative final totals from incremental deltas, compare with deaths already credited for that identical incident, and apply only the positive missing difference. Fail closed when incident identity/credited amount is ambiguous. Do not subtract unrelated same-date deaths, and keep `revisions.csv` and frontend schema unchanged. A new code fix would require a separate, authorized draft and new full offline regression.

## Reproducible artifact

Files inside the GitHub Actions artifact:
`control.json`, `plus23.json`, `diff.json`, `rollback.json`, `repeat.json`, `metrics.json`, `test_fixture.json`, `frontend_probe.txt`, `test_log.txt`, `inputs_sha256.json`, `FINAL_REPORT.md`, `SHA256SUMS`.

Run from the research branch with `python research/casualty_zaporizhzhia_preview_2026_11_12/preview.py` after fetching immutable SHA objects from the workflow. The Python test recreates all dependencies in temporary directories, invokes the **original** `update_casualties.py --no-network` for every scenario, and strips only the two nondeterministic `generated_at` fields for semantic equivalence checks.

**Boundaries:** no change to production `site-prod/revisions.csv`, `site-prod`, WIP, `main`, `casualty_auto_review.py`, the air-alert pipeline, Neon, or deployment; no new media HTTP. Only isolated research code, artifacts and this report. Even a later `PREVIEW_PASS` would require a fresh current-site reconciliation and explicit owner approval before publishing.
