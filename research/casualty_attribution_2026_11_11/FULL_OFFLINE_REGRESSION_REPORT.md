# CASUALTY-ATTRIBUTION-FULL-OFFLINE-REGRESSION-01 — PASS

Date: 2026-11-11. **Research-only, 45/45 PASS; no production approval, merge, deployment or publication.**

## Scope and immutable inputs

- Research input HEAD: `de41094cbe9cf1b34ac9c24f230941564b2cc3dc`.
- Offline CI workflow-only commit: [`adb0419c8191c55d48395c41204eacebade29ec3`](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/commit/adb0419c8191c55d48395c41204eacebade29ec3).
- Successful complete regression: [Actions #43034383784](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43034383784), full verdict [artifact #13863350735](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43034383784/artifacts/13863350735). This immutable run passed on exact head `adb0419c8191c55d48395c41204eacebade29ec3`.
- Previous broad [Actions #43024467127](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43024467127) was 44/45 with one `FileNotFoundError`, not an assertion failure. The pre-existing focused [Actions #43024613349](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43024613349) passed 10/10.

## Original legacy fixture origin and integrity

The **actual original** `research/casualty_automated_review_2026_11_10/cached_evidence.json` was found on branch `research-casualty-automated-review-2026-11-10`, introduced at immutable [commit `05ce47b1a92374af6c44c662f2d31f041a8f8afc`](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/commit/05ce47b1a92374af6c44c662f2d31f041a8f8afc). Its Git blob SHA-1 is `26a54c68892f2304a0abb4be2bbe739bcc645b3d`.

Original fixture SHA-256, independently calculated from GitHub file bytes, cross-checked against that revision's historical `results/manifest.json`, and checked again with `sha256sum -c` in Actions:
`4dad9a007db2e396b8d2f03e9db49b5eaa98707fe7f390341399a5b0966a51b3`.

The same legacy test also reads `research/casualty_automated_review_2026_11_10/results/events.json`. The original was recovered **from the same immutable commit**; Git blob SHA-1 `6c254cfd48c65bde06229d231ee3098374aba6e2` and verified SHA-256 `c82ac990755bc2015fc01cb5c52881edd7b3d9f72af7e49230b5c14838d39339`, matching the historical manifest.

Both files were copied only into the **ephemeral GitHub Actions runner**, by checking out the pinned legacy commit into a separate directory. They were not added to the research Git branch. No synthetic replacement was used.

Frozen article input was the **previously captured** [artifact #13845600971](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42998990269/artifacts/13845600971); ZIP SHA-256 `3fa949194a80d70c23ea3d6f757878f770bff6e1345f7787e51ff9df67341503`; inside `evidence.json` SHA-256 `68ceccdcca68a0c93d42a0c0173c32c9ab47b659415e9bd2b274df8d9cf0fdf9`.

## Complete test execution

- Command: `python -m unittest research/casualty_attribution_2026_11_11/test_replay.py kyiv-air-alerts-grafana/tests/test_casualty_auto_review.py -v`.
- **Ran 45 tests; 45 passed; 0 failures; 0 errors**, including the previously failing `test_real_controls_and_existing_noop`.
- Actions job steps: exact pinned legacy checkout PASS; both historical fixture SHA checks PASS; original article evidence SHA check PASS; test suite PASS; six-input before/after hash comparison PASS.
- Full per-test output, provenance marker, SHA before/after, integrity verdict and `verdict.json` are retained in [artifact #13863350735](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43034383784/artifacts/13863350735). Artifact ZIP digest: `14e7c469833117bb1a4a22ee0d5c34ea8700b8925be24d9811b90e7d128c69d3`.

## Behavioral and replay proof

Frozen `verdict.json` shows:
```json
{
  "before_auto_ready": 0,
  "after_auto_ready": 0,
  "after_new_proposals": 0,
  "replay_new_proposals": 0,
  "after_event_status": {
    "dnipro": "NEEDS_REVIEW",
    "odesa": "NEEDS_REVIEW"
  },
  "odesa_incident": {"city_key": "odesa"},
  "odesa_attribution": "city-mva",
  "protected_inputs_unchanged": true,
  "publication_allowed": false,
  "proposals_for_offline_analysis_only": []
}
```

- **Odesa:** no spurious `+1` from mixing three independent incidents; held `NEEDS_REVIEW` because unique attack identity is still insufficient.
- **Dnipro:** remains `NEEDS_REVIEW`, with unproven direct attribution.
- **Unambiguous single attack:** control remains `AUTO_READY` and offers `+2`; repeated calculation produces zero additional proposals.
- **Duplicate suppression:** frozen replay creates no new proposals.
- **Integrity:** all six protected input files have identical SHA-256 before and after the suite.

## Decision and limitations

**FULL OFFLINE REGRESSION PASS; fixture blocker RESOLVED.** No additional blocker remains for completing *this narrow offline regression*. This does **not** certify general Ukrainian incident segmentation, live source completeness or production-safe automated publication. Any promotion requires a separate decision and evidence; `publication_allowed=false` remains in force.

No changes to `casualty_auto_review.py`, death confirmation policy, WIP queue, `revisions.csv`, production, `main`, deployment, Neon/C6 or media HTTP.
