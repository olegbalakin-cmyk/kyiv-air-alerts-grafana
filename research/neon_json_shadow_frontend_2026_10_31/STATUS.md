# C6 Neon frontend shadow — bounded implementation status (2026-10-31)

**Status: IMPLEMENTED, NOT ACCEPTED; OFFLINE EXECUTION NOT PROVEN.**
**Production: unchanged; GLOBAL_CUTOVER=NO.** This is not a new release checkpoint.

Base: `850f7f8d86314a3edd38ad07df18ba0f668eb30e`.
The accepted C6 code was `research/neon_23city_publication_2026_10_31/pipeline.py`
at `37a8702972c7b875f60aa73e3b0b890b869ab73b`.
C6 original physical run `41206457252` succeeded for the research child; it
is **not** proof for a production C2 receipt.

## Implemented, subject to executable verification

- Default-off `NEON_JSON_SHADOW_ENABLED == 'true'` opt-in in workflow.
- Non-publishing shadow relocated after both production-side derived JSON and
  Kyiv threat-mix builders; the current production commit/publish step is untouched.
- Existing C2 verifier checks 23 cities, workflow/input SHA, corpus digest;
  shadow also binds expected writer branch and endpoint identity and verifies
  matching Neon ingestion-run corpus provenance.
- One `REPEATABLE READ READ ONLY` snapshot holds AIR parents, source observations,
  checkpoints, runs, Kyiv classifications, source links and events.
- Accepted 22-city union, frozen Kyiv B2 selection, site-derived and historical
  KPI builders are retained with immutable asset blob pins. No research child
  TTL, host, source checkout or single-capture proof UUID is hard-coded.
- Candidate output contract: four frontend JSON plus explicit
  `kyiv_threat_mix.json` / `sevastopol_events.json`, with SHA-256.
  All output stays in the isolated runner temporary directory.
- Current status, Kyiv provenance and four physical DST cases are unverified;
  **JSON generation MUST NOT certify those gates or permit publication**.
  Absent/mismatched generator inputs fail closed without a candidate.
- Existing 9/9 canonical fixture tests are prior-session claims only, not a
  test result for this frontend adaptation.

## Independent offline test invocation

From repository root (requires the production site source checkout fixture and
the accepted pinned C6 assets, no Neon credentials for unit tests):

```sh
python -m unittest discover -s tests -p test_neon_json_shadow_frontend.py -v
```

The ten added tests check 23-city binding, C2 rejection, digest rejection,
city boundary, workflow SHA, branch, endpoint, synthetic readback interval/UUID,
workflow flag/builder ordering, and generator surface. These are **test code
only** until actually executed and their stdout/exit status retained. They
do not independently prove full frontend semantics.

## Before the one protected Actions proof

1. Run and retain the ten local unit tests and fixtures. Check pinned production
   builder compatibility, B2 382-parent selection and derived module imports.
2. Provision an **existing** read-only Neon credential for the same branch as
   the actual C2 receipt and same-run corpus. Independently confirm endpoint
   binding and privileges; no new Neon branch or writer alteration.
3. Separately authorize **one** workflow-dispatch run on the research ref
   with opt-in=true. Retain C2 receipt, full shadow verdict, six candidate file
   digests and read-only snapshot proof; require zero extra source GETs/writes.
   The updater is a production-capable workflow: do not launch it without
   explicit permission and publication-risk controls.
4. If any generator dependency is absent (e.g. pinned builder drift, 382 frozen
   Kyiv identities, classification tables or source-run corpus), return
   `BLOCKED_GENERATOR_INPUT` and name the contract. Never treat the prior C6
   child proof as the current C2 snapshot.

**No Action run, Neon SQL, new source request, site-prod update, main merge or
publication was performed for this change.**
