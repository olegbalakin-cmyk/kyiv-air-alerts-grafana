# C6 Neon shadow offline proof — research only

**Implementation prepared; checkpoint not accepted. C6/C3=PARTIAL; GLOBAL_CUTOVER=NO.**

Initial exact command at `9bd04dfcbccc16fb7f875551e6f005dcb787cb13`: **10/10 executed PASS**, Python 3.12.14, exit 0. Logs and dependencies: `offline_proof/initial-unit.*`.

The recovered real generator output contains all four frontend JSON and two explicit Git auxiliaries for 23 cities. Recovery commit `e1204d084ca815ac050028cb9978e60d18132154` was independently confirmed on GitHub. See `OFFLINE_PROOF.md` and `offline_proof/resume/machine_verdict.json` for resumed verification, hashes and limitations. Full generation was not repeated. No new candidate ZIP or full AIR archive was committed.

Minimal fixes:

- Restore `be68` omitted from the archive SHA-256 during adaptation. The value matches accepted `37a87029`; all immutable asset blobs and builder pins remain enforced.
- Bind the C2 success run to its branch/corpus while retaining inherited historical run provenance. Exact retries also require the corresponding successful corpus run.
- Reject missing/ambiguous Kyiv canonical parents; no Git AIR interval substitution.
- Precompute corpus IDs once; validate B2 before expensive derivation. Allow a fixed offline generation clock and retain lineage/readback digests.
- Distinguish fixture validation from physical readback. Synthetic C2 fixtures cannot authorize a physical read.

Local fixtures reconstruct the unchanged original snapshot from accepted Actions `41208139352`, preserved at `9704d5fa`, with all 85 original manifest entries verified. `fixtures/provenance.json` binds every retained member. Original readback: 31,977 AIR parents, 145 observations, 55 classifications, 223 source links.

The **C2-compatible wrapper is synthetic**. The original SELECT omitted `canonicalization_version`; its local contract overlay and one synthetic run are explicitly declared. They do not prove an actual C2 receipt, COMMIT, database version field or new readback. UUIDs, intervals and source relationships from the original snapshot remain unchanged.

Offline input data are pinned production `0ecbb291e8f443f7ab366bc4ac033d096f2c44f4`. All nine pinned builders match current production `3dc4aa8af4b4c2a0d157b5c9edae0bfc179fea1b` and all seven modules import. Current Git data have two additional Kyiv intervals absent from this snapshot; current completeness is not certified.

For a fresh reproduction, first restore fixtures as described in `fixtures/README.md`. Use the locked Python dependencies from the repository root:

```sh
python -m pip install -r research/neon_json_shadow_frontend_2026_10_31/offline_proof/requirements.lock.txt
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -p 'test_neon_json_shadow*py' -v
python -m scripts.neon_json_shadow_offline_proof --output /tmp/neon-offline-candidate
```

Output directories must not already exist. The standalone proof blocks network and SQL and checks every output interval against original Neon parents, daily start counts, both duration series, timezone, source types, B2 relationships and all six hashes.

## Isolated physical workflow — prepared, NOT RUN

`.github/workflows/c6-neon-shadow-isolated-proof.yml` is dispatch-only, restricted to the exact selected SHA on `research-neon-shadow-frontend-2026-10-31`, with read-only GitHub permissions and existing Environment `c6-live-writer-proof`. It never invokes the updater, captures sources, writes Neon, pushes Git or deploys. Source clients are blocked during read/generation. Six files, lineage, readback digests and machine verdict are uploaded as research artifacts.

Before a separately authorized run, the owner must supply/approve:

1. One dispatch authorization and approval through the existing protected Environment; verify its reviewer protection and ref policy.
2. Existing `NEON_JSON_SHADOW_READONLY_DATABASE_URL` on the exact approved branch/endpoint. No writer credential is needed. The role needs CONNECT/USAGE and SELECT on `alert_episodes`, `alert_episode_sources`, `current_ingestion_checkpoints`, `ingestion_runs`, `attack_event_classifications`, `attack_event_sources`, `attack_events`; no DML/DDL. The snapshot rejects INSERT permission on `alert_episodes` and uses REPEATABLE READ READ ONLY.
3. An existing verified real C2 artifact containing `c2-shadow-inputs.zip`, its independent SHA-256, original workflow/input SHAs, run/artifact IDs, branch ID and endpoint. A compatible real bundle is not established by this offline proof. Its fixed members are receipt/status/payload, five same-run `site_data/` JSON, and a `manifest.json` with schema `existing-c2-shadow-inputs-v1` and hashes for every other member. No synthetic receipt is accepted.
4. GitHub Actions dispatch/read and artifact-read access. A workflow existing only on a research ref may need owner-approved registration on the default branch before GitHub permits dispatch; no such merge/registration is authorized or performed here.

If an existing credential, branch or real C2 artifact is unavailable, stop for separate owner approval. Do not create a credential, branch or writer run automatically.

Required verdict separation: `OFFLINE_GENERATION_PASS`; `PHYSICAL_NEON_READBACK_NOT_RUN`; `CURRENT_FRESHNESS_NOT_CERTIFIED`; `PRODUCTION_PUBLICATION_NOT_AUTHORIZED`. No release or production readiness follows from offline generation.
