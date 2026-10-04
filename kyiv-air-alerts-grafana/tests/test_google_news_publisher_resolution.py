from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import monitor_explosion_candidates as monitor


GOOGLE_URL = "https://news.google.com/rss/articles/CBMIFixtureToken_123?oc=5"
GOOGLE_LOCALE_URL = GOOGLE_URL + "&hl=uk&gl=UA&ceid=UA:uk"


class FakeResponse:
    def __init__(
        self,
        *,
        url: str,
        status: int = 200,
        content_type: str = "text/html; charset=utf-8",
        text: str = "",
        history=None,
        location: str | None = None,
    ):
        self.url = url
        self.status_code = status
        self.headers = {"Content-Type": content_type}
        if location:
            self.headers["Location"] = location
        self.text = text
        self.content = text.encode("utf-8")
        self.history = list(history or [])

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def wrapper_html(signature: str = "fixture-signature", timestamp: int = 1770000000) -> str:
    return (
        "<!doctype html><html><body>"
        f'<c-wiz><div jscontroller="Fixture" data-n-a-sg="{signature}" '
        f'data-n-a-ts="{timestamp}"></div></c-wiz>'
        "</body></html>"
    )


def rpc_response(url: str) -> str:
    inner = json.dumps(["garturlres", url, 1], separators=(",", ":"))
    outer = [["wrb.fr", "Fbv4je", inner, None, None, None, "generic"]]
    return ")]}'\n\n" + json.dumps(outer, separators=(",", ":"))


def current_shape_get(resolved_url: str, publisher_body: str = "<article>publisher body</article>"):
    locale_hop = FakeResponse(
        url=GOOGLE_URL,
        status=302,
        content_type="application/binary",
        location=GOOGLE_LOCALE_URL,
    )
    wrapper = FakeResponse(
        url=GOOGLE_LOCALE_URL,
        text=wrapper_html(),
        history=[locale_hop],
    )
    publisher = FakeResponse(url=resolved_url, text=publisher_body)

    calls = []

    def get(url, **kwargs):
        calls.append(("GET", url, kwargs))
        if str(url).startswith("https://news.google.com/"):
            return wrapper
        if url == resolved_url:
            return publisher
        raise AssertionError(url)

    return get, calls, wrapper, publisher


def current_shape_post(resolved_url: str):
    calls = []

    def post(url, **kwargs):
        calls.append(("POST", url, kwargs))
        assert url == monitor.GOOGLE_NEWS_BATCH_RESOLVE_URL
        payload = kwargs["data"]["f.req"]
        decoded = json.loads(payload)
        assert decoded[0][0][0] == "Fbv4je"
        rpc_arg = json.loads(decoded[0][0][1])
        assert rpc_arg[0] == "garturlreq"
        assert rpc_arg[2] == "CBMIFixtureToken_123"
        assert rpc_arg[3] == 1770000000
        assert rpc_arg[4] == "fixture-signature"
        return FakeResponse(
            url=monitor.GOOGLE_NEWS_BATCH_RESOLVE_URL,
            content_type="application/json; charset=utf-8",
            text=rpc_response(resolved_url),
        )

    return post, calls


@pytest.mark.parametrize(
    "resolved_url",
    [
        "https://publisher-one.example/news/a",
        "https://independent-two.example/article/b",
        "https://third-publisher.example.ua/story/c",
    ],
)
def test_current_google_wrapper_resolves_multiple_publishers(monkeypatch, resolved_url):
    get, get_calls, _, _ = current_shape_get(resolved_url)
    post, post_calls = current_shape_post(resolved_url)
    monkeypatch.setattr(monitor.requests, "get", get)
    monkeypatch.setattr(monitor.requests, "post", post)

    body, final_url = monitor.fetch_publisher_fulltext(GOOGLE_URL)

    assert body == "publisher body"
    assert final_url == resolved_url
    assert get_calls[0][2]["allow_redirects"] is True
    assert len(post_calls) == 1
    assert len(get_calls) == 2


def test_locale_normalizing_google_302_is_current_shape(monkeypatch):
    resolved_url = "https://locale-publisher.example/story"
    get, _, wrapper, _ = current_shape_get(resolved_url)
    post, _ = current_shape_post(resolved_url)
    monkeypatch.setattr(monitor.requests, "get", get)
    monkeypatch.setattr(monitor.requests, "post", post)

    assert wrapper.history[0].status_code == 302
    assert wrapper.history[0].headers["Location"] == GOOGLE_LOCALE_URL
    assert monitor.resolve_google_news_publisher_url(
        GOOGLE_URL,
        wrapper_response=wrapper,
        http_post=post,
    ) == resolved_url


def test_legacy_direct_publisher_redirect_is_preserved(monkeypatch):
    resolved_url = "https://legacy-publisher.example/article"
    google_hop = FakeResponse(
        url=GOOGLE_URL,
        status=302,
        content_type="application/binary",
        location=resolved_url,
    )
    response = FakeResponse(
        url=resolved_url,
        text="<article>legacy publisher body</article>",
        history=[google_hop],
    )
    post_calls = []

    monkeypatch.setattr(monitor.requests, "get", lambda *a, **k: response)
    monkeypatch.setattr(monitor.requests, "post", lambda *a, **k: post_calls.append((a, k)))

    body, final_url = monitor.fetch_publisher_fulltext(GOOGLE_URL)

    assert body == "legacy publisher body"
    assert final_url == resolved_url
    assert post_calls == []


def test_malformed_or_expired_article_identifier_fails_cleanly():
    bad = "https://news.google.com/rss/articles/bad!token?oc=5"
    response = FakeResponse(url=bad, text=wrapper_html())
    assert monitor.resolve_google_news_publisher_url(bad, wrapper_response=response) is None


def test_unresolved_google_wrapper_fails_cleanly():
    response = FakeResponse(url=GOOGLE_LOCALE_URL, text="<html><body>no resolver attrs</body></html>")
    assert monitor.resolve_google_news_publisher_url(GOOGLE_URL, wrapper_response=response) is None


def test_non_html_google_response_fails_cleanly():
    response = FakeResponse(
        url=GOOGLE_LOCALE_URL,
        content_type="application/json",
        text='{"no":"html"}',
    )
    assert monitor.resolve_google_news_publisher_url(GOOGLE_URL, wrapper_response=response) is None


def test_google_http_failure_fails_cleanly():
    response = FakeResponse(url=GOOGLE_LOCALE_URL, status=503, text=wrapper_html())
    assert monitor.resolve_google_news_publisher_url(GOOGLE_URL, wrapper_response=response) is None


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "data:text/plain,x",
        "javascript:alert(1)",
        "http://localhost/admin",
        "http://127.0.0.1/internal",
        "http://10.0.0.1/internal",
        "http://169.254.169.254/latest/meta-data",
        "https://news.google.com/articles/x",
        "https://google.com/search?q=x",
        "https://service.local/private",
    ],
)
def test_resolved_publisher_url_validation_rejects_unsafe_targets(url):
    assert monitor.validated_publisher_url(url) is None


def test_resolved_publisher_url_validation_accepts_public_http_https():
    assert monitor.validated_publisher_url("https://publisher.example/story") == "https://publisher.example/story"
    assert monitor.validated_publisher_url("http://publisher.example/story") == "http://publisher.example/story"


def test_fetch_fail_open_on_unresolved_google_wrapper(monkeypatch):
    response = FakeResponse(url=GOOGLE_LOCALE_URL, text="<html><body>unresolved</body></html>")
    monkeypatch.setattr(monitor.requests, "get", lambda *a, **k: response)
    monkeypatch.setattr(monitor.requests, "post", lambda *a, **k: pytest.fail("POST must not be reached"))

    assert monitor.fetch_publisher_fulltext(GOOGLE_URL) == (None, None)


def test_cache_deduplicates_actual_repaired_fetcher(monkeypatch):
    resolved_url = "https://cache-publisher.example/story"
    get, get_calls, _, _ = current_shape_get(
        resolved_url,
        publisher_body="<article>О 21:17 у Полтаві під час атаки БпЛА пролунав вибух.</article>",
    )
    post, post_calls = current_shape_post(resolved_url)
    monkeypatch.setattr(monitor.requests, "get", get)
    monkeypatch.setattr(monitor.requests, "post", post)

    row = {
        "source": "Google News RSS",
        "discovery_basis": "rss_title_snippet",
        "resolved_url": None,
        "url": GOOGLE_URL,
        "matched_text_excerpt": "feed excerpt",
    }
    decision = {
        "candidate_evidence": {
            "exact_city": {"present": True},
            "strict_explosion": {"present": True},
            "air_military_context": {"present": True},
            "same_attack_context": {"present": True},
            "temporal_binding": {"present": False, "episode_specific": False, "episode_id": None},
        }
    }
    cache = {}

    first, first_fetched, first_ok = monitor.enrich_rss_candidate_for_durability(
        dict(row),
        decision,
        fulltext_fetcher=monitor.fetch_publisher_fulltext,
        fetch_cache=cache,
    )
    second, second_fetched, second_ok = monitor.enrich_rss_candidate_for_durability(
        dict(row),
        decision,
        fulltext_fetcher=monitor.fetch_publisher_fulltext,
        fetch_cache=cache,
    )

    assert first_ok and second_ok
    assert first_fetched is True
    assert second_fetched is False
    assert first["resolved_url"] == second["resolved_url"] == resolved_url
    assert len(post_calls) == 1
    assert len(get_calls) == 2


def test_batch_parser_rejects_google_or_internal_url():
    assert monitor.parse_google_news_batch_resolution(rpc_response("https://news.google.com/articles/x")) is None
    assert monitor.parse_google_news_batch_resolution(rpc_response("http://127.0.0.1/private")) is None


def test_build_google_news_candidate_uses_shared_repaired_fetcher(monkeypatch):
    resolved_url = "https://discovery-publisher.example/story"
    get, _, _, _ = current_shape_get(
        resolved_url,
        publisher_body="<article>У Полтаві пролунав вибух під час атаки БпЛА.</article>",
    )
    post, _ = current_shape_post(resolved_url)
    monkeypatch.setattr(monitor.requests, "get", get)
    monkeypatch.setattr(monitor.requests, "post", post)

    row, fetched, rescued = monitor.build_google_news_candidate(
        "poltava",
        "Нічні новини",
        "Оновлення ситуації.",
        GOOGLE_URL,
        "Discovery Publisher",
        "https://discovery-publisher.example",
        "2026-10-04T18:50:00Z",
        fulltext_fetcher=monitor.fetch_publisher_fulltext,
    )

    assert fetched is True
    assert rescued is True
    assert row is not None
    assert row["discovery_basis"] == "publisher_fulltext"
    assert row["resolved_url"] == resolved_url
    assert "вибух" in row["matched_text_excerpt"].casefold()


def test_publisher_fulltext_existing_semantics_equal_injected_fetcher(monkeypatch):
    resolved_url = "https://semantic-publisher.example/story"
    body = "У Полтаві пролунав вибух під час атаки БпЛА."
    expected, expected_fetched, expected_rescued = monitor.build_google_news_candidate(
        "poltava",
        "Нічні новини",
        "Оновлення ситуації.",
        GOOGLE_URL,
        "Semantic Publisher",
        "https://semantic-publisher.example",
        "2026-10-04T18:50:00Z",
        fulltext_fetcher=lambda url: (body, resolved_url),
    )

    get, _, _, _ = current_shape_get(
        resolved_url,
        publisher_body=f"<article>{body}</article>",
    )
    post, _ = current_shape_post(resolved_url)
    monkeypatch.setattr(monitor.requests, "get", get)
    monkeypatch.setattr(monitor.requests, "post", post)

    actual, actual_fetched, actual_rescued = monitor.build_google_news_candidate(
        "poltava",
        "Нічні новини",
        "Оновлення ситуації.",
        GOOGLE_URL,
        "Semantic Publisher",
        "https://semantic-publisher.example",
        "2026-10-04T18:50:00Z",
        fulltext_fetcher=monitor.fetch_publisher_fulltext,
    )

    assert (actual_fetched, actual_rescued) == (expected_fetched, expected_rescued)
    assert actual == expected
