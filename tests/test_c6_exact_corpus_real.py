"""Offline exact C2 #43055353190 reproduction with Work B 262-row evidence.

Use a verified physical SQL snapshot for full Neon parity; this test exercises
the reader's deterministic selection over 33,135 C2 rows + 262 reported
historic rows without performing SQL, source HTTP, or any mutation.
"""
import csv
import hashlib
import io
import json
import os
import unittest
import zipfile
from collections import Counter
from pathlib import Path
from uuid import UUID

from scripts.c6_exact_canonical_selection import select_c2_canonical_closed

BUNDLE_SHA = "ebcf2b6a94080f7a374b0897715c732846c5bd55eb4127f79d202cf8fec04c1d"
CORPUS_SHA = "4cd2fce445e49ec200ea3a202ed8bf9e1ada9c17d60c23eb7e9c7c65e1526226"
C2_RUN = 43055353190
COMMIT = "2026-11-11T16:34:13.678Z"


class RealC2SelectionOffline(unittest.TestCase):
    def test_23_city_exact_corpus_and_stale_inventory(self):
        bundle = Path(os.environ["C6_REAL_C2_BUNDLE"])
        stale = Path(os.environ["C6_WORK_B_STALE_CSV"])
        self.assertEqual(hashlib.sha256(bundle.read_bytes()).hexdigest(), BUNDLE_SHA)
        with zipfile.ZipFile(bundle) as z:
            manifest = json.loads(z.read("manifest.json"))
            self.assertEqual(manifest["github_run_id"], C2_RUN)
            self.assertEqual(manifest["corpus_sha256"], CORPUS_SHA)
            self.assertEqual(manifest["db_branch"], "br-bold-mode-b5rub8pq")
            for path, checksum in manifest["files"].items():
                self.assertEqual(hashlib.sha256(z.read(path)).hexdigest(), checksum)
            payload = json.loads(z.read("payload.json"))
            receipt = json.loads(z.read("receipt.json"))
            self.assertEqual(receipt["run_id"], manifest["canonical_run_id"])
            keys = json.loads(z.read("site_data/dashboard_data.json"))["multicity_meta"]["production_city_keys"]
        self.assertEqual(len(keys), 23)
        self.assertEqual(payload["canonicalization_version"], "alert-canonicalization-v1")
        episodes = [r for key in keys for r in payload["cities"][key]["episodes"]]
        self.assertEqual(len(episodes), 33135)
        serial = {"canonicalization_version": payload["canonicalization_version"],
                  "production_city_keys": keys, "episodes": episodes}
        self.assertEqual(hashlib.sha256(json.dumps(
            serial, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
            allow_nan=False).encode()).hexdigest(), CORPUS_SHA)
        self.assertEqual(receipt["canonical_episode_count"], len(episodes))
        ids = {r["legacy_episode_id"] for r in episodes}
        self.assertEqual(len(ids), 33135)
        with stale.open(newline="", encoding="utf-8") as fh:
            old = list(csv.DictReader(fh))
        self.assertEqual(len(old), 262)
        self.assertEqual(len({r["stale_id"] for r in old}), 262)
        self.assertTrue(all(r["stale_id"] not in ids and r["canonical_id"] in ids
                            and r["city_key"] in keys and r["alert_type"] == "AIR"
                            and r["stale_state"] == r["canonical_state"] == "closed"
                            for r in old))
        # Synthetic UUIDs represent identities, not database UUID readback.
        # The real DB identity is independently checked by Work B SQL hashes.
        def uid(s):
            return str(UUID(bytes=hashlib.md5(s.encode("ascii")).digest()))
        raw = [{**r, "uid": uid(r["legacy_episode_id"]),
                "updated_at": "2026-11-11T16:34:11Z"} for r in episodes]
        for row in old:
            raw.append({
                "legacy_episode_id": row["stale_id"], "city_key": row["city_key"],
                "alert_type": row["alert_type"], "episode_state": row["stale_state"],
                "canonicalization_version": "alert-canonicalization-v1",
                "start_at": row["stale_start"], "end_at": row["stale_end"],
                "uid": uid(row["stale_id"]), "updated_at": "2026-11-11T16:34:11Z",
            })
        kept, evidence = select_c2_canonical_closed(
            episodes, raw, city_keys=keys, ingest_committed_at=COMMIT)
        selected_ids = {r["legacy_episode_id"] for r in kept}
        self.assertEqual(selected_ids, ids)
        self.assertEqual(evidence["cities"], 23)
        self.assertEqual(evidence["raw_closed_episodes"], 33397)
        self.assertEqual(evidence["c2_canonical_episodes"], 33135)
        self.assertEqual(evidence["historical_rows_not_selected"], 262)
        self.assertEqual(sum(r["not_selected"] for r in evidence["by_city"].values()), 262)
        self.assertEqual(Counter(r["city_key"] for r in kept),
                         Counter(r["city_key"] for r in episodes))
        self.assertTrue(all(r["alert_type"] == "AIR" and r["episode_state"] == "closed"
                            and r["canonicalization_version"] == "alert-canonicalization-v1"
                            for r in kept))
        self.assertFalse(evidence["temporal_overlap_deletion"])
        self.assertFalse(evidence["publication_allowed"])


if __name__ == "__main__":
    unittest.main()
