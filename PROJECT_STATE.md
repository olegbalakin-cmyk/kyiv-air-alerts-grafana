# Project State — active coordination snapshot

**Date:** 2026-10-31. **Release decision:** NO-GO. **Purpose:** concise, authoritative coordination state for the Neon cutover. This is not a replacement for the underlying proofs. The complete prior PROJECT_STATE.md is preserved byte-for-byte in [the historical archive](docs/coordination-archive/PROJECT_STATE_full_before_compaction_2026-10-30.md).

## Instructions for Work, agents and reviewers

Read this file and root CHANGELOG.md before repository work. The latest accepted checkpoint governs over chat memory. Verify immutable commits, Actions runs and proof artifacts before technical claims. Keep production, development, historical, backfill, casualty and Neon tracks separate.

Keep this snapshot at 5–8 KiB. Both roots: PASS ≤12,288 UTF-8 bytes; WARNING ≤16,384; FAIL above 16,384. Put active blockers and next tasks outside the checkpoint markers. Prepend self-contained checkpoint sections inside the markers; use `<!-- coordination:keep -->` to pin any still-current record. Preserve the newest checkpoint and archive older text without paraphrasing. Run `python scripts/coordination_docs.py archive --dry-run`, then `archive`; submit a PR.

Read archived evidence only in targeted ranges. [Maintenance procedure](docs/coordination-maintenance.md); [complete archive index](docs/coordination-archive/index.json). Never expose credentials or rewrite shared branches.

## Current release gates — latest accepted main checkpoints

- **GLOBAL_CUTOVER=NO; C6=PARTIAL; C3=PARTIAL.** Production still uses the established Git/JSON publication path, not a proven Neon-backed cutover.
- **C6-23CITY-INTEGRATED-SHADOW-02:** bounded, physical read-only Neon-to-site generation accepted for **23 cities / 31,903 closed AIR episodes**, consumer schema QA PASS (4 exact-city, 19 raion proxies). Against the pinned older production reference, **2,570 JSON-path differences** remained; full current-site parity NOT ACCEPTED. Approved reader proof: [Actions 41076975484](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41076975484), artifact **12986704632**. Do not treat each diff path as an incorrect database episode.
- **Kyiv reader:** frozen B2 proof **382 physical parents to 198 displayed alerts**. At the accepted October cutoff, **nine** site intervals lay outside that frozen B2; **28 classifications on 27 suppressed parents must not be rebound** without provenance. Historic Kyiv reader scope and primary source-to-UUID receipts remain open.
- **DST:** accepted research analysis identifies **three erroneous merged intervals and one missing alert** affecting Kharkiv, Poltava, Zhytomyr and Cherkasy. Proposed UTC fix is **not integrated into production Neon**; any data correction needs the authorized isolated test and a separately gated write plan.
- **Provenance/live writer:** C6-LIVE-WRITER-PHYSICAL-02 verifies one new isolated child and saved-source hash identity. Physical writer/UUID/readback/JSON remain **NOT EXECUTED**: Python cannot resolve Neon; safe child credential injection to Actions is unavailable through the connector. Saved source is also stale under the unchanged six-hour gate. Production writer **NOT READY**; project now **10/10** branches.
- **C3 cutover:** frozen research preview source switch, frontend/CSV/derived consumer package and source-only rollback are physically proven by [C6-PREVIEW-ROLLBACK-01](docs/coordination-archive/2026-10-31/PROJECT_STATE.b5fe84d74bebbfaf.md). Production generator switch/operational rollback, current active alerts, writer durability/ongoing freshness and fail-closed activation still need their release gate. The frozen package retains explicit Git auxiliary dependencies.

<!-- coordination:checkpoints:start -->
## C6-LIVE-WRITER-PHYSICAL-02 — child verified; execution/freshness BLOCKED (2026-10-31)

- [Research proof](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/e9226f3bd92b9341cc6910772034b10612012088/research/neon_live_writer_freshness_2026_10_31/PHYSICAL_02.md), commit `e9226f3bd92b9341cc6910772034b10612012088`, fast-forward from `0f0d7181e04cb053b773fb5c0ecf284bb82bc66a`; remote commit/parent/verdict verified.
- Exactly one child **`br-crimson-star-b59u7ge3`** of **`br-bold-mode-b5rub8pq`**; independent ID/parent/ready/endpoint readback PASS. Inventory **9→10/10**. TTL **2026-11-01T12:20:00Z**; no manual deletion. Reuse this child; do not create another.
- **BLOCKED:** local Python DNS `gaierror [Errno -3]`, psycopg absent. Child URL hostname verified in memory, but child-only role scope not attested; exposed GitHub tools cannot securely inject it into Actions. Existing secret availability UNKNOWN; parent URL not reused.
- Saved bytes/capture/canonical hashes PASS; original writer/gate blobs unchanged. Real saved source age **48,881.8 s > 21,600 s**: unchanged gate rejects **STALE_SOURCE_CAPTURE**. No fresh capture, synthetic tests or timestamp rewrite.
- **Zero SQL; COMMIT/crash86/retry/DB UUID readback/site JSON NOT EXECUTED.** [Machine verdict](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/e9226f3bd92b9341cc6910772034b10612012088/research/neon_live_writer_freshness_2026_10_31/proof/resume_physical_02/machine_verdict.json) `BLOCKED_RUNTIME_AND_STALE_SOURCE`; production preflight ready **NO**. No production Neon/site-prod/WIP/Netlify changes. **C6/C3=PARTIAL; GLOBAL_CUTOVER=NO.**

<!-- coordination:checkpoints:end -->

## Verified refs at documentation compaction (not release pins)

- Accepted coordination base: **main@1c3a4658e6ac2f4a523fce22d3c8b7327f592731** before this documentation-only change.
- Independently observed branch heads at compaction: **site-prod@c6636e838cc5ca1da3f250091bb1c5c0ff08229e**; **multicity-wip-2026-09-16@5611a05b338b63fab2f51a9bdd676c0c6f71cfd5**; research cutover **b3ceeeceedbd0475cbd059e32020bed3d321da26**. Heads can change asynchronously: re-query immediately before acting.
- Production publication, operational WIP, protected Neon environment, research/preview and historical corrections require separate authority. This docs compaction authorizes **no** data writes, site switch, production deployment, branch-force update or new Neon child.

## Shortest safe next path

1. **Resume existing child before TTL:** run original Phase-1 crash/retry/readback on `br-crimson-star-b59u7ge3` using a network-capable runner and verified child-scoped credential. Preserve saved source time: its stale capture cannot pass current freshness; a new verified observation needs separate authority. No manual cleanup without owner permission.
2. **Close remaining source/writer gates:** resolve the four physical DST cases through the authorized isolated proof and separately gated write plan; close Kyiv current selection/provenance exceptions and durable live writer/readback. Keep existing Git auxiliary dependencies explicit.
3. **Run production-like rehearsal:** prove ongoing update freshness, real safe writer path, full consumer contract, controlled legacy|neon switch and rollback. Only then request/execute separately approved production promotion.

## Historical audit index

- [Complete pre-compaction PROJECT_STATE.md](docs/coordination-archive/PROJECT_STATE_full_before_compaction_2026-10-30.md) — exact original Git blob **ebcc286b3bfc93372a61567f1de5fe1d3e49bc2a**.
- [Complete pre-compaction CHANGELOG.md](docs/coordination-archive/CHANGELOG_full_before_compaction_2026-10-30.md) — exact original Git blob **732e7a07f3e92e1138aafe311bff5561f56d60ee**.
- [Archive usage and integrity](docs/coordination-archive/README.md).

**Documentation transition:** COORDINATION-DOCS-AUTOMATION-01. Size CI, exact-byte archival and archive-by-PR workflow added on the maintenance branch; activation on main awaits merge. Required status checks are currently off; branch protection was not changed. Technical release gates above are unchanged.