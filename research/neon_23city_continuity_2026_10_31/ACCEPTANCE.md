# C6-23CITY-CONTINUITY-02 — bounded Kyiv PASS; 23-city continuity BLOCKED

Implementation `d981d52a01daebecb8d70ab38057009c2202cbe1`; execution commit
`f20069efda76aefa6ab1f09d67afb8f21c417fd1`.
[Collection Actions 41208139352](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41208139352)
completed SUCCESS. Raw reports were saved in `bc37588906732892b517c6de6b1a9c0803098ce3`;
independent review and reproducible auditor in `cd8aaf0d3553f08b1a5db04677af94eabbc43b76`.
SUCCESS is the research job result; the live 23-city release verdict is **BLOCKED**.

The owner-authorized experiment ran on existing child `br-crimson-star-b59u7ge3`
from `2026-10-31T14:01:01.028389Z` to `14:28:32.293668Z`: **27m 31.18s**.
Five upstream GET attempts: **four history-source attempts + one documentation
preflight**. One additional GitHub Environment metadata GET gives six HTTP GETs
inside the runner including that control-plane read. No source retry, redirect,
new Neon branch, TTL change or recurring scheduler.

| Evidence class | Accepted result |
| --- | --- |
| Physical PASS | Kyiv Digital HTTP 200 twice; original C2/C3 transactional writer; separate READ ONLY UUID/source/checkpoint/run readbacks; checkpoint `2 → 3 → 4`; same episode/source UUID pair; zero exact duplicates. |
| Physical PASS | Both post-poll child snapshots generated complete 23-city candidates: 31,977 AIR parents / 145 observations; four generated JSON files plus two pinned Git auxiliaries per cycle. |
| Bounded PASS | Kyiv's two source captures at `14:02:12.122110Z` and `14:27:12.951827Z`, about 25 minutes apart. The latest completed event retained its identity while the HTTP body hash changed. This proves repeated observation and checkpoint continuation; source identity remains prospective. |
| BLOCKED | UkraineAlarm Swagger preflight returned HTTP 403. The provider was stopped; **zero regionHistory or active-status requests** followed. All 21 configured UkraineAlarm cities lack live persistence proof in this experiment. Their data endpoint availability is NOT PROVEN, rather than physically tested as unavailable. |
| BLOCKED | Sevastopol's first public channel page returned HTTP 200 and zero completed AIR pairs, recorded in checkpoint 1. The second attempt timed out before an HTTP response; no second checkpoint or episode UUID proof. Occupation-administration provenance is retained. |
| NOT PROVEN | Complete current active AIR status, upstream cache/current-data certification, long-term continuity and canonical active-to-closed transition. Two-round current source observations are verified only for **Kyiv: 1/23**; fully certified current source currency remains **0/23**. |

Kyiv episode UUID: `478ea32b-e567-4f8d-a11a-b822648c41ee`.
Source observation UUID: `43435751-c595-4c18-9615-dde70ab18bb7`.
The source observation's first capture hash/time remained unchanged. Each new
capture hash/time is bound in its new immutable checkpoint and ingestion-run
receipt; DB commit and candidate generation time do not refresh the source clock.

**PUBLICATION_BLOCKED**, including the actual missing-source case. No publish
directory was created, no Git-data fallback was used to manufacture freshness,
and neither candidate was published. Existing physical DST repairs and Kyiv
current selection/provenance remain separate release dependencies. No new full
historical backfill gate is introduced. C6/C3 PARTIAL; GLOBAL_CUTOVER=NO.

The protected Environment metadata read passed: Environment ID `25877858735`
has a custom branch-policy protection rule. The runtime verified the exact
child hostname, database and child-only role, against the current Neon branch
attestation and accepted role-scope proof. No credential value was recorded.

## Evidence and independent verification

- [Artifact 13046430297](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41208139352/artifacts/13046430297), ZIP SHA-256 `808dbfed16200857f0e099642a5258397eec2573c6b827e49c6de03ce18b65f3`.
- An independent download verified all **85** manifest hashes, saved successful
  HTTP entities, capture/commit/read ordering, checkpoint links, stable UUIDs,
  provider-stop behavior and both 23-city candidates. The Git machine-verdict
  bytes matched the original artifact. The failed 403 body was hashed by the
  runner but not retained; its raw digest cannot be independently recomputed.
- [Independent review](proof/41208139352/independent_verification.json),
  [raw verdict](proof/41208139352/machine_verdict.json),
  [source matrix](proof/41208139352/source_matrix.json),
  [request ledger](proof/41208139352/http_requests.json), and SQL receipts in
  `proof/41208139352/cycle-*/sql/`.
- [Complete evidence archive](proof/41208139352/full_evidence.zip) and
  [archive index](proof/41208139352/full_evidence_index.json) retain all artifact
  files in research Git, including source entities, both snapshots/candidates
  and SQL receipts. The preservation workflow makes no source request or DB write.
  [Preservation Actions 41210485947](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41210485947)
  passed; saved archive commit `9704d5fa02c23ecc28c452c06b44639dc757107b`.
  The archive is 11,037,069 bytes, SHA-256
  `5a011fae488c3efc5994b45818f8e473d85aba08eadd3bfa39d0c9be800bcd55`.
  Independent reconstruction from the downloaded artifact matched both that
  SHA-256 and Git blob `b6e558b201433fe64c4524058dc8807457a3088a`.

Offline audit: `python research/neon_23city_continuity_2026_10_31/audit_evidence.py ARTIFACT.zip --expected-zip-sha256 808dbfed16200857f0e099642a5258397eec2573c6b827e49c6de03ce18b65f3 --output review.json`.

Next work is source-specific: resolve the provider-approved UkraineAlarm
documentation/access contract without bypassing the 403; obtain history and
current AIR/ancestor-status receipts for its 21 cities; establish a complete
Sevastopol current-status contract; resolve cache/source currency and Kyiv
current selection. Then close the separately scoped DST/Kyiv dependencies and
operational source-switch/rollback preflight. Do not repeat accepted parity,
PG17, browser, CSV, rollback or single-capture proofs.
