# WORK L — immutable C2 recovery (research, not production)

Exact C2: [Actions #43321997695](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43321997695), attempt 1, main `712c9e351fc3548325cf594cf0617bb33e70a002`. The `update-site` job succeeded; dependent C6 failed before runner assignment. This is a *metadata fact*, not proof of a scheduler root cause.

Downloaded artifact #13991878472: GitHub ZIP SHA-256 `2686f1c54e77e630fd7f8c920f4d88d05f6048b68be26f11f5e3fa03745bebde`; inner bundle SHA-256 `3f53c7ca4a0bc1d0f25cd228dcde003cd45ac247ecab76747405f556f75e8030`. C2 manifest: source input `6648a11242fac16cf023114cd6e58a65c3b49968`, corpus `f855be9c2cfb8617903666d0d898c223c6a91ac0fc56029b5b036dc153db84d4`, 23/23 cities, existing branch `br-bold-mode-b5rub8pq`, existing endpoint `ep-still-violet-b5bg6mhp.c-7.us-east-2.aws.neon.tech`. Writer: 33315 episodes, +48, 0 updated, persisted, confirmed.

Only this exact run/attempt, exact four jobs and their expected statuses, known zero-step C6 failure, archive SHA, writer receipt, 23 receipts, branch and corpus can be recovered. All mismatches are failures. This script does not grant a production publication right.

**Not dispatched.** For a future physical Work A proof, owner must separately approve the **new full PR HEAD** and ensure the protected `c6-neon-shadow-readonly` environment explicitly permits this research branch, with `C6_SHADOW_APPROVED_RESEARCH_SHA` exactly equal to that HEAD. The original branch/SHA receipt cannot be reused. Dispatch the existing **C6 isolated read-only Neon shadow proof** workflow on `research-c6-work-l-recover-2026-11-13`, with:
- research_sha = new exact PR HEAD
- c2_artifact_run_id = `43321997695`; c2_artifact_name = `c2-shadow-inputs-43321997695-1`
- bundle_sha256 = `3f53c7ca4a0bc1d0f25cd228dcde003cd45ac247ecab76747405f556f75e8030`
- writer_workflow_sha = `712c9e351fc3548325cf594cf0617bb33e70a002`
- input_sha = `6648a11242fac16cf023114cd6e58a65c3b49968`
- db_branch = `br-bold-mode-b5rub8pq`
- db_endpoint = `ep-still-violet-b5bg6mhp.c-7.us-east-2.aws.neon.tech`
- owner_approval = `APPROVE_ONE_READONLY_PROOF`

**Post-proof limitation:** an independently created research artifact belongs to the recovery Actions run, not original C2 run #43321997695; it MUST NOT be disguised as `c6-neon-git-preparation-43321997695-1`. The current final-release preparer requires an actual C2-run-bound preparation artifact and overall C2 success. A separately reviewed narrow, owner-gated recovery-aware final-release binding is required before final ZIP. Do not bypass these checks or create a fake original artifact. Freshness, Netlify two-plane binding and rollback remain separate.

No new C2, source HTTP, writer, Git JSON publication, deploy, merge, DST or casualty changes. `GLOBAL_CUTOVER=NO`.
