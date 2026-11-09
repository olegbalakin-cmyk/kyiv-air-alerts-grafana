# C6 minimal same-run capture receipts integration (draft, 2026-11-09)

**REVIEW ONLY — NOT ACTIVATED.** `publication_allowed=false`; `GLOBAL_CUTOVER=NO`.

Authority: `main@0546986e69f2bbd4d5507f80dada426775eb1489`; site-prod `f90a61ea60ac8ce69d81b0fc21920b84bfef9d64`.
The actual production workflow is `.github/workflows/update-netlify-site.yml` on main, with
`actions/checkout ref: site-prod`. Changes to main-only research collector copies cannot
activate site-prod. Production's three exact collector blobs match the independently
replayed base of `3d686a8a622433e242a01917a659a299082ec5bc`.

Existing research proofs, not repeated: 70 receipt tests / 17 DST tests;
physical Neon->JSON read-only proof Actions 42487688608; existing DST
rolling diagnosis `83829c07e9b1e169121ba91029ff1f5f5e52f855` is BLOCKED.
The 21 historical bridge checkpoints are bounded evidence only; 0/23 full
new-contract physical receipts and 0/23 physical 36-hour passes.

Scope: minimal flagged collector hooks and persistent metadata-only checkpoints
in a separate site-prod-targeted draft; flagged export in the current C2
workflow; same-run corpus/run/input/source-hash verification in the existing
research reader. A separately approved read-only proof must obtain real
continuous captures. Do not enable writer, publish, or switch frontend sources.

Do NOT merge this draft, the companion site-prod draft, or change any
Environment/repository variables before an owner-approved rollout. No current
release or historical acceptance claim, no changes to PR #42/#44/#45,
PROJECT_STATE.md or CHANGELOG.md.
