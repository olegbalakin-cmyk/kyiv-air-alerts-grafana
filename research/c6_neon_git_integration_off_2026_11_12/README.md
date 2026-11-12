# C6 — default-OFF Neon → JSON → Git preparation (2026-11-12)

**Scope:** isolated preparation and atomic **local** Git candidate only. Do not merge, publish,
cut over, deploy Netlify, dispatch a writer, alter DST or casualty tracks. This is not
a release approval. \`GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF\`.

## Integration point

\`.github/workflows/update-netlify-site.yml\` retains its original \`update-site\`
job and all its existing Git publication semantics. A new independent job,
\`c6-neon-six-json-prepare\`, has \`needs: update-site\` and an opt-in
\`C6_NEON_JSON_PREPARE_ENABLED == 'true'\` condition (unset = OFF). Even if enabled,
the job has **contents: read**, no Git credentials on checkouts, no Netlify
credentials, and never pushes. Its Git remote is deleted before making a detached
local commit; the candidate is an artifact/report only. Production Neon publication
has **no enable switch or authorization code path** in this PR.

Same-run identity: read the verified C2 artifact of that exact Actions run/attempt,
verify its ZIP SHA sidecar, C2 receipt, original workflow SHA, \`input_sha\`,
Neon branch, corpus, 23 full historical source captures. The site collector is
checked out at the artifact's exact \`input_sha\`. It reads from Neon using the
previously accepted physical read-only runner/generator pinned at
\`82a7cc775ed2f2a6fd0134440db709690f0c04d1\`, with *only* the exact
new merged Sevastopol PR #93 parser blob allowlisted (Git blob
\`d31c5ac43ac9e76491ee38033f9a46838c5abfbb\`); all other unexpected
builder drift still blocks. Source HTTP is patched off and Neon SQL remains
repeatable-read, read-only. No new writer.

The PR #94 fail-closed guard is included unchanged as an isolated verification
component. The freshly generated candidate must pass its 18 evidence hashes,
six JSON digests, 23/23 historical binding and ≤36h source ages at consumption,
frontend/23-city historical index shape, current-alert UNKNOWN and DST-OFF policy.
The staging wrapper independently binds the proof to C2 run/attempt, workflow SHA,
input SHA, branch, corpus, exact auxiliary bytes, casualty fields and Kyiv interval
superset; SHA verifies every file before and after staging.

## Six-file destination map

| Candidate file | Proposed Git destination | Actual consumer |
|---|---|---|
| dashboard_data.json | kyiv-air-alerts-grafana/data/dashboard_data.json | frontend Git raw |
| site_derived.json | kyiv-air-alerts-grafana/data/site_derived.json | frontend Git raw |
| alerts_combined.json | kyiv-air-alerts-grafana/data/alerts_combined.json | Kyiv derived and historical |
| kyiv_threat_mix.json | kyiv-air-alerts-grafana/data/kyiv_threat_mix.json | frontend Git raw |
| sevastopol_events.json | kyiv-air-alerts-grafana/data/sevastopol_events.json | auxiliary/backend |
| historical-daily-kpi.json | historical-daily-kpi.json (repository root) | **Netlify static build**, not Git raw |

The main site frontend currently still points to \`site-prod\` raw Git JSON.
PR #90's scoped Neon KPI \`validIndex()\` compatibility is still a **draft
on site-prod**; the approved preview does not establish a production release.
The root index does not currently exist on \`site-prod\`, so staging it is an
explicit new tree entry. Updating these files in one Git commit makes the
repository snapshot atomic, **not** the independently deployed Netlify static
index and live raw Git data. Release remains blocked until the two-plane delivery
and rollback are separately approved/proven.

## Offline evidence and release gates

The dedicated no-network offline CI reuses approved physical #43187464328
(artifact #13929117121) and exact historical C2 #43055353190
(artifact #13873291895) as **test fixtures, not current publication inputs**.
It verifies SHA/receipt and runs negative staging tests for missing/incorrect
receipts, stale source, mismatched corpus, candidate generation failure, wrong
index, casualty or auxiliary modification, Kyiv interval loss, forged authority,
unsafe output path and generator code drift. It exercises a single detached,
no-remote six-file local commit; verifies no push/deploy.

**Activation still requires**, separately: (1) next regular C2 23/23
post-PR #93 receipts and new true same-run proof; (2) accepted current authority
for publication distinct from PR #94 \`publication_allowed=false\`; (3) accepted
PR #90-compatible production frontend/index generation and two-plane rollout;
(4) pinned Git/static rollback baseline and operational rollback controls;
(5) owner's express merge and production cutover authorization. No automatic
promotion from passing CI. \`GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF\`.

Proposed coordination checkpoint, **NOT ACCEPTED**:
\`C6-NEON-GIT-DEFAULT-OFF-INTEGRATION-PREPARED-01\`; status is preparation only,
production publication OFF. Do not modify PR #78 until coordinator accepts.
