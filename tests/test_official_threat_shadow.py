#!/usr/bin/env python3
"""Synthetic official-source threat shadow tests; no real HTTP."""
import importlib.util
import os
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/official_threat_shadow.py"
spec = importlib.util.spec_from_file_location("official_threat_shadow", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def msg(n, text, channel="kpszsu", at="2026-11-16T10:01:00+00:00"):
    return {"url":f"https://t.me/{channel}/{n}","channel":channel,"published_at":at,"text":text}


def alert(city="kharkiv", start="2026-11-16T10:00:00Z", end="2026-11-16T10:30:00Z"):
    return {"city_key":city,"start":start,"end":end}


class TestThreatEvidence(unittest.TestCase):
    def test_candidate_not_confirmed_reason(self):
        r=mod.join_evidence([alert()], [msg(1,"Загроза ударних БпЛА в м. Харків",channel="air_alert_ua")])
        ep=r["episodes"][0]
        self.assertEqual(ep["threat_types"],["uav"])
        self.assertEqual(ep["evidence"][0]["relationship"],"ONSET_REASON_CANDIDATE")
        self.assertFalse(ep["reason_confirmed"])
        self.assertFalse(r["publish_allowed"])

    def test_oblast_not_imputed_to_city(self):
        r=mod.join_evidence([alert()], [msg(2,"БпЛА на Харківщині")])
        self.assertEqual(r["metrics"]["messages_associated"],0)

    def test_multiple_threats_preserved(self):
        r=mod.join_evidence([alert()], [msg(3,"БпЛА на Харків"),msg(4,"Балістична загроза, Харків")])
        self.assertEqual(r["episodes"][0]["threat_types"],["ballistic","uav"])

    def test_all_clear_not_threat(self):
        r=mod.join_evidence([alert()], [msg(5,"Відбій, загрозу БпЛА для Харкова знято")])
        self.assertEqual(r["metrics"]["alerts_with_evidence"],0)

    def test_outside_interval(self):
        r=mod.join_evidence([alert()], [msg(6,"БпЛА на Харків",at="2026-11-16T12:00:00+00:00")])
        self.assertEqual(r["metrics"]["messages_associated"],0)

    def test_official_domain_and_tz_required(self):
        with self.assertRaises(ValueError):
            mod.validate_message(msg(7,"БпЛА на Харків",channel="fake"))
        with self.assertRaises(ValueError):
            mod.validate_message(msg(8,"БпЛА на Харків",at="2026-11-16T10:00:00"))

    def test_saved_html_parser(self):
        raw=b'<div class="tgme_widget_message" data-post="kpszsu/99"><div class="tgme_widget_message_text">test</div><time datetime="2026-11-16T10:00:00Z"></time></div>'
        self.assertEqual(mod.parse_saved_html(raw,"kpszsu")[0]["url"],"https://t.me/kpszsu/99")
        with self.assertRaises(ValueError):
            mod.parse_saved_html(raw,"air_alert_ua")

    def test_http_without_owner_go_off(self):
        with patch.dict(os.environ,{},clear=True):
            with self.assertRaises(PermissionError):
                mod.fetch_one_public_preview("kpszsu",http_go=True)

    def test_ambiguous_overlap_unmatched(self):
        r=mod.join_evidence([alert(),alert(start="2026-11-16T10:02:00Z",end="2026-11-16T10:32:00Z")],
                            [msg(9,"БпЛА на Харків",at="2026-11-16T10:03:00Z")])
        self.assertEqual(r["metrics"]["alerts_with_evidence"],0)

    def test_conflicting_post_fails(self):
        with self.assertRaises(ValueError):
            mod.normalize_messages([msg(10,"БпЛА на Харків"),msg(10,"Балістика на Харків")])


if __name__ == "__main__":
    unittest.main()
