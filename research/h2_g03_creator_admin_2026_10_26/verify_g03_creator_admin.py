#!/usr/bin/env python3
"""Offline G03 result policy: exactly one PG18 creator-ADMIN edge.

No database, HTTP, API, or credential access. This module does not execute SQL.
The accepted Candidate A SQL and original verifier are intentionally unchanged.
"""
import argparse
import copy
import hashlib
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
HERE = pathlib.Path(__file__).resolve().parent
MANIFEST = ROOT / "H2_READONLY_QUERY_MANIFEST.json"
POLICY = HERE / "G03_CREATOR_ADMIN_POLICY.json"

SOURCE_COMMIT = "a4f30691d89a4206b910b8dfde5dac44aee0ed99"
MANIFEST_BLOB = "c4d4f6174699cd64710a0157da3c1bf1c85cae8d"
G03_SQL_SHA = "3935fdb92b3e4ec081b68ac204a2bd0af9419fe91ee4d880a64665470ce29e40"
COLUMNS = ("granted_role", "member_role", "admin_option", "inherit_option", "set_option")
EXPECTED_ROW = {
    "granted_role": "h2_catalog_inspector_ro",
    "member_role": "neondb_owner",
    "admin_option": True,
    "inherit_option": False,
    "set_option": False,
}

EXPECTED_POLICY = {
    "schema_version": 1,
    "kind": "H2_G03_PG18_CREATOR_ADMIN_NARROW_EXCEPTION",
    "mode": "OFFLINE_PROPOSAL_NO_LIVE_ACCEPTANCE",
    "source_candidate_a_commit": SOURCE_COMMIT,
    "source_independent_acceptance_run": 39613681469,
    "source_immutable_manifest_git_blob": MANIFEST_BLOB,
    "source_g03_sql_sha256": G03_SQL_SHA,
    "source_g03_columns": list(COLUMNS),
    "target": {
        "project_id": "green-cake-44216048",
        "branch_id": "br-bold-mode-b5rub8pq",
        "database": "neondb",
        "inspector_role": "h2_catalog_inspector_ro",
    },
    "accepted_rowset": [EXPECTED_ROW],
    "rejection_rule": "REJECT_ZERO_ROWS_DUPLICATES_ANY_EXTRA_INCOMING_OR_OUTGOING_MEMBERSHIP_OR_FLAG_DRIFT",
    "other_candidate_a_queries": "EXACT_ORIGINAL_GIT_BLOB_UNMODIFIED",
    "login_and_runtime_gates": "NOT_ATTESTED_NOT_AUTHORIZED_BY_THIS_POLICY",
    "neon_mutations": 0,
    "production_deployment": False,
}


def git_blob_sha(data):
    header = b"blob " + str(len(data)).encode("ascii") + bytes([0])
    return hashlib.sha1(header + data).hexdigest()


def verify_source_and_policy():
    source_bytes = MANIFEST.read_bytes()
    if git_blob_sha(source_bytes) != MANIFEST_BLOB:
        raise ValueError("original accepted Candidate A manifest changed")
    manifest = json.loads(source_bytes)
    if [q["id"] for q in manifest["queries"]] != [
            "G%02d" % n for n in range(1, 15)]:
        raise ValueError("unexpected query inventory")
    if manifest["target"]["project_id"] != EXPECTED_POLICY["target"]["project_id"]:
        raise ValueError("wrong project")
    if manifest["target"]["branch_id"] != EXPECTED_POLICY["target"]["branch_id"]:
        raise ValueError("wrong branch")
    g03 = manifest["queries"][2]
    if (g03["id"] != "G03"
            or g03["sha256"] != G03_SQL_SHA
            or hashlib.sha256(g03["sql"].encode("utf-8")).hexdigest() != G03_SQL_SHA
            or g03["columns"] != list(COLUMNS)
            or g03["max_rows"] != 17):
        raise ValueError("G03 source/columns/budget mismatch")
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    if policy != EXPECTED_POLICY:
        raise ValueError("policy changed from independently pinned exception")
    return policy


def verify_g03_rows(rows):
    """Validate *actual rows of the unchanged G03 SELECT* if safely supplied.

    The caller must independently verify the session route, effective role,
    snapshot, G01/G02, TLS and other I1-I7 conditions. No implicit coercion.
    """
    if type(rows) is not list or len(rows) != 1:
        raise ValueError("G03 must return exactly one membership edge")
    row = rows[0]
    if type(row) is not dict or set(row) != set(COLUMNS):
        raise ValueError("G03 row keys differ from the pinned SELECT")
    for name, expected in EXPECTED_ROW.items():
        value = row[name]
        if type(value) is not type(expected) or value != expected:
            raise ValueError("G03 unauthorized role membership or flags: " + name)
    return True


def negative_cases():
    row = copy.deepcopy(EXPECTED_ROW)

    def changed(**kwargs):
        modified = copy.deepcopy(row)
        modified.update(kwargs)
        return modified

    outgoing = {
        "granted_role": "pg_read_all_data",
        "member_role": "h2_catalog_inspector_ro",
        "admin_option": False,
        "inherit_option": True,
        "set_option": True,
    }
    negatives = [
        ("no_edge", []),
        ("duplicate_edge", [row, copy.deepcopy(row)]),
        ("unapproved_incoming", [row, changed(member_role="postgres")]),
        ("unapproved_outgoing", [row, outgoing]),
        ("single_outgoing", [outgoing]),
        ("wrong_creator", [changed(member_role="cloud_admin")]),
        ("wrong_parent", [changed(granted_role="neon_superuser")]),
        ("reversed_edge", [changed(granted_role="neondb_owner",
                                   member_role="h2_catalog_inspector_ro")]),
        ("admin_false", [changed(admin_option=False)]),
        ("inherit_true", [changed(inherit_option=True)]),
        ("set_true", [changed(set_option=True)]),
        ("admin_int_one", [changed(admin_option=1)]),
        ("inherit_int_zero", [changed(inherit_option=0)]),
        ("set_string_false", [changed(set_option="false")]),
        ("null_flag", [changed(admin_option=None)]),
        ("missing_member", [{k: v for k, v in row.items() if k != "member_role"}]),
        ("extra_grantor", [changed(grantor="cloud_admin")]),
        ("wrong_parent_type", [changed(granted_role=42)]),
        ("row_not_dict", [["h2_catalog_inspector_ro", "neondb_owner", True, False, False]]),
        ("tuple_not_list", (row,)),
        ("not_rows", None),
        ("empty_dict", [{}]),
    ]
    return negatives


def test_negatives():
    rejected = []
    for name, rows in negative_cases():
        try:
            verify_g03_rows(rows)
        except ValueError:
            rejected.append(name)
        else:
            raise AssertionError("G03 fail-open on " + name)
    return rejected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-file", default=None,
                        help="optional synthetic-only result JSON, never live credentials")
    args = parser.parse_args()
    verify_source_and_policy()
    assert verify_g03_rows([copy.deepcopy(EXPECTED_ROW)])
    negatives = test_negatives()
    evidence = {
        "kind": "H2_G03_CREATOR_ADMIN_NEGATIVE_CONTROLS",
        "mode": "SYNTHETIC_OFFLINE_ONLY",
        "source_manifest_git_blob": MANIFEST_BLOB,
        "g03_sql_sha256": G03_SQL_SHA,
        "positive_exact_one_row": "PASS",
        "negative_count": len(negatives),
        "rejected_cases": negatives,
        "neon_sql_calls": 0,
        "credentials_provisioned": 0,
        "runtime_I1_to_I7": "UNVERIFIED_NO_GO",
        "previous_candidate_a": "UNCHANGED",
    }
    if args.evidence_file:
        pathlib.Path(args.evidence_file).write_text(
            json.dumps(evidence, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print("PASS OFFLINE G03: one exact PG18 creator edge; "
          + str(len(negatives)) + "/" + str(len(negatives))
          + " negatives rejected; Candidate A unchanged; Neon NO-GO")


if __name__ == "__main__":
    main()
