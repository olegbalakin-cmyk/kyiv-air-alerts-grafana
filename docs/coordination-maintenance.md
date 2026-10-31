# Coordination document maintenance

Read root PROJECT_STATE.md and CHANGELOG.md first. Keep technical evidence in research files, Actions artifacts or the archive. Archive files are historical evidence; the root state governs current decisions.

## Limits and record format

Sizes are UTF-8 **bytes**, using 1 KiB = 1,024 bytes. Each root passes through 12,288 bytes, warns from 12,289 through 16,384 and fails from 16,385. PROJECT_STATE.md should normally stay at 5–8 KiB. CHANGELOG.md keeps 5–10 recent accepted transitions, newest first.

Put complete checkpoint records between `coordination:checkpoints:start` and `coordination:checkpoints:end` comments. Use `## CHECKPOINT-ID — title` in state and `### CHECKPOINT-ID — title` under optional date headings in changelog. Keep open blockers, track status and next tasks **outside** that region. `<!-- coordination:keep -->` pins a still-current record. The archiver keeps the first state record, the first five changelog records and every pinned record. It never summarizes prose or guesses which historical findings are still current.

The protected text outside the markers remains byte-exact during automatic archival. If protected/pinned material alone exceeds 12 KiB, archival stops with an actionable error before writing files. A maintainer must then move full proofs out of the active snapshot and edit the current state. This cannot be solved safely by deleting arbitrary text.

## CLI

Use Python 3.12 or later; no third-party dependencies are needed. From the repository root:

```bash
python scripts/coordination_docs.py check --base origin/main
python scripts/coordination_docs.py archive --dry-run
python scripts/coordination_docs.py archive
python scripts/coordination_docs.py verify --base origin/main
python -m unittest discover -s tests/coordination -v
```

`archive --force --date YYYY-MM-DD` compacts even below the warning threshold. `--keep-changelog 5` through `10` changes retention. A dry-run writes nothing. After successful archival, a repeated run makes no changes, even with a different date. Make a normal branch commit and PR; never force-push or push automatic archival directly to main.

For reproducible naming, automated runs use the source commit's date; CLI runs default to the UTC date. Each changed root is preserved in full under `docs/coordination-archive/YYYY-MM-DD/<name>.<source-sha256-prefix>.md`. The JSON manifest records its source commit, SHA-256, Git blob SHA, checkpoint byte ranges, retained/archived disposition and before/after sizes. `index.json` authenticates snapshots and manifests with SHA-256. Retained records can therefore also appear in an older full snapshot; this is intentional provenance. Removed records do not reappear or get appended again on rerun.

`verify --base REF` rejects lost checkpoint bytes, modified/deleted legacy archive blobs and removed index entries. CI fetches full Git history and uses the actual PR base or pre-push commit. Existing relative links in exact historical snapshots are interpreted relative to the recorded source root/commit; use the manifest's source commit to follow those links. Absolute SHA, Actions and artifact links remain unchanged. Do not load entire archives into Work context.

## GitHub workflows and permissions

`coordination-docs.yml` runs tests, size checks, archive hash checks and base-history preservation on every PR targeting main and every push to main, with no path filter. The stable status-check name is **coordination-docs**. It also supports manual runs and uploads `coordination-docs-report`. It has read-only repository permissions and no service secrets.

`coordination-docs-archive.yml` runs on root/maintenance changes pushed to main, or manually. Above 12 KiB (or more than ten changelog records), it archives on `automation/coordination-docs-<base-sha>` and opens a PR. Manual input `force=true` exercises the same path below the threshold. It runs only trusted main code, never `pull_request_target` code. It requires contents write, pull-requests write, actions write and the repository setting **Allow GitHub Actions to create and approve pull requests**. GitHub can restrict these even when the workflow declares them.

GitHub can place PR workflows created by GITHUB_TOKEN in an approval-required state, so the helper explicitly dispatches `coordination-docs.yml` on its branch. The [GitHub trigger rules](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow) allow workflow_dispatch from GITHUB_TOKEN. It never merges. A rerun reuses an existing PR; if a push succeeded but PR creation failed, it verifies that branch and retries PR creation without another push. Divergent or unexpected changes require manual review.

If GitHub denies branch push, PR creation or workflow dispatch, the job fails with the CLI fallback. The branch is retained if already pushed; main remains untouched. CLI and read-only CI work independently of these write permissions. No PAT, secret or branch-protection change is made by this setup.

## Enforcement status

At preflight on 2026-10-31, `main@5f64048c2b8de40c336c75b263941598a606a3bf` reported `protected=false`, required-check enforcement `off`, and no repository rulesets. The administration-only protection endpoint returned 403 for the connector. Branch protection has not been changed.

After merging this PR, the owner can make **coordination-docs** a required status check and require PRs on main. Until that owner action, CI detects excessive growth but cannot prevent a direct push or an unchecked merge. Skipped workflows and administrator bypasses are governed by GitHub protection settings. The scripts do not claim permanent enforcement without them.
