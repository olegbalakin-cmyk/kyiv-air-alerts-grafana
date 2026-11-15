#!/usr/bin/env python3
"""Shared fail-closed single-use owner GO, staged for controlled GitHub Actions.

No network requests are made by importing this module. Every network-capable
runner must explicitly claim before a GET; older branches do not inherit it.
"""
from __future__ import annotations
import hashlib
import copy
import ipaddress
import json
import re
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

LEDGER_PREFIX = "refs/tags/casualty-owner-go-consumed/"
FIELDS = {"owner_go_id", "approved_head", "allowed_urls", "rss_get_budget",
          "article_get_budget", "allowed_methods", "expires_at"}
KINDS = {"rss", "article"}

class GoBlocked(RuntimeError):
    pass

def canonical_digest(grant: dict) -> str:
    data = json.dumps(grant, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")
    return hashlib.sha256(data).hexdigest()

def safe_url(value: str) -> bool:
    if not isinstance(value, str) or not 0 < len(value) <= 2048:
        return False
    if re.search(r"[\x00-\x20\x7f\\]", value):
        return False
    try:
        p = urlsplit(value)
        host = (p.hostname or "").lower()
        if (p.scheme != "https" or not host or p.username is not None or
            p.password is not None or p.port not in (None,443) or p.fragment or
            p.netloc.lower() not in (host, host + ":443")):
            return False
        try:
            ipaddress.ip_address(host)
        except ValueError:
            return True
        return False  # No literal IP target in any GO.
    except ValueError:
        return False

def validate_grant(grant: dict, *, approved_digest: str, head: str,
                   now: datetime | None = None) -> None:
    if not isinstance(grant, dict) or set(grant) != FIELDS:
        raise GoBlocked("GRANT_SCHEMA_MISMATCH")
    if (not re.fullmatch(r"[a-f0-9]{64}", approved_digest or "") or
        canonical_digest(grant) != approved_digest):
        raise GoBlocked("OWNER_APPROVAL_DIGEST_MISMATCH")
    if (not isinstance(grant["owner_go_id"], str) or
        not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{5,79}", grant["owner_go_id"])):
        raise GoBlocked("INVALID_GO_ID")
    if (not re.fullmatch(r"[a-f0-9]{40}", head or "") or
        grant["approved_head"] != head):
        raise GoBlocked("APPROVED_HEAD_MISMATCH")
    if grant["allowed_methods"] != ["GET"]:
        raise GoBlocked("METHOD_NOT_ALLOWED")
    allowed = grant["allowed_urls"]
    if not isinstance(allowed, dict) or set(allowed) != KINDS:
        raise GoBlocked("URL_SCOPE_MISMATCH")
    for kind, key, ceiling in (("rss","rss_get_budget",23),
                               ("article","article_get_budget",10)):
        urls, budget = allowed[kind], grant[key]
        if (type(budget) is not int or not 0 <= budget <= ceiling or
            not isinstance(urls,list) or any(not safe_url(u) for u in urls) or
            len(set(urls)) != len(urls) or len(urls) > budget):
            raise GoBlocked("INVALID_URL_OR_BUDGET")
    if not allowed["rss"] and not allowed["article"]:
        raise GoBlocked("EMPTY_NETWORK_GRANT")
    try:
        expiry = datetime.fromisoformat(grant["expires_at"].replace("Z","+00:00"))
        if expiry.tzinfo is None:
            raise ValueError("timezone required")
    except (ValueError, TypeError, AttributeError) as exc:
        raise GoBlocked("BAD_EXPIRY") from exc
    at = now or datetime.now(timezone.utc)
    if at.tzinfo is None or at.astimezone(timezone.utc) >= expiry.astimezone(timezone.utc):
        raise GoBlocked("GO_EXPIRED")

def _post_create_ref(ref: str, sha: str, *, repo: str, token: str):
    if not token or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo or ""):
        raise GoBlocked("GH_LEDGER_NOT_CONFIGURED")
    req = Request("https://api.github.com/repos/" + repo + "/git/refs",
                  method="POST", data=json.dumps({"ref":ref,"sha":sha}).encode(),
                  headers={"Authorization":"Bearer "+token,
                           "Accept":"application/vnd.github+json",
                           "X-GitHub-Api-Version":"2022-11-28",
                           "User-Agent":"casualty-go-single-use-v1"})
    try:
        with urlopen(req,timeout=10) as resp:
            if resp.status != 201:
                raise GoBlocked("REF_CREATE_UNEXPECTED_STATUS")
    except HTTPError as exc:
        raise GoBlocked("REF_CREATE_DENIED_OR_ALREADY_SPENT") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise GoBlocked("REF_CREATE_UNCERTAIN_FAIL_CLOSED") from exc

def claim_grant(grant: dict, *, approved_digest: str, head: str,
                repo: str, token: str, create_ref=None,
                now: datetime | None = None):
    validate_grant(grant,approved_digest=approved_digest,head=head,now=now)
    ref = LEDGER_PREFIX + grant["owner_go_id"]
    # The POST CREATE, not a read/check or Actions concurrency, is atomic.
    try:
        if create_ref is None:
            _post_create_ref(ref,head,repo=repo,token=token)
        elif create_ref(ref,head) is not True:
            raise GoBlocked("REF_CREATE_NOT_CONFIRMED")
    except GoBlocked:
        raise
    except Exception as exc:
        raise GoBlocked("REF_CREATE_UNCERTAIN_FAIL_CLOSED") from exc
    return ClaimedGo(grant,ref)

class ClaimedGo:
    def __init__(self,grant,ref):
        self.grant,self.spent_ref=copy.deepcopy(grant),ref
        self.attempts={"rss":0,"article":0}
        self.seen_urls={"rss":set(),"article":set()}
    def authorize_get(self,kind,url,*,method="GET"):
        if kind not in KINDS or method != "GET":
            raise GoBlocked("REQUEST_TYPE_OR_METHOD_BLOCKED")
        if url not in self.grant["allowed_urls"][kind]:
            raise GoBlocked("URL_NOT_APPROVED")
        if url in self.seen_urls[kind]:
            raise GoBlocked("URL_ALREADY_ATTEMPTED")
        if self.attempts[kind]>=self.grant[kind+"_get_budget"]:
            raise GoBlocked("GET_BUDGET_SPENT")
        self.attempts[kind]+=1  # Consume before the attempt, even if it fails.
        self.seen_urls[kind].add(url)

def lookup_spent_ref(*,repo,token,owner_go_id):
    # Readback only for proof; NEVER a check-before-create lock.
    url=("https://api.github.com/repos/"+repo+"/git/ref/tags/"+
         quote("casualty-owner-go-consumed/"+owner_go_id,safe="/"))
    req=Request(url,headers={"Authorization":"Bearer "+token,
                             "Accept":"application/vnd.github+json",
                             "User-Agent":"casualty-go-ledger-readback"})
    try:
        with urlopen(req,timeout=10) as r:
            return json.load(r).get("object",{}).get("sha")
    except HTTPError as exc:
        if exc.code == 404:
            return None
        raise GoBlocked("LEDGER_READBACK_ERROR") from exc
    except (URLError,TimeoutError,OSError) as exc:
        raise GoBlocked("LEDGER_READBACK_ERROR") from exc
