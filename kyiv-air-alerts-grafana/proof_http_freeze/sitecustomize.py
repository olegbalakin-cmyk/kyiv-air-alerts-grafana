"""Proof-only HTTP capture/replay shim loaded through PYTHONPATH."""
from __future__ import annotations

import base64
import json
import os
import threading
from pathlib import Path

MODE = os.environ.get("PROOF_HTTP_MODE", "").strip().lower()
FIXTURE = Path(os.environ.get("PROOF_HTTP_FIXTURE", "")) if os.environ.get("PROOF_HTTP_FIXTURE") else None
_LOCK = threading.Lock()


def _load():
    if not FIXTURE or not FIXTURE.exists():
        return {}
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _save(data):
    if not FIXTURE:
        return
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _key(method, url):
    return f"{method.upper()} {url}"


def _record(key, status, headers, body, url):
    with _LOCK:
        data = _load()
        if key not in data:
            data[key] = {
                "status": int(status),
                "content_type": str(dict(headers).get("Content-Type") or dict(headers).get("content-type") or ""),
                "body_b64": base64.b64encode(body).decode("ascii"),
                "url": url,
            }
            _save(data)


def _lookup(key):
    data = _load()
    if key not in data:
        raise RuntimeError(f"proof HTTP replay miss: {key}")
    return data[key]


if MODE in {"capture", "replay"}:
    try:
        import requests
        from requests import Response
        from requests.sessions import Session

        _orig_request = Session.request

        def _requests_request(self, method, url, **kwargs):
            req = requests.Request(method=method.upper(), url=url, params=kwargs.get("params"), data=kwargs.get("data"), json=kwargs.get("json"))
            prepared = req.prepare()
            full_url = prepared.url
            key = _key(method, full_url)
            if MODE == "capture":
                response = _orig_request(self, method, url, **kwargs)
                _record(key, response.status_code, response.headers, response.content, response.url or full_url)
                return response
            item = _lookup(key)
            response = Response()
            response.status_code = int(item["status"])
            response._content = base64.b64decode(item["body_b64"])
            if item.get("content_type"):
                response.headers["Content-Type"] = item["content_type"]
            response.url = item.get("url") or full_url
            response.request = prepared
            response.encoding = requests.utils.get_encoding_from_headers(response.headers)
            return response

        Session.request = _requests_request
    except Exception:
        pass

    try:
        import urllib.request

        _orig_urlopen = urllib.request.urlopen

        class _ReplayURLResponse:
            def __init__(self, item):
                self.status = int(item["status"])
                self.headers = {"Content-Type": item.get("content_type", "")}
                self._body = base64.b64decode(item["body_b64"])
            def read(self, *args, **kwargs):
                return self._body
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc, tb):
                return False

        def _urllib_urlopen(req, *args, **kwargs):
            if isinstance(req, urllib.request.Request):
                url = req.full_url
                method = req.get_method()
            else:
                url = str(req)
                method = "GET"
            key = _key(method, url)
            if MODE == "capture":
                response = _orig_urlopen(req, *args, **kwargs)
                body = response.read()
                status = getattr(response, "status", 200)
                headers = getattr(response, "headers", {})
                _record(key, status, headers, body, url)
                return _ReplayURLResponse({"status": status, "content_type": str(dict(headers).get("Content-Type") or ""), "body_b64": base64.b64encode(body).decode("ascii")})
            return _ReplayURLResponse(_lookup(key))

        urllib.request.urlopen = _urllib_urlopen
    except Exception:
        pass

_FIXED_NOW = os.environ.get("PROOF_FIXED_NOW", "").strip()
if _FIXED_NOW:
    try:
        import datetime as _dt
        _base_datetime = _dt.datetime
        _fixed = _base_datetime.fromisoformat(_FIXED_NOW.replace("Z", "+00:00"))
        class _FrozenDateTime(_base_datetime):
            @classmethod
            def now(cls, tz=None):
                value = _fixed
                if tz is None:
                    return value.replace(tzinfo=None) if value.tzinfo else value
                if value.tzinfo is None:
                    value = value.replace(tzinfo=_dt.timezone.utc)
                return value.astimezone(tz)
            @classmethod
            def utcnow(cls):
                value = _fixed
                if value.tzinfo is not None:
                    value = value.astimezone(_dt.timezone.utc).replace(tzinfo=None)
                return value
        _dt.datetime = _FrozenDateTime
    except Exception:
        pass
