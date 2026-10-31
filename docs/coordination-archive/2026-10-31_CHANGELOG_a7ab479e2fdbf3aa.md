# Changelog — recent accepted checkpoints

Accepted coordination transitions, newest first. **This root file is intentionally small.** The complete prior changelog, with every original accepted checkpoint, remains byte-for-byte intact at [docs/coordination-archive/CHANGELOG_full_before_compaction_2026-10-30.md](docs/coordination-archive/CHANGELOG_full_before_compaction_2026-10-30.md). Historical technical detail and older judgments can be read in targeted ranges from that archive. Read the root [PROJECT_STATE.md](PROJECT_STATE.md) for the authoritative *current* coordination state.

## 2026-10-31

### NEON-BRANCH-SLOT-FREED-01 — capacity recovered (coordination-only)

- Owner deleted obsolete historical Neon leaf `br-cold-sky-b5jhai9p`; independently checked Neon project `green-cake-44216048`: **9/10** existing branches, deleted ID absent. Quota blocker removed, but **no child created or writer run** by this verification.
- Next: execute saved `isolated_writer.py` on a new disposable child of `br-bold-mode-b5rub8pq` in an authorized runner with independently verified child-scoped credentials; require crash-after-COMMIT, retry, UUID/readback, freshness and fail-closed evidence. **Production remains NO-GO**; no production or Neon writes during this checkpoint.


### C6-LIVE-WRITER-FRESHNESS-01 — bounded live HTTP identity accepted, writer blocked at 10/10 branches

- Independently checked [Actions 41141326530](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41141326530) SUCCESS with artifact **13018209142**: genuine Kyiv Digital HTTP 200, 917,331 raw entity bytes and a prospective canonical source identity; 15/15 **synthetic** freshness/fail-closed tests PASS. No physical Neon UUID.
- Follow-on [Actions 41196606039](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41196606039) SUCCESS; original HTTP proof now saved in research commit `0f0d7181e04cb053b773fb5c0ecf284bb82bc66a`, backup artifact **13040277727**. Machine verdict `PARTIAL_HTTP_IDENTITY_ONLY`.
- Neon project `green-cake-44216048` independently shows Free **10/10** non-deleted branches (4 ready, 6 archived), consistent with reported isolated create `HTTP 422 branches limit exceeded`. **No child created, no SQL write, no independent UUID/readback or new rendered JSON.** `C6/C3=PARTIAL`, `GLOBAL_CUTOVER=NO`.
- Next owner decision: authorize deleting one verified obsolete isolated leaf, or raise branch limit; then execute the saved physical isolated writer/freshness gate. No production or Neon mutations in this docs-only checkpoint.


### C6-PREVIEW-ROLLBACK-01 — 23-city frozen browser package and source-only rollback accepted

- [Actions 41139538902](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41139538902) **SUCCESS**, tested source `9c006f84d1b647d717e2ba27db0ceed5fbccd9c1`, [proof commit `66f87241`](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/commit/66f872413f67668c9bd23b94cff17520fea705f9), artifact **13018841540**. Authorized runner-local Chrome: **23 cities (4 exact / 19 proxy), eight city modes, comparisons, September historical KPI control, derived charts/table, 45 downloaded CSV content checks and four visible HTTP/JSON failure cases PASS**; browser response digests match candidate, 0 cross-origin requests and 0 uncaught page errors.
- Preview-only switch survives URL updates/reload. Source-only rollback changes **only preview-config.js**, restores all **23 legacy** monthly/history views and a real legacy CSV; frontend/data hashes unchanged. Kharkiv October witness **313 → 312 alerts**. Accepted candidate JSON bytes unchanged; same-source historical fallback and Git auxiliaries documented.
- Candidate visibly marked **RESEARCH / NEON CANDIDATE / DST SIMULATION**, cutoff **2026-10-30T15:27:55.138400Z**, no ongoing-freshness claim. Complete downloadable preview/proofs plus screenshots retained. No external Netlify deployment: connector lacks upload/deploy and CLI lacks authorization; local browser execution completed on the authorized Actions runner.
- **C6/C3 PARTIAL; GLOBAL_CUTOVER=NO.** Four physical DST cases, live writer/fail-closed/ongoing freshness, Kyiv current provenance and production switch/operational rollback remain separate gates. No Neon, writer, site-prod, operational WIP or production Netlify changes. Next: close those gates; frozen parity/browser/CSV/preview rollback need no new general audit.

### C6-RECOVERED-PARITY-VERIFICATION-02 — frozen replay reproduced; difference causes verified

- Physically executed pinned offline replay: **31,935 → 31,939** rows after DST simulation, **23 cities**, original reports byte-identical. First saved replay checkpoint `9ea0693fa5b8d24959d88c1ba55981d059c5fc23`; final verified research commit [`741f277f`](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/commit/741f277f73d1dde1325069d25fa00b44a42d6f03). Direct 22-city differences **0 without / 366 with DST projection**.
- Corrected accounting of **1,354** exact JSON paths: **847 DST + 457 legacy derived omission of accepted C4-KH-06 + 49 cutoff timestamps + 1 research marker; unexplained 0**. Single-interval Kharkiv counterfactual reproduces published derived fields exactly. Minimal loader correction passes isolated real-loader regression checks; candidate already uses the accepted long interval. No deployed generator or Neon modification.
- All seven DST proposal tuples match pinned source events. Four physical DST cases remain open. Reproducible harness, complete classified diff, tests, patch, source witnesses and hashes saved under `research/neon_cutover_work_2026_10_30/`; candidate ready for bounded research preview with DST simulation. Fresh database/primary receipt, complete upstream CSV, browser/CSV, freshness and switch/rollback are outside this proof. **C6/C3 PARTIAL; GLOBAL_CUTOVER=NO**. Next: authorized preview consumer and rollback rehearsal.

### RECOVERY-RESEARCH-COMMITS-01 — two original Work commits saved and remotely verified

- Owner recovered an original Git bundle and performed an ordinary **non-force fast-forward push**. Independently verified remote `research-neon-cutover-work-2026-10-30@e153495537ac4cf002c6ec9aaa58ddb03c0e88ba`; GitHub commit parents **b3ceeece → e8a1717afc6d2f7c574479aa8f369b8c82b4f3f2 → e153495537ac4cf002c6ec9aaa58ddb03c0e88ba**, compare ahead 2 / behind 0.
- Recovered research source, pinned inputs, JSON machine diffs, DST simulation account, smoke script, cutover patch proposals and SHA-256 manifest exist in `research/neon_cutover_work_2026_10_30/`. Source artifacts are **research-only, not promoted or re-executed** as an accepted cutover proof. Saved machine verdict **PARTIAL_RESEARCH**, **1,354** difference paths; replay numbers are marked `recovered_not_yet_reexecuted` in the saved checkpoint.
- **Accepted scope:** Git preservation recovered; physical latest parity, writer/readback, frontend browser/CSV, rollback and production release remain open. `RESEARCH_COMMITS_RECOVERED=PASS`, `C6=PARTIAL`, `C3=PARTIAL`, `GLOBAL_CUTOVER=NO`. Next: verify/re-execute preserved 23-city candidate and difference accounting, then fix only critical release blockers. This transition updates documentation only.

## 2026-10-30

### DOC-CONTEXT-COMPACTION-01 — coordination documentation compacted; historical evidence retained

- Root PROJECT_STATE.md and CHANGELOG.md replaced by concise current-state and recent-transition summaries to avoid repeatedly loading ~1.43 million characters into Work sessions.
- Their complete previous contents are kept under docs/coordination-archive by **reusing exact original Git blobs**: PROJECT_STATE **ebcc286b3bfc93372a61567f1de5fe1d3e49bc2a**, CHANGELOG **732e7a07f3e92e1138aafe311bff5561f56d60ee**. Archives are immutable historical reference, not reinterpreted evidence.
- Confirmed newer research Actions **41123467415** completed with artifact **13009048201**, but this job did not perform physical Neon persistence and is **not** a cutover gate. Interrupted Work's reported local commits and parity improvements remain unaccepted until recovered and independently reviewed.
- **No change** to site-prod, operational WIP, Neon data or production writer; **GLOBAL_CUTOVER=NO; C6=PARTIAL; C3=PARTIAL**. Next task: preserve interrupted Work commits, then verify the actual 23-city parity candidate and rehearse rollback.

### C6-PROVENANCE-04B — bounded negative evidence accepted (previous checkpoint)

- [Actions 41120424463](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41120424463) failed with **zero job steps** and no artifact. The accepted negative proof does not establish an actual HTTP→physical Neon UUID. Newer, independent research run 41123467415 succeeded in the network/parser stage only; those are distinct execution scopes. Full original checkpoint in [archived changelog](docs/coordination-archive/CHANGELOG_full_before_compaction_2026-10-30.md).

### C6-23CITY-INTEGRATED-SHADOW-02 — bounded physical reader accepted, release parity partial (previous checkpoint)

- [Actions 41076975484](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41076975484): read-only Neon 23-city consumer-schema proof accepted (**31,903** closed AIR); **2,570** JSON path differences to pinned legacy reference, not proven current parity. Full original checkpoint and immutable evidence references in the [archived changelog](docs/coordination-archive/CHANGELOG_full_before_compaction_2026-10-30.md).

## Maintenance policy

After accepting any checkpoint that changes the current state or next task, update root PROJECT_STATE.md and prepend a **brief** accepted transition here. Keep the root files under approximately 20 KB; periodically move older detailed entries to dated archives while retaining exact source Git blobs and stable links. Do not record exploratory Work updates as accepted physical evidence, or infer production from a research-only run.