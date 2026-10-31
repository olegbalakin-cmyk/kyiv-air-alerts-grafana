# C6-LIVE-WRITER-PHYSICAL-03 — persistence PASS; freshness BLOCKED

[Actions 41203425205](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41203425205) completed successfully on workflow commit `a24e1cdaa36e02ee9a0861cbd9496ae755584565`. Both physical-proof and save-proof jobs succeeded. Immutable results are in [proof commit ac516e8f](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/commit/ac516e8fe9f25bc6cacbfe566e28bd856ea8fbe1), under `proof/physical_03/runs/41203425205/`. Artifact **13043214025**, digest `sha256:4a31ec8223801bd1d301b57123f71dcb6bc496fe16a331f9645986e1da10e1bc`. Independent retrieval and SHA-256 recomputation matched all **10 manifest members**.

## Credential and branch scope

The existing child `br-crimson-star-b59u7ge3` remains a ready, nondefault child of `br-bold-mode-b5rub8pq`; expiry **2026-11-01T12:20:00Z**. No child was created or deleted. Separate control-plane role inventories found `c6_writer_probe` on this child only, absent on all nine other project branches, including production and parent. Required table privileges passed. Its broad `neon_superuser` membership is recorded; this is a child-isolation attestation, not a least-privilege certification.

The runner received only `NEON_ISOLATED_PROOF_DATABASE_URL` from GitHub Environment `c6-live-writer-proof`. Before writes it verified the independently read child endpoint hostname, TLS, database `neondb`, actual `current_user=c6_writer_probe`, source hashes and TTL. Credentials and driver tracebacks were not emitted or committed. The writer job had a read-only GitHub token; a separate job without the database secret saved artifacts through a normal non-force research push. Environment binding and secret delivery worked; required-reviewer and branch-policy settings were not independently inspected.

## Persistence — physical PASS, bounded to this saved observation

The unchanged `isolated_writer.py` called the original pinned `persist_phase1_payload` twice in separate Python processes. Original Phase-1 persistence/core and source capture hashes passed.

- First transaction COMMIT succeeded; process then exited **86**. Ingestion run `dd0ffbf0-9620-47a7-8e00-1e84aff66d74` is independently readable as `succeeded`.
- First transaction **reused one existing canonical episode** (`episodes_inserted=0; episodes_existing=1`), inserted **one new source observation and one bootstrap checkpoint**. This does not prove allocation of a new episode UUID.
- Independent retry returned `exact_retry=true`: **0 new episodes, 0 new source observations, 0 new checkpoints**. The existing observation's last-seen receipt was updated; both ingestion runs are durable and child-tagged.
- Separate read-only connections recovered episode UUID `82f869c5-9c79-4f5f-98b0-2464f5c9f1cd`, source-observation UUID `66d5e1f9-cca5-4304-8b57-ea8c1c74e7fd`, legacy ID `92e8de1475c6d77b797ad217`, exact source-record identity, raw SHA-256 and original source retrieval/checkpoint time. Extended readback binds the observation to the **new probe ingestion run**, rather than misattributing the pre-existing episode's older creation receipt.

## Post-write JSON — bounded consumer witness PASS

The original pinned production `update_data.build_outputs` generated an offline **single-episode Kyiv consumer JSON witness** from the independently read database interval, with physical UUID/source provenance. Its KPI and daily arrays contain exactly one observed episode. SHA-256: `eee125830a9c42d9a9cb45d1be1ce602523c41e2e636822697286ca06e7a558b`.

This is not a regenerated 23-city site, display-selection certification, production build or publication. Full-site parity/browser/CSV/rollback were not repeated. The witness is explicitly research-only and publication-disabled.

## Freshness — BLOCKED, with real stale-input rejection

The exact saved source capture time remains **2026-10-30T22:56:24.503909Z** in original input, source observation, checkpoint and JSON source-as-of metadata. The physical COMMIT occurred at **2026-10-31T12:58:24.049662Z**; a new COMMIT/build did not change source age. The unchanged gate rejected `STALE_SOURCE_CAPTURE`: **50,521.9 s > 21,600 s**. No new HTTP capture, timestamp rewrite, threshold widening or synthetic test occurred.

Machine result: **`PASS_PERSISTENCE_FRESHNESS_BLOCKED`**. Production writer readiness **NO**; **C6/C3 PARTIAL; GLOBAL_CUTOVER NO**. A current-source freshness PASS requires the owner's separate authorization for a new real observation. The original single-bootstrap stream cannot accept a changed capture as a blind retry: a separately authorized continuation/new observation must preserve identity and checkpoint semantics.

No production Neon, parent data, site-prod, operational WIP, Netlify or production writer changes. Child remains for automatic TTL expiry; no manual cleanup.
