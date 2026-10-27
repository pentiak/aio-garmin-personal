"""Exchange of a Personal API key for short-lived access tokens."""

from __future__ import annotations

import asyncio
import base64
import binascii
from collections.abc import Callable
from dataclasses import dataclass, field
from http import HTTPStatus
import json
import time

import aiohttp

from .const import TOKEN_PATH, TOKEN_REFRESH_MARGIN
from .exceptions import (
    GarminPersonalAuthenticationError,
    GarminPersonalConnectionError,
    GarminPersonalRateLimitError,
    GarminPersonalResponseError,
)


@dataclass(frozen=True)
class AccessToken:
    """A bearer token and its expiry in seconds since the epoch."""

    value: str = field(repr=False)
    expires_at: float


class TokenProvider:
    """Hand out a valid access token, exchanging the API key only when needed.

    Tokens are kept in memory only. Concurrent callers share one exchange.
    """

    def __init__(
        self,
        session: aiohttp.ClientSession,
        api_key: str,
        *,
        base_url: str,
        request_timeout: float,
        clock: Callable[[], float] = time.time,
    ) -> None:
        """Create a provider for one API key.

        Raises:
            ValueError: `api_key` is empty or only whitespace.
        """
        if not api_key.strip():
            raise ValueError("api_key must not be empty")
        self._session = session
        self._api_key = api_key.strip()
        self._url = f"{base_url}{TOKEN_PATH}"
        self._timeout = aiohttp.ClientTimeout(total=request_timeout)
        self._clock = clock
        self._token: AccessToken | None = None
        self._lock = asyncio.Lock()

    async def async_get_token(self) -> str:
        """Return a token valid for at least `TOKEN_REFRESH_MARGIN` more seconds.

        Raises:
            GarminPersonalAuthenticationError: Garmin rejected the API key.
            GarminPersonalRateLimitError: Garmin answered HTTP 429.
            GarminPersonalConnectionError: the token endpoint could not be reached.
            GarminPersonalResponseError: any other failure status, or a body that is not a
                JWT with an `exp` claim.
        """
        async with self._lock:
            token = self._token
            if (
                token is None
                or token.expires_at - self._clock() <= TOKEN_REFRESH_MARGIN
            ):
                token = await self._async_exchange()
                self._token = token
            return token.value

    def invalidate(self) -> None:
        """Forget the cached token so the next call exchanges the key again."""
        self._token = None

    async def _async_exchange(self) -> AccessToken:
        try:
            async with self._session.post(
                self._url,
                headers={"Accept": "*/*", "Authorization": f"ApiKey {self._api_key}"},
                timeout=self._timeout,
            ) as response:
                body = await response.text()
                status = response.status
                retry_after = response.headers.get("Retry-After")
        except (TimeoutError, aiohttp.ClientError) as err:
            raise GarminPersonalConnectionError(f"Token request failed: {err}") from err

        # Garmin answers 401 for a key it never issued and 404 for one that was deleted.
        if status in (
            HTTPStatus.UNAUTHORIZED,
            HTTPStatus.FORBIDDEN,
            HTTPStatus.NOT_FOUND,
        ):
            raise GarminPersonalAuthenticationError(f"API key rejected (HTTP {status})")
        if status == HTTPStatus.TOO_MANY_REQUESTS:
            raise GarminPersonalRateLimitError(
                "Token request rate limited", retry_after=parse_retry_after(retry_after)
            )
        if status != HTTPStatus.OK:
            raise GarminPersonalResponseError(
                f"Token request returned HTTP {status}", status
            )

        value = body.strip()
        return AccessToken(value=value, expires_at=jwt_expiry(value))


def jwt_expiry(token: str) -> float:
    """Return the `exp` claim of a JWT without verifying its signature.

    Raises:
        GarminPersonalResponseError: the token is not a JWT or has no numeric `exp` claim.
    """
    try:
        payload_segment = token.split(".")[1]
        padded = payload_segment + "=" * (-len(payload_segment) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded))
        expiry = payload["exp"]
    except (IndexError, KeyError, TypeError, ValueError, binascii.Error) as err:
        raise GarminPersonalResponseError(
            "Token endpoint did not return a JWT"
        ) from err
    if isinstance(expiry, bool) or not isinstance(expiry, int | float):
        raise GarminPersonalResponseError("Token has no numeric exp claim")
    return float(expiry)


def parse_retry_after(value: str | None) -> float | None:
    """Return a `Retry-After` header given in seconds, or `None`.

    The HTTP-date form of the header is not supported and also yields `None`.
    """
    if value is None:
        return None
    try:
        seconds = float(value)
    except ValueError:
        return None
    return seconds if seconds >= 0 else None
