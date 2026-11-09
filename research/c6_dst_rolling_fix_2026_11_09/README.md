# C6 DST rolling corpus fix: baseline missing

**BLOCKED.** The retained inputs do not provide the complete raw baseline
needed to implement the requested preservation and provenance checks.
The frozen binding guards remain unchanged. A new regular C2 corpus is
ineligible. `publication_allowed=false; GLOBAL_CUTOVER=NO`.

Branch: `research-c6-dst-rolling-fix-2026-11-09`, from
`d99dc40f5b9135963f7ec876b21926813139a50b`.
Read `main:PROJECT_STATE.md` and `main:CHANGELOG.md`, and verified main at
`0546986e69f2bbd4d5507f80dada426775eb1489`. Its latest accepted checkpoint is
still `C6-UA-CURRENT-ONEGET-01`. Inherited research proposals are not accepted
main transitions. Neither root document is edited by this work.

## Baseline diagnosis

`binding_from_snapshot()` is the narrowest available validation point: it
receives all seven reader result sets before computing their hashes. No
generator call-site change would be needed. The missing input is the trusted
before-image needed to compare historical rows and permit specific changes
to checkpoints/runs.

The retained physical ZIP has the pinned digest
`b0aa64392cb2b682eae14faf15df5df45da3fc208d8c45323dffab63b3d4245e`.
Its manifest and all 14 member hashes match. GitHub metadata independently
confirms run `42487688608` completed successfully on `38539e51`, and artifact
`13619973574` has this digest. No artifact was downloaded or duplicated.

The ZIP stores calculation lineage, candidate JSON, selection diagnostics
and aggregate readback evidence. Its 32,647 lineage rows have only city,
UTC bounds, physical UUIDs and selection. They omit the full episode records,
source observations and ingestion service records. The active-row file is
empty. The four-case readback explicitly limits historical equality to
identities and boundaries.

An existing older readback fixture was checked against every pinned table
digest. This recovers exact rows for classifications and source links;
the events table is provably empty. It does not recover these required sets:

| Reader result set | Required pinned rows | Older fixture rows | Exact digest match |
| --- | ---: | ---: | --- |
| episodes | 32,918 | 31,977 | No |
| observations | 143 | 145 | No |
| checkpoints | 1 | 4 | No |
| runs | 188 | 169 | No |

The frozen Kyiv bundle covers 382 source rows, not this full snapshot.
Neither it nor the seven historical witnesses can fill these gaps.
An aggregate digest can confirm an independently recovered exact table;
it cannot identify permitted field differences in a changed checkpoint or run.
No increase in row count or new corpus SHA is accepted as append-only evidence.

`baseline_audit.json` records the counts, hashes, archive inventory and
missing inputs. Reproduce it without network access:

```sh
python -m research.c6_dst_rolling_fix_2026_11_09.audit_retained_baseline \
  --older-fixture /path/to/retained/readback-c2-fixture.zip
```

Exit 2 reports the expected BLOCKED result. The optional older fixture is the
already retained `research/neon_json_shadow_frontend_2026_10_31/fixtures/readback-c2-fixture.zip`;
its archive digest is recorded in the audit. No raw rows are copied into this patch.

## Targeted checks

The existing DST suite was executed here: **17/17 PASS**, Python 3.12.14.
`dst-tests.log` retains its output. The first attempt passed nine correction
checks, then two class setups failed because `requests` was missing. Reusing
the existing local test dependencies allowed the complete suite to pass.
No runtime installation or infrastructure change was needed.

The passing checks cover the frozen four-case result, exact integer arithmetic,
unchanged Kyiv intervals and auxiliaries, table/corpus and projection drift,
evidence changes, duplicate/deleted projection rows, rejection of reapplication
and the exact six-file offline rollback. The suite also exercises the existing
UTC union regressions and renderer. This reruns no physical or browser proof.

Safe additions and per-row preservation/provenance, new-row conflicts and
checkpoint/run transition rules are **not certified**. Their rolling tests
were not implemented because the required baseline is missing. Existing
aggregate drift rejection must not be described as rolling row-level coverage.
Runtime code and tests are byte-identical to the starting review commit.

## Required input and proposed checkpoint

Provide retained original reader rows for the four missing sets from snapshot
`504832:504832:` at `2026-11-08T14:01:16.871475Z`, bound to C2 corpus
`f8d2970565ad908d78c3daf004affc14b463897082971307ce56745cd80bce2a`.
They must reproduce the existing pinned counts and full ordered-table digests,
including legacy IDs, times, run references, observation hashes and all returned
provenance fields. A later database read is not an automatic replacement.
Reader field/type contracts, including empty result sets, must also be explicit
before permitting rolling inputs; this snapshot does not retain a complete
seven-table schema description.

`C6-DST-ROLLING-BASELINE-01 / BLOCKED` (proposed, pending acceptance):
the raw-row validation point is available, but the baseline lacks four required
result sets. Preserve the frozen correction and fail-closed guards. Resume
implementation only with verifiable baseline rows. Freshness, Work B and
production remain separate.
