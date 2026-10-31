# Coordination documentation archive

These two files are **historical reference only**. Current coordination truth and release gates live in the compact root [PROJECT_STATE.md](../../PROJECT_STATE.md), with recent accepted transitions in root [CHANGELOG.md](../../CHANGELOG.md).

## Immutable pre-compaction snapshots

Original coordination HEAD before archival: **main@1c3a4658e6ac2f4a523fce22d3c8b7327f592731**, 2026-10-30.

- [PROJECT_STATE_full_before_compaction_2026-10-30.md](PROJECT_STATE_full_before_compaction_2026-10-30.md): original Git blob **ebcc286b3bfc93372a61567f1de5fe1d3e49bc2a**. Every prior checkpoint preserved.
- [CHANGELOG_full_before_compaction_2026-10-30.md](CHANGELOG_full_before_compaction_2026-10-30.md): original Git blob **732e7a07f3e92e1138aafe311bff5561f56d60ee**. Every prior accepted transition preserved.

The archive paths point to **the very same Git blob objects** as the pre-compaction root files; this is byte-exact archival, not regenerated text. Verify with Git blob SHA, not just a paraphrase or visual comparison.

## Efficient reading

Do **not** load either entire file into an AI chat or Work context. Search by exact checkpoint name and fetch only bounded line ranges or use local streaming scripts. Save large extracted evidence and machine diffs to files; return concise summaries with commit SHA, Actions run and artifact ID. If old Markdown anchors are needed, link to the appropriate archived file path rather than the compact root document.

Archive history is not a production deployment record. Only newly accepted checkpoints documented in the compact coordination root can change the current release decision.

## Automatic archival (2026-10-31 onward)

Use [the manifest](manifest.json) for the complete snapshot inventory, SHA-256, Git blob SHA-1, byte lengths and byte-range hashes of transferred checkpoint records. [Browse dated snapshots](.). Root documents link here through a fixed index link. The index therefore stays discoverable without growing the root files.

- Exact main roots before this maintenance: [PROJECT_STATE](2026-10-31_PROJECT_STATE_3c1fb6fe218ee955.md) and [CHANGELOG](2026-10-31_CHANGELOG_a7ab479e2fdbf3aa.md).
- Prepared pre-archive roots: the manifest records five transferred PROJECT_STATE checkpoint sections and five transferred CHANGELOG transitions. Eight unique checkpoint IDs occur in those ten transferred sections; overlap is deliberate. Full snapshots also preserve concurrent accepted `main@5f64048c2b8de40c336c75b263941598a606a3bf`; its latest checkpoint remains in current state.
- The two original pre-compaction archives above remain the exact original Git blobs. Nothing in them is rewritten or summarized. Each new dated snapshot is also a complete byte-exact pre-archive document.

Run `python scripts/coordination_docs.py verify --base-ref origin/main` to verify immutable snapshots and historical-record coverage against the Git base. Read [maintenance instructions](../coordination-maintenance.md) for safe CLI use and automatic PR permission limits. Old relative link text is preserved; resolve it at its source Git ref or from the repository root, rather than relative to this archive directory.
