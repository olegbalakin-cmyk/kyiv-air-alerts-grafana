"""Narrow offline transport/excerpt/lineage tests; NO external HTTP."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kyiv-air-alerts-grafana/scripts"))
from casualty_evidence_capture import (CaptureError, MAX_RESPONSE_BYTES,
    capture_snapshot, get_publisher_document, safe_url, select_excerpts)
from casualty_auto_review import extract_cached_reports, prepare


DN = "https://suspilne.media/dnipro/1443491-udar-rf-po-dnipru-so-vidbuvaetsa-na-misci-ataki/"
AR = "https://armyinform.com.ua/2026/11/03/udar-po%C2%A0dnipru-dvoye-zagyblyh-zrosla-kilkist-postrazhdalyh/"
OD = "https://suspilne.media/odesa/1448653-v-odesi-ogolosili-den-zalobi-za-zagiblimi-vnaslidok-ataki-rf-2/"
LB = "https://lb.ua/society/2026/11/09/779642_odesi_cherez_rosiysku_ataku.html"
GOOGLE = "https://news.google.com/rss/articles/CBMi-test"


def html_doc(*paragraphs):
    return ("<html><body><article><h1>Новини про атаку на місто</h1>"
            + "".join("<p>" + p + "</p>" for p in paragraphs)
            + "</article></body></html>").encode("utf-8")


class Response:
    def __init__(self, status=200, content=b"", headers=None):
        self.status_code = status
        self.content = content
        self.headers = headers or {"Content-Type": "text/html; charset=utf-8"}
        self.closed = False

    def iter_content(self, chunk_size=8192):
        for i in range(0, len(self.content), 8192):
            yield self.content[i:i + 8192]

    def close(self):
        self.closed = True


class Session:
    def __init__(self, responses):
        self.responses = responses
        self.called = []

    def get(self, url, **kwargs):
        self.called.append((url, kwargs))
        value = self.responses.get(url)
        if value is None:
            return Response(status=503)
        return value

    def post(self, url, **kwargs):
        self.called.append((url, kwargs))
        value = self.responses.get(url)
        if value is None:
            return Response(status=503)
        return value


def candidate(cid, url, city="dnipro", title="Атака російських військ"):
    return {"candidate_id": cid, "city_key": city, "city": "Дніпро" if city == "dnipro" else "Одеса",
            "url": url, "published_at": "2026-11-03" if city == "dnipro" else "2026-11-09",
            "title": title, "snippet": "", "status": "needs_review",
            "publisher": "publisher", "publisher_url": "https://" + url.split("/")[2]}


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.output = Path(self.t.name) / "evidence.json"

    def test_https_host_port_and_private_redirect_rejected(self):
        for link in ["http://suspilne.media/a", "https://127.0.0.1/a",
                     "https://suspilne.media:8443/a", "https://localhost/a",
                     "https://evil.com/a", "https://news.google.com/search?q=x",
                     "https://u:p@suspilne.media/a"]:
            with self.subTest(link=link), self.assertRaises(CaptureError):
                safe_url(link)

    def test_safe_redirect_and_google_wrapper(self):
        s = Session({
            GOOGLE: Response(302, headers={"Location": DN}),
            DN: Response(content=html_doc("Вранці 3 листопада РФ атакувала Дніпро ракетами. Загинули двоє людей."))
        })
        doc = get_publisher_document(GOOGLE, session=s, counter=[0])
        self.assertEqual(doc["url"], DN)
        self.assertEqual(len(s.called), 2)
        self.assertTrue(all(x[1]["allow_redirects"] is False for x in s.called))
        self.assertTrue(all(x[1]["stream"] is True for x in s.called))

    def test_google_html_link_resolution(self):
        news = (b'<html><head><link rel="canonical" href="https://suspilne.media/dnipro/real-article/">'
                b'<meta name="description" content="Safe intermediate news redirect with a publisher canonical link"></head></html>')
        target = "https://suspilne.media/dnipro/real-article/"
        s = Session({GOOGLE: Response(content=news),
                     target: Response(content=html_doc("РФ атакувала Дніпро ракетами: двоє людей загинули."))})
        doc = get_publisher_document(GOOGLE, session=s, counter=[0])
        self.assertEqual(doc["url"], target)
        self.assertEqual(len(s.called), 2)

    def test_current_opaque_google_rss_signed_rpc_resolves_allowed_publisher(self):
        opaque = "https://news.google.com/rss/articles/" + "CBMi" + "A" * 55 + "?oc=5"
        token = opaque.split("?")[0].split("/")[-1]
        google_html = ('<html><body><c-wiz><div data-n-a-id="' + token +
                       '" data-n-a-sg="AV_R3e-signed123" data-n-a-ts="1783791812">'
                       'Google News article redirect</div></c-wiz></body></html>').encode()
        rpc = "https://news.google.com/_/DotsSplashUi/data/batchexecute"
        rpc_body = b")]}'\n\n" + json.dumps([
            ["wrb.fr", "Fbv4je", json.dumps(["garturlres", DN]), None, None, None],
            ["di", 16]], ensure_ascii=True).encode()
        s = Session({
            opaque: Response(content=google_html),
            rpc: Response(content=rpc_body),
            DN: Response(content=html_doc(
                "Вранці 3 листопада РФ атакувала Дніпро ракетами. Загинули двоє людей.")),
        })
        attempts = [0]
        doc = get_publisher_document(opaque, session=s, counter=attempts)
        self.assertEqual(doc["url"], DN)
        self.assertEqual(attempts[0], 3)
        self.assertEqual(len(s.called), 3)
        self.assertEqual(s.called[1][0], rpc)
        options = s.called[1][1]
        self.assertFalse(options["allow_redirects"])
        self.assertTrue(options["stream"])
        self.assertIn("application/x-www-form-urlencoded", options["headers"]["Content-Type"])
        outer = json.loads(options["data"]["f.req"])
        self.assertEqual(outer[0][0][0], "Fbv4je")
        inner = json.loads(outer[0][0][1])
        self.assertEqual(inner[0], "garturlreq")
        self.assertEqual(inner[2], token)
        self.assertEqual(inner[3], 1783791812)
        self.assertEqual(inner[4], "AV_R3e-signed123")

    def test_current_opaque_google_rpc_rejects_unapproved_target(self):
        opaque = "https://news.google.com/rss/articles/" + "CBMi" + "A" * 50
        token = opaque.split("/")[-1]
        html = (f'<html><div data-n-a-id="{token}" data-n-a-ts="1783791812" '
                'data-n-a-sg="AV_R3e-signed123"></div></html>').encode()
        rpc = "https://news.google.com/_/DotsSplashUi/data/batchexecute"
        for target in ["http://suspilne.media/internal",
                       "https://127.0.0.1/internal",
                       "https://evil.example/story",
                       "https://suspilne.media:8443/story"]:
            with self.subTest(target=target):
                response = b")]}'\n\n" + json.dumps([
                    ["wrb.fr", "Fbv4je", json.dumps(["garturlres", target])]]).encode()
                sess = Session({opaque: Response(content=html),
                                rpc: Response(content=response)})
                with self.assertRaisesRegex(CaptureError, "GOOGLE_RPC_TARGET_NOT_ALLOWED"):
                    get_publisher_document(opaque, session=sess, counter=[0])
                self.assertEqual(len(sess.called), 2)

    def test_google_rpc_requires_signed_params_matching_article_id(self):
        opaque = "https://news.google.com/rss/articles/" + "CBMi" + "A" * 50
        samples = [
            b'<html><body><div>Consent required</div></body></html>',
            b'<html><div data-n-a-id="DIFFERENT" data-n-a-ts="1783791812" '
            b'data-n-a-sg="AV_R3e-signed123"></div></html>',
            b'<html><div data-n-a-ts="1783791812" data-n-a-sg="x">'
            b'Really short signed data</div></html>',
        ]
        for html in samples:
            with self.subTest(html=html[:50]):
                sess = Session({opaque: Response(content=html)})
                with self.assertRaises(CaptureError):
                    get_publisher_document(opaque, session=sess, counter=[0])
                self.assertEqual(len(sess.called), 1)

    def test_google_rpc_empty_result_is_fail_closed(self):
        opaque = "https://news.google.com/rss/articles/" + "CBMi" + "A" * 50
        html = (b'<html><div data-n-a-ts="1783791812" data-n-a-sg="AV_R3e-signed123">'
                   b'Google News article wrapper with sufficient HTML content for the size gate'
                   b'</div></html>')
        rpc = "https://news.google.com/_/DotsSplashUi/data/batchexecute"
        sess = Session({
            opaque: Response(content=html),
            rpc: Response(content=b")]}'\n\n" + json.dumps(
                [["wrb.fr", "Fbv4je", None, None, None, [3]]]).encode())
        })
        with self.assertRaisesRegex(CaptureError, "GOOGLE_RPC_UNRESOLVED"):
            get_publisher_document(opaque, session=sess, counter=[0])
        self.assertEqual(len(sess.called), 2)

    def test_google_rpc_obeys_shared_request_budget(self):
        opaque = "https://news.google.com/rss/articles/" + "CBMi" + "A" * 50
        html = (b'<html><div data-n-a-ts="1783791812" data-n-a-sg="AV_R3e-signed123">'
                   b'Google News article wrapper with sufficient HTML content for the size gate'
                   b'</div></html>')
        sess = Session({opaque: Response(content=html)})
        with self.assertRaisesRegex(CaptureError, "HTTP_REQUEST_BUDGET_EXHAUSTED"):
            get_publisher_document(opaque, session=sess, counter=[39])
        self.assertEqual(len(sess.called), 1)

    def test_reject_redirect_to_internal(self):
        s = Session({GOOGLE: Response(302, headers={"Location": "https://127.0.0.1/private"})})
        with self.assertRaises(CaptureError):
            get_publisher_document(GOOGLE, session=s, counter=[0])
        self.assertEqual(len(s.called), 1)

    def test_bounded_body(self):
        s = Session({DN: Response(content=b"x" * (MAX_RESPONSE_BYTES + 1))})
        with self.assertRaisesRegex(CaptureError, "BODY_TOO_LARGE"):
            get_publisher_document(DN, session=s, counter=[0])

    def test_factual_extract_and_provenance(self):
        body = html_doc("Вранці 3 листопада РФ атакувала Дніпро ракетами. "
                        "Внаслідок удару загинули двоє людей, 20 зазнали поранень.",
                        "Про це повідомили 3 листопада в ДСНС.")
        summary = capture_snapshot([candidate("dn1", DN)], self.output,
                                   session=Session({DN: Response(content=body)}))
        saved = json.loads(self.output.read_text())
        self.assertEqual(summary["articles_downloaded"], 1)
        self.assertEqual(summary["usable_evidence_packages"], 1)
        self.assertIn("двоє людей", saved["articles"][0]["text"])
        self.assertEqual(saved["receipts"][0]["body_sha256"], hashlib.sha256(body).hexdigest())
        self.assertTrue(saved["receipts"][0]["fragments"])
        self.assertEqual(saved["receipts"][0]["candidate_id"], "dn1")
        self.assertNotIn("html", json.dumps(saved))

    def test_unavailable_and_empty_do_not_stop_batch(self):
        s = Session({DN: Response(403), AR: Response(content=html_doc("Тут реклама, але немає жодного повідомлення про інцидент."))})
        summary = capture_snapshot([candidate("dn1", DN), candidate("dn2", AR)],
                                   self.output, limit=2, session=s)
        saved = json.loads(self.output.read_text())
        self.assertEqual(summary["urls_checked"], 2)
        self.assertEqual(summary["usable_evidence_packages"], 0)
        self.assertEqual(len(saved["failures"]), 2)
        self.assertEqual(saved["failures"][0]["reason"], "HTTP_STATUS_403")

    def test_repeat_does_not_create_new_article_and_retains_evidence_on_failure(self):
        body = html_doc("Вранці 3 листопада РФ атакувала Дніпро ракетами. "
                        "Внаслідок атаки загинули двоє людей.", "За даними ДСНС, загинули двоє людей.")
        q = [candidate("dn1", DN)]
        capture_snapshot(q, self.output, session=Session({DN: Response(content=body)}))
        before = json.loads(self.output.read_text())
        capture_snapshot(q, self.output, session=Session({DN: Response(content=body)}))
        replay = json.loads(self.output.read_text())
        self.assertEqual(replay["articles"], before["articles"])
        self.assertEqual(len(replay["receipts"]), 1)
        capture_snapshot(q, self.output, session=Session({DN: Response(status=503)}))
        retained = json.loads(self.output.read_text())
        self.assertEqual(retained["articles"], before["articles"])
        self.assertTrue(retained["failures"][0]["previous_evidence_retained"])

    def test_two_candidates_one_source_fetched_once(self):
        body = html_doc("Вранці 3 листопада РФ атакувала Дніпро ракетами. "
                        "Загинули двоє людей, повідомили в ДСНС.")
        s = Session({DN: Response(content=body)})
        summary = capture_snapshot([candidate("dn1", DN), candidate("dn2", DN)],
                                   self.output, limit=2, session=s)
        self.assertEqual(summary["http_requests"], 1)
        self.assertEqual(summary["usable_evidence_packages"], 2)
        self.assertEqual(len(json.loads(self.output.read_text())["articles"]), 2)

    def test_critical_negation_cannot_be_silently_dropped(self):
        body = html_doc(
            "Вранці 3 листопада російська ракета вдарила по Дніпру. Загинули двоє людей.",
            "Пізніше прокуратура спростувала попередню інформацію: загиблих немає.")
        selected, fragments = select_excerpts(body)
        self.assertIn("спростувала", selected)
        self.assertIn("загинули двоє", selected.casefold())
        self.assertTrue(any("negation_update" in f["reason"] for f in fragments))

    def test_warning_time_is_not_selected_as_attack_time(self):
        body = html_doc(
            "Вранці 9 листопада РФ атакувала Одесу реактивним безпілотником.",
            "За даними прокуратури, унаслідок атаки загинули троє людей.",
            "Повітряна тривога тривала від 09:22 до 09:34. О 09:23 Повітряні Сили попередили про дрон.")
        selected, _ = select_excerpts(body)
        self.assertNotIn("09:23", selected)
        self.assertIn("загинули троє", selected)

    def test_unrelated_teaser_is_not_accepted_as_fatality_body(self):
        body = html_doc("Російський паливний ринок знову має проблеми після відновлення постачань.")
        body = body.replace("<h1>Новини про атаку на місто</h1>".encode("utf-8"),
                            "<h1>Удар по Дніпру: двоє загиблих</h1>".encode("utf-8"))
        with self.assertRaisesRegex(CaptureError, "INSUFFICIENT_ARTICLE_BODY_FACTS"):
            select_excerpts(body)

    def test_conflicting_totals_review_not_auto_ready(self):
        one = candidate("dn1", DN)
        two = candidate("dn2", AR)
        body1 = html_doc("Вранці 3 листопада РФ атакувала Дніпро ракетами. "
                         "Загинули двоє людей, повідомили в ДСНС.")
        body2 = html_doc("Вранці 3 листопада РФ атакувала Дніпро ракетами. "
                         "Загинули троє людей, повідомили в ДСНС.")
        capture_snapshot([one, two], self.output, limit=2,
                         session=Session({DN: Response(content=body1), AR: Response(content=body2)}))
        reports = extract_cached_reports([one, two], json.loads(self.output.read_text())["articles"])
        result = prepare([one, two], [], reports, {"dnipro": {"through": "2026-09-18"}})
        self.assertEqual(len(result["proposals"]), 0)
        self.assertGreaterEqual(result["summary"]["needs_review"], 1)


if __name__ == "__main__":
    unittest.main()
