# C6 — minimum same-run historical capture integration (review draft)

**STATUS: BLOCKED for physical rollout; scoped code ready for review.**
`publication_allowed=false`; `GLOBAL_CUTOVER=NO`; historical DST correction remains default OFF.

## Verified starting point

- Coordination baseline: `main@0546986e69f2bbd4d5507f80dada426775eb1489`,
  `PROJECT_STATE.md` and `CHANGELOG.md`. Latest accepted root checkpoint:
  `C6-UA-CURRENT-ONEGET-01`; newer research work is not automatically an
  accepted production checkpoint.
- Collector checkout is **site-prod of the same repository**, not main and
  not a second repository: `site-prod@f90a61ea60ac8ce69d81b0fc21920b84bfef9d64`.
  Production collector blobs exactly match freshness patch originals:
  Kyiv `cebc2b455fb08ee16e03b9e4fcdb17aa2d9d6833`,
  UkraineAlarm `8b95c4b508b9a473240889603f593e399cf8815d`,
  Sevastopol `e4c091a677622eb28e504b0592a89e4d92d5fe02`.
- Existing freshness implementation `3d686a8a622433e242a01917a659a299082ec5bc`;
  existing DST `14e1b0b9a63d8471591a804cbd8e44aadc9cd120`;
  rolling DST diagnosis `83829c07e9b1e169121ba91029ff1f5f5e52f855`
  **BLOCKED** (raw baseline missing). No old incomplete Nov 8 baseline reused.
- Previous physical read-only 23-city Neon -> JSON:
  Actions `42487688608` SUCCESS, artifact `13619973574`; not a freshness PASS.
  Existing 70 freshness and 17 DST tests are retained, **not rerun**.
- Latest inspected normal run `42572683255`: production update PASS; C2
  writer and Git update PASS; C2 bundle checkout/export/upload all **skipped**.
  No new source HTTP, Neon operations, workflow dispatch, or deployment here.

## Draft change sets (neither merged)

1. **PR #47, targeting `site-prod`**: isolated production collector
   hook patch to the three exact original blobs. It records actual source
   bytes and hashes after successful existing HTTP responses, replays source
   parsers, creates bootstrap checkpoints only after genuine capture, advances
   on history overlap and retains only metadata in
   `data/c2_history_capture_checkpoints.json`. The source bytes remain in
   the existing ephemeral same-run C2 payload. A dedicated
   `C2_HISTORY_CAPTURE_ENABLED=true` guard keeps durable writes **OFF**
   by default. Existing scheduler, writer, frontend and source endpoints
   are not changed. First bootstrap is `continuity_verified=false`.
2. **PR #46, targeting `main`**: forwards that flag from a repository
   variable (unset/OFF by default), brings the exact existing hashed C2
   export validator and 36-hour source/corpus/readback gate, pins the matching
   capture contract, stages a private raw reader-row retention helper, and
   adds narrow no-network capture/overlap tests. Existing
   `C2_SHADOW_BUNDLE_EXPORT_ENABLED` remains OFF. A main workflow merge
   triggers its normal production updater by its existing push rule; **do not
   merge without a separate production-rollout authorization**.

The current six-file JSON delivery remains the existing Git path. Source
receipts and raw reader rows are not frontend outputs. Neither draft changes
PR #42, #44 or #45, nor modifies accepted coordination roots.

## Additional review blocker: physical readback adapter

The accepted `3d686a8a` research reader `scripts/neon_json_shadow.py` has
the `history_bundle` / `history_bundle_sha256` parameters and rejects
stale, missing, unbound, tampered and foreign receipts. **However**, its
existing manual launcher `scripts/neon_json_shadow_physical_proof.py` has not
yet been wired to forward its already pinned `--bundle` and
`--bundle-sha256` to those parameters. Required minimal caller change in
the reviewed research lineage:

```python
# inside the existing shadow.execute(...) call, add:
history_bundle=args.bundle,
history_bundle_sha256=args.bundle_sha256,
```

A separately reviewed exact research SHA and protected read-only workflow
approval must be used before dispatch. Do not copy the whole research branch
into main or site-prod, do not enable the production reader.

The optional `scripts/c6_private_reader_baseline.py` helper accepts an
*already obtained*, read-only repeatable-read snapshot, and stages all 7
raw reader arrays with per-file SHA-256, mode 0600, strictly outside the
checkout. It does **not** perform any SQL/readback itself and has **not yet
been wired into the physical reader**. A later reviewed caller must explicitly
opt in; raw rows must not be uploaded as public Actions artifacts, committed
to Git, or included in the frontend output. Secure owner-controlled transfer
and retention need separate approval. Old incomplete baseline is forbidden.

## Narrow verification scope and remaining work

- Collector hooks were applied mechanically to the three exact, verified
  site-prod source blobs, producing the same three collector hook blobs as
  the retained `3d686a8a` patch.
- New gate defaults OFF; the existing 4-hour cron remains
  `15 */4 * * *`; the active Git data path remains unchanged until
  approval, merge and explicit capture/export flags.
- The committed small test checks actual response bytes, bootstrap/overlap,
  failed advancement, default OFF. **No new test run is claimed**; PR CI and
  scoped test execution still need inspection. Previous 70/17 tests are
  evidence for original source changes, not for this new orchestration patch.
- A frozen C2 bundle must be tied to exact `github_run_id`, attempt,
  `workflow_sha`, `input_sha`, `corpus_sha256`, canonical C2 run ID,
  source payload SHA-256s and checkpoint history; no dashboard generation
  clock can stand in for source capture.
- First Kyiv/Sevastopol historical checkpoint must come from a genuine
  normal collector capture and remains BLOCKED for continuity; the next
  normal capture needs overlap and confirmed same-run readback. UkraineAlarm
  21/21 real history receipts are needed in that same run.
- Rejected/old/missing/foreign receipt and >36-hour cases must fail closed
  during the single separately approved read-only proof.
- DST stays default OFF with existing corpus guards; new rolling baseline
  cannot be declared ready until full private reader rows and their hashes
  have been retained and reviewed.

## Owner approval gates for a later rollout

1. Review PR #47 and #46 independently, scrutinize default-OFF behavior,
   persistence, raw response retention, privacy, and narrow CI; approve a
   carefully ordered merge/release (never automatic).
2. Explicitly authorize production collector capture hooks and
   same-run C2 bundle export by changing the two **separate** opt-in variables.
   Scheduler and writer architecture stay the same.
3. Let the first normal 4-hour cycle create genuine bootstrap checkpoints;
   expect insufficient history continuity, not PASS. Allow a later **normal**
   cycle to prove overlap for all 23 cities and persist the metadata
   checkpoints across scheduled Git publication.
4. Within 36 hours of the **oldest** relevant real source capture, separately
   authorize one branch-bound repeatable-read Neon -> JSON proof with the
   *same* C2 export run/attempt, corpus, input SHA, sources and bundle digest.
   Complete its reviewed readback adapter before dispatch; no new HTTP,
   Neon writes, or independent collector.
5. If separately approved, privately retain full raw reader rows and hashes
   for a **new** DST baseline; no GitHub raw-row exposure and no DST activation.
6. On trouble, turn capture/export variables OFF and restore the previous
   collector revision / Git JSON source settings. This is not permission to
   deploy or switch sources.

**Conclusion:** The existing 4-hour production scheduler can supply the
necessary genuine capture cycles **without a new pipeline**, conditional
on successful sources, persisted overlapping checkpoints and a subsequent
separately approved read-only proof. It does not independently certify
the 36-hour gate or rolling DST. Publication remains forbidden.
