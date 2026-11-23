#!/usr/bin/env python3
"""Read-only, fail-closed, owner-gated monthly-source capture.

No source GET when imported, tested, validated or invoked without --capture.
Source bodies preserved only as encrypted private evidence. No plaintext HTML/PDF in reports or public artifacts. Does not write or promote casualty/site data.
"""
from __future__ import annotations

import argparse
import hashlib
import http.client
import ipaddress
import json
import os
import queue
import re
import socket
import ssl
import subprocess
import sys
import threading
import time
import zlib
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from private_body_archive import PrivateBodyArchive, ArchiveError

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "approved_sources_manifest.json"
RESEARCH_REF = "refs/heads/research-casualty-monthly-collector-2026-11-22"
REPO = "olegbalakin-cmyk/kyiv-air-alerts-grafana"
ACTOR = "olegbalakin-cmyk"
MAX_GETS = 50
MAX_BYTES = 2 * 1024 * 1024
CONNECT_TIMEOUT = 8.0
TOTAL_TIMEOUT = 20.0
TAG_PREFIX = "refs/tags/casualty-monthly-go-consumed/"
UTC = timezone.utc
GRANT_KEYS = {
    "owner_go_id", "approved_head", "source_manifest_sha256",
    "get_budget", "allowed_methods", "expires_at"
}


class Blocked(RuntimeError):
    """Network disabled or hard safety condition not met."""


def sha256(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def canonical_sha256(obj: object) -> str:
    raw = json.dumps(obj, sort_keys=True, ensure_ascii=False,
                     separators=(",", ":"), allow_nan=False).encode("utf-8")
    return sha256(raw)


def time_utc(value: str) -> datetime:
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError, AttributeError) as exc:
        raise Blocked("INVALID_EXPIRY") from exc
    if stamp.tzinfo is None:
        raise Blocked("EXPIRY_NEEDS_TIMEZONE")
    return stamp.astimezone(UTC)


def safe_https_url(url: str, allowed_hosts: set[str]) -> tuple[str, str]:
    if (not isinstance(url, str) or not url or len(url) > 2048 or
            re.search(r"[\x00-\x20\x7f\\]", url)):
        raise Blocked("INVALID_URL")
    try:
        p = urlsplit(url)
        host = (p.hostname or "").lower()
        port = p.port
    except ValueError as exc:
        raise Blocked("INVALID_URL") from exc
    if (p.scheme != "https" or host not in allowed_hosts or
            p.username is not None or p.password is not None or
            p.fragment or port not in (None, 443) or
            p.netloc.lower() not in (host, host + ":443") or
            not re.fullmatch(r"[a-z0-9.-]+", host) or
            host.startswith(".") or host.endswith(".")):
        raise Blocked("URL_OUTSIDE_EXACT_HTTPS_ALLOWLIST")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise Blocked("IP_LITERAL_BLOCKED")
    path = (p.path or "/") + (("?" + p.query) if p.query else "")
    return host, path


def load_manifest(path: Path = MANIFEST) -> tuple[dict, bytes]:
    raw = path.read_bytes()
    document = json.loads(raw)
    if (set(document) != {
            "go_id", "month", "prior_month", "owner_go", "get_budget",
            "promote", "site_prod_write", "allowed_hosts", "cities", "targets"
    } or document["get_budget"] != MAX_GETS or
            document["promote"] is not False or
            document["site_prod_write"] is not False):
        raise Blocked("MANIFEST_SCHEMA_OR_SAFETY_MISMATCH")
    hosts = document["allowed_hosts"]
    if (not isinstance(hosts, list) or not hosts or
            len(set(hosts)) != len(hosts) or
            any(not re.fullmatch(r"[a-z0-9.-]+", h) for h in hosts)):
        raise Blocked("INVALID_ALLOWED_HOSTS")
    if (document["month"] != "2026-10" or
            document["prior_month"] != "2026-09" or
            len(document["cities"]) != 23 or
            len(set(document["cities"])) != 23):
        raise Blocked("MONTH_OR_CITY_COVERAGE_DRIFT")
    targets = document["targets"]
    if (not isinstance(targets, list) or not 1 <= len(targets) <= MAX_GETS):
        raise Blocked("INVALID_TARGET_COUNT")
    urls = set()
    for index, target in enumerate(targets, 1):
        if (set(target) != {"id", "city_slug", "label", "scope", "url"} or
                target["id"] != f"s{index:02d}" or
                target["city_slug"] not in document["cities"] or
                not isinstance(target["label"], str) or
                not isinstance(target["scope"], str) or
                target["url"] in urls):
            raise Blocked("TARGET_SCHEMA_OR_DUPLICATE")
        safe_https_url(target["url"], set(hosts))
        urls.add(target["url"])
    return document, raw


def validate_environment(env: dict) -> str:
    if (env.get("GITHUB_EVENT_NAME") != "workflow_dispatch" or
            env.get("GITHUB_REF") != RESEARCH_REF or
            env.get("GITHUB_REPOSITORY") != REPO or
            env.get("GITHUB_ACTOR") != ACTOR or
            env.get("GITHUB_TRIGGERING_ACTOR") != ACTOR or
            env.get("GITHUB_RUN_ATTEMPT") != "1" or
            env.get("CASUALTY_MONTHLY_GO") != "OWNER_APPROVED_ONE_SHOT"):
        raise Blocked("NOT_SINGLE_OWNER_MANUAL_DISPATCH")
    head = env.get("GITHUB_SHA", "")
    if not re.fullmatch(r"[a-f0-9]{40}", head):
        raise Blocked("INVALID_DISPATCH_HEAD")
    if env.get("CASUALTY_MONTHLY_APPROVED_HEAD") != head:
        raise Blocked("APPROVED_HEAD_MISMATCH")
    return head


def validate_grant(grant: dict, *, digest: str, head: str,
                   manifest: dict, manifest_bytes: bytes,
                   env: dict, now: datetime | None = None) -> None:
    if not isinstance(grant, dict) or set(grant) != GRANT_KEYS:
        raise Blocked("GRANT_SCHEMA_MISMATCH")
    if not re.fullmatch(r"[a-f0-9]{64}", digest or "") or canonical_sha256(grant) != digest:
        raise Blocked("OWNER_MANIFEST_DIGEST_MISMATCH")
    if (grant["approved_head"] != head or
            grant["approved_head"] != env.get("CASUALTY_MONTHLY_APPROVED_HEAD")):
        raise Blocked("GRANT_HEAD_MISMATCH")
    if (grant["owner_go_id"] != manifest["go_id"] or
            grant["owner_go_id"] != env.get("CASUALTY_MONTHLY_GO_ID") or
            not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{5,79}", grant["owner_go_id"])):
        raise Blocked("OWNER_GO_ID_MISMATCH")
    if grant["source_manifest_sha256"] != sha256(manifest_bytes):
        raise Blocked("SOURCE_MANIFEST_CHANGED")
    if (grant["allowed_methods"] != ["GET"] or
            type(grant["get_budget"]) is not int or
            grant["get_budget"] != len(manifest["targets"]) or
            grant["get_budget"] > MAX_GETS):
        raise Blocked("GET_SCOPE_OR_BUDGET_MISMATCH")
    current = now or datetime.now(UTC)
    expiry = time_utc(grant["expires_at"])
    if expiry <= current or expiry > current + timedelta(hours=24):
        raise Blocked("GRANT_EXPIRED_OR_TOO_LONG")
    if env.get("CASUALTY_MONTHLY_GO_DIGEST") != digest:
        raise Blocked("GRANT_DIGEST_INPUT_MISMATCH")


def claim_once(grant: dict, head: str, env: dict, create_ref=None) -> str:
    """Atomic GitHub tag creation BEFORE the first source GET (no read-first race)."""
    ref = TAG_PREFIX + grant["owner_go_id"]
    if create_ref is not None:
        try:
            result = create_ref(ref, head)
        except Exception as exc:
            raise Blocked("TAG_CLAIM_UNCERTAIN_FAIL_CLOSED") from exc
        if result is not True:
            raise Blocked("TAG_CLAIM_REJECTED")
        return ref
    token = env.get("GH_OWNER_LEDGER_TOKEN", "")
    if not token:
        raise Blocked("NO_GITHUB_TAG_TOKEN")
    payload = json.dumps({"ref": ref, "sha": head}).encode("utf-8")
    req = Request(
        "https://api.github.com/repos/" + REPO + "/git/refs",
        data=payload, method="POST",
        headers={
            "Authorization": "Bearer " + token,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
            "User-Agent": "casualty-monthly-one-shot",
        },
    )
    try:
        with urlopen(req, timeout=10) as response:
            if response.status != 201:
                raise Blocked("GITHUB_TAG_CREATE_NOT_201")
    except HTTPError as exc:
        raise Blocked("GITHUB_TAG_SPENT_OR_FORBIDDEN") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise Blocked("GITHUB_TAG_CLAIM_UNCERTAIN_FAIL_CLOSED") from exc
    return ref


def _public_addresses(host: str, deadline: float):
    result = queue.Queue(maxsize=1)
    def lookup() -> None:
        try:
            result.put((socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM), None))
        except Exception as exc:
            result.put((None, type(exc).__name__))
    threading.Thread(target=lookup, daemon=True).start()
    try:
        records, error = result.get(
            timeout=max(0.001, min(CONNECT_TIMEOUT, deadline - time.monotonic())))
    except queue.Empty as exc:
        raise Blocked("DNS_TIMEOUT") from exc
    if error or not records:
        raise Blocked("DNS_LOOKUP_FAILED")
    for family, _, _, _, addr in records:
        if family not in (socket.AF_INET, socket.AF_INET6):
            raise Blocked("UNEXPECTED_ADDRESS_FAMILY")
        ip = ipaddress.ip_address(addr[0])
        if not ip.is_global or (
            getattr(ip, "ipv4_mapped", None) and not ip.ipv4_mapped.is_global
        ):
            raise Blocked("NONPUBLIC_IP_IN_DNS")
    return records


class PublicPinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, host: str, deadline: float):
        super().__init__(host, port=443, timeout=CONNECT_TIMEOUT,
                         context=ssl.create_default_context())
        self.deadline = deadline

    def connect(self):
        addresses = _public_addresses(self.host, self.deadline)
        errors = []
        for family, typ, proto, _, sockaddr in addresses:
            remaining = self.deadline - time.monotonic()
            if remaining <= 0:
                raise Blocked("TOTAL_TIMEOUT")
            sock = socket.socket(family, typ, proto)
            try:
                sock.settimeout(min(CONNECT_TIMEOUT, remaining))
                sock.connect(sockaddr)
                remaining = self.deadline - time.monotonic()
                if remaining <= 0:
                    raise Blocked("TOTAL_TIMEOUT")
                sock.settimeout(min(CONNECT_TIMEOUT, remaining))
                self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
                return
            except (OSError, ssl.SSLError) as exc:
                errors.append(type(exc).__name__)
                sock.close()
        raise Blocked("PUBLIC_TLS_CONNECT_FAILED:" + ",".join(errors[:3]))


def _read_cap(response, conn, deadline: float) -> bytes:
    content_length = response.getheader("Content-Length", "")
    if content_length.isdecimal() and int(content_length) > MAX_BYTES:
        raise Blocked("RAW_BODY_TOO_LARGE")
    raw = bytearray()
    while True:
        rem = deadline - time.monotonic()
        if rem <= 0:
            raise Blocked("TOTAL_TIMEOUT")
        if conn.sock is not None:
            conn.sock.settimeout(min(CONNECT_TIMEOUT, rem))
        chunk = response.read(min(65536, MAX_BYTES + 1 - len(raw)))
        if not chunk:
            break
        raw.extend(chunk)
        if len(raw) > MAX_BYTES:
            raise Blocked("RAW_BODY_TOO_LARGE")
    return bytes(raw)


def _decode_cap(raw: bytes, coding: str) -> bytes:
    coding = coding.strip().lower()
    if coding in ("", "identity"):
        return raw
    if coding not in ("gzip", "deflate"):
        raise Blocked("UNSUPPORTED_ENCODING")
    d = zlib.decompressobj(16 + zlib.MAX_WBITS if coding == "gzip" else zlib.MAX_WBITS)
    try:
        out = d.decompress(raw, MAX_BYTES + 1)
        if len(out) > MAX_BYTES or d.unconsumed_tail:
            raise Blocked("DECOMPRESSED_BODY_TOO_LARGE")
        out += d.flush(MAX_BYTES + 1 - len(out))
    except zlib.error as exc:
        raise Blocked("INVALID_COMPRESSION") from exc
    if len(out) > MAX_BYTES or not d.eof or d.unused_data:
        raise Blocked("DECOMPRESSED_BODY_TOO_LARGE")
    return out


def fetch_once(url: str, allowed_hosts: set[str]) -> dict:
    """Only invoked after an atomic spent-tag; no redirects or retries."""
    host, path = safe_https_url(url, allowed_hosts)
    deadline = time.monotonic() + TOTAL_TIMEOUT
    conn = PublicPinnedHTTPS(host, deadline)
    try:
        conn.request("GET", path, headers={
            "User-Agent": "air-alerts-casualty-monthly-research/1.0",
            "Accept": "text/html,application/xhtml+xml,application/pdf",
            "Accept-Encoding": "gzip,deflate,identity",
            "Connection": "close",
        })
        rem = deadline - time.monotonic()
        if rem <= 0:
            raise Blocked("TOTAL_TIMEOUT")
        if conn.sock is not None:
            conn.sock.settimeout(min(CONNECT_TIMEOUT, rem))
        response = conn.getresponse()
        status = int(response.status)
        if 300 <= status < 400:
            raise Blocked("REDIRECT_BLOCKED_STATUS_" + str(status))
        if status != 200:
            raise Blocked("HTTP_STATUS_" + str(status))
        content_type = response.getheader("Content-Type", "").split(";")[0].strip().lower()
        if content_type not in {"text/html", "application/xhtml+xml", "application/pdf"}:
            raise Blocked("UNSUPPORTED_CONTENT_TYPE")
        raw = _read_cap(response, conn, deadline)
        decoded = _decode_cap(raw, response.getheader("Content-Encoding", ""))
        return {
            "http_status": status, "content_type": content_type,
            "raw_bytes": len(raw), "decoded_bytes": len(decoded),
            "raw_sha256": sha256(raw), "decoded_sha256": sha256(decoded),
            "_raw": raw, "_decoded": decoded,
        }
    finally:
        conn.close()


class ShortEvidence(HTMLParser):
    OMIT = {"script", "style", "nav", "footer", "aside", "form", "iframe",
            "noscript", "template", "svg"}
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.title = []
        self.article = []
        self.main = []
        self.body = []
    def handle_starttag(self, tag, attrs):
        self.stack.append(tag)
    def handle_startendtag(self, tag, attrs):
        pass
    def handle_endtag(self, tag):
        if tag in self.stack:
            for i in range(len(self.stack) - 1, -1, -1):
                if self.stack[i] == tag:
                    del self.stack[i:]
                    break
    def handle_data(self, data):
        if any(tag in self.stack for tag in self.OMIT):
            return
        text = " ".join(data.split())
        if not text:
            return
        if "title" in self.stack:
            self.title.append(text)
        if "article" in self.stack:
            self.article.append(text)
        if "main" in self.stack:
            self.main.append(text)
        if "body" in self.stack:
            self.body.append(text)


def brief_evidence(document: bytes, content_type: str) -> dict:
    if content_type == "application/pdf":
        return {"title": None, "context": None, "body_chars": None,
                "review_note": "PDF_CAPTURED_HASH_ONLY"}
    parser = ShortEvidence()
    parser.feed(document.decode("utf-8", errors="replace"))
    parser.close()
    body = " ".join(parser.article or parser.main or parser.body)
    title = " ".join(parser.title)
    match = re.search(
        r".{0,65}(?:загибл|загинул|померл|вбит|fatalit|killed|deaths).{0,85}",
        body, re.IGNORECASE)
    # Tiny attributed context for review only. No full article in artifacts.
    snippet = " ".join(match.group(0).split())[:150] if match else None
    return {
        "title": title[:150] if title else None,
        "context": snippet, "body_chars": len(body),
        "review_note": "NEEDS_HUMAN_SCOPE_AND_INCIDENT_RECONCILIATION",
    }


def write_proof(directory: Path, report: dict) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    blob = (json.dumps(report, sort_keys=True, ensure_ascii=False,
                       indent=2) + "\n").encode("utf-8")
    proof = directory / "capture_report.json"
    proof.write_bytes(blob)
    digest = {"capture_report.json": sha256(blob)}
    (directory / "sha256_manifest.json").write_text(
        json.dumps(digest, sort_keys=True) + "\n", encoding="utf-8")


def capture(env: dict, *, manifest_path: Path = MANIFEST,
            transport=fetch_once, tag_claim=None,
            now: datetime | None = None) -> dict:
    manifest, raw = load_manifest(manifest_path)
    head = validate_environment(env)
    try:
        actual_head = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True,
            check=True, timeout=5).stdout.strip()
    except (OSError, subprocess.SubprocessError) as exc:
        raise Blocked("LOCAL_GIT_HEAD_UNAVAILABLE") from exc
    if actual_head != head:
        raise Blocked("CHECKOUT_SHA_MISMATCH")
    try:
        grant = json.loads(env.get("CASUALTY_MONTHLY_GRANT_JSON", ""))
    except (ValueError, TypeError) as exc:
        raise Blocked("INVALID_GRANT_JSON") from exc
    digest = env.get("CASUALTY_MONTHLY_GO_DIGEST", "")
    validate_grant(grant, digest=digest, head=head, manifest=manifest,
                   manifest_bytes=raw, env=env, now=now)
    out_dir = Path(env.get("CASUALTY_MONTHLY_OUTPUT", "/tmp/casualty-monthly-oneshot"))
    if not str(out_dir.resolve()).startswith("/tmp/casualty-monthly-"):
        raise Blocked("OUTPUT_MUST_BE_ISOLATED_TMP")
    # Archive MUST be ready before the one-shot GO tag and before publisher GET.
    try:
        archive = PrivateBodyArchive(
            out_dir / "private-archive",
            env.get("CASUALTY_MONTHLY_ARCHIVE_KEY_B64", ""),
            checkout_root=HERE.parents[1],
        )
    except ArchiveError as exc:
        raise Blocked("ENCRYPTED_ARCHIVE_NOT_READY:" + str(exc)) from exc
    spent_ref = claim_once(grant, head, env, create_ref=tag_claim)
    report = {
        "kind": "CASUALTY_MONTHLY_23CITY_REVIEW_ONLY",
        "go_id": grant["owner_go_id"], "grant_sha256": digest,
        "head": head, "source_manifest_sha256": sha256(raw),
        "spent_tag": spent_ref, "attempted_gets": 0,
        "budget": grant["get_budget"], "target_count": len(manifest["targets"]),
        "promotion": "OFF", "automatic_credits": 0,
        "rss_gets": 0, "production_writes": 0, "wip_writes": 0,
        "source_full_text_saved": False, "results": [],
        "finished": False,
    }
    attempted = set()
    try:
        for target in manifest["targets"]:
            url = target["url"]
            if url in attempted or report["attempted_gets"] >= grant["get_budget"]:
                raise Blocked("DUPLICATE_URL_OR_BUDGET_EXCEEDED")
            attempted.add(url)
            report["attempted_gets"] += 1  # Count before transport.
            item = {"id": target["id"], "city_slug": target["city_slug"],
                    "scope": target["scope"], "url": url,
                    "status": "PENDING", "deaths_auto_credit": 0}
            try:
                reply = transport(url, set(manifest["allowed_hosts"]))
                decoded = reply.pop("_decoded")
                raw_body = reply.pop("_raw")
                if (reply.get("raw_sha256") != sha256(raw_body) or
                        reply.get("decoded_sha256") != sha256(decoded)):
                    raise Blocked("TRANSPORT_DIGEST_MISMATCH")
                receipt = archive.store(
                    target_id=target["id"], url=url,
                    content_type=reply["content_type"],
                    raw=raw_body, decoded=decoded,
                    captured_at=datetime.now(UTC).isoformat(),
                )
                item.update(reply)
                item.update(brief_evidence(decoded, reply["content_type"]))
                item["archive_receipt"] = receipt
                item["status"] = "HTTP200_REVIEW_ONLY"
            except ArchiveError as exc:
                # Archive failure is fatal: NEVER proceed to another publisher GET
                # when a successful body could be discarded unsealed.
                item["status"] = "ARCHIVE_FAILED_STOP"
                item["reason"] = "PRIVATE_ARCHIVE_FAILURE"
                report["results"].append(item)
                raise Blocked("PRIVATE_ARCHIVE_FAILURE_STOP") from exc
            except Exception as exc:
                # Never retry or add error text that may disclose internals.
                item["status"] = "BLOCKED_OR_FAILED"
                item["reason"] = (str(exc) if isinstance(exc, Blocked)
                                  else type(exc).__name__)[:120]
            report["results"].append(item)
    finally:
        report["finished"] = True
        report["successful_gets"] = sum(
            x["status"] == "HTTP200_REVIEW_ONLY" for x in report["results"])
        # The index contains URL/digests/lengths and ciphertext paths, no body.
        index_receipt = archive.write_index()
        report["encrypted_archive"] = {
            "format": "AES-256-GCM",
            "record_count": index_receipt["count"],
            "index_sha256": index_receipt["index_sha256"],
            "storage": "private-archive/",
            "key_in_artifact": False,
        }
        report["source_full_text_saved"] = index_receipt["count"] > 0
        write_proof(out_dir, report)
    return report


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--validate", action="store_true",
                    help="Validate pinned manifest without any publisher HTTP")
    ap.add_argument("--capture", action="store_true",
                    help="Only for owner manual Actions with spent GO tag")
    args = ap.parse_args()
    if args.validate and not args.capture:
        manifest, raw = load_manifest()
        print("MONTHLY_MANIFEST_VALIDATED_OFFLINE",
              len(manifest["targets"]), sha256(raw))
        return
    if not args.capture or args.validate:
        raise Blocked("DEFAULT_OFF: pass --validate or approved Actions --capture")
    output = capture(dict(os.environ))
    if output["attempted_gets"] > MAX_GETS or output["production_writes"]:
        raise Blocked("POST_CAPTURE_GUARD_FAIL")
    print("CASUALTY_MONTHLY_ONE_SHOT_REVIEW_ONLY",
          output["attempted_gets"], output["successful_gets"],
          output["source_manifest_sha256"])


if __name__ == "__main__":
    try:
        main()
    except Blocked as exc:
        print("CASUALTY_MONTHLY_FAIL_CLOSED", str(exc), file=sys.stderr)
        raise SystemExit(2)
