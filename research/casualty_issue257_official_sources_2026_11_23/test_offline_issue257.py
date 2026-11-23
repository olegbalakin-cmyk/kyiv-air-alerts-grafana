#!/usr/bin/env python3
"""Issue 257: offline fail-closed primary-source + 23-city completeness audit.
No network imports, subprocess, cloud workflow or production writes.
Run: python -m unittest discover -s research/casualty_issue257_official_sources_2026_11_23 -p 'test_*.py' -v
"""
import csv
import copy
import json
import unittest
from pathlib import Path
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
REQUIRED_PUBLISHER_HOSTS = {
    "kyiv.npu.gov.ua", "kyivcity.gov.ua", "health.kyivcity.gov.ua"
}
EXPECTED_CITY_SLOTS = {"2026-09": 15, "2026-10": 11}
EXPECTED_SEPTEMBER_PARTIAL_KNOWN = 56


def read():
    def csv_rows(name):
        with (HERE / name).open(encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))
    def json_data(name):
        return json.loads((HERE / name).read_text(encoding="utf-8"))
    return (csv_rows("official_primary_source_matrix.csv"),
            csv_rows("coverage_gap_priority_23cities.csv"),
            json_data("revised_official_source_go_request.json"),
            json_data("coverage_metrics.json"))


def validate(slots, coverage, go, metrics):
    errs = []
    def require(test, message):
        if not test:
            errs.append(message)

    require(len(slots) == 26, "26 victim slots, not 26 independent signed deaths")
    require(len({s["slot_id"] for s in slots}) == len(slots), "duplicate victim alias")
    require(len({s["incident_id"] for s in slots}) == 14,
            "expected eight September and six October physical groups")
    require(len({s["issue252_record_id"] for s in slots}) == 12,
            "expected eight September and four October Issue252 proposal groups")
    require(all(sum(s["month"] == m for s in slots) == n
                for m, n in EXPECTED_CITY_SLOTS.items()), "monthly slot split")
    require(all(s["city"] == "kyiv" for s in slots), "not a Kyiv city slot")
    require(all(s["attack_date"].startswith(s["month"] + "-") for s in slots),
            "attack date not month date")
    require(all(s["decision"] == "HELD_INSUFFICIENT_PROOF"
                and s["proposed_slot_count"] == "1"
                and s["independently_releasable_delta"] == "0"
                for s in slots), "unapproved credit")
    require(all(s["full_body_witness"] == "MISSING_NOT_FETCHED"
                and s["body_sha256"] == ""
                and s["source_date_verification"] == "COMMENT_ONLY_UNVERIFIED"
                for s in slots), "false publisher body or date attestation")
    require(all(s["proposed_evidence_sufficiency"] == "INSUFFICIENT_FULL_BODY"
                and s["missing_full_body_witness"] == "YES"
                and s["conflicting_evidence"]
                for s in slots), "missing insufficiency warning")
    require(all(s["prior_excerpt_digests_NOT_FULL_BODY"]
                and s["prior_saved_excerpt_refs"]
                for s in slots), "missing original excerpt chain")
    require(all(len(s["prior_excerpt_digests_NOT_FULL_BODY"].split("|")) ==
                len(s["prior_saved_excerpt_refs"].split("|"))
                for s in slots), "excerpt ref/digest parity")
    require(all(s["source_url"].startswith("https://")
                and urlsplit(s["source_url"]).hostname in REQUIRED_PUBLISHER_HOSTS
                for s in slots), "unapproved/non-primary source URL")

    require(len(coverage) == 23 and len({c["city_slug"] for c in coverage}) == 23,
            "23 unique cities")
    require(all(c["september_coverage_status"] == "PARTIAL"
                and c["september_complete_month_proof"] == "MISSING"
                and c["october_complete_month_proof"] == "MISSING"
                and c["september_zero_does_not_prove_absence"] == "YES"
                and c["oblast_total_sufficient_for_city"] == "NO"
                for c in coverage), "month-complete/oblast/zero shortcut")
    require(all(c["october_coverage_status"] in {"PARTIAL", "UNKNOWN"}
                for c in coverage), "October claim must be partial or unknown")
    require(sum(c["september_cutoff_unknown"] == "true" for c in coverage) == 19,
            "19 unknown exact September cutoffs")
    require(sum(int(c["september_known_partial_minimum"] or "0") for c in coverage) ==
            EXPECTED_SEPTEMBER_PARTIAL_KNOWN, "prior published 56 not preserved")
    require({c["city_slug"]: c["september_cutoff_proven"]
             for c in coverage if c["september_cutoff_proven"]} ==
            {"kyiv": "2026-09-15", "kherson": "2026-09-17",
             "odesa": "2026-09-18", "zaporizhzhia": "2026-09-18"},
            "unverified cutoff treated as proven")
    require(sum(int(c["october_vetted_incident_minimum_NOT_PUBLISHED"] or "0")
                for c in coverage) == 11, "Release-1 uncredited four-city events altered")
    require(all(c["official_city_only_MVA_OVA_full_month_report"] ==
                "NOT_VERIFIED_IN_PINNED_RESEARCH" for c in coverage),
            "unproven city monthly authority summary")

    require(go["PROMOTE"] == "OFF" and not go["publication_allowed"]
            and not go["allow_execute"] and go["authorization"] == "NOT_GRANTED",
            "GO packet cannot authorize publisher requests or publication")
    require(go["previous_12_URL_secondary_manifest_not_reusable"] is True,
            "spent prior collection may not be replayed")
    require(len(go["targets"]) == 12, "twelve primary leads")
    require(len({x["source_url"] for x in go["targets"]}) == 12,
            "unique target URLs")
    require(all(x["full_body_witness"] == "MISSING_NOT_FETCHED"
                and x["full_body_sha256"] is None and x["http_get_performed"] is False
                and x["date_verification"] == "PR254_COMMENT_ONLY_NOT_INDEPENDENTLY_VERIFIED"
                for x in go["targets"]), "not-fetched official source misrepresented")
    require(all(urlsplit(x["source_url"]).hostname in REQUIRED_PUBLISHER_HOSTS
                and x["source_url"].startswith("https://")
                for x in go["targets"]), "target must be exact HTTPS official host")
    mapping = {x["id"]: x for x in go["targets"]}
    require(all(s["source_url"] in {x["source_url"] for x in go["targets"]}
                for s in slots), "slot source not allowlisted")
    require(any(s["attack_date"] == "2026-10-07" and
                s["original_date"] == "2026-10-08" and
                s["source_url"] == mapping["OCT07_EVENING"]["source_url"]
                for s in slots), "Oct7 evening reported Oct8 cannot become Oct8 event")
    require(sum(s["attack_date"] == "2026-09-25" for s in slots) == 5,
            "Sep25 final seven is not 4+1+7")
    require(sum(s["attack_date"] == "2026-10-08" for s in slots) == 4,
            "Oct8 earlier city three cannot be added to final four")
    require(sum(s["attack_date"] == "2026-10-20" for s in slots) == 1,
            "Oct20 Chabany regional three excluded")
    g = go["guard"]
    require(g["publisher_gets_now"] == 0 and
            g["max_gets_only_after_explicit_fresh_owner_GO"] == 12 and
            g["max_per_exact_url"] == 1 and g["timeout_seconds"] == 15 and
            g["max_response_bytes"] == 2097152 and
            g["https_only"] is True and g["public_ip_only"] is True and
            g["redirects"] == "OFF" and g["retries"] == "OFF" and
            g["concurrency"] == 1, "future collection safety budget")
    for forbidden in ("rss_gets", "main_writes", "site_prod_writes",
                      "neon_writes", "c6_writes", "wip_writes",
                      "revisions_writes", "netlify_deploys", "automatic_credits"):
        require(g[forbidden] == 0, "forbidden action " + forbidden)

    require(metrics["PROMOTE"] == "OFF" and not metrics["publication_allowed"],
            "metrics publication off")
    im = metrics["incident_level_lower_bounds"]
    require(im["september_23city_published_partial_minimum"] == 56
            and im["kyiv_september_published_partial_through_09_15"] == 18
            and im["kyiv_september_proposed_15_HELD"] == 15
            and im["sep25_citywide_unallocated_2_HELD"] == 2
            and im["kyiv_october_proposed_11_HELD"] == 11
            and im["october_four_other_city_events_11_PREAPPROVED_NOT_PUBLISHED"] == 11
            and im["newly_releasable_kyiv"] == "NOT_YET_VERIFIED"
            and im["authorized_new_credit"] == 0, "incident bounds conflated with releases")
    m = metrics["month_complete_coverage_proof"]
    require(m["city_count"] == 23 and m["city_month_pairs"] == 46
            and m["september_full_month_city_proofs"] == 0
            and m["october_full_month_city_proofs"] == 0
            and m["september_partial_cities"] == 23
            and m["october_partial_research_cities"] ==
                sum(c["october_coverage_status"] == "PARTIAL" for c in coverage)
            and m["october_unknown_cities"] ==
                sum(c["october_coverage_status"] == "UNKNOWN" for c in coverage),
            "month-complete evidence cannot be inferred from incident minima")
    require(metrics["primary_sources"]["direct_official_research_leads"] == 12
            and metrics["primary_sources"]["full_publisher_bodies_archived"] == 0
            and metrics["primary_sources"]["publisher_gets_issued"] == 0,
            "body proof / GET count invented")
    return errs


class Issue257OfflineAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs = read()

    def test_frozen_record_and_coverage(self):
        self.assertEqual([], validate(*self.inputs))

    def reject(self, i, update):
        arr = copy.deepcopy(self.inputs)
        update(arr[i])
        self.assertTrue(validate(*arr))

    def test_unsupported_promotion_fails(self):
        self.reject(2, lambda x: x.__setitem__("PROMOTE", "ON"))

    def test_fake_body_hash_fails(self):
        self.reject(0, lambda x: x[0].__setitem__("body_sha256", "0" * 64))

    def test_fake_full_month_fails(self):
        self.reject(1, lambda x: x[0].__setitem__("september_complete_month_proof", "COMPLETE"))

    def test_zero_not_unknown_fails(self):
        self.reject(1, lambda x: x[0].__setitem__("september_zero_does_not_prove_absence", "NO"))

    def test_region_counts_cannot_fill_city(self):
        self.reject(1, lambda x: x[0].__setitem__("oblast_total_sufficient_for_city", "YES"))

    def test_no_double_credits_sep25(self):
        self.reject(0, lambda x: x.append(dict(x[0], slot_id="extra-city-seven",
                                             attack_date="2026-09-25")))

    def test_oct7_report_day_not_attack_date(self):
        self.reject(0, lambda x: next(y for y in x if
                     y["original_date"] == "2026-10-08" and
                     y["attack_date"] == "2026-10-07").__setitem__(
                         "attack_date", "2026-10-08"))

    def test_oct8_interim_cannot_be_added(self):
        self.reject(0, lambda x: x.append(dict(x[-2], slot_id="extra-interim-three",
                                             attack_date="2026-10-08")))

    def test_chabany_outside_city(self):
        self.reject(0, lambda x: x.append(dict(x[-1], slot_id="chabany-outside-city",
                                             attack_date="2026-10-20")))

    def test_no_new_credits(self):
        self.reject(0, lambda x: x[0].__setitem__("independently_releasable_delta", "1"))

    def test_no_blank_official_urls(self):
        self.reject(0, lambda x: x[0].__setitem__("source_url", ""))

    def test_no_secondary_go_target(self):
        self.reject(2, lambda x: x["targets"][0].__setitem__(
            "source_url", "https://www.pravda.com.ua/news/2026/09/23/8054726/"))

    def test_no_network_claims(self):
        self.reject(2, lambda x: x["guard"].__setitem__("publisher_gets_now", 1))

    def test_no_reuse_spent_go(self):
        self.reject(2, lambda x: x.__setitem__(
            "previous_12_URL_secondary_manifest_not_reusable", False))

    def test_no_missing_city(self):
        self.reject(1, lambda x: x.pop())

    def test_no_unverified_monthly_report_as_proof(self):
        self.reject(1, lambda x: x[0].__setitem__(
            "official_city_only_MVA_OVA_full_month_report", "COMPLETE"))

    def test_no_netlify_preview(self):
        self.reject(2, lambda x: x["guard"].__setitem__("netlify_deploys", 1))


if __name__ == "__main__":
    unittest.main()
