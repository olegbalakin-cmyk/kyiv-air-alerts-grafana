# Changelog — recent accepted checkpoints

Accepted coordination transitions, newest first. **This root file is intentionally small.** The complete prior changelog, with every original accepted checkpoint, remains byte-for-byte intact at [docs/coordination-archive/CHANGELOG_full_before_compaction_2026-10-30.md](docs/coordination-archive/CHANGELOG_full_before_compaction_2026-10-30.md). Historical technical detail and older judgments can be read in targeted ranges from that archive. Read the root [PROJECT_STATE.md](PROJECT_STATE.md) for the authoritative *current* coordination state.

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
