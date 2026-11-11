# C6 Work A — exact-run readback preflight (2026-11-11)

**Decision: PHYSICAL_READBACK_BLOCKED_BY_APPROVAL.** `GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF`.

## Immutable evidence

- Accepted coordination checkpoint: `main:PROJECT_STATE.md` / `main:CHANGELOG.md`, `C6-POSTMERGE-C2-EXPORT-23-01`. This research result does not promote a new release checkpoint.
- C2 Actions `43055353190`: completed/success, scheduled, GitHub workflow SHA `b22a2699466170d33ea72b71bd35b4aa12706bca`, attempt 1.
- C2 Actions artifact `13873291895` (outer GitHub artifact ZIP `0bbbe59ba6d4066a949f071a1bbf61f7c3a21a4ba487cb9e3d1dcadd297c2922`).
- **Inner** `c2-shadow-inputs.zip` SHA-256 `ebcf2b6a94080f7a374b0897715c732846c5bd55eb4127f79d202cf8fec04c1d`; validated against inner sidecar.
- `manifest.json` SHA-256 `f64620936677b3a329a5e7823d3f4d52e4bc60c5b6a29bb8da6ff943adf3e433`; all eight file hashes match.
- C2 manifest: 23/23 historical receipt cities, 23/23 complete cities; site input SHA `6de49e3b0cf9692c7bb242672e92f062e516af20`; db branch `br-bold-mode-b5rub8pq`; db endpoint `ep-still-violet-b5bg6mhp.c-7.us-east-2.aws.neon.tech`.
- C2 receipt: 33,135 canonical episodes; corpus SHA-256 `4cd2fce445e49ec200ea3a202ed8bf9e1ada9c17d60c23eb7e9c7c65e1526226`; run ID `f7da738b-9f8c-4845-bbe9-2a8073477dcb`.

## PR70 scoped allowlist and tests

- PR #70 immutable tested SHA: `cdfb456def46cecead8fc4e78ebe88b4f19f0b44`.
- C6 builder blobs at exact post-PR62 `site-prod@6de49e3b0cf9692c7bb242672e92f062e516af20` and current `site-prod@cf960d7c7a626681295e1d6444dec97a341be7cf`:
  - `update_data.py` `45d4c3b656b91f927dc519cffdbd09f09ed00392`
  - `apply_ukrainealarm_bridge.py` `aaedf36299bac69a76971d7e8399894e416d1643`
  - `add_sevastopol_exact.py` `6698ec743b6efcd9aeb059dd81b51cc05ae93493`
- All three correspond to path/exact baseline-bound approved lists; `6698ec743b...` is the specific new PR #62 blob.
- Targeted GitHub Actions `43074337098` SUCCESS, artifact `13882250271`, **4/4 PASS**. The workflow checked out `cdfb456def46cecead8fc4e78ebe88b4f19f0b44` explicitly. Four tests cover authorized blob, arbitrary blob rejection, cross-path rejection, and baseline mismatch rejection. No code defect proven.

## Narrow research-only workflow staging

- Research branch `research-c6-post62-exact-head-tests-2026-11-11`, base `cdfb456def46cecead8fc4e78ebe88b4f19f0b44`.
- Commit `84a70736cac92c05d2d90ea397f9a313f35b7997` introduced offline-only workflow targeting immutable PR70 code. PASS as above.
- Commit `5316fcf5bc96fd30653012c4048960a1a23a569e` changed ONLY two occurrences of the old research-branch pin in `.github/workflows/c6-neon-shadow-isolated-proof.yml` to this new branch.
- Approval controls **unchanged**: `workflow_dispatch`, GitHub actor `olegbalakin-cmyk`, owner phrase `APPROVE_ONE_READONLY_PROOF`, full `github.sha == inputs.research_sha`, environment `c6-neon-shadow-readonly` and `vars.C6_SHADOW_APPROVED_RESEARCH_SHA` exact match, success-C2 metadata, artifact digest, pinned site checkout, read-only DB credential, non-publishing gate, and always-upload fail-closed verdict.
- This research-branch workflow edit does **not** establish that the manually dispatched workflow is authorized or that the environment variable/secret is configured. The exact post-staging branch HEAD must be verified again before any proposed dispatch; it is not the original `cdfb456d...` PR70 SHA.

## Precise BLOCKED reasons

1. No explicit owner approval phrase for this specific new physical proof was supplied or observed through GitHub.
2. No independently verified GitHub Environment approval for **the new research head** (`C6_SHADOW_APPROVED_RESEARCH_SHA`) or evidence that `NEON_JSON_SHADOW_READONLY_DATABASE_URL` is configured for it. Protected environment permissions cannot be presumed.
3. Existing main workflow remains pinned to `research-c6-unblock-shadow-proof-2026-11-01`; the minimal branch-specific workflow change is research-only and unmerged. The manual dispatch must be made by the required owner on a correctly approved workflow ref; never bypass an `if` guard.
4. No physical Neon transaction, SQL readback, six-file candidate proof, or DB snapshot SHA was produced. No production deployment/merge, source HTTP, Neon writes, C2 writer, or DST activation.

## Next gated action

After owner reviews research-only workflow change, approves its **current full HEAD** in the protected GitHub Environment and confirms the dedicated read-only secret, dispatch **one** read-only proof with: `research_sha` matching the selected run ref full SHA, `c2_artifact_run_id=43055353190`, `c2_artifact_name=c2-shadow-inputs-43055353190-1`, inner bundle SHA `ebcf2b6a94080f7a374b0897715c732846c5bd55eb4127f79d202cf8fec04c1d`, `writer_workflow_sha=b22a2699466170d33ea72b71bd35b4aa12706bca`, `input_sha=6de49e3b0cf9692c7bb242672e92f062e516af20`, `db_branch=br-bold-mode-b5rub8pq`, `db_endpoint=ep-still-violet-b5bg6mhp.c-7.us-east-2.aws.neon.tech`; `owner_approval=APPROVE_ONE_READONLY_PROOF` only after owner explicitly approves. Keep `GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF`.
