# C6-23CITY-PUBLICATION-01

Research-only end-to-end path: existing child persisted AIR episodes/source
observations -> read-only repeatable-read snapshot -> accepted adapter/B2/pure
site generators -> six consumer files -> explicit publication decision.

No new HTTP source request, writer, DST simulation/repair, current provenance
repair, production file change or external deployment. No frozen parity,
browser/CSV or rollback rerun. Existing evidence: parity `741f277f`, browser
`66f87241`, one real HTTP capture/new UUID `1cf607b3`, Actions `41204874911`.

The existing child must remain `br-crimson-star-b59u7ge3`, parent
`br-bold-mode-b5rub8pq`, expiry `2026-11-01T12:20:00Z`. It is independently
verified through Neon before execution. The runner verifies child host/role,
TLS, TTL, database identity and read-only transaction. The pinned role has
broader child rights, but this runner issues SELECT and transaction control only.
No parent URL, new branch or TTL extension is allowed. Local failed DNS must
not trigger any Git interval fallback.

Run in GitHub Actions using `.github/workflows/c6-23city-publication-gate.yml`
on the existing research branch and protected `c6-live-writer-proof` Environment.
Push a change to `run-request.txt`, rerun the read-only job, or dispatch the
workflow on that branch. There is no schedule. Repeating this runner cannot
create database duplicates: it invokes no writer; two independent snapshots
must have identical content fingerprints. This is distinct from live writer
idempotence, whose earlier physical crash/retry proof is not repeated.

Local equivalent (network-capable environment; secret injected privately):

```bash
python research/neon_23city_publication_2026_10_31/pipeline.py \
  --site /pinned-site/kyiv-air-alerts-grafana \
  --accepted /pinned-accepted-repo --output /new-output-directory
```

The site checkout must be `0ecbb291e8f443f7ab366bc4ac033d096f2c44f4` and
accepted code checkout `741f277f73d1dde1325069d25fa00b44a42d6f03`. The adapter
ZIP and B2/generator blobs are pinned and hash-checked. No archived physical
input is used as a replacement for a new read from this child.

Four files are generated: `dashboard_data.json`, `site_derived.json`,
`alerts_combined.json`, `historical-daily-kpi.json`. Two explicit pinned Git
auxiliaries are copied: `kyiv_threat_mix.json`, `sevastopol_events.json`.
Non-AIR/casualty metadata remain separate Git inputs. Historical Kyiv Git
membership selects exact physical intervals; B2 frozen display rules stay
unchanged, and the already accepted new physical episode is included as a
research-only prospective observation. A full UUID/union/source link sidecar
is retained with the physical readback in the Actions artifact. Incomplete
source provenance is reported, never filled with a fabricated receipt. Existing
observation integrity is checked; missing historical links do not introduce a
new full-backfill gate on top of accepted historical baseline evidence. Current
source capture and continuity still require their own physical evidence.

`source_captured_at`, checkpoint `checked_at`, ingestion `ingest_committed_at`,
reader snapshot time and `site_generated_at` are separately recorded. Only
Kyiv's hash/UUID/run match to the already accepted real HTTP capture can
establish a verified capture time. Lviv's old checkpoint is historical; a
current DB update or generated JSON does not refresh any source clock.

`PUBLICATION_BLOCKED` is an expected successful research result. The workflow
requires generation success and explicit blocking, uploads all evidence and
saves bounded reports/hashes into the research branch without force. No publish
directory is created. Connection/read/generator failure records blocking with
no Git fallback. Closed-alert builders never convert an active alert's missing
end into build time; open rows are preserved in evidence and the active-status
gate remains OPEN. This run cannot certify current status or continuous updates.

Next owner decision: authorize a bounded isolated continuity experiment with
explicit source endpoints, request budget, at least two observation rounds and
an end time. The live-source gate remains OPEN. No additional captures are
implemented or enabled here. If child TTL expires before that decision, a new
isolated child needs separate explicit authorization. Physical DST and Kyiv
current provenance remain separate release dependencies, not repair scope here.
