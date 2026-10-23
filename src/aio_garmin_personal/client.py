"""Client for the Garmin Connect Personal API."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from http import HTTPStatus
import json
from typing import Any

import aiohttp

from .auth import TokenProvider, parse_retry_after
from .const import (
    DAILY_SUMMARY_PATH,
    DEFAULT_BASE_URL,
    DEFAULT_REQUEST_TIMEOUT,
    USER_SETTINGS_PATH,
)
from .exceptions import (
    GarminPersonalAuthenticationError,
    GarminPersonalConnectionError,
    GarminPersonalRateLimitError,
    GarminPersonalResponseError,
)
from .models import DailySummary, UserSettings


class GarminPersonalClient:
    """Read the data of the Garmin account that owns the API key.

    The caller owns `session` and closes it; the client never does. One client instance
    is safe to share between concurrent tasks.

    ```python
    async with aiohttp.ClientSession() as session:
        client = GarminPersonalClient(session, api_key)
        summary = await client.async_get_daily_summary(date.today())
    ```
    """

    def __init__(
        self,
        session: aiohttp.ClientSession,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        request_timeout: float = DEFAULT_REQUEST_TIMEOUT,
    ) -> None:
        """Create a client for one API key.

        Raises:
            ValueError: `api_key` is empty or only whitespace.
        """
        self._session = session
        self._base_url = base_url.rstrip("/")
        self._timeout = aiohttp.ClientTimeout(total=request_timeout)
        self._tokens = TokenProvider(
            session, api_key, base_url=self._base_url, request_timeout=request_timeout
        )

    async def async_get_user_settings(self) -> UserSettings:
        """Return the account's profile settings, including its time zone."""
        body = await self._async_get_json(USER_SETTINGS_PATH)
        if not isinstance(body, Mapping):
            raise GarminPersonalResponseError("User settings response is not an object")
        return UserSettings.from_dict(body)

    async def async_get_daily_summary(self, calendar_date: date) -> DailySummary | None:
        """Return the wellness totals for one calendar day in the account's time zone.

        A day without data, in the future or before the account existed, still returns a
        summary, with every metric `None`. `None` is returned only for an empty body.
        """
        body = await self._async_get_json(
            DAILY_SUMMARY_PATH, params={"calendarDate": calendar_date.isoformat()}
        )
        if body is None:
            return None
        if not isinstance(body, Mapping):
            raise GarminPersonalResponseError("Daily summary response is not an object")
        return DailySummary.from_dict(body)

    async def _async_get_json(
        self, path: str, params: Mapping[str, str] | None = None
    ) -> Any:
        """GET a path and decode its JSON body; `None` for an empty body.

        A 401 with a cached token is retried once with a fresh token, because Garmin
        invalidates tokens when the key is deleted or regenerated.
        """
        for attempt in range(2):
            token = await self._tokens.async_get_token()
            status, body, retry_after = await self._async_get(path, params, token)
            if status == HTTPStatus.UNAUTHORIZED:
                self._tokens.invalidate()
                if attempt == 0:
                    continue
                raise GarminPersonalAuthenticationError(f"GET {path} returned HTTP 401")
            break

        if status == HTTPStatus.TOO_MANY_REQUESTS:
            raise GarminPersonalRateLimitError(
                f"GET {path} rate limited", retry_after=parse_retry_after(retry_after)
            )
        if status == HTTPStatus.NO_CONTENT or (status == HTTPStatus.OK and not body):
            return None
        if status != HTTPStatus.OK:
            raise GarminPersonalResponseError(
                f"GET {path} returned HTTP {status}", status
            )
        try:
            return json.loads(body)
        except ValueError as err:
            raise GarminPersonalResponseError(
                f"GET {path} returned invalid JSON"
            ) from err

    async def _async_get(
        self, path: str, params: Mapping[str, str] | None, token: str
    ) -> tuple[int, str, str | None]:
        try:
            async with self._session.get(
                f"{self._base_url}{path}",
                params=params,
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Bearer {token}",
                },
                timeout=self._timeout,
            ) as response:
                return (
                    response.status,
                    await response.text(),
                    response.headers.get("Retry-After"),
                )
        except (TimeoutError, aiohttp.ClientError) as err:
            raise GarminPersonalConnectionError(f"GET {path} failed: {err}") from err
