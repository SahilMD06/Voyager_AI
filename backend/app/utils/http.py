"""Small HTTP helper with timeouts, retries and back-off for rate limits."""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class ExternalAPIError(RuntimeError):
    """Raised when an external API cannot be reached or returns an error."""


def _reason(response: httpx.Response) -> str | None:
    try:
        body = response.json()
    except ValueError:
        return None
    return body.get("reason") if isinstance(body, dict) else None


def get_json(url: str, params: dict[str, Any] | None = None) -> dict:
    """GET ``url`` and return parsed JSON, retrying transient failures."""
    settings = get_settings()
    last_error: str = "unknown error"
    headers = {"User-Agent": settings.http_user_agent}
    for attempt in range(1, settings.http_max_retries + 1):
        try:
            response = httpx.get(
                url,
                params=params,
                timeout=httpx.Timeout(settings.http_timeout_seconds, connect=6.0),
                headers=headers,
            )
            if response.status_code in RETRYABLE_STATUS:
                last_error = f"HTTP {response.status_code}"
                retry_after = response.headers.get("Retry-After")
                wait = (
                    float(retry_after)
                    if retry_after and retry_after.isdigit()
                    else 0.8 * attempt
                )
                if wait > 30:
                    # e.g. Open-Meteo daily quota: retrying now is pointless.
                    reason = _reason(response) or "rate limit exceeded"
                    raise ExternalAPIError(
                        f"HTTP {response.status_code}: {reason}"
                    )
                logger.warning(
                    "%s returned %s (attempt %d), retrying in %.1fs",
                    url, response.status_code, attempt, wait,
                )
                time.sleep(min(wait, 5))
                continue
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise ExternalAPIError(f"Unexpected payload from {url}")
            if payload.get("error"):
                raise ExternalAPIError(
                    str(payload.get("reason", "API reported an error"))
                )
            return payload
        except httpx.HTTPStatusError as exc:
            reason = _reason(exc.response)
            raise ExternalAPIError(
                f"HTTP {exc.response.status_code} from {url}"
                + (f": {reason}" if reason else "")
            ) from exc
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            logger.warning("Network error on %s (attempt %d): %s",
                           url, attempt, last_error)
            time.sleep(0.5 * attempt)
        except ValueError as exc:
            raise ExternalAPIError(f"Invalid JSON from {url}") from exc
    raise ExternalAPIError(f"Request to {url} failed: {last_error}")
