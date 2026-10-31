# C6 offline frontend shadow — recovered result

**OFFLINE_GENERATION_PASS; checkpoint awaiting owner acceptance. C6/C3=PARTIAL; GLOBAL_CUTOVER=NO.**

Recovery commit: `e1204d084ca815ac050028cb9978e60d18132154`, independently confirmed as research-branch HEAD. It preserves implementation, tests and compact evidence without uploading the 31,977-parent fixture archive. Original local commit `0260d8d9` and both original output directories were retained.

## Executed evidence

- Initial frontend tests: 10/10 PASS, Python 3.12.14, recorded exit 0 (`offline_proof/initial-unit.*`).
- Recovered full-suite log: 30 tests / OK, including one full-generation test and 19 negative cases. Its process exit code was not retained; no exit code is inferred.
- Resumed existing-output validation: exit **0**, all **15** manifest entries match, exactly **4+2 JSON**, **23 cities**, **31,712** lineage intervals. Daily count and both duration series match independent calculations; B2 **382 → 198**, **55** classifications, **223** source links, **0** rebinds. All 19 negative results match the retained test log and reject candidates/publication.
- Immutable-source restoration: exit **0**, archive **85/85** hashes and fixture **65/65** member hashes match. Original accepted Git tree was independently checked against GitHub; source Actions 41208139352 is SUCCESS. The first restore attempt detected a trailing newline mismatch in reconstructed payload bytes; the final serializer reproduces the original hash exactly. Both attempt logs are retained.
- Isolated workflow preflight: **2/2 PASS**, exit **0**; manual research-ref/SHA/read-permission guards and physical rejection of synthetic C2 input. This is local testing, not an Actions run.

Full generation was **not repeated**. Original output files physically remain in the recovered Work directory. Exact six candidate hashes are in `offline_proof/recovered/verdict.json` and `offline_proof/resume/machine_verdict.json`; every output/evidence hash is in `offline_proof/recovered/sha256_manifest.json`. The compact manifest references the full local output, not just the small subset copied into Git.

Reproduce fixtures through local immutable Git objects with `python -m scripts.neon_json_shadow_restore_fixtures`; see `fixtures/README.md`. Verify retained outputs without generating them with `python -m scripts.neon_json_shadow_verify_existing --output PATH --negatives PATH --unit-log PATH`. The verifier checks all output hashes, schema, lineage, KPI, source gates and retained negative-test evidence. Stdout, stderr, exit codes, code SHA/file hashes, source snapshot SHA and machine verdict are in `offline_proof/resume/`.

## Physical scope remains open

`PHYSICAL_NEON_READBACK_NOT_RUN; CURRENT_FRESHNESS_NOT_CERTIFIED; PRODUCTION_PUBLICATION_NOT_AUTHORIZED`.

The protected workflow is prepared and locally checked. It has only `workflow_dispatch`, exact authorized research ref/SHA, existing Environment `c6-live-writer-proof`, read-only GitHub permissions, source-client blocking and isolated artifact output. It does not call the production updater, capture upstream sources, write Neon, publish or change secrets.

One new owner authorization is needed for **one isolated protected read-only Actions proof** on an exact SHA, using an approved existing real C2 bundle and matching existing read-only credential/endpoint. Their actual availability, current Environment reviewer/ref protection and default-branch workflow registration remain unverified. The connector does not expose the Environment metadata or workflow-registration read used here. Permission alone does not resolve unavailable inputs; stop before dispatch if those preconditions fail. No main merge or credential creation is included.

This recovery performed **0** source GETs, **0** Neon connections/writes, **0** Actions dispatches and **0** publications. Production, `site-prod`, Netlify, secrets and coordination roots were unchanged. No Git AIR fallback, synthetic source freshness, DST repair or Kyiv rebind was introduced.
