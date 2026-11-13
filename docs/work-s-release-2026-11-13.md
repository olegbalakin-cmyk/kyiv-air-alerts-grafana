# Work S: final release preflight, 13 November 2026

`FINAL_RELEASE_PREFLIGHT=FAIL; CUTOVER_READY=NO; ROLLBACK_READY=YES; ADMIN_FREEZE_VERIFIED=YES; GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF`.

Data, historical freshness, merged recovery code and current rollback bytes pass. Execution is blocked by uninstalled production authorization: `c6-neon-git-release` does not exist; neither production grant nor the required release variables is configured. Existing Work M authorization is prepare-only. **Minimal action: obtain a separate owner production GO for this exact sequence and its temporary configuration.** No C2, Work L/M rerun, source request or code fix is needed at the checked state.

The [machine receipt and invalid grant templates](work-s-release-2026-11-13.json) contain exact hashes, inputs and fields. These templates have invalid expiry/deploy placeholders; they are not authorization and were not installed.

## Verified state

- `main@d68e35e35c8d50954a77adf99a7dda668724734b` and `site-prod@99648321e64037a6dcf3ae0072d66eedcccc2839` match the approved merges. Work N/R changed code is byte-identical to the exact research heads with prior 20/20 and 16/16 offline PASS; these suites were not rerun. Work R merge changed only its four release-code/test/workflow files.
- C2 #43321997695 attempt 1 still has successful `update-site` and the exact C6 failure before runner/steps. Work L #43390770985 and Work M #43403595621 are successful, attempt 1. Their artifacts and Work N backup are unexpired. Physical L/M/final-report/N ZIP digests match their pinned metadata.
- FINAL generation `2026-11-13T10:08:11.334497+02:00`; 23 cities; six JSON hashes match manifest. Current Git generation `2026-11-13T00:40:41.768144+02:00`. Current casualty tracked blobs (12), two auxiliary audit blobs, five runtime JSON and frontend match Work N. Embedded casualty fields match the final candidate; Kyiv intervals **2858 → 2858**, none lost. There were 55 read-only identity/hash/preservation checks, not a new regression suite.
- Work N #14028565807 remains a current data/static backup after #120. Its 18 member hashes pass; inner package SHA `79e6a1ba0339c9f02d4089933cd91f77db060221a572e49df3c7d11fb2d31ff5`. No redundant snapshot or physical Work P test was made. Work P API publication/restoration timestamps remain 11:22:01Z/11:23:02Z; current `6adb629bc3ebc570117d82e1` is ready/locked and Work O alias `6af6eac51390a92065e9164f` is ready.
- Browser read: pause=true, both production workflows disabled manually, Netlify Auto publishing OFF; release environment/grants absent; NETLIFY_AUTH_TOKEN secret name exists. Owner has repository admin, Actions allow all, publisher YAML explicitly requests `contents:write` and `actions:read`; site-prod is unprotected. Token contents/scope were not read or exercised. GitHub in-progress/queued/waiting/pending/requested queries each returned 0.
- Existing publication freshness gate evaluated at current UTC passes 23/23. Oldest receipt is Kyiv `2026-11-12T22:40:40.888431+00:00`. **Both Netlify verification and Git publication must finish before 2026-11-14 12:40:40 EET (2026-11-14T10:40:40.888431+00:00).** A later run must recheck with its real clock; expiry means NO-GO, with no clock substitution or gate bypass. This certifies historical receipts, not live alert status.

| Final path | SHA-256 |
|---|---|
| `historical-daily-kpi.json` | `ce3cd92fb28e7bad1217d598b2350ac08700c29035e035e36afe702a672194d5` |
| `kyiv-air-alerts-grafana/data/alerts_combined.json` | `633f713d801139ac638aebc6d20dfc867b7d4577a0dbcd1000efb904cdcbd01e` |
| `kyiv-air-alerts-grafana/data/dashboard_data.json` | `1acd666dd2722e8fbc86a95df8e2d85e1a79067283a9a08b21d8d909f7839974` |
| `kyiv-air-alerts-grafana/data/kyiv_threat_mix.json` | `6ba257e402638b7822edcb74d92e6e562736ba3761bdfbd30a0a04074b0f43af` |
| `kyiv-air-alerts-grafana/data/sevastopol_events.json` | `5da726a5f95d3605f51725af5456360c0a9ee1c4de450271a01e98ecdfb7e6fe` |
| `kyiv-air-alerts-grafana/data/site_derived.json` | `4fc0a6b1cd74ac3c880738036af98c14194a91b9ff2b767636fc4dbd1116dbf2` |

## One release sequence, only after separate owner GO

1. Recheck the pinned refs, all current runtime/casualty/aux hashes, active jobs and 36-hour bound. Keep `C6_GIT_ONLY_PUBLISHER_PAUSED=true`; keep ordinary C2, prepare flags, casualty/WIP settings and source access unchanged. Reuse the current Work N/O backup only while these hashes match. No workflow reruns are part of this plan.
2. Create the environment already named by the publisher, **`c6-neon-git-release`**, restricted to branch `main`, with owner `olegbalakin-cmyk` as required reviewer. Keep the sole-owner approval path usable (do not enable prevent-self-review). Do not loosen existing environments. Install only the Netlify repository variables below and a NEW `C6_WORK_L_NETLIFY_OWNER_RELEASE_GRANT_JSON` repository secret from the JSON template, after GO. Set its actual expiry to at most one hour and before the historical deadline. Leave Git publication disabled at this stage.
3. Enable only workflow **360885508**, `.github/workflows/netlify-production.yml`. Once no competing job/deploy exists, temporarily unlock the current Netlify deploy immediately before the authorized production dispatch. Dispatch **once** as `olegbalakin-cmyk`, ref `site-prod`, expected SHA `99648321e64037a6dcf3ae0072d66eedcccc2839`:

```json
{
  "neon_release_mode": true,
  "work_l_recovery_mode": true,
  "c6_run_id": "43321997695",
  "c6_run_attempt": "1",
  "c6_artifact_id": "13991878472",
  "c6_artifact_sha256": "2686f1c54e77e630fd7f8c920f4d88d05f6048b68be26f11f5e3fa03745bebde",
  "final_release_run_id": "43403595621",
  "final_release_run_attempt": "1",
  "final_release_artifact_id": "14025629654",
  "final_release_artifact_sha256": "f2252da0014ce4ed28d5d52a7164e077b8fcd8c99380dd752ee0650412b051ed",
  "approved_release_binding_sha256": "d09bde00bfe80182b19ac70640fc9b07a1fe3f7e4dcb9ecb84f5c6b827584ff7",
  "approved_kpi_sha256": "ce3cd92fb28e7bad1217d598b2350ac08700c29035e035e36afe702a672194d5",
  "approved_generation": "2026-11-13T10:08:11.334497+02:00",
  "work_a_run_id": "43390770985",
  "work_a_artifact_id": "14020616892",
  "work_a_artifact_sha256": "79acb3017dccefdf19def7fe15bdaf2033b27d8c8a6d41f146d7b0e903bd3954"
}
```

The job validates C2 → Work L → Work M, uses FINAL root KPI bytes, deploys the static frontend and verifies live app.js, kpi-range.js and KPI bytes. It must not publish Git JSON. If it fails, stop before step 4. After success, record the actual new production deploy ID, independently confirm the live root KPI SHA `ce3cd92fb28e7bad1217d598b2350ac08700c29035e035e36afe702a672194d5`, generation, release binding `d09bde00bfe80182b19ac70640fc9b07a1fe3f7e4dcb9ecb84f5c6b827584ff7` and 23 verified cities. Re-lock the new approved production deploy and re-disable the Netlify workflow. No Git grant may claim HTTP verification before this proof exists.
4. Fill the separate **Git** grant template with that observed Netlify deploy ID and a fresh expiry at most one hour/before the historical deadline. Store it as `C6_NEON_GIT_OWNER_GRANT_JSON` in `c6-neon-git-release`; set environment variable `C6_NEON_GIT_RELEASE_ENABLED=true`. Recheck expected site-prod SHA and pause=true, then temporarily enable only workflow **360885782**, `.github/workflows/update-netlify-site.yml`. Dispatch **once**, ref `main`, expected SHA `d68e35e35c8d50954a77adf99a7dda668724734b`:

```json
{
  "c6_final_prepare_only": false,
  "c6_neon_git_release": true,
  "c6_preparation_artifact_id": "13991878472",
  "work_a_proof_artifact_id": "14020616892",
  "c6_bundle_artifact_id": "",
  "c6_final_release_artifact_id": "14025629654"
}
```

Here `c6_preparation_artifact_id=13991878472` means the real C2 bundle solely under the explicit Work M recovery contract; it is never represented as a missing preparation artifact. Approve only the resulting `c6-neon-git-release` environment job. The ordinary C2 job remains skipped by input/pause guards. The publisher rechecks physical Work L freshness and hosted KPI, then makes one fast-forward commit of the six allowlisted FINAL files. No writer/source request is involved. Immediately disable the workflow, set the Git release flag false and clear its one-shot secret after completion or failure.
5. Verify Git commit parent, exactly allowlisted changed files and all six FINAL hashes. Through the real production URL check every one of the 23 city keys: KPI/generation/source binding; graph rendering for all eight established modes; CSV parsing/counts; Kyiv intervals and reasons; embedded casualties plus all 12 tracked casualty hashes; Kyiv-threat/Sevastopol and both audit auxiliaries. Check share controls and JS errors. Reuse the existing QA criteria from Work O; do not count its prior proof as the new release's HTTP result. Any data/aux/casualty change or stale receipt stops acceptance.
6. Remove both temporary grants; turn off both owner release flags and the Work L recovery flag. Restore/remove temporary pin variables to their captured prior state. Leave both workflows disabled and pause=true through QA. Netlify Auto publishing can be restored only after successful production QA, a check that no pending/newer deploy will replace the approved release, and the owner-approved end state. **Do not resume ordinary Git-only C2 publication after the Neon switch:** it would replace these six JSON with Git output. No recurring Neon delivery is certified by this one-shot release.

| Netlify repository variable, install only after GO | Exact value |
|---|---|
| `C6_NEON_RELEASE_OWNER_APPROVED` | `true` |
| `C6_WORK_L_NETLIFY_RECOVERY_ENABLED` | `true` |
| `C6_NEON_WORK_A_APPROVED_RUN_ID` | `43390770985` |
| `C6_NEON_APPROVED_FINAL_RELEASE_RUN_ID` | `43403595621` |
| `C6_NEON_APPROVED_FINAL_ATTEMPT` | `1` |
| `C6_NEON_APPROVED_FINAL_ARTIFACT_ID` | `14025629654` |
| `C6_NEON_APPROVED_FINAL_HEAD_SHA` | `9d846279b91b44b324a722ca00276a99956b4fca` |
| `C6_NEON_APPROVED_FINAL_WORKFLOW` | `.github/workflows/update-netlify-site.yml` |
| `C6_NEON_APPROVED_FINAL_ARTIFACT_NAME` | `c6-neon-final-release-43403595621-1` |
| `C6_NEON_APPROVED_FINAL_ARTIFACT_SHA256` | `f2252da0014ce4ed28d5d52a7164e077b8fcd8c99380dd752ee0650412b051ed` |
| `C6_NEON_APPROVED_FINAL_BINDING_SHA256` | `d09bde00bfe80182b19ac70640fc9b07a1fe3f7e4dcb9ecb84f5c6b827584ff7` |
| `C6_NEON_APPROVED_FINAL_FILES_JSON` | `exact files map in the adjacent JSON` |
| `C6_NEON_APPROVED_WORK_A_ARTIFACT_SHA256` | `79acb3017dccefdf19def7fe15bdaf2033b27d8c8a6d41f146d7b0e903bd3954` |

## Immediate rollback within the verified freeze

Stop the release writer, disable its switch/workflow, retain pause=true and lock Auto publishing. Record the current site-prod head and all current runtime/casualty/aux hashes before any recovery write. A failed Netlify job that never published leaves the previous deployment live; first inspect the actual production pointer.

If no post-snapshot data changed, use Work N #14028565807: recover only its five Git runtime JSON plus its same-generation Git historical KPI in one **new fast-forward commit** on the current branch, preserving release code and all files outside the six paths. Republish the validated Work O compatible static deploy `6af6eac51390a92065e9164f` using the operator path physically proven by Work P; verify pointer, lock and actual production HTTP/23-city UI. This future recovery action must be included in the distinct production GO. `6adb629bc3ebc570117d82e1` is the original production pointer, not the current no-loss Git/static package.

If any newer C2, casualty, Kyiv or aux data exists, **do not restore old JSON or reset site-prod**. Preserve those bytes, recapture/reconcile a current Git-only package using the existing no-loss policy, and deploy only a matching-generation static index. A full source rollback is blocked until that reconciliation passes. Work P authority does not prove zero-loss restoration of an arbitrary later data state.

No production operation, workflow enable, unlock, merge, C2/writer/source HTTP, Git publication, DST or casualty/WIP change was performed in Work S. The only remote changes are this requested coordination update in PR #78.
