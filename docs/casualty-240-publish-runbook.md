# Casualty partial-month Git-only contract — Issue #240 (NO PUBLISH)

**State:** research branch only. `PROMOTE=OFF`, `publication_allowed=false`. No release GO granted. This document is not a permission to mutate `main`, `site-prod`, Neon, actual revisions, or Netlify.

## Pinned read-only preflight — 2026-11-23

- `main@b35ca5c8d189a011c1b7158275f189a195192890`; read `PROJECT_STATE.md` and `CHANGELOG.md`. C6 watchdog schedule reliability remains OPEN.
- **Production baseline:** `site-prod@f7e0681ca6aa98405638dae7a63c884f4ed55d20`; last Git-only C2/Neon publish at 2026-11-23 07:16:11 UTC. Parent `9fce20812e441e44ec46fa21d65ce9c79dea9b39`. Re-pin this live SHA immediately before any future GO, because C6 keeps changing it.
- Relevant C6 proof: prior accepted `#45018970389` independent 23-city/same-release read-only PASS; physical scheduled `#44995863969` SUCCESS cited by state; check the **latest actual** C6 run, readback, six-JSON manifest and immutable artifact at release time. Historical Netlify `6b02d5edba0ff97b80b83052` READY+locked per accepted state; verify lock again, never infer current state from this historical receipt.
- PR #235 `17291da5ab7a682eabc1b9458685b2a2724b3d71` (13 candidate groups, no publish), PR #236 `270702ccc4a76d81ee8cc5b9cf73059fd19df025` (four reviewed October events, 11 incident deaths, CI #45073045655 SUCCESS), PR #237 `b8f29139bfde02fa85ff72ffec62465ce65495c7` (draft UI). PR #237 historically read from `site-prod` via `RAW_DATA_BASE`; its partial preview still uses a local October fixture, **not** this sidecar. Browser source-binding end-to-end remains a joint UI+data release gate.
- **Reproducible frozen evidence:** see `source_frozen_git_blob_shas` in sidecar. 20-city baseline, Kyoto audited baseline, three separate city baselines and city manifests, pinned September Sumy revision and byte-exact PR #236 four-event reviewed JSON. These are real Git blob SHAs, not invented `identity_proof` or `credited_proof` per-incident hashes.

## Semantics

Separate JSON `kyiv-air-alerts-grafana/data/casualty_partial_months.json` has exactly 23 keys, per-city `2026-09` and `2026-10`. **September is an incomplete existing baseline**, numeric 0 is allowed *only when the frozen source explicitly records 0*, and all `monthly_exact_total` fields are null. Kyiv Sept baseline 18 through Sep 15; Kherson 12 through Sep 17; Odesa 3 and Zaporizhzhia 4 through Sep 18. Sumy 3 frozen + one already confirmed Sep 20 revision = **4 existing**, not +1 new. Each city's original upstream coverage date differs. Labels should say `partial baseline`, not full September.

October is **four event lower bounds only**, not a month or annual exact total: Lutsk 6, Poltava 1, Ivano-Frankivsk 1, Khmelnytskyi 3; 19 unknown = JSON null, never zeros. 6 is not 5+1 again; Khmelnytskyi 3 is cumulative 2+one later hospital death, not additive; exclude Ivano-Frankivsk October 11 three military deaths and Kyiv oblast deaths outside the city. No new `revisions.csv` rows. The legacy Sumy record cannot be altered or rewritten as a new incident. Every entry has `is_complete=false`; the entire sidecar has `publication_allowed=false`.

The generator at `kyiv-air-alerts-grafana/scripts/build_casualty_partial_sidecar.py` operates locally and deterministically. It fails for any unexpected source byte, different baseline, extra incident ID, changed cumulative count, military/oblast/ground event, duplicate identity or missing provenance. It does not run the existing `update_casualties.py`, update `dashboard_data.json` or change the official exact-month/annual series. It intentionally does **not** invent `identity_proof`/`credited_proof`. A future real revision requires verified independent immutable provenance and the existing generator's `reconcile_confirmed_revisions` guard, plus a separate owner GO.

```sh
python3 kyiv-air-alerts-grafana/scripts/build_casualty_partial_sidecar.py --check
python3 -m unittest discover -s tests -p 'test_casualty_240_sidecar.py' -v
```

Read-only CI checks exact regenerated sidecar, source pins, Sep partial, October 4/19, prior months, 2026 annual parity, CSV null/export semantics, negative tamper cases and absence of writes. It produces a QA artifact; all tests run with no external source HTTP and with `contents: read`. **This alone does not prove browser rendering.**

## Deployment mechanism: one UI release, repeated data commits

The existing `app.js` already loads historical data from the raw `site-prod` GitHub JSON URL rather than Netlify's bundled `data.json`. Future UI integration must use the **exact canonical** `RAW_DATA_BASE + "casualty_partial_months.json"`, with validation, `publication_allowed` as a publication-policy flag rather than a data-quality promise, and an independently owner-enabled UI feature gate. No `main` or research branch URL is an acceptable production data endpoint. A cache-busting source commit/version query and readback must bind both JSON files to the same `site-prod` SHA or same accepted release manifest, avoiding mixed snapshots.

1. After coordinator verifies PR #237 and this PR together, request **separate owner GO for the single frontend release**. Bundle the JS + sidecar copying/build contract exactly once into a deliberately gated Netlify release; validate UA/EN/mobile charts and CSV with 23 live city series; relock Netlify; preserve disabled auto-publishing. **Do not do that in Issue #240.**
2. For every later casualty update, freeze a new baseline and source proof, run the builder/tests, obtain explicit owner GO for an exactly scoped `site-prod` JSON commit, verify the current C6 six-JSON manifest and `site-prod` HEAD before commit, update only the casualty sidecar, then read back Git bytes. No routine Netlify deploy. No alterations to `dashboard_data.json` for unverified monthly counts.
3. Keep the C6 four-hour pipeline completely separate: its six-JSON allowlist and writer/reader still own historic alerts. A casualty JSON update must **never** overwrite C6's latest `site-prod` commit or stale-base rebase data. Existing C6 UI-only race recovery is not an authorization to treat casualty changes as UI-only; conflict = STOP, new source capture / owner re-approval.
4. Require explicit release manifest with exact `base_sha`, proposed `head_sha`, SHA-256 of each staged JSON (including old/new sidecar and C6 assets), tests, artifact ID, reviewer signoff, C6 readback evidence, rollback target. No scripted publishing path is introduced here.

## First publication OWNER GO request template — **NOT SENT / NOT APPROVED**

**Requested action:** owner to approve future joint UI + casualty-data release only after new end-to-end browser QA. Production presently unchanged.

- Proposed source: Issue #240 Draft PR exact HEAD = **fill at review**, UI PR #237 exact HEAD = **re-pin at review**; baseline used in research `f7e0681ca6aa98405638dae7a63c884f4ed55d20`.
- Actual `site-prod` base SHA immediately before operation: **TBD** (never reuse frozen research base).
- Proposed `site-prod` head SHA: **TBD until assembled**, Git diff allowlist: **TBD**.
- Sidecar SHA-256 old/new, six C6 data hashes, binding/release manifest SHA-256: **TBD from generated physical artifacts**, no fake hashes.
- 23-city baseline parity + partial/unknown + annual + CSV + UA/EN/desktop/mobile browser: **TBD actual Actions run and immutable artifact**.
- Netlify prior deploy ID, lock state, one-shot release ID, readback proof: **TBD**.
- Rollback: revert only the explicitly approved UI commit/data commit, using the pinned prior `site-prod` JSON/Netlify deploy; protect all newer C6 commits, do not reset shared branch. STOP on any changed HEAD or mismatch.
- **Before written owner GO:** zero production writes, external media GET, automatic promotions, actual revisions, C2/Neon mutation, Netlify release or lock change.

## Open blockers

Research PR #236 contains reviewed URLs/identities but **not** independent immutable content hashes required to credit new deaths as actual revisions. October coverage remains incomplete. PR #237 needs an actual 23-city browser test against canonical `site-prod` sidecar JSON after staged integration. The versioned sidecar in this research branch is NOT present in `site-prod` and MUST NOT be advertised as live. The only branch write approved by Issue #240 is this isolated draft.
