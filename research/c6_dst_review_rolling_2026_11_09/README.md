# C6 DST recurring corpus review

**BLOCKED.** The correction remains restricted to its frozen input.
Compatibility with recurring corpus growth has not been established.
`publication_allowed=false; GLOBAL_CUTOVER=NO`.

Review date: 2026-11-09. Branch:
`research-c6-dst-review-rolling-2026-11-09`, starting at
`14e1b0b9a63d8471591a804cbd8e44aadc9cd120`.

## Review result

The existing full-binding guard must remain. Replacing it with a check of
the three target UUIDs and seven witnesses would remove protections that
the projected lineage cannot replace.

| Input to `apply()` | Information available | Limit for recurring use |
| --- | --- | --- |
| Lineage | City, UTC bounds, physical UUIDs, selection | No legacy IDs, source observations, run records or table schemas |
| Binding | Counts, seven whole-table SHA-256 digests, C2 corpus digest | A new digest does not identify which rows were added, changed or removed |
| Pinned evidence | Historical identities, boundaries, witnesses, evidence SHA | Does not establish the contents or provenance of a later snapshot |

A target legacy-ID change, a removed source observation, or a schema change
can leave the displayed intervals unchanged. The current whole-table binding
detects that drift. Retaining only the target projection checks would allow
such changes to pass once the whole-table guard was removed. A larger row
count and nonoverlapping displayed intervals also do not establish that
existing provenance survived.

`binding_from_snapshot()` does have the raw current rows before returning
aggregate hashes. A future narrow implementation could validate those rows
there without changing the generator's call site. It would still need a
verifiable baseline or another reviewed rule that proves preservation of
existing rows, identifies independent additions, validates their provenance
and rejects unknown schemas. This review did not establish that rule from
the retained aggregate binding. This is a limit of the current contract,
not a claim that recurring support is impossible.

No corpus hash was relaxed, no caller-supplied “append-only” assertion was
trusted, and no new versioning system was introduced. All runtime code,
tests, evidence SHA constants, default-OFF behavior and six-file rollback
are unchanged from the parent.

## Checks and execution limit

Read `main:PROJECT_STATE.md` and `main:CHANGELOG.md`; the latest accepted
checkpoint remains `C6-UA-CURRENT-ONEGET-01`. The parent's research proposals
are not accepted main transitions.

Reviewed the three DST files, the generator's snapshot/binding call site
without editing it, the saved readback evidence, original test log and
machine verdict. The prepared `union_alerts()` patch sorts starts and performs
both boundary comparisons in UTC while retaining the touching policy.
No writer redesign is proposed.

The saved physical run **42487688608** was checked by metadata:
completed/success, head
`38539e51e1ebdd3143d50d627f8f147f76a23821`. It was not rerun.
The parent's saved log reports 17 passing tests; that is prior evidence,
not a result of this review. No ZIP was downloaded or duplicated.

**New or changed Python tests executed: 0.** The workspace shell failed
to start with `No such file or directory (os error 2)`; the available
desktop Node runtime also failed to start. The existing coordination
workflow runs coordination tests, not DST tests. No workflow was altered
or physical proof dispatched to work around this limitation.

No new Python implementation or test changes are being presented as
validated. Frozen, append-growth and drift scenarios have not been newly
executed. The existing guards were preserved.

## Proposed checkpoint, pending separate acceptance

`C6-DST-ROLLING-REVIEW-01 / BLOCKED`: frozen correction remains available;
recurring growth is unproven. Review found that projection identities plus
aggregate hashes are insufficient to prove safe growth after relaxing
the original binding. A tested raw-row preservation/provenance rule is
required before changing that guard. No main coordination update is made.

Resume with an operational Python workspace and the existing retained
inputs. Keep the current guard until tests prove the frozen result,
independent growth, target/legacy/provenance/schema drift rejection,
interval conflicts, duplicates and rejection of reapplication. Preserve
the original six-file rollback and keep source freshness certification
outside this historical exception.

## Existing evidence and residual risks

The parent's [research README](../c6_dst_projection_2026_11_09/README.md)
and [manifest](../c6_dst_projection_2026_11_09/evidence/sha256_manifest.json)
remain authoritative for the frozen proof.

- Physical artifact SHA-256:
  `b0aa64392cb2b682eae14faf15df5df45da3fc208d8c45323dffab63b3d4245e`.
- Corrected offline archive SHA-256:
  `64e822ea6bd727f10c5307fabdc7f474725831aa0d1843a1100a87e268c54346`.
- New regular input may stop opt-in generation with
  `DST_CORRECTION:INPUT_CORPUS_OR_SCHEMA_DRIFT`; a changed projection also
  remains rejected.
- Frozen correction proves neither current source freshness nor physical
  Neon repair. Existing production integration and release gates remain.

This commit adds only this review record. It does not modify the generator,
C2 receipts, freshness metadata, Work B, PR #42/#44/#45, root coordination
documents, source HTTP, SQL, Neon or production.
