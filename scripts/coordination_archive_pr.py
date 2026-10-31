#!/usr/bin/env python3
"""Create a docs-only archival PR using runner git credentials and GH_TOKEN.

No force pushes, main writes, merges, permission changes, or external services.
If PR permissions are unavailable, retain the CLI patch and an explicit report.
"""
import json
from pathlib import Path
import subprocess
import sys

import coordination_docs as docs


def run(*args):
    return subprocess.check_output(args, text=True).strip()


def main():
    root = Path(__file__).resolve().parents[1]
    report = {"automatic_pr": "NOT_NEEDED", "main_push": False}
    try:
        if not any(i["bytes"] > docs.WARN for i in docs.check(root)):
            return 0
        head = run("git", "rev-parse", "HEAD")
        if run("git", "status", "--porcelain", "--untracked-files=no"):
            raise ValueError("Start from a clean main checkout")
        date = docs.dt.datetime.now(docs.dt.timezone.utc).date().isoformat()
        plan = docs.archive(root, date, head, dry_run=False)
        if not plan["changes"]:
            raise ValueError("Threshold exceeded but no old checkpoint can be archived safely")
        docs.verify(root, head)
        branch = f"automation/coordination-archive-{head[:16]}"
        run("git", "add", "--", *docs.FILES, str(docs.MANIFEST),
            *[c["archive"] for c in plan["changes"]])
        patch = subprocess.check_output(["git", "diff", "--cached", "--binary"])
        (root / "coordination-archive.patch").write_bytes(patch)
        existing = run("gh", "pr", "list", "--head", branch, "--base", "main", "--json", "url")
        if json.loads(existing):
            report.update(automatic_pr="EXISTING", url=json.loads(existing)[0]["url"])
            return 0
        run("git", "switch", "-c", branch)
        run("git", "-c", "user.name=github-actions[bot]", "-c",
            "user.email=41898282+github-actions[bot]@users.noreply.github.com",
            "commit", "-m", "docs: archive older coordination checkpoints [skip netlify]")
        # A racing main update is safe: PR is based on the pinned source head.
        # An existing different archive branch causes push rejection, never overwrite.
        run("git", "push", "origin", f"HEAD:refs/heads/{branch}")
        body = root / "coordination-archive-pr-body.txt"
        body.write_text("Coordination documents exceeded 12 KiB. Older explicitly marked checkpoints are preserved "
                        "byte-for-byte in dated snapshots; live blockers and the latest checkpoint remain.\n\n"
                        "Validation: archive hashes, byte-range record coverage, and comparison with the source commit passed. "
                        "The coordination docs check runs on the new branch via workflow_dispatch. No auto-merge.\n")
        url = run("gh", "pr", "create", "--head", branch, "--base", "main", "--title",
                  "docs: archive older coordination checkpoints", "--body-file", str(body))
        report.update(automatic_pr="CREATED", url=url, branch=branch)
        # GITHUB_TOKEN-created PR checks may require approval or be suppressed.
        # Explicit workflow_dispatch supplies a check on this branch SHA.
        try:
            run("gh", "workflow", "run", "coordination-docs.yml", "--ref", branch)
            report["validation_dispatch"] = "REQUESTED"
        except subprocess.CalledProcessError:
            report["validation_dispatch"] = "DENIED: manually dispatch Coordination docs on the PR branch"
            print("::warning::PR opened but validation dispatch denied; run Coordination docs on the PR branch")
        return 0
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        report.update(automatic_pr="UNAVAILABLE", reason=str(exc))
        print("::warning::Automatic archive PR unavailable. See coordination-archive-pr-report.json and "
              "coordination-archive.patch artifact. Run python scripts/coordination_docs.py archive --dry-run, "
              "then archive on a maintenance branch and open a PR. No main push attempted.")
        return 1
    finally:
        (root / "coordination-archive-pr-report.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report))


if __name__ == "__main__":
    sys.exit(main())
