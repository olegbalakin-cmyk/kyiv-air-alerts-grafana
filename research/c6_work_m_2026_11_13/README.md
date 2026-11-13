# Work M — exact-pair final prepare preflight (NOT AUTHORIZED)

**Research only; no production action executed.** Existing `c6_neon_final_prepare.py` and `update-netlify-site.yml` are narrowly changed on Draft PR #116. Original C2 preparation is absent; it is NOT reconstructed or claimed as immutable.

## Immutable provenance (verified)
- C2 run `43321997695`, attempt `1`, main `712c9e351fc3548325cf594cf0617bb33e70a002`; `update-site=success`, overall `failure` due to zero-runner/zero-step C6 dependent job. Both release jobs skipped.
- C2 outer ZIP artifact `13991878472` SHA `2686f1c54e77e630fd7f8c920f4d88d05f6048b68be26f11f5e3fa03745bebde`; inner bundle SHA `3f53c7ca4a0bc1d0f25cd228dcde003cd45ac247ecab76747405f556f75e8030`; 8/8 payload hashes, 23/23 receipts, persisted 33,315 episodes (+48).
- Work L independent run `43390770985` attempt `1`, exact SHA `325669a4441f5cfaeed8327f08032c0ecf4449b9`; artifact `14020616892` outer SHA `79acb3017dccefdf19def7fe15bdaf2033b27d8c8a6d41f146d7b0e903bd3954`; 18/18 evidence hashes, 6/6 candidate JSON, 23/23 historical freshness.
- Neon branch `br-bold-mode-b5rub8pq`; source input `6648a11242fac16cf023114cd6e58a65c3b49968`; corpus `f855be9c2cfb8617903666d0d898c223c6a91ac0fc56029b5b036dc153db84d4`; generation `2026-11-13T10:08:11.334497+02:00`.
- Original `c6-neon-git-preparation-43321997695-1` **never existed**. The new contract accepts only exact C2 failed-before-runner + exact Work L physical evidence. It refuses substitutions and keeps SHA, 23-city, expiry, identity, run attempt and owner authorization checks.

## Owner-gated *future* prepare-only action (not executed)

Before attempting a physical run, require offline exact-HEAD tests to PASS, review exact-source/zero-side-effect constraints, and get explicit permission **for one prepare-only dispatch** at that HEAD. Existing production updater workflow is currently manually disabled; do not re-enable or merge it under this research task without a distinct permission and controlled workflow state plan.

The protected environment `c6-final-prepare-only` must approve the exact branch/SHA. Repository variable `C6_FINAL_PREPARE_ENABLED` remains OFF unless separately owner-enabled. The repository secret `C6_FINAL_PREPARE_OWNER_RECEIPT_JSON` must be configured by an authorized admin; **do not commit the receipt**. The receipt is purpose-limited, expires within 36 hours, is bound to current exact prepare SHA and has:
```json
{
  "schema": "c6-final-release-prepare-only-work-l-v1",
  "decision": "APPROVE_PREPARE_ONLY_NO_PUBLICATION",
  "repository": "olegbalakin-cmyk/kyiv-air-alerts-grafana",
  "publication_allowed": false,
  "global_cutover": "NO",
  "dst_correction": "OFF",
  "provenance_contract": "C2_FAILED_PRERUN_C6_WORKL_PHYSICAL_PROOF_V1",
  "prepare_code_sha": "<approved exact HEAD, 40 lowercase hex>",
  "release_id": "<approved unique release id>",
  "expires_at": "<time-bound UTC timestamp, at most 36h>",
  "c2_run_id": 43321997695,
  "c2_run_attempt": 1,
  "c2_head_sha": "712c9e351fc3548325cf594cf0617bb33e70a002",
  "c2_input_sha": "6648a11242fac16cf023114cd6e58a65c3b49968",
  "c2_corpus_sha256": "f855be9c2cfb8617903666d0d898c223c6a91ac0fc56029b5b036dc153db84d4",
  "c2_bundle_sha256": "3f53c7ca4a0bc1d0f25cd228dcde003cd45ac247ecab76747405f556f75e8030",
  "c2_bundle_artifact_id": 13991878472,
  "c2_bundle_artifact_sha256": "2686f1c54e77e630fd7f8c920f4d88d05f6048b68be26f11f5e3fa03745bebde",
  "work_a_run_id": 43390770985,
  "work_a_run_attempt": 1,
  "work_a_head_sha": "325669a4441f5cfaeed8327f08032c0ecf4449b9",
  "work_a_artifact_id": 14020616892,
  "work_a_artifact_sha256": "79acb3017dccefdf19def7fe15bdaf2033b27d8c8a6d41f146d7b0e903bd3954",
  "neon_branch": "br-bold-mode-b5rub8pq",
  "expected_cities": 23,
  "generation": "2026-11-13T10:08:11.334497+02:00"
}
```
Dispatch input: `c6_final_prepare_only=true`, `c6_neon_git_release=false`, `c6_preparation_artifact_id` **empty**, `c6_bundle_artifact_id=13991878472`, `work_a_proof_artifact_id=14020616892`. All default OFF; no C2 run. The job uses only GitHub evidence and local ZIP transformations and writes eight final files (six JSON + binding/manifest) after guards PASS. Verify uploaded artifact SHA against all eight member SHA and independent report before declaring `FINAL_ZIP=PASS`.

**HARD boundary:** existing `c6_neon_one_shot_publisher.py` still rejects this recovery pair because it requires C2 overall SUCCESS and the absent original C2 preparation artifact. This draft does NOT change that publisher. Even a future FINAL ZIP PASS does not permit publication or a cutover; separately review/approve publisher adaptation and establish a fresh cutover-time Git-only no-loss rollback.

## Rollback verdict (2026-11-13)
- Current `site-prod@f0cfcbc862ca3dbf1b853e72de07ffcf6042856f`; the earlier Work G2 baseline `d0a7d22de2828c93236562cccc9d2e68c6a66e3d` is stale.
- Netlify current production `6adb629bc3ebc570117d82e1` (Oct 23), not current Git-only rollback.
- Nonproduction alias `6af629b311d9632a220e652a` is READY but was generated against the earlier Git-only baseline and proves only alias deployment, not recovery of current production.
- Fresh cutover-time Git-only five-JSON and static KPI snapshot, complete casualty/aux/interval no-loss comparison, and production restore permission/rehearsal remain OPEN.
- `FINAL_ZIP=FAIL; ROLLBACK_READY=NO; CUTOVER_READY=NO; GLOBAL_CUTOVER=NO`.

## Physical constraints
No new C2, writer, source HTTP, merge, Git publication, Netlify production deployment, cutover, or DST correction. No future action without distinct owner approval.
