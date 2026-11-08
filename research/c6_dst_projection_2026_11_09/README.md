# C6 historical DST calculation correction

**OFFLINE_CORRECTION_READY_FOR_REVIEW.** A versioned, default-OFF projection
exception removes the four known defects from historical calculations without
changing Neon. `publication_allowed=false; GLOBAL_CUTOVER=NO`.

The branch starts at generator implementation `38539e51e1ebdd3143d50d627f8f147f76a23821`.
Main was read and verified at `0546986e69f2bbd4d5507f80dada426775eb1489`.
Its latest accepted coordination checkpoint is still C6-UA-CURRENT-ONEGET-01.
The documentation updates here are review-pending research proposals. PR #42,
#44 and #45 are unchanged; this branch does not accept or merge those drafts.

## Decision and implementation

Use the existing `neon_json_shadow_generator.py` and its accepted pure builders.
The explicit option `--dst-correction c6-dst-projection-v1` enables the new
calculation layer. Omitting it keeps the previous projection. No workflow,
production writer, frontend, CSV exporter or publication route is enabled.

The correction operates after physical-parent projection/lineage construction
and before the city metrics and shared historical analytics are finalized:

- Exclude exactly the three confirmed bad UUIDs from calculation lineage, with
  exact city, UTC boundaries and accepted legacy-ID bindings.
- Add exactly seven accepted source-witness intervals. They carry their legacy
  IDs and evidence hashes, `physical_uids=[]`, explicit calculation-only
  provenance, and `physical_neon_observation=false`. No Neon UUID is invented.
- Preserve Cherkasy UUID `ff046d6c-fc7e-4cd2-9470-3e5433c3d582` and every
  unrelated interval. Never rebind classifications or mutate the snapshot.
- Rebuild the four city metric subtrees through the same adapter functions;
  use the existing shared comparison/profile/derived/historical phase. Keep
  casualty and both explicit Git auxiliary dependencies unchanged.
- Put the version, exact exclusions, replacements, SHA evidence bindings and
  arithmetic in `dst_correction.json` and the output provenance metadata.
  Physical DST repair certification remains false.

`scripts/c6_dst_projection.py` pins both the complete saved projection and the
original readback binding: C2 corpus hash, counts and all seven table content
hashes. These include episode UUIDs, legacy IDs, UTC bounds and version data.
It also pins all four evidence files and their schema. Any changed/missing row,
schema field, evidence byte, candidate collision, source conflict, unknown
version or changed input corpus stops generation; there is no Git-data fallback.
The seven source witnesses are an explicitly declared historical exception,
not new physical Neon observations or a current source capture.

This v1 is deliberately restricted to the retained corpus. A later scheduled
snapshot or changed corpus will fail its guards and requires a reviewed
evidence/version update. Input/reader schema drift is covered; this offline
work makes no new claim about a live database catalog after the accepted
readback. Automatic schema migration, current-source certification and dynamic
production activation are outside this patch.

## Evidence reused

| Evidence | Immutable identity |
| --- | --- |
| Accepted DST evidence | `7265e40af6d012267ada515e9cac415f3e1e24b7`, C6-DST-UTC-01 |
| Seven source witnesses | `741f277f73d1dde1325069d25fa00b44a42d6f03` |
| Original source bridge | Git blob `9910c5793de9fdb400aa6525b9c096949152deac`; seven exact raw-event matches, retained subset in `source_witnesses.json` |
| Physical DST readback | `9ba2c04ca7cf187bacf35efa05e5c267be6dc6cb`; imported public evidence bytes unchanged |
| Existing physical JSON | Actions **42487688608**, research `38539e51`, artifact **13619973574** |
| Pre-cutover constraints | PR #45, `3e08daf4e3efc33fa1b02664e5cb96af8500de81` |

The existing physical artifact ZIP is retained in `evidence/` (SHA-256
`b0aa64392cb2b682eae14faf15df5df45da3fc208d8c45323dffab63b3d4245e`).
Its manifest and 14 files were verified. The new offline command consumes its
saved calculation lineage and six-file candidate. It does not reconstruct a
physical snapshot or rerun the physical proof. No private full-row artifact is
published. Source-subset extraction was checked against the accepted Git blob,
with no source HTTP.

## New offline checks

**17 tests PASS** in `tests/test_c6_dst_projection.py`, with network sockets
blocked. Machine results and exact output hashes are in
[`evidence/offline-machine-verdict.json`](evidence/offline-machine-verdict.json).

| Calculation | Episode change | Duration change, microseconds |
| --- | ---: | ---: |
| Kharkiv | +1 | -3,311,259,182 |
| Poltava | +1 | -3,042,657,209 |
| Zhytomyr | +1 | -2,962,107,438 |
| Cherkasy | +1 | +256,663,871 |
| Total | **+4** | **-9,059,359,958** |

Saved calculation intervals: **32,647 → 32,651**. These are projected intervals,
not physical row counts. Other intervals are exactly equal. Kyiv retains all
**2,819** intervals and its exact JSON bytes. The other 19 city metric/history
subtrees and their table/profile/heatmap entries are unchanged. Four daily
counts change only on 2026-10-25. Casualty objects and both auxiliary files are
preserved. JSON fields, row shapes and value types consumed by the current
frontend/CSV remain equal, apart from optional provenance metadata. The CSV
exporter and frontend code were not edited; no browser/CSV runtime proof was
repeated. The historical index remains verified and matches the dashboard.

Default OFF / rollback restores the prior six candidate files byte-for-byte
and restores the prior lineage. Drift checks cover every bound table, corpus
count/hash, projection field/row, missing/changed evidence and unknown version.
Reapplying the correction to already corrected lineage fails closed.

For reproducibility, use the pinned builder checkout
`site-prod@f60214c61de08cef677e90f158e2824d90bc324b` and its normal requirements:

```sh
C6_TEST_SITE=/path/to/pinned/kyiv-air-alerts-grafana \
  python -m unittest -v tests.test_c6_dst_projection

python -m scripts.c6_dst_projection_offline \
  --site /path/to/pinned/kyiv-air-alerts-grafana \
  --output /tmp/dst-corrected --dst-correction c6-dst-projection-v1

# Default OFF: produce the exact previous projection in a new directory.
python -m scripts.c6_dst_projection_offline \
  --site /path/to/pinned/kyiv-air-alerts-grafana --output /tmp/dst-rollback
```

Both commands consume only retained data. Existing output directories are
refused and failed calculations expose no candidate. The corrected six-file
set, lineage and receipt are retained as
[`evidence/corrected-offline-candidate.zip`](evidence/corrected-offline-candidate.zip).
It is a frozen research artifact with publication disabled.

## UTC prevention patch

`kyiv-air-alerts-grafana/scripts/apply_ukrainealarm_bridge.py:union_alerts()`
now sorts start times and performs both boundary comparisons in UTC. It retains
the existing timezone representation, source label and touching-interval policy.
Regression checks cover the four accepted cases, fold ordering, end extension
across the repeated hour, touching intervals and empty input. The original
function fails all four accepted case witnesses; the patched function passes.
The patch is research only and has not reached production.

## Schema comparison and remaining gates

| Route | Required change | Provenance and rollback | Decision |
| --- | --- | --- | --- |
| Calculation projection | Explicit versioned seven-witness exception in the existing reader/generator; no database schema or writer changes | SHA-bound exclusions and source witnesses; original physical records retained; OFF restores prior exact projection | Shorter path for this historical site; offline ready for review |
| Physical supersession | At minimum, an immutable correction version/header, old-episode exclusion mapping and replacement-episode/source mapping, selected by explicit reader version | Retain original UUIDs/before-images and source identities; select previous version for rollback; prevent writer reactivation/double counting | Unnecessary for the requested projection; still requires separate schema/writer/reader design and physical proof |

No DDL is proposed or executed. A physical route would need the writer to
respect the versioned exclusions and the reader to count only that version's
replacement set. Existing v1 episode-state and canonicalization constraints do
not provide that mechanism. This patch avoids that dependency by preserving the
database and applying the exception only to the named calculation view.

The next step is review of this bounded patch. Production cutover still needs
the per-city historical source/corpus bindings and reviewed source-switch /
operational rollback from PR #45. No SQL transactions, Neon writes, GRANT/DDL,
source HTTP, C2 export, historical parity, physical JSON proof, browser QA,
production deployment or PR #42/#44/#45 mutation occurred in this work.
