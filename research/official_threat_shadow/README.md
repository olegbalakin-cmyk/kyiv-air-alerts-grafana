# Official Telegram threat evidence for 23 cities (2026-11-17)

**State:** OFF / local shadow only. No live channel GET was run, no scheduled workflow, no active Neon writes and no production outputs changed.

## Goal and semantic contract
The question is **what type of threat accompanied each already known alert**, not whether the threat message proves *why the alert was originally announced*.

Evidence categories:
- `THREAT_DURING_ALERT`: official threat message within known alert interval and **explicit same-city mention**.
- `ONSET_REASON_CANDIDATE`: alert-channel text references threat within ±5 minutes of start; still *candidate*, never automatically accepted as a confirmed cause.
- `UNKNOWN`: no reliable matching message, ambiguous geography or conflicting/negative text.

Labels may be multiple for one alert: UAV (`uav`), ballistic (`ballistic`), cruise missile (`cruise_missile`), guided bomb (`guided_bomb`), aviation (`aviation`), unspecified missile (`unspecified_missile`).

## Sources & ingestion
A preliminary source registry contains `kpszsu` and `air_alert_ua` Telegram post IDs. **Verify the latter handle's exact official status before any live pilot** and pin source identity and UTC evidence. The classifier is designed to work on saved public `t.me/s/<channel>` HTML or manually supplied normalized JSON. It does not scrape private/group content, request Telegram user authentication or poll on a schedule.

```bash
python scripts/official_threat_shadow.py \
   --saved-html kpszsu:/path/to/saved_kpszsu.html \
   --alerts /path/to/frozen_23city_completed_alerts.json \
   --out /tmp/threat_shadow.json
python -m unittest discover -s tests -p 'test_official_threat_shadow.py' -v
```

Input alert format: JSON array of `{"city_key":"kharkiv","start":"2026-11-16T10:00:00Z","end":"2026-11-16T10:30:00Z","alert_id":"optional-stable-id"}` using the current 23 production city keys. This is a **read-only adapter contract**; no production extraction adapter has been enabled. Other input mode: `--messages normalized.json` with `channel,url,published_at,text`.

Live **manual** public-page GET helper exists but is default-denied, requires both `--one-shot-http-go` and `THREAT_SHADOW_HTTP_GO=YES`; HTTPS pinned host, no redirect, bounded response (2 MiB), timeout 15 s. It is not separately authorized, and has not been exercised against publishers. Before any real GET: verify source handle, guard proxies/public-IP and read-only budget, exact commit SHA, idempotent one-shot decision, and owner GO.

## Fail-closed safeguards
- Only `https://t.me/<pinned_channel>/<numeric_post_id>` post URLs accepted.
- Explicit **city name** required; do NOT promote an oblast-wide statement to a particular city or raion.
- Completed non-overlapping city-alert match required; ambiguous matches skipped.
- Published timestamp must have timezone, original text and SHA256 retained.
- Obvious negations/all-clears/summaries excluded conservatively; this is heuristic, not reliable semantic interpretation. Mentions of movement, reports about attacks or quotes can still create false positives. Human audit and stronger source context are required before promotions.
- All labels are shadow; `reason_confirmed=false`, `claims_alert_cause=false`, `publish_allowed=false`.
- No active workflow integration. No cause chart, site-prod, Neon, C2, casualties or Netlify changes.

## Validation and next work
Local synthetic unit tests (including multi-type, region-only, all-clear, out-of-window, duplicate, overlap, HTTP OFF) passed. This is not a measured real-world accuracy estimate.

Next: verify source registry and source-permitted retrieval, assemble 100 frozen completed alert intervals covering Kharkiv/Dnipro/Lviv, capture corresponding official messages with exact provenance, manually adjudicate matches against timestamps and geography, report classification **coverage, precision and ambiguity** by city and threat type. Only after proof and separate owner GO, integrate a read-only shadow evidence exporter with existing scheduling; promotion remains OFF until an accepted methodology and UI contract exist.
