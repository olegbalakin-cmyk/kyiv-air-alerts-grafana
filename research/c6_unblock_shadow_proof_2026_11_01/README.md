# C6 physical shadow: prepared changes for owner review

2026-11-01. Implementation and local contract checks are complete. No physical proof was run. `C6/C3=PARTIAL; GLOBAL_CUTOVER=NO`.

Coordination baseline: `main@95397e14e7fd929b5d90585465b194affd5a49a7`; latest accepted checkpoint remains `C6-UA-CURRENT-ONEGET-01`. Reader baseline: `6e121e0629685895ea402a21cc66cccb4c6f277f`. This preparation is not a newly accepted release checkpoint; root coordination files remain unchanged pending acceptance.

The existing production run [41210446729](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41210446729) was rechecked through its run metadata, job steps and bounded log excerpts. SUCCESS, workflow SHA `5ae1c9719d686654d3c46492e1c7d6f1465d37ec`, input SHA `33f2a1f85d8de41ada7eed165f7846b7b9047789`, 23 cities, 31,739 episodes, branch `br-bold-mode-b5rub8pq`, corpus SHA-256 `0eeab3ba6f07d6361f55f36202c7dda69e1c9fddd15a09a76977369c07689b96`. Its missing bundle was not reconstructed. A future authorized C2 cycle must create a new bundle with its own identity.

## Patches

The frontend research branch contains the exporter, physical bundle verifier, privilege gate, manual workflow and new tests. A separate export branch starts at current main and changes only `scripts/c2_shadow_bundle.py` and three added steps in `.github/workflows/update-netlify-site.yml`. This export can be reviewed without promoting the frontend reader.

The registration PR starts at current main and adds only `.github/workflows/c6-neon-shadow-isolated-proof.yml`. It does not change the updater. Both branch diffs must be reviewed separately. No branch was merged and no workflow was dispatched.

## Bundle contract

Production already declares `MULTICITY_CANONICAL_PAYLOAD_PATH=${RUNNER_TEMP}/multicity_canonical_payload.json` before builders. The writer consumes that payload, writes `${RUNNER_TEMP}/multicity_canonical_db_shadow.json`, and the independent classifier writes `${RUNNER_TEMP}/c2_publication_status.json`. The export runs after `Build Kyiv alert-cause JSON without Netlify`, when derived JSON is complete.

`C2_SHADOW_BUNDLE_EXPORT_ENABLED` must equal the exact string `true`; absence is OFF. All export steps also require the classifier output `NEON_SUCCEEDED`. The export validates the existing production receipt verifier and same-run corpus digest. It imports no database client, performs no source GET and does not invoke the writer. It parses only the hostname from the existing writer URL at runtime, then stores the normalized direct endpoint hostname. Credentials are excluded from the archive and output; credential-shaped JSON fields/text are rejected.

The artifact is `c2-shadow-inputs-<run_id>-<attempt>`. It contains one `c2-shadow-inputs.zip` and `c2-shadow-inputs.zip.sha256`. The ZIP has exactly these regular files:

| ZIP member | Origin in the same run |
| --- | --- |
| `receipt.json` | `RUNNER_TEMP/multicity_canonical_db_shadow.json` |
| `status.json` | `RUNNER_TEMP/c2_publication_status.json` |
| `payload.json` | `MULTICITY_CANONICAL_PAYLOAD_PATH` |
| `site_data/dashboard_data.json` | completed production builder output |
| `site_data/site_derived.json` | completed derived JSON builder output |
| `site_data/alerts_combined.json` | existing same-run Kyiv input/output |
| `site_data/kyiv_threat_mix.json` | completed cause JSON builder output |
| `site_data/sevastopol_events.json` | existing same-run Sevastopol input/output |
| `manifest.json` | export metadata and all eight input digests |

Manifest schema: `existing-c2-shadow-inputs-v1`. Required fields: `repository`, `github_run_id`, `github_run_attempt`, `workflow_sha`, `input_sha`, `corpus_sha256`, `canonical_run_id` (nullable on exact retry), `db_branch`, `db_endpoint`, and `files` mapping each of the eight input names to its SHA-256. Bundle and manifest SHA-256 are also printed to the run summary; no self-referential manifest digest is used. The exporter independently rereads the ZIP and verifies its member set, file digests, receipt identity and absence of fixture flags before exposing output.

Missing inputs, malformed receipt/status, mismatched corpus/identity or credential content block export. ZIP failures block physical reading. Export checkout, packaging and upload are nonfatal to production; a failed export produces no accepted artifact and does not change the existing Git publication code. No candidate directory enters production staging.

For local hash verification after downloading and unpacking the outer GitHub artifact:

```powershell
Get-FileHash .\c2-shadow-inputs.zip -Algorithm SHA256
```

Compare the computed digest with the independent run summary and checksum sidecar. Read the manifest from the ZIP and use its exact run/SHA/branch/endpoint fields for dispatch. Do not substitute the old production run ID or an offline fixture.

## Owner configuration in GitHub UI

The connector explicitly excludes secrets APIs. No secrets API was retried, secret value read, secret created, or Environment modified. Secret presence, endpoint mapping and actual role grants remain unconfirmed until the owner checks them.

1. Open [repository Environments](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/settings/environments). Create or inspect `c6-neon-shadow-readonly`. Keep `c6-live-writer-proof` unchanged.
2. Set **Deployment branches and tags → Selected branches and tags → Add rule → Branch** to the exact `research-c6-unblock-shadow-proof-2026-11-01`. Do not allow `main`, all branches or matching tags for this proof Environment.
3. Set a required reviewer to owner `olegbalakin-cmyk`, where supported. A sole owner can leave **Prevent self-review** disabled so the owner can dispatch and approve their own run. Leave administrator bypass disabled. If reviewer protection is unavailable on the repository plan, the owner-only dispatch phrase and pinned SHA guard still apply; record that limitation before approving dispatch.
4. Under **Environment secrets**, confirm the name `NEON_JSON_SHADOW_READONLY_DATABASE_URL`. If absent, the owner must supply an existing least-privilege role URL privately through GitHub UI. Do not copy any writer secret or disclose a URL in chat, logs or PRs. The workflow references only this one DB secret.
5. Under **Environment variables**, set `C6_SHADOW_APPROVED_RESEARCH_SHA` to the full final SHA of the frontend research branch after reviewing it. The job refuses a different SHA before any DB connection.
6. In Neon Console, select the existing branch named by the new C2 receipt; confirm its endpoint hostname matches manifest `db_endpoint`, allowing only the ordinary `-pooler` hostname variation. Confirm the secret was configured for that same endpoint, database and read-only role. GitHub cannot display stored secret values; its name alone cannot establish endpoint identity. The owner can confirm the configuration record or privately replace it with the approved existing URL.
7. Confirm this is an existing SQL-created least-privilege role with SELECT/USAGE for the seven reader tables: `alert_episodes`, `alert_episode_sources`, `current_ingestion_checkpoints`, `ingestion_runs`, `attack_event_classifications`, `attack_event_sources`, `attack_events`. Catalog SELECT is also used. Do not choose an administrator role merely because its name contains “readonly”.

The proof checks the effective privileges of the current role and all MEMBER roles inside its existing `REPEATABLE READ READ ONLY` transaction. It rejects privileged role flags, table/column DML, sequence writes, database/schema/tablespace CREATE, TEMP, ownership, and callable application SECURITY DEFINER routines. The catalog check precedes episode reads and fails closed; transaction cleanup uses ROLLBACK. The check is implemented but has not been executed on Neon.

PUBLIC grants can make a role fail even after per-role REVOKE; database TEMP is a common example. Do not revoke PUBLIC privileges on the production database blindly. If the approved role still has these rights, owner/DBA approval for the exact ACL change is required before the proof. This task prepared no grant mutation or role creation.

GitHub environment setup is described in [GitHub Docs](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments). [Neon role documentation](https://github.com/neondatabase/website/blob/main/content/docs/manage/roles.md) states that Console/API/CLI-created roles receive `neon_superuser`; limited roles use SQL. The privilege query uses the [PostgreSQL 17 privilege inquiry functions](https://www.postgresql.org/docs/17/functions-info.html#FUNCTIONS-INFO-ACCESS-TABLE).

## Authorization and execution order

1. **Register the manual workflow.** Owner reviews and merges only the workflow-registration PR. Its diff is one file. No dispatch is included. Configure the isolated Environment and approve the exact research SHA through UI.
2. **Obtain one real bundle.** Separately authorize promotion of only the two-file export patch and one existing production C2 cycle with `C2_SHADOW_BUNDLE_EXPORT_ENABLED=true`. Merging the updater change matches its existing push trigger: this authorization must explicitly cover the normal source capture, canonical writer and unchanged production Git publication performed by that cycle. Merging with the flag OFF will not produce a bundle. Reuse that one resulting cycle; do not dispatch a duplicate writer run. Turn the export flag OFF afterward to prevent repeated bundle exports. None of this authorization has been assumed or executed.
3. **Authorize one physical read-only proof.** After the real artifact exists and its digest/identity and role setup are approved, owner dispatches `c6-neon-shadow-isolated-proof.yml` on `research-c6-unblock-shadow-proof-2026-11-01`. Enter the exact research SHA, C2 run ID/artifact name, bundle digest, writer workflow SHA, input SHA, branch, direct endpoint hostname, and `owner_approval=APPROVE_ONE_READONLY_PROOF`. Then approve the Environment job. A dispatch from main, another actor/ref/SHA, or without the phrase is refused. The workflow independently checks GitHub run SUCCESS and its writer SHA before downloading inputs and connecting to Neon.

The physical job performs one existing-database snapshot and isolated generation, then uploads research evidence. No writer or source client is invoked. It has only GitHub `contents:read` and `actions:read`; no Git push, production publish or Netlify step. Publication stays unauthorized even if generation succeeds.

`READY_FOR_PHYSICAL_PROOF` means: the workflow is registered; the approved research SHA is unchanged; a new real C2 bundle passes its hash and identity checks; the owner confirms the isolated secret/endpoint/branch policy and least-privilege role; and the owner authorizes one pinned read-only dispatch. At this handoff the code is prepared, while those owner-controlled prerequisites remain pending.

## Local verification

`PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -p 'test_c2_shadow_bundle.py' -v`: **12/12 PASS**, including per-input missing cases and per-privilege negative cases. Log: [tests.txt](tests.txt). Synthetic contract inputs are temporary and never represented as real C2 evidence. The unchanged production receipt verifier is stubbed in unit tests; a separate synthetic export integration passed with its actual pinned blob `94271238a5453bc387bcc03d28b19677758e1373`. The five previously saved site JSON inputs also passed the new credential-content check without generation.

Both workflow files parse as YAML. Their shell blocks pass `bash -n`; embedded Python passes AST parsing. Production workflow equality passes after removing exactly the three optional export steps, including the canonical writer, publication logic, permissions and triggers. No generator/parity/PG17/browser/CSV/rollback test was repeated. No new source HTTP, live Neon SQL, secret/Environment change, site-prod write or deployment was performed.
