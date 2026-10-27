# H2 C4 — 79 historical source membership adjudications (offline, research only)

## Scope and original authority

Base: `main@2d865aa3578af896893fc964406222f67416b2d7`. Accepted source: `c23387942a6b3effafa612195582b1e56afe618f:research/neon_h2_19542_field_authority_containment_revalidation_2026-10-12.json`, Git blob `2abd72d10bdac896d3c4ed10c582c38aafb162af`, SHA-256 `c3827de8c0574c0305e5da1efe619da678faaa2e8a201150ac8fe5fa7f57bd8c`. Original independent Actions: [38248023146](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/38248023146), [38248253820](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/38248253820), both success.

Original 1,429 links: 286 originally accepted, 1,064 independently derivable and exactly 79 replay-derived. This audit is **only** about these 79; the original 1,429 identities, all 19,542 classifications, 6,863 H1 classifications, separate 25 UNBOUND cases, and all historical decisions/keys remain immutable.

## Research proposal (requires independent CI and coordinator acceptance)

| Individual disposition | Links | Historical evidence standard |
| --- | ---: | --- |
| Independently derivable (proposed) | **3** | Exact original offset-aware alert start, uniquely identical to accepted historical alert start (2); or two original offset-aware event clocks both inside one unique original alert interval (1) |
| Replay-derived only | **76** | Missing source-specific timezone (63); approximate/incomplete/unmatched clocks (9); unaccepted historical split-child assignment (2); an explicit clock does not equal accepted alert boundary (2) |
| Positive contradictions to accepted historical canonical rows | **0 demonstrated** | Two mismatched explicit clocks are **unresolved binding evidence**, not permission to alter accepted rows |
| Direct original accepted promotions | **0** | Original records do not expressly bind a persisted source-link key |

The 63 timezone cases are **Dnipro 37, Mykolaiv 26**. The source-specific historical timezone contract has not been identified in frozen originals or worker proofs. Code usage of `Europe/Kyiv` is inadequate. The remaining 16 non-timezone cases are individually explained in `registry.json`.

The three narrowly eligible original source rows are: Chernihiv `ec6494ce9e2adf86cfa18091`, Odesa `b49c1af64689c2f3468e3b4f`, and Odesa `c69a06bf7af6a025147a3de3`. No application keys or source memberships have been changed. Source link key equality alone is computational, **not** proof of full key-input historical authority.

## Independent offline verification

`registry.json` contains exactly 79 one-to-one accepted source-link keys with original Git commit, path, blob SHA, row index, raw canonical record SHA256, worker proof reference, UTC target interval, each missing prerequisite or bounded independent derivation, and status. `verify_independent.py` reads the original accepted audit and all selected city original frozen evidence plus original canonical chronology source slices directly from Git by exact commit. It checks original raw file hashes, all 79 exact link/key/parent identities, all original UTC intervals, 63 timezone cases, 16 others and 13 intentionally invalid cases. It does **not** consult Neon, rerun the classifier, fetch live URLs or accept a later replay as historical truth.

Run locally from a complete repository Git clone:

```bash
python3 research/h2_c4_79_historical_memberships_2026_10_27/verify_independent.py
```

Isolated GitHub Actions: `.github/workflows/h2-c4-79-memberships-offline.yml`, triggered only for this research branch; fetch-depth 0, read-only Git permissions, artifact receipt.

## Limits and specific next work

This is **NOT** acceptance of `C4 = PASS`. The 63 cases need dated/source-specific original timestamp or UTC-offset attestation traceable to that source (not an inferred timezone). The nine ambiguous clocks need independently contemporaneous exact timestamps/episode pairings. The two split cases need original child-by-event evidence; the other two need a documented independent original-to-canonical episode binding despite differing clocks. The separate H2 key-input authority, H1, 25 UNBOUND, global missing/extra and C5 gates remain open.

This research branch is submitted for coordinator review. Only **after coordinator acceptance** may a separate coordination-only change update `main:PROJECT_STATE.md` and append `main:CHANGELOG.md`. No Neon, production, source-data, classifier, casualty or backfill changes are authorized by this study.
