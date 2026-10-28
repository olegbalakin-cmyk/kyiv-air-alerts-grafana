# C3-RC4 — OWNER REVIEW (research / staging only)

## Verdict
**C3_RC4_PARTIAL**. **RELEASE_AUTHORIZED=NO**. This is a research result, not coordinator acceptance or production release.

## Verified preflight
main `4a97b2c73add677ecc37e28323a59278005cbca4`; site-prod `c0e3cef6bb4437492cb5933fad5f2f6d5b23e3be`; operational WIP `6071cd7d2398a5b85bcb0637575038c5faafbc25`. Read main PROJECT_STATE.md/CHANGELOG.md and found latest accepted C3-RC3 `EXECUTED_PARTIAL_ACCEPTED_BOUNDED`.

Prior accepted RC3 exact CI: `40774891544`, job `123121491113`, artifact `12853623493` and zip sha256 `28c519931297d4cce9e55b264f86cfdb0092680054cd5aa290765643b02ceff1`.

## Executed RC4 preliminary fault evidence
[Research CI first probe 40780027105](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/40780027105) on `12460d3942a98a31336579bf448d89badf43ebc7`, PG16.15 service. Four new cases individually printed PASS: independent readback fault; source identity conflict; source failure retry; positive event-stage rollback. Accepted original six were reexecuted with PASS. The new readback/source failure used actual `monitor.main()` 3 times each; identity conflict/positive rollback used real persistence and journal functions directly; **do not call these latter two full integrated monitor.main proofs**. SQL snapshot receipts (before/failure/retry/repeat) were uploaded in runtime artifact `12856951254`. CI artifact zip digest `sha256:f588fbb3d74937becc6943b86c4422ad3e127d63219c63e70a0aa68946c6e661`. This first probe is not final SHA evidence.

## Current pinned source
Production `c0e3cef6` bridge blob `8b9dad34` and Sevastopol blob `4aa7359d`, Kyiv JSON blob unchanged `3a50f76f`. Measured source SHA-256:
- bridge `cabecea6cb7b451035779a7dcb4c65976c188ae74282051c5dc5c2bfeaf3a548`
- Sevastopol `bd1e479f54370606313ad0099ab448b00396685859ca5ca0f40e9d824c501f86`
- Kyiv `93d9fbaa912119d765f55fecd64f8de10a23c7f5fd5aa7bed4bfe1ece96ec50e`

First unlocked probe recorded **8476** source episodes / **2916** eligible / **2916** journal pending / 0 ACK with no source identity mismatches; 23 per-city statuses `NOT_PROVEN` until source SHA locks are committed and the exact-SHA rerun succeeds. No assertion of 2916 persisted rows.

## Operational containment blocker
`main:update-explosion-wip.yml` is a manual writer without job guard. `main:explosion-monitor-wip.yml` has `if: false` but that does not disable the other writer. `main:live-due-orchestration-readback.yml` has a `workflow_run` event listener and hardcoded old source SHA; reachability must be evaluated separately. All workflow files were inspected across three pinned refs in the executed matrix. The matrix result is PARTIAL, with conservative writer candidates; the static scanner does not prove account-level Actions policy or that every potential downstream mutation is actually reachable.

Minimal change proposed in `OPERATIONAL_CONTAINMENT_MINIMAL_PATCH_PROPOSAL.md`, **not applied** to main or operational WIP. Owner authorization required, then an independent effective-trigger check. Even a green exact-SHA fault/source run cannot satisfy the release gate while this real operational hold is incomplete.

## Research execution boundaries
No real Neon DDL/DML or compute/secrets/environment changes, production monitor, operational WIP execution, casualty changes, historical backfill, H1/H2, A5 or 470/47 replay. Canary cap remains 10. No main/site-prod/WIP changes and no automatic merging.

## CI linkage
Use the **latest exact-SHA** Actions run attached to the final branch HEAD; the runtime proof manifest's tested_sha is authoritative, never a preceding static manifest with an obsolete run ID. Full independent before/failure/retry SQL receipts and 23-city matrix are in the CI artifact. Static JSON files in Git are bounded summaries and links, not copied SQL receipts. 

## Next smallest owner decision
Authorize just a one-line `if: ${{ false }}` hold on default-branch `update-explosion-wip.yml`, while preserving the other hold and auditing the listener guard. After that, run a fresh assertion-based containment CI at actual operational main. Do not promote C3 until separately owner-approved.
