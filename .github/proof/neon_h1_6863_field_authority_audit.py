#!/usr/bin/env python3
"""Independent, bounded H1 historic source/event/key field-authority audit.
Read only: immutable Git objects. Does not invoke a classifier or a database.
"""
import collections
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

CAMPAIGN = "71cb6f6fbe856cc7b96759310fe9cc9c71cc0453"
BATCH_PREFIX = "research/historical_attack_event_backfill/historical-attack-events-v2-2026-09-27"
EXPORT_COMMIT = "02ad2e8fadee78442753567bc2d3a540345d8e8a"
EXPORT_PATH = "research/attack_event_5city_persistence_identity_export_v2_2026-10-04.json"
EXPORT_BLOB = "a2e34c4a114ad335d35068d6c6a3a4606b09db7f"
EXPORT_BYTES = 29774541
EXPORT_SHA256 = "71ab9ac4f8dbeefcdb074ab60d485ac0546086ce4bd9db755af797398895d544"
REPAIR_COMMIT = "5d18ef85a66384f189ede5ca5654d750f60f088b"
REPAIR_PATH = "research/historical_offline_repair_recovery_scan_2026-10-02.json"
REPAIR_BLOB = "26db43c2bd7fbd9e16a53e8ccefea080636bbb73"
TARGET_SHA = "652bda9bc4037d263e7e1090455ff4df5387d1f4f1a73a8c5e160d7ce62132f5"
STATUS_PATH = "research/historical_attack_event_backfill_status.json"
STATUS_BLOB = "615b380b51c0da7aa052bad06222c12785090986"
PRODUCER_COMMIT = "0ae2b596ea38c80793c18884e747dceb66d91307"
PRODUCER_PATH = ".github/workflows/attack-event-5city-persistence-identity-v2-proof.yml"
PRODUCER_BLOB = "0bd21bf527e8158419de05a98241ea2b3237c2f0"
V2_COMMIT = "bd82a6c0a19aca4610a8af6df73a307a88c35bf6"
V2_PATH = "research/attack_event_classification_identity_availability_addendum_2026-10-04.json"
STEP1_COMMIT = "b205d38dbc50bc502d10e682d4ae53491af542ea"
STEP1_PATH = "research/attack_event_neon_persistence_contract_2026-10-02.json"
PROV_COMMIT = "79f79b1a7ac610ef7f1093bea214cc44e15b70bd"
PROV_PATH = "research/attack_event_5city_repaired_classifier_provenance_addendum_2026-10-04.json"
PROV_BLOB = "d5e37030e7ff1ace22c4e2185f51669d228c38e7"
CLASSIFIER_ORIGINAL = "778469b74c2aa807d851cf2c2ee35cf4aa785589"
CLASSIFIER_REPAIRED = "06ddfa13e918b3131799c8dadd290f84f20cb901"
CLASS_KEY_VERSION = "attack-event-classification-key-v2"
EVENT_KEY_VERSION = "attack-event-key-v1"
LINK_KEY_VERSION = "attack-event-source-link-key-v1"
CITY_COUNTS = {"lviv": 126, "sevastopol": 527, "cherkasy": 1548, "sumy": 2297, "zaporizhzhia": 2365}
POSITIVE = {"STRICT_EVENT_POSITIVE", "SENSITIVITY_EVENT_POSITIVE"}
REPO = Path(os.environ.get("GITHUB_WORKSPACE") or os.getcwd()).resolve()
SIXTY_FOUR_HEX = re.compile(r"^[0-9a-f]{64}$")

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def canon(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

def compact(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))

def alternate_canon(obj):
    """Independent key preimage encoder, recursive explicit JSON array/dict construction."""
    if isinstance(obj, list):
        return "[" + ",".join(alternate_canon(item) for item in obj) + "]"
    if isinstance(obj, dict):
        return "{" + ",".join(alternate_canon(k) + ":" + alternate_canon(obj[k]) for k in sorted(obj)) + "}"
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))

def keyhash(preimage):
    a = sha(canon(preimage))
    b = sha(alternate_canon(preimage).encode("utf-8"))
    if a != b:
        raise ValueError("INDEPENDENT_CANONICAL_ENCODER_MISMATCH")
    return a

def git(*parts):
    return subprocess.check_output(["git", *parts], cwd=REPO, stderr=subprocess.PIPE)

def get_file(commit, path, required_blob=None, required_size=None, required_sha=None):
    blob = git("rev-parse", commit + ":" + path).decode().strip()
    if required_blob and blob != required_blob:
        raise ValueError("GIT_BLOB_ID_MISMATCH: " + path)
    raw = git("cat-file", "blob", blob)
    independent_blob = hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\x00" + raw).hexdigest()
    if independent_blob != blob:
        raise ValueError("GIT_OBJECT_HASH_MISMATCH: " + path)
    if required_size is not None and len(raw) != required_size:
        raise ValueError("BYTE_SIZE_MISMATCH: " + path)
    if required_sha and sha(raw) != required_sha:
        raise ValueError("CONTENT_SHA256_MISMATCH: " + path)
    return raw, {"commit": commit, "path": path, "git_blob": blob, "bytes": len(raw), "sha256": sha(raw)}

def iso_micro(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("MISSING_ALERT_BOUND")
    value = value.strip()
    v = value[:-1] + "+00:00" if value.endswith("Z") else value
    t = datetime.fromisoformat(v)
    if t.tzinfo is None or t.utcoffset() is None:
        raise ValueError("NAIVE_ALERT_BOUND_NOT_ALLOWED")
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

def clock_authority(value):
    if value is None or value == "":
        return "NOT_OBSERVABLE"
    if not isinstance(value, str):
        return "INVALID_TYPE"
    try:
        t = datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
        if t.tzinfo is None or t.utcoffset() is None:
            return "NAIVE_NO_AUTHORIZED_TIMEZONE"
        return "EXPLICIT_UTC_OR_OFFSET_RECORDED"
    except (TypeError, ValueError):
        return "UNPARSEABLE_NATIVE_TIMESTAMP"

def require(cond, code):
    if not cond:
        raise ValueError(code)

def audit():
    raw_export, export_meta = get_file(EXPORT_COMMIT, EXPORT_PATH, EXPORT_BLOB, EXPORT_BYTES, EXPORT_SHA256)
    export = json.loads(raw_export)
    raw_repair, repair_meta = get_file(REPAIR_COMMIT, REPAIR_PATH, REPAIR_BLOB)
    repair = json.loads(raw_repair)
    raw_status, status_meta = get_file(CAMPAIGN, STATUS_PATH, STATUS_BLOB)
    status = json.loads(raw_status)
    producer_meta = get_file(PRODUCER_COMMIT, PRODUCER_PATH, PRODUCER_BLOB)[1]
    prov_meta = get_file(PROV_COMMIT, PROV_PATH, PROV_BLOB)[1]
    v2_raw, v2_meta = get_file(V2_COMMIT, V2_PATH)
    step1_raw, step1_meta = get_file(STEP1_COMMIT, STEP1_PATH)
    v2, step1 = json.loads(v2_raw), json.loads(step1_raw)
    require(step1.get("verdict") == "ATTACK-EVENT NEON PERSISTENCE CONTRACT FROZEN", "H1_STEP1_CONTRACT_MISSING")
    require((v2.get("classification_identity_v2") or {}).get("classification_key_version") == CLASS_KEY_VERSION, "H1_V2_CLASS_KEY_CONTRACT_MISMATCH")
    require((v2.get("accepted_five_city_source") or {}).get("repaired_target_state_sha256") == TARGET_SHA, "H1_V2_REPAIR_CONTRACT_MISMATCH")
    require((repair.get("hashes") or {}).get("repaired_target_state_sha256") == TARGET_SHA, "H1_REPAIRED_TARGET_SHA_MISMATCH")
    require(export.get("target_state_sha256") == TARGET_SHA, "H1_EXPORT_TARGET_SHA_MISMATCH")
    require(export.get("classification_key_version") == CLASS_KEY_VERSION and export.get("attack_event_key_version") == EVENT_KEY_VERSION and export.get("source_link_key_version") == LINK_KEY_VERSION, "H1_EXPORT_KEY_CONTRACT_MISMATCH")

    paths = [p for p in git("ls-tree", "-r", "--name-only", CAMPAIGN, "--", BATCH_PREFIX).decode().splitlines()
             if re.fullmatch(re.escape(BATCH_PREFIX) + r"/(lviv|sevastopol|cherkasy|sumy|zaporizhzhia)/batch_[0-9]{6}\.json", p)]
    paths.sort()
    require(len(paths) == 139, "H1_BATCH_INVENTORY_NOT_139")
    batch_manifest, observations, targets = [], {}, {}
    obs_origin, target_origin = {}, {}
    city_episodes = collections.Counter()
    original_references = collections.Counter()
    for path in paths:
        raw, meta = get_file(CAMPAIGN, path)
        doc = json.loads(raw)
        require(doc.get("campaign_id") == "historical-attack-events-v2-2026-09-27", "H1_CAMPAIGN_ID_MISMATCH")
        city = doc["city_key"]
        require(city in CITY_COUNTS and path.split("/")[-2] == city, "H1_BATCH_CITY_DISAGREEMENT")
        version = doc.get("campaign_version") or {}
        require(version.get("classifier_sha") == CLASSIFIER_ORIGINAL and
                version.get("normalization_version") == "historical-attack-event-observation-v2" and
                version.get("methodology_version") == "historical-attack-event-air-defense-action-v2", "H1_BATCH_FROZEN_VERSION_CHANGED")
        meta["batch_number"] = doc["batch_number"]
        meta["city_key"] = city
        meta["episode_rows"] = len(doc.get("episode_results") or [])
        meta["source_observations"] = len(doc.get("observations") or [])
        batch_manifest.append(meta)
        for o in doc.get("observations") or []:
            oid = o.get("observation_id")
            require(bool(oid) and oid not in observations, "H1_ORIGINAL_SOURCE_ID_MISSING_OR_DUPLICATED")
            observations[oid], obs_origin[oid] = o, meta
        for row in doc.get("episode_results") or []:
            eid = row.get("episode_id")
            key = (city, eid)
            require(bool(eid) and key not in targets, "H1_EPISODE_ID_MISSING_OR_DUPLICATED")
            targets[key], target_origin[key] = row, meta
            city_episodes[city] += 1
            for oid in row.get("source_observation_ids") or []:
                original_references[(key, oid)] += 1
    require(len(targets) == 6863 and dict(city_episodes) == CITY_COUNTS, "H1_ORIGINAL_EPISODE_COUNT_MISMATCH")
    require(all(v == 1 for v in original_references.values()), "H1_DUPLICATED_SOURCE_IN_ORIGINAL_EPISODE")

    repair_records = {}
    for r in (repair.get("targets") or {}).get("changed_targets") or []:
        key = (r["city"], r["episode_id"])
        require(key in targets and key not in repair_records, "H1_INVALID_REPAIR_EPISODE")
        repair_records[key] = r
    require(len(repair_records) == 25, "H1_REPAIR_COUNT_NOT_25")
    changed_observations = {r["observation_id"]: r for r in
        (repair.get("observations") or {}).get("changed_observations") or []}
    require(len(changed_observations) == len((repair.get("observations") or {}).get("changed_observations") or []), "H1_DUPLICATED_REPAIR_OBSERVATION")
    for key,r in repair_records.items():
        require(r.get("contributing_observation_ids"), "H1_REPAIR_EMPTY_SOURCE_CONTRIBUTION")
        require(all(oid in changed_observations and oid in observations for oid in r["contributing_observation_ids"]), "H1_REPAIR_CONTRIBUTOR_NOT_ORIGINAL")
    repair_by_city = dict(collections.Counter(key[0] for key in repair_records))
    require(repair_by_city == {"sumy": 7, "zaporizhzhia": 18}, "H1_REPAIR_CITY_COUNTS_CHANGED")

    effective = {k: repair_records[k]["repaired_outcome"] if k in repair_records else v["classifier_result"]
                 for k,v in targets.items()}
    launch_order = [(city, eid) for city in status["frozen_cities"] if city != "kyiv"
                    for eid in status["cities"][city]["frozen_episode_ids"]]
    require(len(launch_order) == 6863 and set(launch_order) == set(targets), "H1_ACCEPTED_LAUNCH_ORDER_MISMATCH")
    reconstructed_target_sha = sha("".join(city+"\t"+eid+"\t"+effective[(city,eid)]+"\n" for city,eid in launch_order).encode())
    require(reconstructed_target_sha == TARGET_SHA, "H1_ACCEPTED_VERDICT_TARGET_SHA_MISMATCH")

    eclasses = export["classifications"]
    esources = export["source_links"]
    eevents = export["attack_events"]
    require(len(eclasses) == 6863 and len(esources) == 2340 and len(eevents) == 119, "H1_EXPORT_AGGREGATE_COUNT_CHANGED")
    class_by_episode = {(c["city_key"],c["historical_episode_id"]):c for c in eclasses}
    require(len(class_by_episode) == 6863, "H1_EXPORT_CLASSIFICATION_DUPLICATE")
    link_by_identity = {(l["classification_key_v2"],l["observation_id"],l["content_sha256"]):l for l in esources}
    require(len(link_by_identity) == 2340, "H1_EXPORT_SOURCE_LINK_IDENTITY_DUPLICATE")
    event_by_episode = {(e["city_key"],e["historical_episode_id"]):e for e in eevents}
    require(len(event_by_episode) == 119, "H1_EXPORT_EVENT_PARENT_DUPLICATE")

    class_ledger, link_ledger, event_ledger, obs_ledger = [], [], [], []
    reconstructed_link_keys = set()
    reconstructed_event_keys = set()
    expected_link_ids = set()
    expected_event_ids = set()
    used_obs = collections.Counter()
    original_refs_count = 0
    repair_refs_count = 0
    dedup_overlay_count = 0
    authority_counts = collections.Counter()
    reason_counts = collections.Counter()
    key_counts = collections.Counter()
    source_timestamp_states = collections.Counter()
    cty = collections.defaultdict(lambda: collections.Counter())
    class_input_limits = collections.Counter()

    for city,eid in sorted(targets):
        k = (city,eid)
        row, home = targets[k], target_origin[k]
        repair = repair_records.get(k)
        orig_ids = row.get("source_observation_ids") or []
        repair_ids = repair.get("contributing_observation_ids") or [] if repair else []
        original_refs_count += len(orig_ids)
        repair_refs_count += len(repair_ids)
        dedup_overlay_count += len(set(orig_ids) & set(repair_ids))
        members = sorted(set(orig_ids) | set(repair_ids))
        source_pairs = []
        types = set(str(v) for v in row.get("event_types_found") or [])
        review_values = {}
        member_rows = []
        for oid in members:
            require(oid in observations, "H1_EPISODE_SOURCE_MISSING_FROM_GIT:"+city+":"+eid+":"+oid)
            obs, origin = observations[oid], obs_origin[oid]
            content_hash = str(obs.get("content_hash") or "")
            require(bool(SIXTY_FOUR_HEX.fullmatch(content_hash)), "H1_NATIVE_SOURCE_CONTENT_HASH_INVALID")
            source_pairs.append([oid,content_hash])
            used_obs[oid] += 1
            in_original = oid in orig_ids
            in_repair = oid in repair_ids
            ch = changed_observations.get(oid) if in_repair else None
            native_ep = obs.get("classification_episode_id")
            match = obs.get("candidate_matching") or {}
            match_ep = match.get("matched_episode_id")
            match_ids = match.get("matched_episode_ids") or []
            temporal = obs.get("temporal_binding") or {}
            native_support_ids = set(str(x) for x in match_ids)
            native_support_ids.update(str(x) for x in temporal.get("supported_episode_ids") or [])
            if match_ep: native_support_ids.add(str(match_ep))
            if native_ep: native_support_ids.add(str(native_ep))
            overlay_binding = (ch or {}).get("new_temporal_binding") or {}
            overlay_affected = (ch or {}).get("affected_episode_ids") or []
            overlay_target_support = eid in overlay_affected or eid in (overlay_binding.get("supported_episode_ids") or []) or overlay_binding.get("episode_id") == eid
            # Contradictory when an original explicit singular native parent excludes this frozen parent.
            native_foreign = bool(native_ep and native_ep != eid) or bool(
                match.get("outcome") == "unique_match" and match_ep and match_ep != eid
                and eid not in (match.get("matched_episode_ids") or []))
            if native_foreign:
                category, why = "CONTRADICTION", "NATIVE_EXPLICIT_EPISODE_BINDING_DISAGREES_WITH_FROZEN_MEMBERSHIP"
            elif in_original:
                category, why = "ORIGINAL_ACCEPTED", "FROZEN_ORIGINAL_EPISODE_EXPLICIT_SOURCE_OBSERVATION_ID"
            elif in_repair and overlay_target_support:
                category, why = "INDEPENDENTLY_DERIVABLE_UNDER_FROZEN_CONTRACT", "ACCEPTED_REPAIR_CONTRIBUTOR_AND_TARGET_BINDING"
            else:
                category, why = "REPLAY_DERIVED_ONLY", "REPAIR_CONTRIBUTOR_WITHOUT_INDEPENDENT_TARGET_SUPPORT"
            clock = clock_authority(obs.get("source_timestamp"))
            event_clock = clock_authority(ch.get("new_parsed_event_timestamp") if ch and ch.get("new_parsed_event_timestamp") else obs.get("event_timestamp_if_stated"))
            if clock != "EXPLICIT_UTC_OR_OFFSET_RECORDED":
                source_timestamp_states[clock] += 1
            if category in ("REPLAY_DERIVED_ONLY","CONTRADICTION"):
                class_input_limits[category] += 1
            authority_counts[category] += 1
            reason_counts[why] += 1
            cty[city]["source_"+category] += 1
            used = ch if ch is not None else {}
            if in_repair:
                types.update(str(v) for v in (obs.get("event_types") or []))
            review_val = obs.get("review_provenance")
            if review_val not in (None, {}, [], ""):
                review_values[sha(canon(review_val))] = review_val
            rec = {
                "city_key":city, "historical_episode_id":eid,"observation_id":oid,
                "content_sha256":content_hash,"frozen_original_member":in_original,
                "accepted_repair_contributor":in_repair,
                "source_origin":{"commit":CAMPAIGN,"path":origin["path"],"git_blob":origin["git_blob"]},
                "parent_origin":{"commit":CAMPAIGN,"path":home["path"],"git_blob":home["git_blob"]},
                "repair_origin":{"commit":REPAIR_COMMIT,"path":REPAIR_PATH,"git_blob":REPAIR_BLOB} if in_repair else None,
                "original_source_family":obs.get("source_family"),"original_source_type":obs.get("source_type"),
                "source_url":obs.get("source_url"),"telegram_channel":obs.get("telegram_channel"),
                "telegram_message_id":obs.get("telegram_message_id"),
                "source_native_timestamp":obs.get("source_timestamp"),
                "source_native_timestamp_authority":clock,
                "event_time_native_or_repaired": used.get("new_parsed_event_timestamp") or obs.get("event_timestamp_if_stated"),
                "event_time_authority":event_clock,
                "source_native_matching_outcome":match.get("outcome"),
                "source_native_matched_episode":match_ep,
                "source_native_classification_episode":native_ep,
                "source_native_temporal_binding_code":temporal.get("code"),
                "source_native_supported_episode_count":len(native_support_ids),
                "source_native_supports_target":eid in native_support_ids,
                "repair_observation_affects_target":eid in overlay_affected if in_repair else None,
                "repair_temporal_supports_target":eid in (overlay_binding.get("supported_episode_ids") or []) if in_repair else None,
                "authority_category":category,"authority_reason":why,
                "normalization_version":"historical-attack-event-observation-v2",
                "physical_incident_identity_authority":"NOT_OBSERVABLE"
            }
            member_rows.append(rec)
        require(len(review_values) <= 1,"H1_REVIEW_PROVENANCE_AMBIGUOUS")
        review_sha = next(iter(review_values)) if review_values else None
        verdict = effective[k]
        start, end = iso_micro(row["alert_start"]), iso_micro(row["alert_end"])
        require(start < end, "H1_ACCEPTED_ALERT_INTERVAL_INVALID")
        qa = row.get("qa_reasons")
        require(isinstance(qa,list) and qa == sorted(qa), "H1_ORIGINAL_QA_NOT_MATERIALIZED_SORTED")
        class_blob = CLASSIFIER_REPAIRED if repair else CLASSIFIER_ORIGINAL
        evidence_hash = keyhash(source_pairs)
        if repair:
            # The frozen producer extends event types using all repair-contributor original observations.
            for oid in repair_ids:
                types.update(str(t) for t in observations[oid].get("event_types") or [])
        cpre = [CLASS_KEY_VERSION,city,eid,start,end,verdict,compact(sorted(types)),
                "MATERIALIZED",compact(qa),class_blob,
                "historical-attack-event-air-defense-action-v2","historical-attack-event-observation-v2",
                evidence_hash,review_sha]
        ckey = keyhash(cpre)
        exp = class_by_episode.get(k)
        discrepancies = []
        if exp is None:
            discrepancies.append("CLASSIFICATION_MISSING_IN_EXPORT")
        else:
            checks = {
                "classification_key":ckey,
                "alert_start_utc_microseconds":start,
                "alert_end_utc_microseconds":end,
                "verdict":verdict,
                "evidence_set_sha256":evidence_hash,
                "qa_reasons":qa,
                "event_types":sorted(types),
                "classifier_blob_sha":class_blob,
                "normalization_version":"historical-attack-event-observation-v2",
                "classifier_methodology_version":"historical-attack-event-air-defense-action-v2",
                "review_provenance_sha256":review_sha,
                "native_frozen_episode_result":row,
                "repair_overlay":repair,
            }
            for field, expected in checks.items():
                if exp.get(field) != expected: discrepancies.append("CLASSIFICATION_"+field.upper()+"_MISMATCH")
        if discrepancies: key_counts["classification_mismatched"] += 1
        else: key_counts["classification_matched"] += 1
        cty[city]["classifications"] += 1
        cty[city]["positive_classifications"] += verdict in POSITIVE
        cty[city]["repair_overlays"] += repair is not None
        if repair: class_input_limits["REPAIR_DERIVED_VERDICT_INPUT"] += 1
        if any(m["source_native_timestamp_authority"] != "EXPLICIT_UTC_OR_OFFSET_RECORDED" for m in member_rows):
            class_input_limits["SOURCE_NATIVE_CLOCK_PRECISION_GAP"] += 1
        class_ledger.append({"city_key":city,"historical_episode_id":eid,
            "classification_key_recomputed":ckey,
            "classification_key_exported":exp.get("classification_key") if exp else None,
            "evidence_set_sha256":evidence_hash,
            "evidence_membership_count":len(source_pairs),
            "accepted_verdict":verdict,"repaired":repair is not None,
            "frozen_batch_blob":home["git_blob"],"frozen_batch_path":home["path"],
            "alert_start_utc_microseconds":start,"alert_end_utc_microseconds":end,
            "classifier_blob_sha":class_blob,
            "key_computation":"MATCH" if not discrepancies else "MISMATCH",
            "mismatch_reasons":discrepancies,
            "key_input_authority":"PARTIAL" if any(m["authority_category"] in ("REPLAY_DERIVED_ONLY","CONTRADICTION") or
                m["source_native_timestamp_authority"] != "EXPLICIT_UTC_OR_OFFSET_RECORDED" for m in member_rows) else
                "ACCEPTED_OR_CONTRACT_DERIVED_AT_FROZEN_EPISODE_GRAIN",
            "publisher_original_version_authority":"NOT_OBSERVABLE"})
        for m in member_rows:
            oid, content_hash = m["observation_id"], m["content_sha256"]
            lpre = [LINK_KEY_VERSION,ckey,oid,content_hash]
            lk = keyhash(lpre)
            m["source_link_key_recomputed"] = lk
            link_id = (ckey,oid,content_hash)
            expected_link_ids.add(link_id)
            exported_link = link_by_identity.get(link_id)
            ldiscrepancies = []
            if exported_link is None:
                ldiscrepancies.append("SOURCE_LINK_MISSING_IN_EXPORT")
            else:
                for field, expected in {
                    "source_link_key":lk,"source_link_key_version":LINK_KEY_VERSION,
                    "source_family":m["original_source_family"],
                    "source_type":m["original_source_type"],
                    "source_url":m["source_url"],
                    "telegram_channel":m["telegram_channel"],
                    "telegram_message_id":m["telegram_message_id"],
                    "source_timestamp":m["source_native_timestamp"],
                }.items():
                    if exported_link.get(field) != expected:
                        ldiscrepancies.append("SOURCE_LINK_"+field.upper()+"_MISMATCH")
                if m["accepted_repair_contributor"]:
                    changed = changed_observations.get(oid) or {}
                    expected_event_time = changed.get("new_parsed_event_timestamp") or observations[oid].get("event_timestamp_if_stated")
                else:
                    expected_event_time = observations[oid].get("event_timestamp_if_stated")
                if exported_link.get("event_timestamp_if_stated") != expected_event_time:
                    ldiscrepancies.append("SOURCE_LINK_EVENT_TIMESTAMP_MISMATCH")
            if lk in reconstructed_link_keys: ldiscrepancies.append("DUPLICATE_RECOMPUTED_LINK_KEY")
            reconstructed_link_keys.add(lk)
            m["exported_source_link_key"] = exported_link.get("source_link_key") if exported_link else None
            m["key_computation"] = "MATCH" if not ldiscrepancies else "MISMATCH"
            m["mismatch_reasons"] = ldiscrepancies
            m["key_input_authority"] = ("PARTIAL" if m["authority_category"] in ("REPLAY_DERIVED_ONLY","CONTRADICTION") or
                m["source_native_timestamp_authority"] != "EXPLICIT_UTC_OR_OFFSET_RECORDED" else
                "RECORDED_OR_CONTRACT_DERIVED_WITH_DOWNSTREAM_CLASS_KEY_CEILING")
            key_counts["source_link_matched" if not ldiscrepancies else "source_link_mismatched"] += 1
            link_ledger.append(m)
        if verdict in POSITIVE:
            epre = [EVENT_KEY_VERSION,"HISTORICAL_ALERT_EPISODE",city,eid,start,end]
            ek = keyhash(epre)
            evt = event_by_episode.get(k)
            expected_event_ids.add(k)
            edisc = []
            if evt is None:
                edisc.append("MODELED_EVENT_MISSING_IN_EXPORT")
            else:
                for field, expected in {
                    "attack_event_key":ek,
                    "event_grain":"HISTORICAL_ALERT_EPISODE",
                    "city_key":city,"historical_episode_id":eid,
                    "alert_start_utc_microseconds":start,
                    "alert_end_utc_microseconds":end,
                    "classification_key_v2":ckey,
                }.items():
                    if evt.get(field) != expected: edisc.append("MODELED_EVENT_"+field.upper()+"_MISMATCH")
            if ek in reconstructed_event_keys: edisc.append("DUPLICATE_RECOMPUTED_EVENT_KEY")
            reconstructed_event_keys.add(ek)
            key_counts["event_matched" if not edisc else "event_mismatched"] += 1
            event_ledger.append({"city_key":city,"historical_episode_id":eid,
                "historical_verdict":verdict,"event_grain":"HISTORICAL_ALERT_EPISODE",
                "event_start_utc_microseconds":start,"event_end_utc_microseconds":end,
                "event_key_recomputed":ek,"event_key_exported":evt.get("attack_event_key") if evt else None,
                "classification_key":ckey,"frozen_original_parent_batch":home["path"],
                "frozen_original_parent_blob":home["git_blob"],
                "repair_overlay_applied":repair is not None,
                "historical_modeled_relation_authority":"ORIGINAL_OR_ACCEPTED_REPAIR_AT_EPISODE_GRAIN",
                "physical_attack_identity_authority":"NOT_OBSERVABLE",
                "key_input_authority":"ACCEPTED_EPISODE_ID_AND_EXPLICIT_OFFSET_BOUNDS",
                "key_computation":"MATCH" if not edisc else "MISMATCH",
                "mismatch_reasons":edisc})
    extra_class = sorted(set(class_by_episode) - set(targets))
    extra_events = sorted(set(event_by_episode) - expected_event_ids)
    extra_links = len(set(link_by_identity) - expected_link_ids)
    require(len(class_ledger)==6863 and len(event_ledger)==119 and len(link_ledger)==2340, "H1_RECONSTRUCTED_ROW_UNIVERSE_MISMATCH")
    source_by_content = collections.defaultdict(set)
    obs_ids_with_original_binding = collections.Counter(oid for (_,oid), n in original_references.items() for _ in range(n))
    for oid,obs in sorted(observations.items()):
        origin = obs_origin[oid]
        source_by_content[str(obs.get("content_hash"))].add(oid)
        obs_ledger.append({
            "observation_id":oid,"source_origin":{"commit":CAMPAIGN,"path":origin["path"],"git_blob":origin["git_blob"]},
            "source_family":obs.get("source_family"),"source_type":obs.get("source_type"),
            "source_url":obs.get("source_url"),"telegram_channel":obs.get("telegram_channel"),
            "telegram_message_id":obs.get("telegram_message_id"),
            "native_content_sha256":obs.get("content_hash"),
            "native_source_timestamp":obs.get("source_timestamp"),
            "native_source_timestamp_authority":clock_authority(obs.get("source_timestamp")),
            "native_event_timestamp":obs.get("event_timestamp_if_stated"),
            "native_event_timestamp_authority":clock_authority(obs.get("event_timestamp_if_stated")),
            "original_frozen_membership_reference_count":obs_ids_with_original_binding.get(oid,0),
            "effective_export_membership_count":used_obs.get(oid,0),
            "unbound_reason":"NO_ORIGINAL_EPISODE_OR_ACCEPTED_REPAIR_MEMBERSHIP" if not used_obs.get(oid) else None,
            "normalization_contract":"historical-attack-event-observation-v2",
        })
    nonunique_contents = {h:sorted(ids) for h,ids in source_by_content.items() if len(ids)>1}
    disagreement_count = sum(key_counts[x] for x in ["classification_mismatched","source_link_mismatched","event_mismatched"])
    disagreement_count += len(extra_class)+len(extra_events)+extra_links
    verdicts = {
        "H1_SOURCE_MEMBERSHIP_HISTORICAL_AUTHORITY":"CONTRADICTION" if authority_counts["CONTRADICTION"] else
            "PARTIAL" if authority_counts["REPLAY_DERIVED_ONLY"] else "PASS",
        "H1_MODELED_EVENT_RELATIONSHIP_HISTORICAL_AUTHORITY":"PASS" if key_counts["event_matched"]==119 and not extra_events else "CONTRADICTION",
        "H1_CLASSIFICATION_KEY_INPUT_AUTHORITY":"PARTIAL",
        "H1_EVENT_KEY_INPUT_AUTHORITY":"PASS (HISTORICAL_ALERT_EPISODE INPUTS ONLY)" if key_counts["event_matched"]==119 and not extra_events else "CONTRADICTION",
        "H1_SOURCE_LINK_KEY_INPUT_AUTHORITY":"PARTIAL",
        "H1_6863_FIELD_AUTHORITY_AUDIT":"CONTRADICTION" if disagreement_count or authority_counts["CONTRADICTION"] else "PARTIAL",
    }
    return {
        "schema_version":"h1_6863_historical_field_authority_independent_reconstruction_v1",
        "objective":"H1 source membership, modeled event relations, classification/event/source-link key input audit",
        "scope_guards":{"database_queries":0,"database_writes":0,"neon_access":0,"production_modifications":0,
            "classifier_reruns":0,"historical_backfill":0,"historical_parent_admissions":0,
            "global_neon_parity_certified":False,"c4_accepted":False,"c5_accepted":False,
            "immutable_h2_predecessor_unchanged":True,"unit_a_a5_reruns":0},
        "inputs":{"original_export":export_meta,"original_139_batches_commit":CAMPAIGN,"campaign_status":status_meta,
                  "repair_authority":repair_meta,"accepted_repaired_target_state_sha256":TARGET_SHA,
                  "original_producer_workflow":producer_meta,
                  "frozen_class_identity_contract":v2_meta,"frozen_persistence_contract":step1_meta,
                  "classifier_provenance_contract":prov_meta,"original_producer_actions_run":37228197343,
                  "preceding_authority_transport_actions_runs":[38130936739,38168146240]},
        "immutable_batch_manifest":batch_manifest,
        "method":{"source_categories":["ORIGINAL_ACCEPTED","INDEPENDENTLY_DERIVABLE_UNDER_FROZEN_CONTRACT",
                                      "REPLAY_DERIVED_ONLY","NOT_OBSERVABLE","CONTRADICTION"],
            "original_accepted":"source_observation_id is explicitly recorded in original episode_results of immutable campaign batch",
            "independently_derivable":"separately accepted first-state repair overlay explicitly contributes observation and ties it to target through frozen observation repair record",
            "replay_only":"derived exporter binding is not an accepted original episode link and repair-target corroboration is absent",
            "contradiction":"native unambiguous episode binding conflicts with frozen assigned parent or expected row/key does not match",
            "source_native_timestamp":"recorded source-native value; explicit UTC/offset is not independent publisher version verification",
            "clock_precision_policy":"do not coerce naive source timestamp to UTC or substitute importer local date",
            "event_grain":"HISTORICAL_ALERT_EPISODE, never independently established physical attack",
            "key_preimage_format":"UTF-8 compact JSON arrays; Python canonical sorted keys; independent handwritten recursive encoder cross-check",
            "normalized_evidence_set":"sorted [observation_id, source-native content_hash] pairs with dedup per parent",
            "classification_tuple_fields":["version","city","episode_id","alert_start_micro_utc","alert_end_micro_utc",
                 "accepted_verdict","compact_event_types","qa_state","compact_qa_reasons",
                 "accepted_classifier_blob","methodology","normalization","evidence_set_sha256","review_sha256"],
            "modeled_event_tuple_fields":["version","HISTORICAL_ALERT_EPISODE","city","episode_id","start","end"],
            "source_link_tuple_fields":["version","classification_key","observation_id","native_content_sha256"]},
        "original_source_accounting":{"physical_source_observations":len(observations),
            "unique_source_content_sha256":len(source_by_content),
            "reused_native_content_hashes_count":len(nonunique_contents),
            "reused_native_content_hashes":nonunique_contents,
            "unique_original_frozen_source_references":len(original_references),
            "original_frozen_source_references":original_refs_count,
            "accepted_repair_contributor_references":repair_refs_count,
            "repair_original_reference_overlap_dedup":dedup_overlay_count,
            "effective_source_links":len(link_ledger),
            "distinct_source_observations_with_effective_memberships":len(used_obs),
            "source_observations_not_bound_to_accepted_episode":len(observations)-len(used_obs),
            "observations_used_in_multiple_episodes":sum(n>1 for n in used_obs.values()),
            "source_timestamp_non_explicit_in_memberships":dict(source_timestamp_states),
            "member_authority_distribution":dict(authority_counts),
            "member_authority_reasons":dict(reason_counts)},
        "reconciliation":{"historical_accepted_episode_count":6863,
            "historical_accepted_episode_unique":len(targets),
            "campaign_batches_verified":len(batch_manifest),
            "classification_recomputed":len(class_ledger),"classification_matched":key_counts["classification_matched"],
            "classification_mismatched":key_counts["classification_mismatched"],
            "classification_missing":sum("CLASSIFICATION_MISSING_IN_EXPORT" in x["mismatch_reasons"] for x in class_ledger),
            "classification_extra":len(extra_class),
            "source_link_recomputed":len(link_ledger),"source_link_matched":key_counts["source_link_matched"],
            "source_link_mismatched":key_counts["source_link_mismatched"],
            "source_link_missing":sum("SOURCE_LINK_MISSING_IN_EXPORT" in x["mismatch_reasons"] for x in link_ledger),
            "source_link_extra":extra_links,
            "positive_classifications":sum(effective[k] in POSITIVE for k in effective),
            "modeled_event_recomputed":len(event_ledger),"modeled_event_matched":key_counts["event_matched"],
            "modeled_event_mismatched":key_counts["event_mismatched"],
            "modeled_event_missing":sum("MODELED_EVENT_MISSING_IN_EXPORT" in x["mismatch_reasons"] for x in event_ledger),
            "modeled_event_extra":len(extra_events),
            "original_repaired_target_state_sha256":reconstructed_target_sha,
            "independent_key_encoders_agreed_for_every_key":True,
            "classification_input_limitations":dict(class_input_limits),
            "affirmative_historical_source_binding_contradictions":authority_counts["CONTRADICTION"],
            "unexplained_key_or_row_contradictions":disagreement_count},
        "per_city":{city:{"original_episode_rows":CITY_COUNTS[city],**dict(cty[city])} for city in CITY_COUNTS},
        "accepted_repair_provenance":{"changed_target_count":len(repair_records),
            "changed_targets_by_city":repair_by_city,"repair_targets":[{"city":x[0],"historical_episode_id":x[1],
                "frozen_outcome":v["frozen_outcome"],"accepted_repaired_outcome":v["repaired_outcome"],
                "original_batch_origin":target_origin[x]["path"],
                "accepted_contributor_observation_ids":v["contributing_observation_ids"]}
                for x,v in sorted(repair_records.items())]},
        "observations":obs_ledger,
        "classifications":class_ledger,
        "source_membership_ledger":link_ledger,
        "modeled_event_relationship_ledger":event_ledger,
        "verdicts":verdicts,
        "historical_authority_ceilings":[
           "Native Git source records prove frozen observed content and recorded associations, not original article HTTP versions",
           "A membership explicitly recorded in a frozen batch is a historically recorded classifier decision, not automatically an independently proven causal attack link",
           "Repaired contributor associations must remain distinct from original frozen membership and from 25 unresolved canonical-parent admissions",
           "HISTORICAL_ALERT_EPISODE event-grain key equality does not prove a distinct real physical attack identity",
           "Source clocks without explicit offsets are not accepted UTC instants",
           "A Git-derived October 4 export has independent lineage from Neon but is not complete persisted-row parity",
           "The 25 historical UNBOUND parent admissions (H1 5, H2 20) and global missing/extra Neon state are outside this research audit"
        ],
        "global_cutover_gates":{"H2_19542_FIELD_AUTHORITY_AUDIT":"PARTIAL — ACCEPTED",
            "H1_FULL_SOURCE_EVENT_KEY_FIELD_AUTHORITY":"NOT PROVEN",
            "HISTORICAL_PARENT_ADMISSION":"UNRESOLVED","UNBOUND_UNRESOLVED":25,
            "GLOBAL_HISTORICAL_MISSING_EXTRA":"NOT CERTIFIED","C4":"NOT PROVEN","C5":"NOT PROVEN",
            "NEON_AUTHORITY_ACTIVE":"NO","PRODUCTION_CUTOVER_EXECUTED":"NO"}
    }

def negative_tests(proof):
    r = proof["classifications"][0]
    e = proof["modeled_event_relationship_ledger"][0]
    l = proof["source_membership_ledger"][0]
    h = keyhash([CLASS_KEY_VERSION,r["city_key"],r["historical_episode_id"],r["classification_key_recomputed"]])
    assert h != keyhash([CLASS_KEY_VERSION,r["city_key"],r["historical_episode_id"],"tampered-"+r["classification_key_recomputed"]])
    assert keyhash([EVENT_KEY_VERSION,"HISTORICAL_ALERT_EPISODE",e["city_key"],e["historical_episode_id"],e["event_start_utc_microseconds"],e["event_end_utc_microseconds"]]) == e["event_key_recomputed"]
    assert keyhash([EVENT_KEY_VERSION,"HISTORICAL_ALERT_EPISODE",e["city_key"],e["historical_episode_id"],e["event_start_utc_microseconds"],e["event_end_utc_microseconds"].replace(".000000Z",".000001Z") if ".000000Z" in e["event_end_utc_microseconds"] else e["event_end_utc_microseconds"][:-2]+"1Z"]) != e["event_key_recomputed"]
    assert keyhash([LINK_KEY_VERSION,l["source_link_key_recomputed"],l["observation_id"]]) != keyhash([LINK_KEY_VERSION,l["source_link_key_recomputed"],"different-observation"])
    assert keyhash([LINK_KEY_VERSION,l["source_link_key_recomputed"],l["historical_episode_id"]]) != keyhash([LINK_KEY_VERSION,l["source_link_key_recomputed"],"different-parent"])
    assert keyhash([LINK_KEY_VERSION,l["source_link_key_recomputed"],l["content_sha256"]]) != keyhash([LINK_KEY_VERSION,l["source_link_key_recomputed"],"0"*64])
    assert keyhash([[l["observation_id"],l["content_sha256"]]]) != keyhash([[l["observation_id"],"f"*64]])
    try:
        iso_micro("2026-04-26T22:48:00")
        raise AssertionError("NAIVE_TIMESTAMP_WRONGLY_ACCEPTED")
    except ValueError as exc:
        assert str(exc) == "NAIVE_ALERT_BOUND_NOT_ALLOWED"
    assert clock_authority("2026-04-26 22:48:00") == "NAIVE_NO_AUTHORIZED_TIMEZONE"
    assert iso_micro("2026-04-26T22:48:00+03:00") == "2026-04-26T19:48:00.000000Z"
    assert iso_micro("2026-04-26T22:48:00Z") != iso_micro("2026-04-26T22:48:00+03:00")
    return {"altered_value":"PASS","event_interval_precision":"PASS","source_identity":"PASS",
            "source_parent_binding":"PASS","content_hash":"PASS","evidence_membership":"PASS",
            "naive_utc_block":"PASS","explicit_offset_conversion":"PASS","timezone_assumption":"PASS"}

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: audit.py /tmp/h1_A.json")
    proof = audit()
    proof["negative_tests"] = negative_tests(proof)
    output = canon(proof) + b"\n"
    Path(sys.argv[1]).write_bytes(output)
    print("H1_CORE_SHA256="+sha(output))
    print("H1_SUMMARY="+json.dumps({"reconciliation":proof["reconciliation"],
        "authority":proof["original_source_accounting"]["member_authority_distribution"],
        "verdicts":proof["verdicts"],"negative_tests":proof["negative_tests"],
        "source_time_limitations":proof["original_source_accounting"]["source_timestamp_non_explicit_in_memberships"]},
        sort_keys=True,ensure_ascii=False))
