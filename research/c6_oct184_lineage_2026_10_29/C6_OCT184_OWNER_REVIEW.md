# C6-OCT184-L1 — Independent source-lineage owner review (2026-10-29)

## Research verdict: PARTIAL; no October production mapping

Frozen R3 candidate pairs **184/184** accounted for, each assigned `NOT_PROVABLE` due to absent original raw HTTP source records/native event identifiers. **IDENTITY_SUPPORTED=0; SOURCE_CONFLICT=0; AMBIGUOUS=0; NOT_PROVABLE=184.** This is **not** a negative conclusion that episodes are different; it is a bounded evidentiary limit, even though the observed minute-floor pattern is complete.

## Proven material origin, not physical identity

GitHub verified `main@896c7c8598bc2a8a44c8793385af4e8858f22844`, `site-prod@e08cc7da8cf29fc8603f199c85f0964610a850a7`, WIP `92011e2cd6a0ce515cd048a4c298c0f0a7bfdf98`, and accepted C6-R3 baseline `0cc4d4b56c547ff0b1b0ccc75c0fd0c7e4027c1e`. Verified R3 Actions `40867099080` and R4 `40881999530` at exact baseline, plus producer runs bootstrap `36918355446` and shadow `37284284054`; all SUCCESS. Those tests/runs do not establish physical source identity.

Producer lineage:
- Bootstrap `.github/workflows/multicity-permanent-bootstrap-resume.yml` at `7c54a9e4` invokes `export_multicity_canonical.py` and reads **site-prod/kyiv-air-alerts-grafana/data/alerts_combined.json** for Kyiv. The pinned Vadimkin CSV is for other cities and is not Kyiv's source.
- Shadow `.github/workflows/update-netlify-site.yml` at `edd9aae8` checks out site-prod, runs `update_data.py`, builds a same-run ephemeral canonical payload, and calls `multicity_canonical_shadow.py`; `alerts_combined.json` is written by the update process, **not necessarily the actual payload consumed** by shadow. This corrects R3's unverified generic input-path assumption.
- `update_data.py:parse_live_history` reads public Kyiv Digital human-readable event times via regex capturing **HH:MM only**, resulting in zero seconds. `parse_official` reads municipality `dateTimeStart/dateTimeEnd` as ISO timestamps and preserves seconds. These are **distinct observable sources**, not demonstrated transformations of identical original source bytes.
- `db_phase1_core.py:legacy_episode_id` deterministically hashes city+actual start+actual end, so different precise timestamps yield different identifiers.
- The 184 minute parent records match `source=kyiv_digital_live` in four Git snapshots: `9c06040d` 42, `54353510` 47, `92afb886` 47, `f7bc55dd` 48; total 184. All precise parent record intervals match `source=official_json` in `site-prod@e08cc7da`. Each source input commit's `alerts_combined.json` Git blob also verified present (92 distinct input commits), but the original upstream source payloads and historical ephemeral shadow input bytes are not available.

## Neon read-only assessment

Target existing NON-DEFAULT shadow branch `green-cake-44216048/br-bold-mode-b5rub8pq/neondb`, existing `ep-calm-rice-b5073ypp` compute. Verified endpoint is `read_only`; actual SQL `transaction_read_only=on`, `pg_is_in_recovery=true`. Readback snapshot `434176:434176:`, replay LSN `0/1188F638`. **Queries are individual READ COMMITTED snapshots, not one executed REPEATABLE READ transaction**: do not claim common-transaction proof.

October raw Kyiv AIR parents **382** (vs frozen snapshot **379**), candidate pairs **184** (unchanged), all 184 frozen pair UUID identities present and no extra candidate identity. Extra parents are outside frozen set; no mutation or automatic merge.

## Classification dependencies

55 original classification UUIDs survive and individually match current read-only SQL for parent UUID, binding state, classification key, source membership identifiers: **28 minute**, **27 precise**, **55 BOUND**, **45 NEEDS_REVIEW**, **10 NO_CONFIRMED_EVENT**, **223 associated attack_event_sources**, and **0 linked attack_events**. No parent alert_episode_sources entries for these pairs. The 223 source links are *attack classification evidence*, not original AIR state source IDs. No A5 September changes, no historical UNBOUND edits.

## Evidence boundaries and next authorization

Original HTTP response bodies with acquisition timestamps and hashes, upstream native event identifiers and direct proof that both publisher representations refer to the same physical state transition are absent. **Do not approve any October mapping**, do not change C6-R4 reader behavior, and do not infer production deployment.

Safe next step: separately authorized bounded publisher raw-capture / original source-native identity recovery with immutable byte hashes, then replay the two parsers on the actual captured inputs, individually adjudicate 184 cases, and only subsequently request owner/coordinator mapping acceptance. Independent source-lineage = **PARTIAL**, classification relationship audit = **PASS_BOUNDED_READONLY**, reader cutover = **NO**; Neon writes = **0**, production mappings = **0**. Exact-SHA CI for this new research branch not run; branch Git commits and source blob hashes are checkable proof of this executed connector investigation.
