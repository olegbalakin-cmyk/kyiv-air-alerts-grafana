# Coordination documents: maintenance contract

Read only root PROJECT_STATE.md and CHANGELOG.md to start Work. Read historical evidence by checkpoint ID and bounded lines. PROJECT_STATE is the current state; archives preserve previous judgments without changing their technical meaning.

Sizes use **UTF-8 bytes, 1 KiB = 1,024 bytes**. Up to and including 12,288 bytes: PASS; 12,289–16,384: WARNING; above 16,384: FAIL. Aim for 5–8 KiB for PROJECT_STATE and concise 5–10 accepted transitions in CHANGELOG. The CI check always runs for PRs to main and pushes to main, without path filters.

## Writer instructions

Keep live track status, unresolved blockers and next tasks **outside** the `coordination:history:start/end` markers in PROJECT_STATE. Put accepted checkpoint details inside the markers, newest first. In CHANGELOG use `### CHECKPOINT-ID — title (date)` inside the same markers; write short transitions with SHA, Actions and artifact links when applicable. Do not add dated `##` groups or unmarked historical records. Do not change or reuse checkpoint IDs. Update the live state when accepting a transition. Archival never decides a technical gate.

```bash
python scripts/coordination_docs.py check
python scripts/coordination_docs.py archive --dry-run
python scripts/coordination_docs.py archive --source-ref "$(git rev-parse HEAD)"
python scripts/coordination_docs.py verify --base-ref origin/main
python -m unittest discover -s tests -p 'test_coordination_docs.py' -v
```

Run on a separate branch; commit snapshots, manifest and roots together; push normally and open a PR. Never push main automatically. `--date YYYY-MM-DD` makes archive names reproducible. Snapshot names include a content hash; a second run (even on a later date) makes no changes. A dry-run writes nothing. No network, dependencies, AI text rewriting or credentials are needed by the archival CLI.

## What is retained and verified

The archiver keeps the newest detailed PROJECT_STATE checkpoint and the latest five CHANGELOG transitions. It moves older entries by removing only their marked byte ranges. Each archive is a **complete exact pre-archive root document**, including every link and all surrounding context. This deliberately retains some overlap. It avoids reconstructing or shortening historical evidence. Immutable snapshot SHA-256, Git blob SHA-1, byte lengths and removed-record offsets/digests are in [manifest.json](coordination-archive/manifest.json).

The checker verifies every snapshot, every recorded removed entry and both original large pre-compaction blobs. Against the Git base it also requires every removed/changed historical record to exist verbatim in a snapshot and forbids rewriting/removing earlier snapshots or manifest entries. Current blockers are never eligible for automatic deletion. The root files contain a stable archive index link so that archive links do not grow with history.

If the active state or five retained transitions still exceed 12 KiB, archival fails before changing any file. Save the exact original with a verified snapshot, then edit only the current-state description or newly written transition; retain live blockers. Automation cannot safely infer which unresolved issue to discard. A newly accepted unusually long checkpoint can require a shorter root description plus a link to its full evidence. Do not paraphrase historical archive text.

The snapshots preserve relative link text exactly. Resolve an old root-relative link at the snapshot's `source_ref` in GitHub, or from the repository root; a link copied into an archive can otherwise resolve relative to the archive directory. All original SHA/Actions/artifact URLs remain byte-exact.

## Automatic PR and enforcement limits

After merge, `Coordination docs` checks every main push and PR. An independent main-only job starts archival as soon as either root exceeds 12 KiB, including WARNING. It creates a docs-only branch and PR, never pushes main or merges. It explicitly dispatches validation on the bot PR branch: depending on GitHub's version/settings, GITHUB_TOKEN-created PR checks can require approval or be suppressed, while workflow_dispatch can start a run. See [GitHub's token documentation](https://docs.github.com/en/actions/concepts/security/github_token). No PAT or additional secret is required. If the repository/org disallows Actions PR creation, write scopes or workflow dispatch, the job reports the denial and uploads a CLI patch where available; manual branch + CLI + PR remains supported. Existing PRs are reused, remote branches are never force-pushed.

At initial implementation, GitHub's main-branch API reports `protected=false`, required checks `enforcement_level=off`, empty contexts/checks; repository rulesets are empty. The detailed protection endpoint returns integration HTTP 403. **No required status check currently blocks a direct main push or merge.** No protection setting was changed. Once reviewed, the owner can require `coordination-docs / size-and-integrity` and restrict bypasses. CI is detection until that protection is enabled, and automation becomes active only after the workflow is merged. PR-creation permissions cannot be read through the available connector; the main-only job detects any runtime denial and preserves the CLI fallback.
