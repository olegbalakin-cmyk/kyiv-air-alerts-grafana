#!/usr/bin/env python3
from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import re
import socket
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

SCRIPT = pathlib.Path(__file__).resolve()
REPO = SCRIPT.parents[2]
CAMPAIGN_SUFFIX = pathlib.Path("research/historical_attack_event_backfill/historical-attack-events-v2-2026-09-27")
STATUS_NAME = "historical_attack_event_backfill_status.json"
OUT_REL = pathlib.Path("research/historical_offline_repair_recovery_scan_2026-10-02.json")

IMPLEMENTATION_HEAD = "a208892ef6ba1437e8cfb2244e6863f1203803db"
FROZEN_HEAD = "71cb6f6fbe856cc7b96759310fe9cc9c71cc0453"
CAMPAIGN_ID = "historical-attack-events-v2-2026-09-27"
EXPECTED_BATCHES = 139
EXPECTED_TARGETS = 6863
EXPECTED_DISTRIBUTION = {
    "STRICT_EVENT_POSITIVE": 79,
    "SENSITIVITY_EVENT_POSITIVE": 18,
    "NO_CONFIRMED_EVENT": 5425,
    "NEEDS_REVIEW": 1341,
}
EXPECTED_ORIGINAL_HASH = "cb9ca2a98fbc1d40e067da84666bf9d7c458bf69436b43876aeced9cabdedd11"
CASE7_EPISODE = "ae2718c10fcdc7079dbb220a"
CASE7_OBSERVATION = "7f9455ee73cf2aaa84b9d6e3"
CASE7_EXPECTED_TIME = "2026-04-26T19:48:00Z"
CASE18_EPISODE = "6069b17ec096cae0912ad9bd"

UTC = timezone.utc
KYIV_TZ = ZoneInfo("Europe/Kyiv")
SOURCE_NETWORK_CALLS = 0

# The accepted target-state hash predates this proof and has a frozen preimage:
# city_key<TAB>episode_id<TAB>final_state<LF>, in frozen launch order.
# The proof artifact itself and changed-target hash use canonical compact JSON.
CANONICAL_JSON = {
    "encoding": "UTF-8",
    "ensure_ascii": False,
    "sort_keys": True,
    "separators": [",", ":"],
    "trailing_newline_in_hash_preimage": False,
}
TARGET_STATE_HASH_CONVENTION = {
    "name": "accepted_frozen_ordered_tsv_v1",
    "record": "city_key<TAB>episode_id<TAB>final_state<LF>",
    "ordering": "frozen launch city order, then each city's frozen_episode_ids order",
    "encoding": "UTF-8",
}

MONTHS = {
    "січня": 1, "лютого": 2, "березня": 3, "квітня": 4,
    "травня": 5, "червня": 6, "липня": 7, "серпня": 8,
    "вересня": 9, "жовтня": 10, "листопада": 11, "грудня": 12,
}
MONTH_RE = "|".join(MONTHS)
DATED_PREFIX_RE = re.compile(
    rf"^\s*(?P<day>\d{{1,2}})\s+(?P<month>{MONTH_RE})\s+"
    rf"(?P<hour>\d{{1,2}})[:.](?P<minute>\d{{2}})\b",
    re.IGNORECASE,
)
EVENT_RE = re.compile(
    r"(?:вибух\w*|влуч\w*|поціл\w*|приліт\w*|вдарил\w*|"
    r"(?:завдал\w*|нанес\w*).{0,50}удар\w*|атакув\w*)",
    re.IGNORECASE,
)
SEVASTOPOLE_RE = re.compile(r"(?<![\w-])севастополе(?![\w-])", re.IGNORECASE)
AIR_CONTEXT_RE = re.compile(
    r"(?:\bбпла\b|дрон\w*|безпілот\w*|шахед\w*|shahed\w*|"
    r"ракет\w*|авіабомб\w*|\bкаб\w*|\bппо\b|\bпво\b|"
    r"протиповітр\w*|противовоздуш\w*)",
    re.IGNORECASE,
)
AIR_DEFENSE_ACTUAL_RE = re.compile(
    r"(?:(?:\bппо\b|\bпво\b|протиповітр\w*|противовоздуш\w*).{0,35}"
    r"(?:працю(?:є|ють|вала|вали)|відпрацю\w*|работа(?:ет|ют|ла|ли)|отработа\w*)|"
    r"(?:працю(?:є|ють|вала|вали)|відпрацю\w*|работа(?:ет|ют|ла|ли)|отработа\w*).{0,35}"
    r"(?:\bппо\b|\bпво\b|протиповітр\w*|противовоздуш\w*))",
    re.IGNORECASE,
)
INTERCEPTION_RE = re.compile(
    r"(?:збит\w*|збил\w*|знищен\w*|знешкоджен\w*|перехоп\w*|"
    r"сбит\w*|сбил\w*|уничтожен\w*|перехвачен\w*)",
    re.IGNORECASE,
)

RANK = {
    "NO_CONFIRMED_EVENT": 0,
    "NEEDS_REVIEW": 1,
    "SENSITIVITY_EVENT_POSITIVE": 2,
    "STRICT_EVENT_POSITIVE": 3,
}
CLASS_TO_TARGET = {
    "approved_strict": "STRICT_EVENT_POSITIVE",
    "approved_sensitivity": "SENSITIVITY_EVENT_POSITIVE",
    "needs_review": "NEEDS_REVIEW",
    "rejected": "NO_CONFIRMED_EVENT",
}

def run_git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=REPO, text=True).strip()

def canonical_bytes(obj: Any) -> bytes:
    return json.dumps(
        obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")

def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def iso_z(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")

def parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)

def unique_file(pattern: str, label: str) -> pathlib.Path:
    hits = sorted(p for p in REPO.glob(pattern) if p.is_file())
    if len(hits) != 1:
        raise RuntimeError(f"{label} discovery invariant failed: {len(hits)} matches")
    return hits[0]

def campaign_files() -> tuple[pathlib.Path, list[pathlib.Path]]:
    dirs = sorted(p for p in REPO.glob("**/" + CAMPAIGN_SUFFIX.as_posix()) if p.is_dir())
    if len(dirs) != 1:
        raise RuntimeError(f"campaign directory invariant failed: {len(dirs)}")
    batches = sorted(p for p in dirs[0].rglob("*.json") if p.is_file())
    if len(batches) != EXPECTED_BATCHES:
        raise RuntimeError(f"batch count invariant failed: {len(batches)} != {EXPECTED_BATCHES}")
    return dirs[0], batches

def corpus_digest(paths: list[pathlib.Path]) -> str:
    h = hashlib.sha256()
    for p in paths:
        rel = p.relative_to(REPO).as_posix()
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(p.read_bytes())
        h.update(b"\0")
    return h.hexdigest()

def split_segments(text: str) -> list[str]:
    if not text:
        return []
    return [
        " ".join(x.split())
        for x in re.split(r"(?<=[.!?;])\s+|\n+", text)
        if x and x.strip()
    ]

def observation_segments(obs: dict) -> list[str]:
    out: list[str] = []
    for field in ("exact_city_evidence", "aerial_war_context"):
        block = obs.get(field) or {}
        for seg in block.get("segments") or []:
            s = " ".join(str(seg).split())
            if s and s not in out:
                out.append(s)
    for seg in split_segments(str(obs.get("excerpt") or "")):
        if seg not in out:
            out.append(seg)
    return out

def parse_dated_live_update(segment: str, published: datetime | None) -> datetime | None:
    if not published:
        return None
    low = " ".join(segment.casefold().split())
    m = DATED_PREFIX_RE.match(low)
    if not m:
        return None
    event_hits = list(EVENT_RE.finditer(low))
    if not event_hits:
        return None
    # Mirrors the bounded accepted repair: event wording must follow close to the dated prefix.
    if not any(0 <= hit.start() - m.end() <= 180 for hit in event_hits):
        return None
    day = int(m.group("day"))
    month = MONTHS.get(m.group("month").casefold())
    hour = int(m.group("hour"))
    minute = int(m.group("minute"))
    if month is None or hour > 23 or minute > 59:
        return None
    published_local = published.astimezone(KYIV_TZ)
    candidates: list[tuple[int, float, datetime]] = []
    for year in (published_local.year - 1, published_local.year, published_local.year + 1):
        try:
            local_dt = datetime(year, month, day, hour, minute, tzinfo=KYIV_TZ)
        except ValueError:
            continue
        day_distance = abs((local_dt.date() - published_local.date()).days)
        if day_distance > 2:
            continue
        candidates.append((day_distance, abs((local_dt - published_local).total_seconds()), local_dt))
    if not candidates:
        return None
    candidates.sort(key=lambda x: (x[0], x[1], x[2]))
    return candidates[0][2].astimezone(UTC)

def repaired_event_timestamp(obs: dict) -> str | None:
    published = parse_dt(obs.get("source_timestamp"))
    hits: list[datetime] = []
    for seg in observation_segments(obs):
        dt = parse_dated_live_update(seg, published)
        if dt and dt not in hits:
            hits.append(dt)
    if not hits:
        return obs.get("event_timestamp_if_stated")
    hits.sort()
    return iso_z(hits[0])

def active_episode_ids(city: str, when: datetime | None, targets_by_city: dict[str, list[dict]]) -> list[str]:
    if not when:
        return []
    ids = []
    for target in targets_by_city.get(city, []):
        start = parse_dt(target.get("alert_start"))
        end = parse_dt(target.get("alert_end"))
        if start and end and start <= when <= end:
            ids.append(str(target.get("episode_id") or ""))
    return sorted(x for x in ids if x)

def exact_city_after(city: str, obs: dict) -> bool:
    old = bool((obs.get("exact_city_evidence") or {}).get("present"))
    if old:
        return True
    if city != "sevastopol":
        return False
    return bool(SEVASTOPOLE_RE.search(str(obs.get("excerpt") or "")))

def strict_signal_for_sevastopole(obs: dict) -> tuple[bool, list[str]]:
    event_types: list[str] = []
    strict = False
    for seg in observation_segments(obs):
        if not SEVASTOPOLE_RE.search(seg):
            continue
        if EVENT_RE.search(seg):
            strict = True
            low = seg.casefold()
            if re.search(r"(?:влуч\w*|поціл\w*|приліт\w*)", low):
                event_types.append("impact")
            elif AIR_DEFENSE_ACTUAL_RE.search(seg):
                event_types.append("air_defense_action")
            elif re.search(r"(?:вибух\w*)", low):
                event_types.append("explosion")
            else:
                event_types.append("strike")
    dedup = []
    for x in event_types:
        if x not in dedup:
            dedup.append(x)
    return strict, dedup

def repaired_temporal(city: str, obs: dict, new_ts: str | None, targets_by_city: dict[str, list[dict]]) -> dict:
    old = copy.deepcopy(obs.get("temporal_binding") or {})
    old_ts = obs.get("event_timestamp_if_stated")
    if new_ts == old_ts or not new_ts:
        return old
    active = active_episode_ids(city, parse_dt(new_ts), targets_by_city)
    if len(active) != 1:
        return old
    episode_id = active[0]
    near = {
        "present": False,
        "episode_specific": False,
        "supported_episode_ids": [],
        "episode_id": None,
    }
    return {
        "present": True,
        "code": "TEMPORAL_EXPLICIT_EVENT_TIME_INSIDE_EPISODE",
        "evidence_type": "explicit_event_time",
        "evidence": new_ts,
        "event_time": new_ts,
        "event_interval": None,
        "message_time": None,
        "episode_specific": True,
        "supported_episode_ids": [episode_id],
        "episode_id": episode_id,
        "near_boundary": near,
        "evidence_sources": ["candidate_evidence"],
    }

def temporal_episode_id(binding: dict) -> str | None:
    if binding.get("present") and binding.get("episode_specific") and binding.get("episode_id"):
        return str(binding["episode_id"])
    near = binding.get("near_boundary") or {}
    if near.get("present") and near.get("episode_specific") and near.get("episode_id"):
        return str(near["episode_id"])
    return None

def repaired_classification(city: str, obs: dict, new_exact: bool, new_temporal: dict) -> tuple[str, str | None, list[str]]:
    old_class = str(obs.get("classification_outcome") or "needs_review")
    old_reasons = list(obs.get("classifier_reason_codes") or [])
    if old_class == "rejected":
        return old_class, obs.get("classification_episode_id"), old_reasons

    event_types = list(obs.get("event_types") or [])
    aerial = bool((obs.get("aerial_war_context") or {}).get("present"))
    same_attack = bool((obs.get("same_attack_context") or {}).get("present"))
    air_defense_context = bool(obs.get("air_defense_context"))
    air_defense_action = bool(obs.get("air_defense_action"))
    interception = bool(obs.get("interception_claim"))

    exact_changed = new_exact != bool((obs.get("exact_city_evidence") or {}).get("present"))
    if exact_changed and city == "sevastopol":
        strict_now, derived_types = strict_signal_for_sevastopole(obs)
        if strict_now and not event_types:
            event_types = derived_types
        text = str(obs.get("excerpt") or "")
        if AIR_CONTEXT_RE.search(text):
            aerial = True
        if AIR_DEFENSE_ACTUAL_RE.search(text):
            air_defense_context = True
            air_defense_action = True
            if "air_defense_action" not in event_types:
                event_types.append("air_defense_action")
        if INTERCEPTION_RE.search(text):
            interception = True
        if strict_now and aerial:
            same_attack = True

    base_event_ok = new_exact and bool(event_types) and aerial and same_attack
    strict_episode = None
    sensitivity_episode = None
    if new_temporal.get("present") and new_temporal.get("episode_specific"):
        strict_episode = new_temporal.get("episode_id")
    near = new_temporal.get("near_boundary") or {}
    if near.get("present") and near.get("episode_specific"):
        sensitivity_episode = near.get("episode_id")

    reasons = list(old_reasons)
    if exact_changed:
        reasons = [r for r in reasons if r not in {"NO_EXACT_CITY_EVENT_TEXT", "EXACT_CITY_EVENT_TEXT"}]
        reasons.append("EXACT_CITY_EVENT_TEXT")
    if strict_episode and base_event_ok:
        if "TEMPORAL_EXPLICIT_EVENT_TIME_INSIDE_EPISODE" not in reasons:
            reasons = [r for r in reasons if not r.startswith("NO_STRICT_TEMPORAL_BINDING")]
            reasons.append("TEMPORAL_EXPLICIT_EVENT_TIME_INSIDE_EPISODE")
        return "approved_strict", str(strict_episode), reasons
    if sensitivity_episode and base_event_ok:
        return "approved_sensitivity", str(sensitivity_episode), reasons

    # Step 3 can make a previously non-city candidate reviewable when it already
    # has a unique frozen episode match, without manufacturing strict proof.
    if exact_changed and new_exact:
        matching = obs.get("candidate_matching") or {}
        matched = matching.get("matched_episode_id")
        if matching.get("outcome") == "unique_match" and matched:
            return "needs_review", str(matched), reasons

    return old_class, obs.get("classification_episode_id"), reasons

def target_state_hash(order: list[tuple[str, str]], states: dict[tuple[str, str], str]) -> str:
    preimage = "".join(f"{city}\t{episode_id}\t{states[(city, episode_id)]}\n" for city, episode_id in order)
    return sha256(preimage.encode("utf-8"))

def strongest(states: list[str]) -> str:
    return max(states, key=lambda s: RANK[s]) if states else "NO_CONFIRMED_EVENT"

def write_artifact(payload: dict) -> None:
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")))

def main() -> int:
    global SOURCE_NETWORK_CALLS

    # Hard-disable source/network access inside the recovery process.
    original_socket_connect = socket.socket.connect
    original_create_connection = socket.create_connection
    def blocked_connect(*args, **kwargs):
        global SOURCE_NETWORK_CALLS
        SOURCE_NETWORK_CALLS += 1
        raise RuntimeError("network access is forbidden in offline recovery scan")
    socket.socket.connect = blocked_connect  # type: ignore[assignment]
    socket.create_connection = blocked_connect  # type: ignore[assignment]

    verdict = "OFFLINE REPAIR RECOVERY SCAN BLOCKED"
    hard_errors: list[str] = []
    scan_head = run_git("rev-parse", "HEAD")
    implementation_is_ancestor = run_git("merge-base", IMPLEMENTATION_HEAD, scan_head) == IMPLEMENTATION_HEAD
    if not implementation_is_ancestor:
        hard_errors.append("scan HEAD is not descended from accepted implementation HEAD")

    campaign_dir, batches = campaign_files()
    before_digest = corpus_digest(batches)
    before_git_diff = run_git("diff", "--name-only")
    status_path = unique_file("**/research/" + STATUS_NAME, "frozen status")
    status = json.loads(status_path.read_text(encoding="utf-8"))

    batch_payloads: list[tuple[pathlib.Path, dict]] = []
    targets: dict[tuple[str, str], dict] = {}
    targets_by_city: dict[str, list[dict]] = defaultdict(list)
    observations: list[tuple[str, pathlib.Path, dict]] = []
    observation_by_id: dict[str, dict] = {}

    for path in batches:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("campaign_id") != CAMPAIGN_ID:
            hard_errors.append(f"unexpected campaign id in {path.name}")
        batch_payloads.append((path, payload))
        city = str(payload.get("city_key") or "")
        for row in payload.get("episode_results") or []:
            episode_id = str(row.get("episode_id") or "")
            key = (city, episode_id)
            if key in targets:
                hard_errors.append(f"duplicate target {city}:{episode_id}")
            targets[key] = row
            targets_by_city[city].append(row)
        for obs in payload.get("observations") or []:
            observations.append((city, path, obs))
            oid = str(obs.get("observation_id") or "")
            if oid:
                observation_by_id[oid] = obs

    if len(targets) != EXPECTED_TARGETS:
        hard_errors.append(f"target count {len(targets)} != {EXPECTED_TARGETS}")

    original_states = {(city, eid): str(row.get("classifier_result")) for (city, eid), row in targets.items()}
    original_distribution = dict(Counter(original_states.values()))
    for state in EXPECTED_DISTRIBUTION:
        original_distribution.setdefault(state, 0)
    if {k: original_distribution[k] for k in EXPECTED_DISTRIBUTION} != EXPECTED_DISTRIBUTION:
        hard_errors.append(f"original distribution mismatch: {original_distribution}")

    frozen_cities = [c for c in (status.get("frozen_cities") or []) if c != "kyiv"]
    launch_order: list[tuple[str, str]] = []
    for city in frozen_cities:
        cp = (status.get("cities") or {}).get(city) or {}
        ids = cp.get("frozen_episode_ids") or []
        for episode_id in ids:
            key = (city, str(episode_id))
            if key not in targets:
                hard_errors.append(f"launch-order target missing from batches: {city}:{episode_id}")
            else:
                launch_order.append(key)
    if len(launch_order) != EXPECTED_TARGETS or len(set(launch_order)) != EXPECTED_TARGETS:
        hard_errors.append(f"launch order size/uniqueness mismatch: {len(launch_order)}")

    original_hash = target_state_hash(launch_order, original_states) if len(launch_order) == EXPECTED_TARGETS else None
    if original_hash != EXPECTED_ORIGINAL_HASH:
        hard_errors.append(
            "ORIGINAL STATE RECONSTRUCTION MISMATCH: "
            f"{original_hash} != {EXPECTED_ORIGINAL_HASH}"
        )

    changed_observations: list[dict] = []
    obs_changes = Counter()
    repaired_obs_class: dict[str, tuple[str, str | None]] = {}
    changed_obs_affected: dict[str, set[str]] = {}

    for city, path, obs in observations:
        oid = str(obs.get("observation_id") or "")
        old_ts = obs.get("event_timestamp_if_stated")
        new_ts = repaired_event_timestamp(obs)
        old_exact = bool((obs.get("exact_city_evidence") or {}).get("present"))
        new_exact = exact_city_after(city, obs)
        old_temporal = copy.deepcopy(obs.get("temporal_binding") or {})
        new_temporal = repaired_temporal(city, obs, new_ts, targets_by_city)
        old_class = str(obs.get("classification_outcome") or "needs_review")
        new_class, new_class_episode, new_reasons = repaired_classification(
            city, obs, new_exact, new_temporal
        )

        ts_changed = old_ts != new_ts
        exact_changed = old_exact != new_exact
        temporal_changed = canonical_bytes(old_temporal) != canonical_bytes(new_temporal)
        class_changed = old_class != new_class
        if ts_changed:
            obs_changes["parsed_event_timestamp_changed"] += 1
        if exact_changed:
            obs_changes["exact_city_result_changed"] += 1
        if temporal_changed:
            obs_changes["temporal_binding_changed"] += 1
        if class_changed:
            obs_changes["classification_changed"] += 1

        repaired_obs_class[oid] = (new_class, new_class_episode)
        if not (ts_changed or exact_changed or temporal_changed or class_changed):
            continue

        affected = set()
        for candidate in (
            obs.get("classification_episode_id"),
            (obs.get("temporal_binding") or {}).get("episode_id"),
            new_temporal.get("episode_id"),
            new_class_episode,
            (obs.get("candidate_matching") or {}).get("matched_episode_id"),
        ):
            if candidate:
                affected.add(str(candidate))
        for candidate in (obs.get("candidate_matching") or {}).get("matched_episode_ids") or []:
            if candidate:
                affected.add(str(candidate))
        changed_obs_affected[oid] = affected

        changed_observations.append({
            "observation_id": oid,
            "city": city,
            "frozen_batch": path.relative_to(REPO).as_posix(),
            "source": {
                "family": obs.get("source_family"),
                "type": obs.get("source_type"),
                "url": obs.get("source_url"),
            },
            "old_parsed_event_timestamp": old_ts,
            "new_parsed_event_timestamp": new_ts,
            "old_exact_city_result": old_exact,
            "new_exact_city_result": new_exact,
            "old_temporal_binding": old_temporal,
            "new_temporal_binding": new_temporal,
            "old_classification": old_class,
            "new_classification": new_class,
            "new_classifier_reason_codes": new_reasons,
            "affected_episode_ids": sorted(affected),
        })

    changed_observations.sort(key=lambda r: (r["city"], r["observation_id"]))

    repaired_states = dict(original_states)
    changed_contributors: dict[tuple[str, str], set[str]] = defaultdict(set)

    # Upgrades or review recoveries mechanically introduced by changed observations.
    for record in changed_observations:
        oid = record["observation_id"]
        new_class, new_episode = repaired_obs_class.get(oid, ("needs_review", None))
        candidate_ids = set()
        if new_episode:
            candidate_ids.add(new_episode)
        if new_class == "needs_review":
            obs = observation_by_id.get(oid) or {}
            matching = obs.get("candidate_matching") or {}
            if matching.get("outcome") == "unique_match" and matching.get("matched_episode_id"):
                candidate_ids.add(str(matching["matched_episode_id"]))
        for episode_id in candidate_ids:
            key = (record["city"], episode_id)
            if key not in repaired_states:
                continue
            candidate_state = CLASS_TO_TARGET.get(new_class, "NO_CONFIRMED_EVENT")
            if RANK[candidate_state] > RANK[repaired_states[key]]:
                repaired_states[key] = candidate_state
                changed_contributors[key].add(oid)

    # Explicit downgrade guard: if a changed observation weakened a frozen positive
    # contributor, recompute that target from all frozen contributors with repaired
    # classifications for changed observations and frozen classifications otherwise.
    downgrade_candidates: set[tuple[str, str]] = set()
    for key, row in targets.items():
        if original_states[key] not in {"STRICT_EVENT_POSITIVE", "SENSITIVITY_EVENT_POSITIVE"}:
            continue
        for oid in row.get("source_observation_ids") or []:
            old_obs = observation_by_id.get(str(oid))
            if not old_obs or str(oid) not in repaired_obs_class:
                continue
            old_c = str(old_obs.get("classification_outcome") or "needs_review")
            new_c = repaired_obs_class[str(oid)][0]
            if RANK[CLASS_TO_TARGET.get(new_c, "NO_CONFIRMED_EVENT")] < RANK[CLASS_TO_TARGET.get(old_c, "NO_CONFIRMED_EVENT")]:
                downgrade_candidates.add(key)

    for key in downgrade_candidates:
        row = targets[key]
        contributor_states = []
        contributor_ids = []
        for oid_raw in row.get("source_observation_ids") or []:
            oid = str(oid_raw)
            obs = observation_by_id.get(oid)
            if not obs:
                continue
            if oid in repaired_obs_class:
                cls = repaired_obs_class[oid][0]
            else:
                cls = str(obs.get("classification_outcome") or "needs_review")
            contributor_states.append(CLASS_TO_TARGET.get(cls, "NO_CONFIRMED_EVENT"))
            contributor_ids.append(oid)
        recomputed = strongest(contributor_states)
        repaired_states[key] = recomputed
        changed_contributors[key].update(contributor_ids)

    changed_targets = []
    transition_counts = Counter()
    transitions_by_city: dict[str, Counter] = defaultdict(Counter)
    downgrades = []
    for key in launch_order:
        old = original_states[key]
        new = repaired_states[key]
        if old == new:
            continue
        city, episode_id = key
        transition = f"{old} -> {new}"
        transition_counts[transition] += 1
        transitions_by_city[city][transition] += 1
        rec = {
            "city": city,
            "episode_id": episode_id,
            "frozen_outcome": old,
            "repaired_outcome": new,
            "contributing_observation_ids": sorted(changed_contributors.get(key, set())),
        }
        changed_targets.append(rec)
        if RANK[new] < RANK[old]:
            downgrades.append(rec)

    changed_targets.sort(key=lambda r: (r["city"], r["episode_id"]))
    repaired_distribution = dict(Counter(repaired_states.values()))
    for state in EXPECTED_DISTRIBUTION:
        repaired_distribution.setdefault(state, 0)

    repaired_hash = target_state_hash(launch_order, repaired_states) if len(launch_order) == EXPECTED_TARGETS else None
    changed_targets_hash = sha256(canonical_bytes(changed_targets))

    case7_obs = next((r for r in changed_observations if r["observation_id"] == CASE7_OBSERVATION), None)
    case7_target = next((r for r in changed_targets if r["episode_id"] == CASE7_EPISODE and r["city"] == "sumy"), None)
    case7_ok = bool(
        case7_obs
        and case7_obs["new_parsed_event_timestamp"] == CASE7_EXPECTED_TIME
        and case7_obs["new_classification"] == "approved_strict"
        and case7_target
        and case7_target["frozen_outcome"] == "NO_CONFIRMED_EVENT"
        and case7_target["repaired_outcome"] == "STRICT_EVENT_POSITIVE"
    )
    if not case7_ok:
        hard_errors.append("case-7 control did not reproduce")

    case18_key = ("sevastopol", CASE18_EPISODE)
    case18_old = original_states.get(case18_key)
    case18_new = repaired_states.get(case18_key)
    case18_qualifying_frozen = []
    for record in changed_observations:
        if record["city"] != "sevastopol":
            continue
        if CASE18_EPISODE in record["affected_episode_ids"] and record["new_classification"] in {"approved_strict", "approved_sensitivity"}:
            case18_qualifying_frozen.append(record["observation_id"])
    case18_ok = not case18_qualifying_frozen and case18_old == case18_new
    if not case18_ok:
        hard_errors.append("case-18 guard failed: frozen corpus newly recovered case 18")

    after_digest = corpus_digest(batches)
    after_git_diff = run_git("diff", "--name-only")
    batch_unchanged = before_digest == after_digest
    if not batch_unchanged:
        hard_errors.append("frozen campaign batch mutation detected")
    if SOURCE_NETWORK_CALLS != 0:
        hard_errors.append(f"source network call attempts detected: {SOURCE_NETWORK_CALLS}")
    if before_git_diff or after_git_diff:
        hard_errors.append("tracked repository mutation detected during scan")

    mutation_guards = {
        "frozen_batch_count_before": len(batches),
        "frozen_batch_count_after": len(batches),
        "frozen_batch_digest_before": before_digest,
        "frozen_batch_digest_after": after_digest,
        "frozen_batch_files_unchanged": batch_unchanged,
        "campaign_batch_mutations": 0 if batch_unchanged else 1,
        "source_registry_unchanged_by_scan": not bool(after_git_diff),
        "canonical_alerts_unchanged_by_scan": not bool(after_git_diff),
        "historical_final_evidence_unchanged_by_scan": not bool(after_git_diff),
        "db_neon_touched": False,
        "deployment_performed": False,
        "incorporation_performed": False,
        "tracked_git_diff_before": before_git_diff.splitlines() if before_git_diff else [],
        "tracked_git_diff_after": after_git_diff.splitlines() if after_git_diff else [],
    }

    if not hard_errors:
        verdict = "OFFLINE REPAIR RECOVERY SCAN COMPLETE"
    elif any("ORIGINAL STATE RECONSTRUCTION MISMATCH" in e for e in hard_errors):
        verdict = "OFFLINE REPAIR RECOVERY SCAN BLOCKED — ORIGINAL STATE RECONSTRUCTION MISMATCH"

    transition_counts_dict = dict(sorted(transition_counts.items()))
    transitions_by_city_dict = {
        city: dict(sorted(counter.items()))
        for city, counter in sorted(transitions_by_city.items())
    }
    recovered_strict = [
        r for r in changed_targets
        if r["repaired_outcome"] == "STRICT_EVENT_POSITIVE"
        and r["frozen_outcome"] != "STRICT_EVENT_POSITIVE"
    ]
    recovered_sensitivity = [
        r for r in changed_targets
        if r["repaired_outcome"] == "SENSITIVITY_EVENT_POSITIVE"
        and RANK[r["frozen_outcome"]] < RANK["SENSITIVITY_EVENT_POSITIVE"]
    ]

    artifact = {
        "schema_version": 1,
        "proof": "historical-offline-repair-recovery-scan-2026-10-02",
        "verdict": verdict,
        "hard_errors": hard_errors,
        "implementation_head": IMPLEMENTATION_HEAD,
        "frozen_campaign_head": FROZEN_HEAD,
        "scan_execution_head": scan_head,
        "final_proof_head": "artifact_commit; resolve branch HEAD after this artifact commit",
        "campaign_id": CAMPAIGN_ID,
        "source_network_calls": SOURCE_NETWORK_CALLS,
        "batch_count": len(batches),
        "observations": {
            "scanned": len(observations),
            "parsed_event_timestamp_changed": obs_changes["parsed_event_timestamp_changed"],
            "exact_city_result_changed": obs_changes["exact_city_result_changed"],
            "temporal_binding_changed": obs_changes["temporal_binding_changed"],
            "classification_changed": obs_changes["classification_changed"],
            "changed_observations": changed_observations,
        },
        "targets": {
            "count": len(targets),
            "before_distribution": {
                k: original_distribution.get(k, 0) for k in EXPECTED_DISTRIBUTION
            },
            "after_distribution": {
                k: repaired_distribution.get(k, 0) for k in EXPECTED_DISTRIBUTION
            },
            "total_changed_targets": len(changed_targets),
            "changed_targets": changed_targets,
            "transition_counts": transition_counts_dict,
            "transitions_by_city": transitions_by_city_dict,
            "newly_recovered_strict_positives": len(recovered_strict),
            "newly_recovered_strict_positive_targets": recovered_strict,
            "newly_recovered_sensitivity_positives": len(recovered_sensitivity),
            "newly_recovered_sensitivity_positive_targets": recovered_sensitivity,
            "no_confirmed_event_to_needs_review": transition_counts.get(
                "NO_CONFIRMED_EVENT -> NEEDS_REVIEW", 0
            ),
            "downgrades": downgrades,
        },
        "downgrade_guard": {
            "status": "DOWNGRADE DETECTED" if downgrades else "PASS — NO DOWNGRADES",
            "count": len(downgrades),
            "affected_episode_ids": [r["episode_id"] for r in downgrades],
        },
        "case_7_control": {
            "passed": case7_ok,
            "city": "sumy",
            "episode_id": CASE7_EPISODE,
            "observation_id": CASE7_OBSERVATION,
            "expected_transition": "NO_CONFIRMED_EVENT -> STRICT_EVENT_POSITIVE",
            "embedded_timestamp": "26 квітня 22:48",
            "parsed_timestamp": case7_obs["new_parsed_event_timestamp"] if case7_obs else None,
            "observed_target_transition": (
                f"{case7_target['frozen_outcome']} -> {case7_target['repaired_outcome']}"
                if case7_target else None
            ),
        },
        "case_18_guard": {
            "passed": case18_ok,
            "city": "sevastopol",
            "episode_id": CASE18_EPISODE,
            "frozen_outcome": case18_old,
            "repaired_outcome": case18_new,
            "qualifying_frozen_observation_ids": sorted(case18_qualifying_frozen),
            "new_source_excluded": "telegram/razvozhaev/23590",
        },
        "hashes": {
            "original_reconstructed_target_state_sha256": original_hash,
            "expected_original_target_state_sha256": EXPECTED_ORIGINAL_HASH,
            "repaired_target_state_sha256": repaired_hash,
            "ordered_changed_target_records_sha256": changed_targets_hash,
            "target_state_hash_convention": TARGET_STATE_HASH_CONVENTION,
            "changed_target_hash_serialization": CANONICAL_JSON,
            "proof_artifact_serialization": CANONICAL_JSON,
        },
        "mutation_guards": mutation_guards,
        "scope": {
            "fresh_discovery": False,
            "source_network_retrieval": False,
            "step_2_source_paths_used": False,
            "campaign_batches_read_locally_in_single_process": True,
            "incorporation_performed": False,
            "db_or_neon_touched": False,
            "deployment_performed": False,
        },
        "proof_artifact_path": OUT_REL.as_posix(),
    }
    write_artifact(artifact)

    socket.socket.connect = original_socket_connect  # type: ignore[assignment]
    socket.create_connection = original_create_connection  # type: ignore[assignment]
    return 0 if verdict == "OFFLINE REPAIR RECOVERY SCAN COMPLETE" else 1

if __name__ == "__main__":
    raise SystemExit(main())
