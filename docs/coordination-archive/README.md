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

## Incremental snapshots

[Machine index](index.json) lists each dated full snapshot and its manifest. Each manifest includes source commit, source SHA-256/Git blob SHA and byte ranges for every retained or archived checkpoint. The index also pins each manifest's SHA-256. The original two blobs above remain mandatory and unchanged.

Run `python scripts/coordination_docs.py verify --base origin/main` to verify the snapshots and ensure every checkpoint in the comparison base is still available verbatim. Run `archive --dry-run` before archival. See [maintenance procedure and CI permissions](../coordination-maintenance.md).
