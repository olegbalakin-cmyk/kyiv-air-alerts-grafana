# Project State — current coordination snapshot

**Date:** 2026-10-31. **Release decision: NO-GO. GLOBAL_CUTOVER=NO; C6=PARTIAL; C3=PARTIAL.**
Latest accepted technical checkpoint: **C6-LIVE-WRITER-PHYSICAL-03**. [Verified research closeout](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/commit/0617e6818f34e4a807e535b35fa4a9281d8d0e0b): bounded physical persistence PASS; current-source freshness remains BLOCKED. No production promotion.

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
- **Live writer / provenance:** protected Actions on existing child `br-crimson-star-b59u7ge3` proved original Phase-1 COMMIT → crash exit 86 → separate exact retry → independent read-only UUID/source readback. One existing canonical episode reused; one new observation/checkpoint inserted; retry inserted 0 semantic duplicates. Post-write **single-episode Kyiv consumer JSON witness PASS**, not full 23-city regeneration or new UUID allocation. Runtime/credential delivery blockers resolved; old capture remains **STALE_SOURCE_CAPTURE** (50,521.9 s > 21,600 s). Production writer NOT READY. Project **10/10** branches; child TTL **2026-11-01T12:20:00Z**, no manual cleanup. See latest checkpoint for evidence.
- **DST / Kyiv:** three erroneous merged intervals and one missing alert across Kharkiv, Poltava, Zhytomyr and Cherkasy still need authorized physical repair proof and a separately gated write plan. Frozen Kyiv reader: 382 parents → 198 displayed alerts; nine later site intervals outside frozen B2. Do not automatically rebind 28 classifications on 27 suppressed parents. Current Kyiv selection/provenance remains open.
- **Preview / C3:** C6-PREVIEW-ROLLBACK-01 accepted a frozen browser package for 23 cities and source-only rollback. [Proof commit 66f87241](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/commit/66f872413f67668c9bd23b94cff17520fea705f9), [Actions 41139538902](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41139538902), artifact 13018841540. It remains an offline research candidate with DST simulation and explicit Git auxiliary dependencies. Production switch/rollback, active alerts and ongoing freshness remain open. Do not repeat accepted frozen parity/browser/CSV/preview rollback work.
- **Operational WIP / historical reference / backfill / casualty:** separate tracks; no change or promotion is established by these research or documentation checkpoints. Consult the relevant pinned evidence through the archive index before acting on a track.

## Concrete next tasks

1. Obtain the owner's **separate authorization for a new HTTP capture** before current-source freshness work. Reuse the existing child before TTL; preserve the accepted old capture and persistence proof. A changed observation needs valid continuation/checkpoint semantics, not a blind retry of the same bootstrap. Complete current-source → persisted observation → readback → publication-gated site generation; the accepted single-episode JSON witness does not certify a live 23-city pipeline. Do not create/delete a child or repeat parity, PG17, browser/CSV/rollback.
2. Resolve the four physical DST cases and Kyiv current provenance through their separate authorized scopes. Prove durable live writer and ongoing update freshness; keep Git auxiliary dependencies explicit.
3. Complete production-like source-switch/operational rollback rehearsal and the release gate before any separately approved production promotion.

## Latest accepted checkpoint — full text

<!-- coordination:history:start -->
## C6-LIVE-WRITER-PHYSICAL-03 — physical persistence PASS; freshness BLOCKED (2026-10-31)

- [Closeout/proof](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/0617e6818f34e4a807e535b35fa4a9281d8d0e0b/research/neon_live_writer_freshness_2026_10_31/PHYSICAL_03.md); raw results `ac516e8fe9f25bc6cacbfe566e28bd856ea8fbe1`; [Actions 41203425205](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41203425205) SUCCESS on `a24e1cdaa36e02ee9a0861cbd9496ae755584565`; artifact **13043214025**. Independent retrieval verified all **10** manifest hashes.
- Existing child/TTL retained. Role `c6_writer_probe` found only on this child, absent from all other nine branches; required rights and actual child URL/user verified in Environment `c6-live-writer-proof`. Broad child privileges recorded; Environment reviewer/branch-policy settings not independently inspected. No credentials logged.
- Unchanged original Phase-1: real COMMIT, crash **86**, independent retry `exact_retry=true`, **0 duplicate inserts**, separate read-only UUID/source/hash/time readback PASS. **Existing episode reused**, new source observation + bootstrap checkpoint; new episode UUID allocation not proven. Post-write original builder generated a **single-episode consumer JSON witness**, not the full site.
- Saved capture **2026-10-30T22:56:24.503909Z** unchanged; new COMMIT/build did not refresh it. Original gate: **STALE_SOURCE_CAPTURE**, **50,521.9 > 21,600 s**. No new HTTP, synthetic tests or forbidden replay. **PASS_PERSISTENCE_FRESHNESS_BLOCKED; C6/C3 PARTIAL; GLOBAL_CUTOVER NO.** Next: separately authorized current observation and valid continuation before a freshness PASS. No production/parent/site-prod/WIP/Netlify/writer change; no branch creation/deletion.

## C6-LIVE-WRITER-PHYSICAL-02 — child verified; execution/freshness BLOCKED (2026-10-31)

- [Research proof](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/e9226f3bd92b9341cc6910772034b10612012088/research/neon_live_writer_freshness_2026_10_31/PHYSICAL_02.md), commit `e9226f3bd92b9341cc6910772034b10612012088`, fast-forward from `0f0d7181e04cb053b773fb5c0ecf284bb82bc66a`; remote commit/parent/verdict verified.
- Exactly one child **`br-crimson-star-b59u7ge3`** of **`br-bold-mode-b5rub8pq`**; independent ID/parent/ready/endpoint readback PASS. Inventory **9→10/10**. TTL **2026-11-01T12:20:00Z**; no manual deletion. Reuse this child; do not create another.
- **BLOCKED:** local Python DNS `gaierror [Errno -3]`, psycopg absent. Child URL hostname verified in memory, but child-only role scope not attested; exposed GitHub tools cannot securely inject it into Actions. Existing secret availability UNKNOWN; parent URL not reused.
- Saved bytes/capture/canonical hashes PASS; original writer/gate blobs unchanged. Real saved source age **48,881.8 s > 21,600 s**: unchanged gate rejects **STALE_SOURCE_CAPTURE**. No fresh capture, synthetic tests or timestamp rewrite.
- **Zero SQL; COMMIT/crash86/retry/DB UUID readback/site JSON NOT EXECUTED.** [Machine verdict](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/e9226f3bd92b9341cc6910772034b10612012088/research/neon_live_writer_freshness_2026_10_31/proof/resume_physical_02/machine_verdict.json) `BLOCKED_RUNTIME_AND_STALE_SOURCE`; production preflight ready **NO**. No production Neon/site-prod/WIP/Netlify changes. **C6/C3=PARTIAL; GLOBAL_CUTOVER=NO.**

<!-- coordination:history:end -->

## Evidence and documentation maintenance

- [Complete archive index and integrity](docs/coordination-archive/README.md): exact previous roots, original large historical blobs and dated snapshots; [machine manifest](docs/coordination-archive/manifest.json).
- [Maintenance contract and CLI](docs/coordination-maintenance.md). CI verifies byte limits, exact historical record coverage and immutable archives. Automatic archival proposes a PR only; no direct main push or auto-merge.
- **DOC-AUTO-MAINTENANCE-MERGE-02:** [PR #34](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/34) merged at `main@3735f359d2bfa3310cc7f9fd46f9c8f3a2af0e8f`; [Actions 41202336197](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41202336197) SUCCESS on main (unit tests, byte gate, archive integrity and dry-run). Roots: PROJECT_STATE **7,990 B**, CHANGELOG **7,127 B** at merge; 10 records / 8 unique checkpoint IDs archived with hashes. Main-only PR-proposal job is now active but no over-threshold PR-creation attempt yet; bot permission remains unproven. No required status checks/rulesets; protection unchanged. CLI/patch fallback remains available. This documentation checkpoint is not a Neon release.
