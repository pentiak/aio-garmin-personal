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
    ACTIVITIES_PATH,
    BODY_BATTERY_PATH,
    DAILY_HYDRATION_PATH,
    DAILY_OVERVIEWS_PATH,
    DAILY_STEPS_PATH,
    DAILY_STRESS_PATH,
    DAILY_SUMMARY_PATH,
    DEFAULT_BASE_URL,
    DEFAULT_REQUEST_TIMEOUT,
    HEART_RATE_PATH,
    HRV_PATH,
    HRV_RANGE_PATH,
    SLEEP_PATH,
    SLEEP_RANGE_PATH,
    SPO2_PATH,
    USER_SETTINGS_PATH,
    WELLNESS_ACTIVITIES_PATH,
)
from .exceptions import (
    GarminPersonalAuthenticationError,
    GarminPersonalConnectionError,
    GarminPersonalRateLimitError,
    GarminPersonalResponseError,
)
from .models import Activity, DailySummary, UserSettings
from .wellness import (
    BodyBatteryDay,
    DailyHydration,
    DailyOverview,
    DailySteps,
    DailyStress,
    HeartRateDay,
    HrvDay,
    HrvSummary,
    Sleep,
    SpO2Day,
    WellnessActivity,
)


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

    async def async_get_activities(
        self, *, limit: int = 20, start: int = 0
    ) -> list[Activity]:
        """Return the account's activities, most recent first.

        `start` is the zero-based offset of the first activity and `limit` the most to
        return. An account without activities gives an empty list.

        Raises:
            ValueError: `limit` is below 1 or `start` below 0.
        """
        if limit < 1 or start < 0:
            raise ValueError("limit must be at least 1 and start at least 0")
        body = await self._async_get_json(
            ACTIVITIES_PATH, params={"start": str(start), "limit": str(limit)}
        )
        if body is None:
            return []
        return [
            Activity.from_dict(item) for item in _array_of_objects(body, "Activities")
        ]

    async def async_get_sleep(self, calendar_date: date) -> Sleep | None:
        """Return the night that ended on `calendar_date`, or `None` if none was recorded."""
        body = await self._async_get_object(
            SLEEP_PATH, "Sleep", params={"date": calendar_date.isoformat()}
        )
        # A day without sleep is an object with every field null, the date included.
        if body is None or body.get("calendarDate") is None:
            return None
        return Sleep.from_dict(body)

    async def async_get_sleep_range(self, start: date, end: date) -> list[Sleep]:
        """Return the nights that ended from `start` to `end`, both included.

        Garmin accepts at most 32 days per request.

        Raises:
            ValueError: `start` is after `end`.
        """
        _check_range(start, end)
        items = await self._async_get_array(
            SLEEP_RANGE_PATH,
            "Sleep summaries",
            params={"startDate": start.isoformat(), "endDate": end.isoformat()},
        )
        return [Sleep.from_dict(item) for item in items]

    async def async_get_hrv(self, calendar_date: date) -> HrvDay | None:
        """Return the night's HRV readings and summary, or `None` without HRV data."""
        body = await self._async_get_object(
            HRV_PATH.format(day=calendar_date.isoformat()), "HRV"
        )
        return None if body is None else HrvDay.from_dict(body)

    async def async_get_hrv_summaries(self, start: date, end: date) -> list[HrvSummary]:
        """Return the HRV summary of each day from `start` to `end` that has one.

        Garmin accepts at most 367 days per request.

        Raises:
            ValueError: `start` is after `end`.
        """
        _check_range(start, end)
        body = await self._async_get_object(
            HRV_RANGE_PATH.format(start=start.isoformat(), end=end.isoformat()),
            "HRV summaries",
        )
        if body is None:
            return []
        return [
            HrvSummary.from_dict(item)
            for item in _array_of_objects(body.get("hrvSummaries"), "HRV summaries")
        ]

    async def async_get_heart_rate(self, calendar_date: date) -> HeartRateDay | None:
        """Return the day's heart rate readings and resting rate.

        A day without data still returns a `HeartRateDay`, with every field `None`.
        `None` is returned only for an empty body.
        """
        body = await self._async_get_object(
            HEART_RATE_PATH, "Heart rate", params={"date": calendar_date.isoformat()}
        )
        return None if body is None else HeartRateDay.from_dict(body)

    async def async_get_body_battery(
        self, start: date, end: date
    ) -> list[BodyBatteryDay]:
        """Return the Body Battery levels and events of each day from `start` to `end`.

        Garmin accepts at most 31 days per request.

        Raises:
            ValueError: `start` is after `end`.
        """
        _check_range(start, end)
        items = await self._async_get_array(
            BODY_BATTERY_PATH,
            "Body Battery reports",
            params={"startDate": start.isoformat(), "endDate": end.isoformat()},
        )
        return [BodyBatteryDay.from_dict(item) for item in items]

    async def async_get_spo2(self, calendar_date: date) -> SpO2Day | None:
        """Return the day's blood oxygen readings.

        A day without data still returns an `SpO2Day`, with every field `None`. `None` is
        returned only for an empty body.
        """
        body = await self._async_get_object(
            SPO2_PATH.format(day=calendar_date.isoformat()), "SpO2"
        )
        return None if body is None else SpO2Day.from_dict(body)

    async def async_get_daily_steps(self, start: date, end: date) -> list[DailySteps]:
        """Return the step totals of each day from `start` to `end`.

        Garmin accepts at most 28 days per request.

        Raises:
            ValueError: `start` is after `end`.
        """
        _check_range(start, end)
        items = await self._async_get_array(
            DAILY_STEPS_PATH.format(start=start.isoformat(), end=end.isoformat()),
            "Daily steps",
        )
        return [DailySteps.from_dict(item) for item in items]

    async def async_get_daily_stress(self, start: date, end: date) -> list[DailyStress]:
        """Return the stress level and durations of each day from `start` to `end`.

        Garmin accepts at most 28 days per request.

        Raises:
            ValueError: `start` is after `end`.
        """
        _check_range(start, end)
        items = await self._async_get_array(
            DAILY_STRESS_PATH.format(start=start.isoformat(), end=end.isoformat()),
            "Daily stress",
        )
        return [DailyStress.from_dict(item) for item in items]

    async def async_get_daily_hydration(
        self, start: date, end: date
    ) -> list[DailyHydration]:
        """Return the logged hydration of each day from `start` to `end` that has any.

        Garmin accepts at most 31 days per request.

        Raises:
            ValueError: `start` is after `end`.
        """
        _check_range(start, end)
        items = await self._async_get_array(
            DAILY_HYDRATION_PATH.format(start=start.isoformat(), end=end.isoformat()),
            "Daily hydration",
        )
        return [DailyHydration.from_dict(item) for item in items]

    async def async_get_daily_overviews(
        self, start: date, end: date
    ) -> list[DailyOverview]:
        """Return the wellness totals of each day from `start` to `end`.

        Garmin rejects ranges longer than about a year, and has answered HTTP 500 for
        ranges of several months; ask for a few months at a time.

        Raises:
            ValueError: `start` is after `end`.
        """
        _check_range(start, end)
        body = await self._async_get_object(
            DAILY_OVERVIEWS_PATH,
            "Daily overviews",
            params={"startDate": start.isoformat(), "endDate": end.isoformat()},
        )
        if body is None:
            return []
        return [
            DailyOverview.from_dict(item)
            for item in _array_of_objects(body.get("data"), "Daily overviews")
        ]

    async def async_get_wellness_activities(
        self, start: date, end: date
    ) -> list[WellnessActivity]:
        """Return the wellness sessions, such as breathwork, from `start` to `end`.

        Raises:
            ValueError: `start` is after `end`.
        """
        _check_range(start, end)
        items = await self._async_get_array(
            WELLNESS_ACTIVITIES_PATH.format(
                start=start.isoformat(), end=end.isoformat()
            ),
            "Wellness activities",
        )
        return [WellnessActivity.from_dict(item) for item in items]

    async def _async_get_object(
        self, path: str, what: str, params: Mapping[str, str] | None = None
    ) -> Mapping[str, Any] | None:
        body = await self._async_get_json(path, params)
        if body is None:
            return None
        if not isinstance(body, Mapping):
            raise GarminPersonalResponseError(f"{what} response is not an object")
        return body

    async def _async_get_array(
        self, path: str, what: str, params: Mapping[str, str] | None = None
    ) -> list[Mapping[str, Any]]:
        body = await self._async_get_json(path, params)
        if body is None:
            return []
        return _array_of_objects(body, what)

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


def _check_range(start: date, end: date) -> None:
    if start > end:
        raise ValueError("start must not be after end")


def _array_of_objects(body: Any, what: str) -> list[Mapping[str, Any]]:
    if not isinstance(body, list) or not all(
        isinstance(item, Mapping) for item in body
    ):
        raise GarminPersonalResponseError(f"{what} response is not an array of objects")
    return body
