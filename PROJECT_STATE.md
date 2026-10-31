# Project State — current coordination snapshot

**Date:** 2026-10-31. **Release decision: NO-GO. GLOBAL_CUTOVER=NO; C6=PARTIAL; C3=PARTIAL.**
Latest accepted technical/coordination checkpoint: **NEON-BRANCH-SLOT-FREED-01**. Source: `main@30b40a2d9ca04bd131689da855d3491681f3d445`. The statements below retain that accepted scope; documentation maintenance does not establish a newer migration result.

## Working instructions

1. Read this root file and [CHANGELOG.md](CHANGELOG.md) before repository work. This file governs current coordination; newer accepted repository checkpoints govern older chat memory.
2. Verify the relevant immutable commits, actual Actions runs and proof artifacts before technical action. A successful research job does not prove production deployment or a release PASS.
3. Keep production, development/WIP, historical reference, backfill, casualty and Neon/persistence tracks separate. Do not overwrite another worker's commits, force-push shared branches, expose credentials or infer a production change from research.
4. Keep unresolved blockers, track status and next tasks **outside** the history markers below. Put detailed accepted checkpoints inside them, newest first; retain the latest checkpoint. Prepend brief accepted transitions inside CHANGELOG's markers. Full evidence belongs in immutable archives or proof files.
5. Aim for **5–8 KiB** here and **5–10 recent transitions** in CHANGELOG. UTF-8 byte gate: ≤12,288 PASS; 12,289–16,384 WARNING; >16,384 FAIL. Before an oversized update, run `python scripts/coordination_docs.py archive --dry-run`, then `archive` on a separate branch. See [maintenance instructions](docs/coordination-maintenance.md).
6. Never load entire historical archives, large JSON/SQL dumps or full Actions logs into Work context. Search an exact checkpoint ID and read bounded lines. Save reproducible work promptly; recover interrupted commits before new research.

## Current tracks and open release gates

- **Production:** established Git/JSON publication path; no accepted Neon-backed production cutover. Production promotion and operational rollback need their own gate. Documentation work does not change site-prod or the published deployment.
- **Neon reader / historical parity:** accepted C6-RECOVERED-PARITY-VERIFICATION-02 reproduced the frozen 23-city candidate at cutoff `2026-10-30T15:27:55.138400Z`. Direct 22-city diff: 0 without / 366 with DST simulation. All 1,354 candidate paths accounted for (847 DST, 457 legacy derived omission, 49 timestamps, 1 research marker). This is bounded offline evidence, not continuous freshness. [Proof commit 741f277f](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/commit/741f277f73d1dde1325069d25fa00b44a42d6f03).
- **Live writer / provenance:** real HTTP/parser identity and 15/15 synthetic freshness tests passed, but physical isolated Neon UUID/COMMIT/retry/readback and post-COMMIT JSON remain NOT PROVEN at this accepted checkpoint. Prepared runner: `research-neon-live-writer-freshness-2026-10-31@0f0d7181e04cb053b773fb5c0ecf284bb82bc66a`, `research/neon_live_writer_freshness_2026_10_31/isolated_writer.py`. Original HTTP [Actions 41141326530](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41141326530), artifact 13018209142; saved proof [Actions 41196606039](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41196606039), artifact 13040277727. Local PG17 receipt proof remains local in scope.
- **DST / Kyiv:** three erroneous merged intervals and one missing alert across Kharkiv, Poltava, Zhytomyr and Cherkasy still need authorized physical repair proof and a separately gated write plan. Frozen Kyiv reader: 382 parents → 198 displayed alerts; nine later site intervals outside frozen B2. Do not automatically rebind 28 classifications on 27 suppressed parents. Current Kyiv selection/provenance remains open.
- **Preview / C3:** C6-PREVIEW-ROLLBACK-01 accepted a frozen browser package for 23 cities and source-only rollback. [Proof commit 66f87241](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/commit/66f872413f67668c9bd23b94cff17520fea705f9), [Actions 41139538902](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41139538902), artifact 13018841540. It remains an offline research candidate with DST simulation and explicit Git auxiliary dependencies. Production switch/rollback, active alerts and ongoing freshness remain open. Do not repeat accepted frozen parity/browser/CSV/preview rollback work.
- **Operational WIP / historical reference / backfill / casualty:** separate tracks; no change or promotion is established by these research or documentation checkpoints. Consult the relevant pinned evidence through the archive index before acting on a track.

## Concrete next tasks

1. Capacity was verified at **9/10 branches** by the latest checkpoint. Before execution, recheck capacity and create one isolated child of `br-bold-mode-b5rub8pq`; use only independently verified child-scoped credentials. Run the saved writer scenario: physical first COMMIT, crash retry, independent UUID/source readback and fresh fail-closed site JSON. Do not repeat HTTP capture or accepted synthetic/local/frozen proofs.
2. Resolve the four physical DST cases and Kyiv current provenance through their separate authorized scopes. Prove durable live writer and ongoing update freshness; keep Git auxiliary dependencies explicit.
3. Complete production-like source-switch/operational rollback rehearsal and the release gate before any separately approved production promotion. **This documentation-maintenance session stops after automation verification.**

## Latest accepted checkpoint — full text

<!-- coordination:history:start -->
## NEON-BRANCH-SLOT-FREED-01 — verified 9/10 branches; isolated writer can now be tested (2026-10-31)

- Owner reported deleting historical archived isolated leaf `br-cold-sky-b5jhai9p` (`lviv-phase1-live-poll-adapter-e2e-2026-09-28`). Independent Neon `list_branches(project=green-cake-44216048, include_deleted=false)` now lists **9 branches** under Free-plan limit **10**; deleted ID is absent. No new child created by this verification.
- **Capacity blocker CLEARED; physical writer gate OPEN/NOT EXECUTED.** The saved two-phase research script at `research-neon-live-writer-freshness-2026-10-31@0f0d7181e04cb053b773fb5c0ecf284bb82bc66a` still requires a fresh child of `br-bold-mode-b5rub8pq`, physical first-COMMIT/crash retry, independent UUID/source readback and fail-closed generation from that child. Separate ongoing freshness/active-alert/production authorization remains necessary.
- Container execution in this chat has no direct outbound network access to GitHub/Neon, so no new child, SQL writes, physical Python runner or cleanup was attempted here. Use an authorized Work/runner with a properly scoped child DB URL. Never put a credential into Git files or workflow logs. **GLOBAL_CUTOVER=NO; C6/C3=PARTIAL.**

<!-- coordination:history:end -->

## Evidence and documentation maintenance

- [Complete archive index and integrity](docs/coordination-archive/README.md): exact previous roots, original large historical blobs and dated snapshots; [machine manifest](docs/coordination-archive/manifest.json).
- [Maintenance contract and CLI](docs/coordination-maintenance.md). CI verifies byte limits, exact historical record coverage and immutable archives. Automatic archival proposes a PR only; no direct main push or auto-merge.
- **DOC-AUTO-MAINTENANCE-01:** implementation in a separate maintenance PR; not a migration release checkpoint. Main currently reports no required status checks; protection was not changed. CI enforcement and the main-only archival job become active after merge. Runtime PR permissions may deny bot PR creation; the CLI/patch fallback remains available.
