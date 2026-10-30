# Project State — active coordination snapshot

**Date:** 2026-10-30. **Release decision:** NO-GO. **Purpose:** concise, authoritative coordination state for the Neon cutover. This is not a replacement for the underlying proofs. The complete prior PROJECT_STATE.md is preserved byte-for-byte in [the historical archive](docs/coordination-archive/PROJECT_STATE_full_before_compaction_2026-10-30.md).

## Instructions for Work, agents and reviewers

1. **Always read this root file and root CHANGELOG.md before repository work.** The root files are intentionally short. Treat the newest accepted checkpoint here as authoritative over older chat summaries.
2. Do **not** fetch entire archived checkpoint files, full JSON, whole SQL dumps, or full Actions logs into conversational context. Read only targeted lines/sections; process large files in the workspace and save machine-readable evidence as files/artifacts.
3. Before technical conclusions, verify referenced immutable commit SHAs, actual GitHub Actions runs and proof artifacts. Research-only execution is not proof of production deployment. A successfully completed job is not automatically a release PASS.
4. Keep production, development, historical-reference, backfill, casualty, and Neon/persistence tracks separate. Never rewrite shared research/WIP branches, override another worker's commits, or infer a production change from a research proof.
5. Following a newly accepted state-changing checkpoint, update this concise current state and **prepend** a bounded transition to root CHANGELOG.md; keep full detailed evidence in dated archives/artifacts. Keep each root file under approximately 20 KB; roll old entries into a dated archive without losing their Git blobs.
6. Commit and push reproducible work frequently. After a session interruption, recover remote and local commits before initiating fresh research. Do not expose database credentials or raw secrets in documentation or logs.

## Current release gates — latest accepted main checkpoints

- **GLOBAL_CUTOVER=NO; C6=PARTIAL; C3=PARTIAL.** Production still uses the established Git/JSON publication path, not a proven Neon-backed cutover.
- **C6-23CITY-INTEGRATED-SHADOW-02:** bounded, physical read-only Neon-to-site generation accepted for **23 cities / 31,903 closed AIR episodes**, consumer schema QA PASS (4 exact-city, 19 raion proxies). Against the pinned older production reference, **2,570 JSON-path differences** remained; full current-site parity NOT ACCEPTED. Approved reader proof: [Actions 41076975484](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41076975484), artifact **12986704632**. Do not treat each diff path as an incorrect database episode.
- **Kyiv reader:** frozen B2 proof **382 physical parents to 198 displayed alerts**. At the accepted October cutoff, **nine** site intervals lay outside that frozen B2; **28 classifications on 27 suppressed parents must not be rebound** without provenance. Historic Kyiv reader scope and primary source-to-UUID receipts remain open.
- **DST:** accepted research analysis identifies **three erroneous merged intervals and one missing alert** affecting Kharkiv, Poltava, Zhytomyr and Cherkasy. Proposed UTC fix is **not integrated into production Neon**; any data correction needs the authorized isolated test and a separately gated write plan.
- **Provenance:** accepted C6-PROVENANCE-03-LITE PG17 local crash-safe receipt proof is bounded LOCAL, not a live Neon proof. Latest accepted C6-PROVENANCE-04B attempt [Actions 41120424463](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41120424463) failed before running any steps; no HTTP-to-Neon physical UUID/readback was proven there.
- **C3 cutover:** minimal legacy|neon source switch and reliable source-only rollback have not been physically rehearsed. Writer durability/freshness and fail-closed activation still need the relevant release gate. Current active alerts, frontend/CSV downloads, derived fields, cutoff alignment and partly Git-backed auxiliary files must be checked as a coherent consumer package.

## Later observed research work — not an accepted cutover checkpoint

- The isolated research branch **research-neon-cutover-work-2026-10-30** was verified at **b3ceeeceedbd0475cbd059e32020bed3d321da26**. [Actions run 41123467415](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41123467415) completed SUCCESS with an executed network/parser step and artifact **13009048201** (GitHub artifact digest SHA-256 **58eec9d0dc8349e19a07fbcfb0407ac06ee6ea8fc61b8435b66eb8cce0e071f4**). It did **not** execute a physical Neon UUID transaction/readback. Original receipt contents still require independent examination before accepting any source claim.
- A subsequently interrupted Work session **reported**, but did not yet preserve in the remote research branch, replay changes: zero direct JSON differences for 22 non-Kyiv cities after partial-month rule alignment; a 23-city replay against the newer site-prod; a DST simulation; and 14 later Kyiv matches to a captured HTTP response. These are **unaccepted Work reports** until code, test inputs, machine diffs, and independent proof are recovered and verified.
- That Work session also reported **two local commits not yet pushed**. Their SHA values and availability are unverified. **Recover/preserve them first**, if the previous workspace exists; do not force-push or overwrite the research branch.

## Verified refs at documentation compaction (not release pins)

- Accepted coordination base: **main@1c3a4658e6ac2f4a523fce22d3c8b7327f592731** before this documentation-only change.
- Independently observed branch heads at compaction: **site-prod@c6636e838cc5ca1da3f250091bb1c5c0ff08229e**; **multicity-wip-2026-09-16@5611a05b338b63fab2f51a9bdd676c0c6f71cfd5**; research cutover **b3ceeeceedbd0475cbd059e32020bed3d321da26**. Heads can change asynchronously: re-query immediately before acting.
- Production publication, operational WIP, protected Neon environment, research/preview and historical corrections require separate authority. This docs compaction authorizes **no** data writes, site switch, production deployment, branch-force update or new Neon child.

## Shortest safe next path

1. **Preserve interrupted Work:** recover the reported two local commits, push without force if safe, and save reproducible parity patch, machine diff, tests and immutable inputs. If workspace is missing, mark it missing rather than inventing proof.
2. **Finish bounded 23-city consumer candidate:** verify current pinned cutoff/partial-month/derived rules; integrate researched DST fix in isolated tests; resolve Kyiv current reader/provenance exceptions; test frontend and CSV locally or on an explicitly authorized preview. Document legacy Git inputs that remain.
3. **Run production-like rehearsal:** prove ongoing update freshness, real safe writer path, full consumer contract, controlled legacy|neon switch and rollback. Only then request/execute separately approved production promotion.

## Historical audit index

- [Complete pre-compaction PROJECT_STATE.md](docs/coordination-archive/PROJECT_STATE_full_before_compaction_2026-10-30.md) — exact original Git blob **ebcc286b3bfc93372a61567f1de5fe1d3e49bc2a**.
- [Complete pre-compaction CHANGELOG.md](docs/coordination-archive/CHANGELOG_full_before_compaction_2026-10-30.md) — exact original Git blob **732e7a07f3e92e1138aafe311bff5561f56d60ee**.
- [Archive usage and integrity](docs/coordination-archive/README.md).

**Documentation transition:** DOC-CONTEXT-COMPACTION-01; archival only, no new physical Neon/cutover success asserted.
