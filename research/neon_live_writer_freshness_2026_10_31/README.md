# C6-LIVE-WRITER-FRESHNESS-01 — isolated writer gate

**Status: BLOCKED (new Neon child creation), not an accepted production release.**

This research task begins after accepted C6-PREVIEW-ROLLBACK-01 (source 66f872413f67668c9bd23b94cff17520fea705f9, Actions 41139538902). It does not repeat frozen parity, browser QA, CSV or rollback. Production / main / site-prod / operational WIP / Netlify / existing Neon branches are unchanged.

## Observed hard blocker

Neon project green-cake-44216048; requested new branch c6-live-writer-freshness-isolated-2026-10-31, parent br-bold-mode-b5rub8pq (existing shadow branch, NOT production). Neon create_branch returned HTTP 422: branches limit exceeded. No automatic deletion, reset, write, or use of an existing branch for this purpose. Production database br-wandering-sunset-b5835alw and existing br-bold-mode-b5rub8pq are explicitly excluded by the proposed writer guard.

The repo's existing site-prod Phase-1 scripts remain pinned:
- update_data.py Git blob cebc2b455fb08ee16e03b9e4fcdb17aa2d9d6833
- db_phase1_core.py Git blob dda23c268e08f74367f33b189a8bafc1358aadd2
- db_phase1_persistence.py Git blob ed014e61fc6186fa9daf91c763c847e7df2f0306

The research-only HTTP workflow uses exactly one GET to https://kyiv.digital/storage/air-alert/stats.html and the original parser, with a bounded raw-byte artifact and a prospective, NOT production-approved source identity. It has no Neon URL, secret, write permission, or production deployment step. Its successful job cannot mean real writer activation.

## Ready isolated child scenario (NOT EXECUTED)

1. Obtain explicit operator approval for one additional disposable child branch/capacity, or separately approve retirement of an identified obsolete branch after checking current dependencies. Do not delete an existing branch autonomously.
2. Create a new Neon branch as a child of br-bold-mode-b5rub8pq with name beginning c6-live-writer-freshness-isolated-. Independently fetch its branch metadata and get its own child-scoped connection URL. Persist non-secret attestation fields id, name, parent_id, default, protected, current_state, approved_connection_hostname and connection_role_scope=new_child_only in an untracked JSON; never commit credentials. Re-check branch ID against the parent, default and production IDs.
3. Run the already-committed capture_source.py on an authorized HTTP runner; obtain proof/canonical_candidate.json and proof/http_capture.json and verify both SHA-256 manifest entries. Use immutable site-prod checkout c6636e838cc5ca1da3f250091bb1c5c0ff08229e.
4. With psycopg 3 and the isolated URL in NEON_ISOLATED_PROOF_DATABASE_URL only, execute the original site-prod db_phase1_persistence.persist_phase1_payload through isolated_writer.py --phase first-commit-crash. Exit code 86 is intentionally expected AFTER COMMIT. Save first_commit_receipt.json.
5. Invoke isolated_writer.py again with the same source/capture/branch proof and --phase retry-readback. Require exact_retry, no inserted semantic duplicate, one physical episode UUID and source-observation UUID, successful ingestion run and independent connection with transaction read-only. Save independent_readback.json.
6. Fetch all city rows from the isolated child with the accepted C6 reader; run the existing bounded full-site JSON generator, never the production publisher. Check exact new episode and provenance inside the generated JSON, source as-of UTC from a durable source checkpoint, generator timestamp separated, and compare source/readback identities via freshness_gate.gate before staging any published bytes. In a second rehearsal force stale checked_at, failed readback, mismatched identity and fake generator freshness; require fail-closed, no candidate publication.
7. Do not activate any operational writer/cron, C3 monitor/listener, protected URL, main/site-prod or Netlify without a separately approved production promotion.

## Concrete production changes after a successful physical child proof

- A scheduled, branch-scoped, source-specific writer using original Phase-1 transaction/receipts; replace the prospective Kyiv Digital HTML key only after formal source-identity acceptance. Implement continuation across each poll (not a single latest episode); explicit current-active-status handling remains required.
- Add post-COMMIT independent readback and a durable idempotent retry/recovery journal; block the generator on failed source/persist/readback rather than substituting Git output under a Neon freshness label.
- Run the accepted 23-city reader from the committed DB snapshot and gate publication on same-branch source UUID/observation links plus source checked_at, committed_at and readback_at. Keep distinct generated_at vs verified data_as_of; a recent build time must never disguise an old source poll.
- Preserve explicit Git auxiliary dependencies, C3/WIP containment and the production operational rollback gate. No new writer is production-ready merely because synthetic gate tests pass.

## Boundary

The accepted local PG17 crash/idempotency proof is NOT re-run here. The attached freshness tests use fake timestamps solely to exercise fail-closed decisions and may not be cited as HTTP→Neon→JSON physical proof. Evidence after an Actions run is under proof/ and its artifact, with machine verdict showing PARTIAL or BLOCKED. Global cutover NO-GO.
