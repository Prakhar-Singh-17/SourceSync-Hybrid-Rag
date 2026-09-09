"""One retry policy, applied in one place.

Three cases, and telling them apart matters:

* **5xx** -- Gemini had a problem. The same request may succeed a moment later,
  so it is retried with a short exponential backoff.
* **429 for a per-minute rate limit** -- too many requests too quickly, which is
  easy to hit while embedding a repository. Waiting genuinely fixes it, so this
  is retried, but with a longer delay than a 5xx and honouring the wait Gemini
  asks for when it names one.
* **429 for a per-day quota** -- the free tier's daily request budget is spent.
  No amount of waiting inside this request will help, and each retry burns
  another unit of the budget to receive the same error, so this fails
  immediately.

The earlier version retried generation inside the answerer *and* retried the
whole pipeline inside the router, so one outage could trigger six generation
calls plus two full re-embeddings of the question.
"""

import asyncio
import logging
import re
from collections.abc import Awaitable, Callable
from typing import TypeVar

from google.genai import errors as genai_errors

logger = logging.getLogger(__name__)

T = TypeVar("T")

RETRYABLE_STATUS_CODES = frozenset({500, 502, 503, 504})
RATE_LIMIT_STATUS_CODE = 429
MAX_ATTEMPTS = 4
SERVER_ERROR_DELAYS = (1.0, 2.0, 4.0)
RATE_LIMIT_DELAYS = (5.0, 15.0, 30.0)
MAX_DELAY_SECONDS = 60.0

# Gemini reports the daily free-tier budget with a quota id naming the period.
_DAILY_QUOTA = re.compile(r"PerDay", re.IGNORECASE)
# ... and sometimes tells us exactly how long to wait.
_RETRY_DELAY = re.compile(r"retryDelay['\"]?:\s*['\"]?(\d+(?:\.\d+)?)s")


def _status_of(error: BaseException) -> int | None:
    if not isinstance(error, genai_errors.APIError):
        return None
    return getattr(error, "status_code", None) or getattr(error, "code", None)


def is_rate_limited(error: BaseException) -> bool:
    """True when Gemini refused because a quota or rate limit was exhausted."""
    return _status_of(error) == RATE_LIMIT_STATUS_CODE


def is_daily_quota_exhausted(error: BaseException) -> bool:
    """True for the free tier's per-day budget, which waiting cannot recover."""
    return is_rate_limited(error) and bool(_DAILY_QUOTA.search(str(error)))


def is_retryable(error: BaseException) -> bool:
    """True for server-side failures that could plausibly succeed on a retry."""
    return _status_of(error) in RETRYABLE_STATUS_CODES


def requested_delay(error: BaseException) -> float | None:
    match = _RETRY_DELAY.search(str(error))
    return float(match.group(1)) if match else None


async def with_retry(
    operation: Callable[[], Awaitable[T]],
    *,
    description: str,
    attempts: int = MAX_ATTEMPTS,
) -> T:
    for attempt in range(1, attempts + 1):
        try:
            return await operation()
        except Exception as error:
            if is_daily_quota_exhausted(error):
                logger.warning(
                    "%s hit the daily Gemini quota; not retrying (it cannot succeed today).",
                    description,
                )
                raise
            if is_rate_limited(error):
                delay = requested_delay(error) or _delay_from(RATE_LIMIT_DELAYS, attempt)
            elif is_retryable(error):
                delay = _delay_from(SERVER_ERROR_DELAYS, attempt)
            else:
                raise

            if attempt == attempts:
                raise
            delay = min(delay, MAX_DELAY_SECONDS)
            logger.warning(
                "%s failed (attempt %s/%s): %s. Retrying in %.0fs.",
                description, attempt, attempts, str(error)[:160], delay,
            )
            await asyncio.sleep(delay)
    raise RuntimeError(f"{description} exhausted its retries without returning.")


def _delay_from(schedule: tuple[float, ...], attempt: int) -> float:
    return schedule[min(attempt, len(schedule)) - 1]
