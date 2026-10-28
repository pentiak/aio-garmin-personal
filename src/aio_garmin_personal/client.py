"""Client for the Garmin Connect Personal API."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from http import HTTPStatus
import json
from typing import Any

import aiohttp

from .activities import ActivityDetails, ActivityWorkout
from .auth import TokenProvider, parse_retry_after
from .body import FitnessAge, HeartRateZones, WeightGoals, WeightRange
from .const import (
    ACTIVITIES_PATH,
    ACTIVITY_FILE_PATH,
    ACTIVITY_PATH,
    ACTIVITY_WORKOUTS_PATH,
    BODY_BATTERY_PATH,
    DAILY_HYDRATION_PATH,
    DAILY_OVERVIEWS_PATH,
    DAILY_STEPS_PATH,
    DAILY_STRESS_PATH,
    DAILY_SUMMARY_PATH,
    DEFAULT_BASE_URL,
    DEFAULT_REQUEST_TIMEOUT,
    FITNESS_AGE_PATH,
    HEART_RATE_PATH,
    HEART_RATE_ZONES_PATH,
    HRV_PATH,
    HRV_RANGE_PATH,
    SLEEP_PATH,
    SLEEP_RANGE_PATH,
    SPO2_PATH,
    USER_SETTINGS_PATH,
    WEIGHT_GOALS_PATH,
    WEIGHT_PATH,
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
    DailyBodyBattery,
    DailyHeartRate,
    DailyHrv,
    DailyHydration,
    DailyOverview,
    DailySleep,
    DailySpO2,
    DailySteps,
    DailyStress,
    HrvSummary,
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
        self,
        *,
        limit: int = 20,
        start: int = 0,
        start_date: date | None = None,
        end_date: date | None = None,
        activity_type: str | None = None,
    ) -> list[Activity]:
        """Return the account's activities, most recent first.

        `start` is the zero-based offset of the first activity and `limit` the most to
        return. Garmin has answered HTTP 500 for limits from about 170 up; page with 100
        or fewer. `start_date` and `end_date` limit the activities to those that started on
        those local days, both included. `activity_type` is Garmin's type key, such as
        `running`; Garmin may include related types, so check `Activity.activity_type`.
        An unknown type raises `GarminPersonalResponseError` with status 400. An account
        without matching activities gives an empty list.

        Raises:
            ValueError: `limit` is below 1, `start` below 0, or `start_date` after
                `end_date`.
        """
        if limit < 1 or start < 0:
            raise ValueError("limit must be at least 1 and start at least 0")
        params = {"start": str(start), "limit": str(limit)}
        if start_date is not None and end_date is not None:
            _check_range(start_date, end_date)
        if start_date is not None:
            params["startDate"] = start_date.isoformat()
        if end_date is not None:
            params["endDate"] = end_date.isoformat()
        if activity_type is not None:
            params["activityType"] = activity_type
        items = await self._async_get_array(
            ACTIVITIES_PATH, "Activities", params=params
        )
        return [Activity.from_dict(item) for item in items]

    async def async_get_activity(self, activity_id: int) -> ActivityDetails | None:
        """Return one activity's summary, or `None` for an empty body.

        An unknown `activity_id` raises `GarminPersonalResponseError` with status 404.
        """
        body = await self._async_get_object(
            ACTIVITY_PATH.format(activity_id=activity_id), "Activity"
        )
        return None if body is None else ActivityDetails.from_dict(body)

    async def async_get_activity_workouts(
        self, activity_id: int
    ) -> list[ActivityWorkout]:
        """Return the planned workouts the activity followed; usually none or one."""
        items = await self._async_get_array(
            ACTIVITY_WORKOUTS_PATH.format(activity_id=activity_id), "Activity workouts"
        )
        return [ActivityWorkout.from_dict(item) for item in items]

    async def async_download_activity(self, activity_id: int) -> bytes:
        """Return the activity's original file as a ZIP archive.

        The archive holds the file the device uploaded, usually a FIT file. It includes
        the recorded track, so it is location data. An unknown `activity_id` raises
        `GarminPersonalResponseError` with status 404.
        """
        path = ACTIVITY_FILE_PATH.format(activity_id=activity_id)
        # Garmin answers 406 to Accept: application/octet-stream.
        body = await self._async_get_body(path, None, accept="*/*")
        if body is None:
            raise GarminPersonalResponseError(f"GET {path} returned no file")
        return body

    async def async_get_sleep(self, calendar_date: date) -> DailySleep | None:
        """Return the night that ended on `calendar_date`, or `None` if none was recorded."""
        body = await self._async_get_object(
            SLEEP_PATH, "Sleep", params={"date": calendar_date.isoformat()}
        )
        # A day without sleep is an object with every field null, the date included.
        if body is None or body.get("calendarDate") is None:
            return None
        return DailySleep.from_dict(body)

    async def async_get_sleep_range(self, start: date, end: date) -> list[DailySleep]:
        """Return the nights that ended from `start` to `end`, both included.

        Days without recorded sleep are left out. Garmin accepts at most 32 days per
        request.

        Raises:
            ValueError: `start` is after `end`.
        """
        _check_range(start, end)
        items = await self._async_get_array(
            SLEEP_RANGE_PATH,
            "Sleep summaries",
            params={"startDate": start.isoformat(), "endDate": end.isoformat()},
        )
        return [
            DailySleep.from_dict(item)
            for item in items
            if item.get("calendarDate") is not None
        ]

    async def async_get_hrv(self, calendar_date: date) -> DailyHrv | None:
        """Return the night's HRV readings and summary, or `None` without HRV data."""
        body = await self._async_get_object(
            HRV_PATH.format(day=calendar_date.isoformat()), "HRV"
        )
        return None if body is None else DailyHrv.from_dict(body)

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

    async def async_get_heart_rate(self, calendar_date: date) -> DailyHeartRate | None:
        """Return the day's heart rate readings and resting rate.

        A day without data still returns a `DailyHeartRate`, with every field `None`.
        `None` is returned only for an empty body.
        """
        body = await self._async_get_object(
            HEART_RATE_PATH, "Heart rate", params={"date": calendar_date.isoformat()}
        )
        return None if body is None else DailyHeartRate.from_dict(body)

    async def async_get_body_battery(
        self, start: date, end: date
    ) -> list[DailyBodyBattery]:
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
        return [DailyBodyBattery.from_dict(item) for item in items]

    async def async_get_spo2(self, calendar_date: date) -> DailySpO2 | None:
        """Return the day's blood oxygen readings.

        A day without data still returns an `DailySpO2`, with every field `None`. `None` is
        returned only for an empty body.
        """
        body = await self._async_get_object(
            SPO2_PATH.format(day=calendar_date.isoformat()), "SpO2"
        )
        return None if body is None else DailySpO2.from_dict(body)

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

    async def async_get_weight(
        self, start: date, end: date, *, include_all: bool = False
    ) -> WeightRange:
        """Return the weight entries from `start` to `end`, and their averages.

        Each day carries its latest entry; `include_all=True` adds every entry of the day.

        Raises:
            ValueError: `start` is after `end`.
        """
        _check_range(start, end)
        body = await self._async_get_object(
            WEIGHT_PATH.format(start=start.isoformat(), end=end.isoformat()),
            "Weight",
            params={"includeAll": "true" if include_all else "false"},
        )
        return WeightRange.from_dict(body or {})

    async def async_get_weight_goals(self, start: date, end: date) -> WeightGoals:
        """Return the weight goals in effect at any time from `start` to `end`.

        Raises:
            ValueError: `start` is after `end`.
        """
        _check_range(start, end)
        body = await self._async_get_object(
            WEIGHT_GOALS_PATH.format(start=start.isoformat(), end=end.isoformat()),
            "Weight goals",
        )
        return WeightGoals.from_dict(body or {})

    async def async_get_fitness_age(self, calendar_date: date) -> FitnessAge | None:
        """Return the latest fitness age as of `calendar_date`, or `None` for an empty body."""
        body = await self._async_get_object(
            FITNESS_AGE_PATH.format(day=calendar_date.isoformat()), "Fitness age"
        )
        return None if body is None else FitnessAge.from_dict(body)

    async def async_get_heart_rate_zones(self) -> list[HeartRateZones]:
        """Return the heart rate zones, one entry per sport that has its own."""
        items = await self._async_get_array(HEART_RATE_ZONES_PATH, "Heart rate zones")
        return [HeartRateZones.from_dict(item) for item in items]

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
        """GET a path and decode its JSON body; `None` for an empty body."""
        body = await self._async_get_body(path, params, accept="application/json")
        if body is None:
            return None
        try:
            return json.loads(body)
        except ValueError as err:
            raise GarminPersonalResponseError(
                f"GET {path} returned invalid JSON"
            ) from err

    async def _async_get_body(
        self, path: str, params: Mapping[str, str] | None, *, accept: str
    ) -> bytes | None:
        """GET a path and return its body; `None` for an empty body.

        A 401 with a cached token is retried once with a fresh token, because Garmin
        invalidates tokens when the key is deleted or regenerated.
        """
        for attempt in range(2):
            token = await self._tokens.async_get_token()
            status, body, retry_after = await self._async_get(
                path, params, token, accept
            )
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
        return body

    async def _async_get(
        self, path: str, params: Mapping[str, str] | None, token: str, accept: str
    ) -> tuple[int, bytes, str | None]:
        try:
            async with self._session.get(
                f"{self._base_url}{path}",
                params=params,
                headers={"Accept": accept, "Authorization": f"Bearer {token}"},
                timeout=self._timeout,
            ) as response:
                return (
                    response.status,
                    await response.read(),
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
