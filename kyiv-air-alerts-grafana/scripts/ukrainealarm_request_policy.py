"""Bounded UkraineAlarm client with same-run request coordination (no live proof required)."""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Callable

import requests

UTC = timezone.utc
MIN_INTERVAL_SECONDS = 70.0
MAX_401_RETRIES = 2
MAX_429_RETRIES = 2
MAX_CONNECTION_RETRIES = 1
MAX_ATTEMPTS_PER_REQUEST = 5
MAX_TOTAL_API_SECONDS = 45 * 60
HTTP_TIMEOUT_SECONDS = 60
HANDOFF_MAX_AGE_SECONDS = 60 * 60
WAIT_PATTERN = re.compile(r"\bplease\s+wait\s+(\d+(?:\.\d+)?)\s+seconds?\b", re.IGNORECASE)


class UkraineAlarmAuthenticationError(RuntimeError):
    """401 persisted after the existing bounded three-attempt policy."""


class UkraineAlarmRateLimitExhausted(RuntimeError):
    """429 continued through the bounded retry budget."""


class UkraineAlarmRetryBudgetExceeded(RuntimeError):
    """Remaining workflow time is insufficient for another safe request."""


def capture_handoff_age(path: str, *, now_utc: datetime) -> float | None:
    """Age of the last authenticated capture request, never of unrelated sources.

    A missing, old, malformed or future diagnostic returns None: the caller then
    conservatively waits a *full* minimum interval before its first request.
    """
    try:
        diagnostic = json.loads(Path(path).read_text(encoding="utf-8"))
        if diagnostic.get("capture_enabled") is not True:
            return None
        source = diagnostic["sources"]["ukrainealarm"]
        if source.get("logical_acquisition_count") != 1:
            return None
        stamped = str(source["request_finished_at"])
        request_at = datetime.fromisoformat(stamped.replace("Z", "+00:00"))
        if request_at.tzinfo is None:
            return None
        elapsed = (now_utc.astimezone(UTC) - request_at.astimezone(UTC)).total_seconds()
        if 0 <= elapsed <= HANDOFF_MAX_AGE_SECONDS:
            return elapsed
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        pass
    return None


def retry_after_seconds(value: str | None, *, now_utc: datetime) -> float | None:
    if value is None or not str(value).strip():
        return None
    raw = str(value).strip()
    if re.fullmatch(r"\d+", raw):
        return float(int(raw))
    try:
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            return None
        return max(0.0, (dt.astimezone(UTC) - now_utc.astimezone(UTC)).total_seconds())
    except (ValueError, TypeError, OverflowError, IndexError):
        return None


def response_wait_seconds(response: requests.Response, *, now_utc: datetime) -> float:
    header = retry_after_seconds(response.headers.get("Retry-After"), now_utc=now_utc)
    if header is not None:
        return header
    # Only parse the wait number; do not log unsanitized publisher response text.
    match = WAIT_PATTERN.search(response.text[:2048])
    if match is not None:
        try:
            seconds = float(match.group(1))
            if 0 <= seconds < float("inf"):
                return seconds
        except ValueError:
            pass
    return MIN_INTERVAL_SECONDS


class UkraineAlarmClient:
    def __init__(
        self,
        token: str,
        *,
        capture_diagnostic_path: str | None = None,
        min_interval: float = MIN_INTERVAL_SECONDS,
        session: requests.Session | None = None,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        utcnow: Callable[[], datetime] | None = None,
        total_api_seconds: float = MAX_TOTAL_API_SECONDS,
    ) -> None:
        self.token = token
        self.session = session if session is not None else requests.Session()
        self.monotonic = monotonic
        self.sleep = sleep
        self.utcnow = utcnow if utcnow is not None else lambda: datetime.now(UTC)
        self.min_interval = max(MIN_INTERVAL_SECONDS, float(min_interval))
        self.started_at = self.monotonic()
        self.deadline = self.started_at + min(MAX_TOTAL_API_SECONDS, float(total_api_seconds))
        self.last_request_at: float | None = None
        self.cooldown_until: float | None = None
        if capture_diagnostic_path:
            age = capture_handoff_age(capture_diagnostic_path, now_utc=self.utcnow())
            # A missing handoff is never permission to issue an immediate request.
            self.last_request_at = self.monotonic() - age if age is not None else self.monotonic()
            print(
                "UkraineAlarm same-run capture handoff: "
                + ("timestamp verified" if age is not None else "conservative full guard"),
                flush=True,
            )

    def _ensure_budget(self, needed: float, context: str) -> None:
        if self.monotonic() + needed > self.deadline:
            raise UkraineAlarmRetryBudgetExceeded(
                f"{context}: global 45-minute UkraineAlarm request budget exhausted"
            )

    def _wait_for_slot(self, context: str) -> None:
        target = self.monotonic()
        if self.last_request_at is not None:
            target = max(target, self.last_request_at + self.min_interval)
        if self.cooldown_until is not None:
            target = max(target, self.cooldown_until)
        wait = max(0.0, target - self.monotonic())
        self._ensure_budget(wait + HTTP_TIMEOUT_SECONDS, context)
        if wait:
            print(f"UkraineAlarm rate-limit guard: sleeping {wait:.1f}s", flush=True)
            self.sleep(wait)

    def get(self, url: str, *, params: dict | None = None, context: str) -> requests.Response:
        failures_401 = 0
        failures_429 = 0
        failures_transport = 0
        for attempt in range(1, MAX_ATTEMPTS_PER_REQUEST + 1):
            self._wait_for_slot(context)
            try:
                response = self.session.get(
                    url,
                    headers={
                        "Accept": "application/json",
                        "Authorization": self.token,
                        "User-Agent": "kyiv-air-alerts-grafana/verified-multicity-bridge",
                    },
                    params=params,
                    timeout=HTTP_TIMEOUT_SECONDS,
                )
            except (requests.Timeout, requests.ConnectionError) as exc:
                failures_transport += 1
                if failures_transport > MAX_CONNECTION_RETRIES or attempt == MAX_ATTEMPTS_PER_REQUEST:
                    raise RuntimeError(
                        f"{context}: {type(exc).__name__} after {attempt} attempts"
                    ) from None
                print(f"{context}: transient {type(exc).__name__}; bounded retry", flush=True)
                continue
            except requests.RequestException as exc:
                raise RuntimeError(f"{context}: non-retryable {type(exc).__name__}") from None
            finally:
                # Includes a timeout or a disconnected request whose server-side
                # processing status is unknown. Never accelerate the next attempt.
                self.last_request_at = self.monotonic()

            if response.status_code == 401:
                failures_401 += 1
                if failures_401 > MAX_401_RETRIES or attempt == MAX_ATTEMPTS_PER_REQUEST:
                    raise UkraineAlarmAuthenticationError(
                        f"{context}: HTTP 401 after {attempt} attempts"
                    )
                print(f"{context}: HTTP 401; retry after guard", flush=True)
                continue

            if response.status_code == 429:
                failures_429 += 1
                if failures_429 > MAX_429_RETRIES or attempt == MAX_ATTEMPTS_PER_REQUEST:
                    raise UkraineAlarmRateLimitExhausted(
                        f"{context}: HTTP 429 after {attempt} attempts; fail closed"
                    )
                wait = response_wait_seconds(response, now_utc=self.utcnow())
                self.cooldown_until = max(
                    self.cooldown_until or 0.0, self.last_request_at + wait
                )
                print(
                    f"{context}: HTTP 429; bounded retry after provider/guard delay",
                    flush=True,
                )
                continue

            if not response.ok:
                # Do not echo arbitrary HTTP bodies: they can contain credentials.
                raise RuntimeError(f"{context}: HTTP {response.status_code}; no retry")
            return response

        raise UkraineAlarmRetryBudgetExceeded(
            f"{context}: maximum request attempt count reached; fail closed"
        )
