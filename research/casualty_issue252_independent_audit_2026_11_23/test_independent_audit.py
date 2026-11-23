#!/usr/bin/env python3
"""Independent, offline and fail-closed validation for casualty Issue #252.

Reads committed audit artifacts only. Never performs HTTP, edits revisions, or
imports a publisher/executor. Run: python -m unittest discover -s
research/casualty_issue252_independent_audit_2026_11_23 -p 'test_*.py' -v
"""
import csv
import io
import json
import re
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SHA256 = re.compile(r"^[0-9a-f]{64}$")
SHA1 = re.compile(r"^[0-9a-f]{40}$")
DECISIONS = {
    "CONFIRMED_FOR_RELEASE",
    "HELD_INSUFFICIENT_PROOF",
    "EXCLUDED_DUPLICATE_OR_OUT_OF_SCOPE",
}
EXPECTED_BRANCH = "research-casualty-issue252-independent-audit-2026-11-23"


def read():
    matrix = list(csv.DictReader(io.StringIO(
        (HERE / "acceptance_matrix.csv").read_text(encoding="utf-8"))))
    proof = json.loads((HERE / "audit_proof.json").read_text(encoding="utf-8"))
    witness = json.loads((HERE / "source_witness_manifest.json").read_text(encoding="utf-8"))
    request = json.loads((HERE / "owner_article_go_request.json").read_text(encoding="utf-8"))
    return matrix, proof, witness, request


def validate(matrix, proof, witness, request):
    errors = []
    def check(condition, message):
        if not condition:
            errors.append(message)

    p = proof["pub_baseline"]
    gate = proof["publication_gate"]
    summary = proof["issue252_matrix"]
    prod = proof["site_prod_sha"]

    check(proof["PROMOTE"] == "OFF" and not proof["publication_allowed"],
          "proof MUST remain PROMOTE=OFF, unpublished")
    check(proof["changes_to_prod"] == 0, "production writes forbidden")
    check(bool(SHA1.fullmatch(prod)), "site-prod SHA pin malformed")
    check(p["kyiv_2026_09_partial_deaths"] == 18
          and p["kyiv_2026_09_cutoff_inclusive"] == "2026-09-15",
          "Kyiv September must use published partial 18 through Sep 15")
    check(p["kyiv_confirmed_new_revisions"] == 0
          and p["october_confirmed_revisions"] == 0
          and p["october_published_city_month_rows"] == 0,
          "published Kyiv/October credit must not be inferred from research")
    check(p["existing_sumy_2026_09_20_revision"] == 1,
          "the Sumy Sep 20 revision is already counted")
    check(all(SHA1.fullmatch(v) for v in proof["prod_blobs"].values()),
          "production blob SHA malformed")
    check(proof["prod_blobs"]["review_queue_json"] ==
          witness["immutable_sources"]["review_queue_git_blob"],
          "queue hash mismatch between proof and witness")
    check(witness["immutable_sources"]["production_site_prod_commit"] == prod,
          "witness source site-prod mismatch")
    check(witness["PROMOTE"] == "OFF" and not witness["publication_allowed"],
          "witness cannot authorize credit")

    sources = witness["witnesses"]
    check(len(sources) == 41, "expected 29 September + 12 October witnesses")
    check(sum(key.startswith("sep/q") for key in sources) == 29,
          "September 29 source cards are required")
    check(sum(key.startswith("oct/q") for key in sources) == 10,
          "October queue witness count mismatch")
    check(sum(key.startswith("oct/s") for key in sources) == 2,
          "October collector witness count mismatch")
    for key, item in sources.items():
        check(item["url"].startswith("https://"),
              "source must use exact HTTPS: " + key)
        check(bool(SHA256.fullmatch(item["sha256"])),
              "bad source hash: " + key)
        check(item["full_publisher_body_archived"] is False,
              "source snippet must not masquerade as full body: " + key)
        if item["queue_index"] is not None:
            check("q" + str(item["queue_index"]) == key.split("/")[-1],
                  "wrong queue locator: " + key)

    check(len(matrix) == summary["rows"] == 36, "expected 36 audit decisions")
    ids = [row["record_id"] for row in matrix]
    check(len(ids) == len(set(ids)), "duplicate incident identity in matrix")
    check(set(r["decision"] for r in matrix).issubset(DECISIONS),
          "invalid decision class")
    check(all(r["independently_releasable_delta"] == "0" for r in matrix),
          "unsupported independently releasable casualty credit")
    check(all(r["published_same_event_credit"] == "0" for r in matrix),
          "source-only candidates cannot be marked as published credit")
    for row in matrix:
        check(row["month"] in ("2026-09", "2026-10"),
              "invalid attack month: " + row["record_id"])
        check(row["city"] in ("kyiv", "lutsk", "poltava",
                             "ivano-frankivsk", "khmelnytskyi", "dnipro",
                             "zaporizhzhia", "kropyvnytskyi", "chernihiv",
                             "kherson"),
              "unrecognized city: " + row["record_id"])
        check(row["missing_proof_or_exclusion"].strip() != "",
              "missing audit reason: " + row["record_id"])
        refs = row["source_refs"].split("|") if row["source_refs"] else []
        hashes = row["source_hashes"].split("|") if row["source_hashes"] else []
        check(len(refs) == len(hashes), "source/hash count mismatch for " + row["record_id"])
        for ref, token in zip(refs, hashes):
            check(ref in sources, "unregistered source: " + ref)
            check(token == ref + ":" + sources.get(ref, {}).get("sha256", ""),
                  "source hash drift: " + row["record_id"])

    sept = [x for x in matrix if x["month"] == "2026-09"]
    octo = [x for x in matrix if x["month"] == "2026-10"]
    sept_candidates = sum(int(x["proposed_new_delta"] or 0) for x in sept)
    oct_candidates = sum(int(x["proposed_new_delta"] or 0) for x in octo)
    prior = sum(int(x["release1_preapproved_not_published"] or 0)
                for x in octo)
    check(sept_candidates == 15 == summary["proposed_sep_candidate_delta"],
          "Sep proposed 15 must be non-additively mapped")
    check(oct_candidates == 11 == summary["proposed_oct_candidate_delta"],
          "Oct proposed 11 must be non-additively mapped")
    check(prior == 11 == summary["release1_earlier_oct_event_minima"],
          "Release-1 earlier 11 MUST NOT be recounted")
    check(sum(int(x["proposed_new_delta"] or 0) for x in matrix
              if x["decision"] == "EXCLUDED_DUPLICATE_OR_OUT_OF_SCOPE") == 0,
          "excluded duplicate or out-of-city credit")
    check(all(x["decision"] == "HELD_INSUFFICIENT_PROOF"
              for x in matrix if int(x["proposed_new_delta"] or 0) > 0),
          "candidate research counts must remain held")
    check(summary["unallocated_sep25_citywide"] == 2
          and next(x for x in matrix if x["record_id"] ==
                   "K25-CITYWIDE-RESIDUAL-2")["unresolved_count"] == "2",
          "September 25 unallocated two must remain blocked")
    check(next(x for x in matrix if x["record_id"] ==
               "K25-CITYWIDE-RESIDUAL-2")["decision"] ==
          "HELD_INSUFFICIENT_PROOF",
          "Sep25 residual two must be HELD, not approved")
    check(next(x for x in matrix if x["record_id"] ==
               "SEP27-CITYWIDE-SECOND-UNMAPPED")["decision"] ==
          "HELD_INSUFFICIENT_PROOF",
          "Sep27 potential additional victim requires scope reconciliation")
    check(next(x for x in matrix if x["record_id"] ==
               "EX-OCT20-CHABANY-THREE")["decision"] ==
          "EXCLUDED_DUPLICATE_OR_OUT_OF_SCOPE",
          "Chabany must stay outside Kyiv city")
    check(next(x for x in matrix if x["record_id"] ==
               "EX-OCT08-INTERIM-THREE")["proposed_new_delta"] == "0",
          "Oct8 interim 3 must not be added to final 4")
    check(next(x for x in matrix if x["record_id"] ==
               "EX-OCT07-DESNIANSKYI-REPORTED-OCT08")["attack_date"] ==
          "2026-10-07",
          "Oct7 Desnianskyi attack cannot be reassigned to report day")
    check(next(x for x in matrix if x["record_id"] ==
               "EX-SEP15-ALREADY-BASELINED")["decision"] ==
          "EXCLUDED_DUPLICATE_OR_OUT_OF_SCOPE",
          "Sep15 victim at inclusive cutoff cannot be credited")
    check(next(x for x in matrix if x["record_id"] ==
               "EX-SEP27-SUBURBAN-MARKET")["decision"] ==
          "EXCLUDED_DUPLICATE_OR_OUT_OF_SCOPE",
          "Sofiivska Borshchahivka is not Kyiv city")
    check(next(x for x in matrix if x["record_id"] ==
               "EX-SEP30-VYSHHOROD-CHILD")["decision"] ==
          "EXCLUDED_DUPLICATE_OR_OUT_OF_SCOPE",
          "Vyshhorod cannot be Kyiv credit")
    check(next(x for x in matrix if x["record_id"] ==
               "EX-SEP19-GLEVAKHA")["decision"] ==
          "EXCLUDED_DUPLICATE_OR_OUT_OF_SCOPE",
          "Hlevakha cannot be Kyiv credit")
    check(summary["independently_releasable_sep"] == "NOT_YET_VERIFIED"
          and summary["independently_releasable_oct"] == "NOT_YET_VERIFIED"
          and summary["independently_releasable_total"] == 0
          and summary["confirmed_for_release_rows"] == 0,
          "unproven new deltas must be NOT_YET_VERIFIED (zero released)")
    check(summary["release1_not_blocked"] is True,
          "Release-1 known 11 must remain unblocked")
    check(gate["READY_FOR_OWNER_GO"] is False
          and gate["article_GO_owner_approved"] is False
          and gate["needs_primary_body_capture"] is True
          and gate["patch_proposal_ready"] is False,
          "research is not owner-GO ready or patch ready")

    guard = request["guard"]
    check(request["authorization"] == "REQUEST_ONLY_NOT_GRANTED"
          and request["allow_execute"] is False
          and request["PROMOTE"] == "OFF",
          "GO packet must not confer authorization")
    check(request["source_baseline"]["site_prod_sha"] == prod
          and request["source_baseline"]["queue_blob"] ==
          proof["prod_blobs"]["review_queue_json"],
          "GO source baseline drift")
    check(len(request["targets"]) == guard["max_gets"] == 12
          and len(set(t["url"] for t in request["targets"])) == 12,
          "12 unique exact GO targets required")
    check(all(t["id"] in sources
              and t["url"] == sources[t["id"]]["url"]
              and t["prior_saved_source_sha256"] == sources[t["id"]]["sha256"]
              for t in request["targets"]), "GO targets not source-pinned")
    check(guard["https_only"] and guard["public_ip_only"]
          and guard["exact_allowlist_only"]
          and guard["max_per_url"] == 1 and guard["max_bytes_per_response"] == 2097152
          and guard["timeout_seconds"] == 15 and guard["redirects"] == "OFF"
          and guard["retries"] == "OFF" and guard["concurrency"] == 1,
          "bounded HTTP request guard weakened")
    for key in ("media_gets_now", "rss_gets", "wip_writes",
                "production_writes", "neon_writes", "c6_writes",
                "revisions_csv_writes", "automatic_credit", "netlify_deploys"):
        check(guard[key] == 0, "forbidden side effect: " + key)
    check(guard["publication_allowed"] is False, "publication forbidden")
    return errors


class IndependentAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.matrix, cls.proof, cls.witness, cls.request = read()

    def test_frozen_audit_passes(self):
        self.assertEqual([], validate(self.matrix, self.proof,
                                      self.witness, self.request))

    def reject(self, part, mutation):
        import copy
        a = [copy.deepcopy(x) for x in
             (self.matrix, self.proof, self.witness, self.request)]
        mutation(a[part])
        self.assertTrue(validate(*a))

    def test_rejects_fake_release_credit(self):
        self.reject(0, lambda a: a[0].__setitem__(
            "independently_releasable_delta", "2"))

    def test_rejects_promotion(self):
        self.reject(1, lambda a: a.__setitem__("PROMOTE", "ON"))

    def test_rejects_owner_go_without_review(self):
        self.reject(1, lambda a: a["publication_gate"].__setitem__(
            "READY_FOR_OWNER_GO", True))

    def test_rejects_kyiv_baseline_drift(self):
        self.reject(1, lambda a: a["pub_baseline"].__setitem__(
            "kyiv_2026_09_partial_deaths", 33))

    def test_rejects_a_fake_october_revision(self):
        self.reject(1, lambda a: a["pub_baseline"].__setitem__(
            "october_confirmed_revisions", 11))

    def test_rejects_release1_recount(self):
        self.reject(0, lambda a: next(x for x in a if x["record_id"] ==
            "LUTSK-2026-10-14-UAV").__setitem__(
                "proposed_new_delta", "6"))

    def test_rejects_sep25_unallocated_credit(self):
        self.reject(0, lambda a: next(x for x in a if x["record_id"] ==
            "K25-CITYWIDE-RESIDUAL-2").__setitem__(
                "decision", "CONFIRMED_FOR_RELEASE"))

    def test_rejects_wrong_queue_hash(self):
        self.reject(2, lambda a: a["witnesses"]["sep/q122"].__setitem__(
            "sha256", "0" * 64))

    def test_rejects_wrong_source_url(self):
        self.reject(3, lambda a: a["targets"][0].__setitem__(
            "url", "https://example.com/other"))

    def test_rejects_duplicate_event_ids(self):
        self.reject(0, lambda a: a[1].__setitem__(
            "record_id", a[0]["record_id"]))

    def test_rejects_oct8_3_plus_4(self):
        self.reject(0, lambda a: next(x for x in a if x["record_id"] ==
            "EX-OCT08-INTERIM-THREE").__setitem__(
                "proposed_new_delta", "3"))

    def test_rejects_chabany_city_credit(self):
        self.reject(0, lambda a: next(x for x in a if x["record_id"] ==
            "EX-OCT20-CHABANY-THREE").__setitem__(
                "independently_releasable_delta", "3"))

    def test_rejects_article_redirects(self):
        self.reject(3, lambda a: a["guard"].__setitem__("redirects", "ON"))

    def test_rejects_unapproved_get(self):
        self.reject(3, lambda a: a.__setitem__("allow_execute", True))

    def test_rejects_get_budget_overrun(self):
        self.reject(3, lambda a: a["guard"].__setitem__("max_gets", 13))

    def test_rejects_missing_source_witness(self):
        self.reject(2, lambda a: a["witnesses"].pop("oct/q69"))

    def test_rejects_disguised_full_body_claim(self):
        self.reject(2, lambda a: a["witnesses"]["sep/q122"].__setitem__(
            "full_publisher_body_archived", True))

    def test_rejects_wrong_attack_date(self):
        self.reject(0, lambda a: next(x for x in a if x["record_id"] ==
            "EX-OCT07-DESNIANSKYI-REPORTED-OCT08").__setitem__(
                "attack_date", "2026-10-08"))

    def test_rejects_sep27_hypothetical_approval(self):
        self.reject(0, lambda a: next(x for x in a if x["record_id"] ==
            "SEP27-CITYWIDE-SECOND-UNMAPPED").__setitem__(
                "decision", "CONFIRMED_FOR_RELEASE"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
