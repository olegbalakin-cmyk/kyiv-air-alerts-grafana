# Original operational failure versus bounded research repair

| Evidence / contract | Original Oct 14 WIP operational run | Isolated Oct 21 real-source research run |
|---|---|---|
| GitHub Actions | Run 38575039007, SUCCESS | Run 39590006641, SUCCESS |
| Report status | `ok: false` (Lutsk source error) | `BOUNDED_RESEARCH_ONLY_NOT_SCHEDULED_LIVE` with explicit successful fixed corpus report |
| Cities | 23 | Kyiv only |
| New alert episodes | 12 | 3 historical selected episodes (not new alert discovery) |
| Newly discovered candidates | 45 | 3 genuine frozen source candidates (not newly fetched) |
| Review queue | 5,521 | No operational queue touched |
| Discovery due checks | 75, all marked checked | No discovery-check ACK; local classification ACK only |
| Canonical persisted classifications | 0 | 0, explicitly forbidden |
| Accepted classifier | Old run not proven to persist classifier results | Accepted repaired classifier, blob `4019b8374dcc44846df04ed0cc41356652214bff`, executed twice |
| Durable ACK | Historically `checked_at` may precede durable canonical result | Atomic local result+ACK, failure remains retryable |
| Negative conclusions | `report.ok=false` not propagated as CI failure | An incomplete-source error cannot be mistaken for `NO_CONFIRMED_EVENT`; any zero candidate label only within frozen search |
| Batch fairness | Oldest candidate cap could repeatedly select old parents | Persistent least-recently-attempted ordering passes 3-episode cap=1 test |
| Operational writes | Old workflow writes WIP states | Zero WIP/site-prod/main/Neon/canonical writes |

## Actual bounded sample

- `e56cdca45ed5b1cd7b0b9746` — Kyiv alert 2022-06-26 02:47:36Z–04:21:19Z; two authentic articles, one accepted strict positive and one needs-review news candidate; episode `STRICT_EVENT_POSITIVE`. One synthetic source-failure trial in local ledger then recovered, two processing attempts, ACK true.
- `6b10a67efd1fa1deac9bff8e` — Kyiv alert 2022-03-02 18:57:03Z–19:24:01Z; one genuine news candidate; `NEEDS_REVIEW` due to incomplete reliable event-time binding; ACK true (review status preserved, not automatically approved).
- `61d634a5595e9f7e63f1454c` — Kyiv alert 2022-03-12 03:21:34Z–06:07:28Z; zero admitted frozen news candidates, `NO_CONFIRMED_EVENT` **within archived search only**, not physical nonoccurrence; ACK true for the bounded classifier result.

Source corpus ZIP digests independently emitted by CI:
- Archived discovery/native evidence artifact 11608819645: SHA256 `cc3da258ccfcb5dbbef9a56f220730e863323766be7b6ea9ebdf74a9205c4ddf`.
- Archived earlier replay artifact 11609004684: SHA256 `3d79b15ae506d488e29abcd5e55e886bf8cf4e0a3527c99e2b4c45ab7654f80c`.
- Full classifier fingerprint from two independently executed processes: `57fa5e402a79ab852b48d540de6a56581c3dd27fde4e986d3cce28ea3b611af8`.

Research run `39590006641`, job `119188306396`, first output artifact `12342075226`, GitHub artifact digest `sha256:efbd75a26970a9a4356e996cc949cda8a7071de7c98da8c7889fb1b64f6a1ef4`. Earlier run `39589777392` was a genuine failed preliminary attempt at the archived ZIP retrieval and is not counted as success.

## Not yet proved

Continuous and complete fresh source retrieval, 23-city live scheduled processing, persistent storage across GitHub Actions runs, exact canonical parent/candidate persistence against Neon, cross-run idempotency, real operational error forwarding and no WIP activation. Three success runs (when achieved) will be independently reproducible executions with fresh workspaces **not** shared-state recovery proof.

## Exact next smallest operational step

Only after separate authorization and a fresh safety preflight, execute a **single no-write current-source discovery canary** for Kyiv using the read-only, locally cached authoritative completed alerts and real publisher discovery, persist only ephemeral report artifacts, compare candidate URLs/timestamps and classification outcomes with pinned behavior, and require an explicit CI gate on partial source failures and zero false ACK. Do **not** activate the held operational workflow or Neon as part of this research result.
