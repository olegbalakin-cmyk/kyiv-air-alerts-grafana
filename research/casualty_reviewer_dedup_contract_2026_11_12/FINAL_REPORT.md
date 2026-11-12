# Work C — reviewer → production dedup contract (research-only)

Checkpoint: CASUALTY-REVIEWER-DEDUP-CONTRACT-WORKC-01

## Scope and immutable references
- Base: main@375e69351e6a5aee1be16892821f7cdde2a8f21a. Main reviewer blob cf65d85c4a5ee28fad3c62a1cd0208c93bc44332; protected operator blob 740b985bffffee8c4196be57061fc8b6c8167325.
- Frozen production generator: site-prod@d0a7d22de2828c93236562cccc9d2e68c6a66e3d, blob f5840c201c850b5312db611896b491a69f10e6ec.
- Existing site-prod reviewer blob: 57c67af1ce108222c9a8dc0fefe34d67f9d0e23e, incompatible before future adoption.
- Real source-backed 10 October 2026 Zaporizhzhia proposal: Work A PR #105, exact HEAD 6a0100b0937218c62c5c079fd46e80e5071783cb, Actions #43290975899, artifact #13975389697.
- Independent failure confirmation: PR #106, exact HEAD 5441bdaf60b96e8efbb5019182ac7cf6a3c76da1.
- Legacy compatibility: original site-prod Sumy +1 row retained intact by all scratch writes.

## Minimal repair
Reviewer now accepts and validates incident_id, count_kind, baseline_credited, identity_proof, credited_proof; persists them in the confirmed review_disposition, validates again at promotion, writes them to CSV, and retains unknown existing columns on CSV rewrites. The existing protected main operator passes exactly these five additional evidence fields in REVIEW and PROMOTE, retains same human approval, snapshots, allowed cities, modes and fail-closed rules. Its preview accounts for cumulative baseline credit and already-reviewed snapshots. Strict site-prod reconcile_confirmed_revisions is unchanged.

## Offline proof
The branch-specific GitHub Actions workflow downloads the previously approved Work A proof from GitHub Actions (no new publisher/source HTTP), checks out the exact site-prod generator at an immutable ref, and runs the *actual reviewer and protected operator methods* against temporary queue and revisions copies. It then loads the scratch revision through production generator and validates the effective delta and replay. Synthetic safety tests separately cover cumulative 18→20→23, credited 18→23 (+5), distinct same-day attacks, invalid evidence, cross-incident reuse, conflicting canonical IDs, Sumy and extra CSV fields, HOLD/REOPEN, stale ref, human-only approval and no PROMOTE overrides.

**NO MERGE, PRODUCTION PUBLISH, C2, NEON, WIP MUTATION OR DEPLOY.** This Draft targets main where the protected operator lives; the separate site-prod reviewer is **not** patched or deployed by this research branch. A later controlled code-only adoption to site-prod would require its own authorization and independent base/reviewer compatibility verification. No new monthly coverage state is inferred; October remains COVERAGE_INCOMPLETE. Work D owns display.

## Exact-head physical GitHub Actions
Pending CI on this Draft branch. Do not claim physical PASS until the exact SHA and artifact are independently verified.
