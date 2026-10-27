"""Typed views of the Personal API responses."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

from .exceptions import GarminPersonalResponseError


@dataclass(frozen=True, kw_only=True)
class UserSettings:
    """Profile settings from `/userprofile-service/userprofile/settings`.

    `time_zone` is an IANA zone name such as `Europe/Warsaw`, or `gmt`. Garmin assigns
    each daily summary to a calendar day in this zone.
    """

    display_name: str | None
    time_zone: str | None
    measurement_system: str | None
    raw: Mapping[str, Any] = field(repr=False)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> UserSettings:
        """Build the settings from the decoded JSON body."""
        return cls(
            display_name=_opt_str(data, "displayName"),
            time_zone=_opt_str(data, "timeZone"),
            measurement_system=_opt_str(data, "measurementSystem"),
            raw=data,
        )


@dataclass(frozen=True, kw_only=True)
class Activity:
    """One recorded activity from `/activitylist-service/activities/search/activities`.

    `owner_full_name` is the account holder's name as entered in Garmin Connect; it may be
    missing.
    """

    activity_id: int
    activity_name: str | None
    start_time_gmt: datetime | None
    owner_display_name: str | None
    owner_full_name: str | None
    raw: Mapping[str, Any] = field(repr=False)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Activity:
        """Build the activity from one element of the decoded JSON array.

        Raises:
            GarminPersonalResponseError: `activityId` is missing or not an integer.
        """
        activity_id = data.get("activityId")
        if isinstance(activity_id, bool) or not isinstance(activity_id, int):
            raise GarminPersonalResponseError("Activity has no activityId")
        return cls(
            activity_id=activity_id,
            activity_name=_opt_str(data, "activityName"),
            start_time_gmt=_opt_gmt_datetime(data, "startTimeGMT"),
            owner_display_name=_opt_str(data, "ownerDisplayName"),
            owner_full_name=_opt_str(data, "ownerFullName"),
            raw=data,
        )


@dataclass(frozen=True, kw_only=True)
class DailySummary:
    """One day of wellness totals from `/usersummary-service/usersummary/daily`.

    Every metric is `None` when Garmin has no data for it, for example before the first
    sync of the day. Totals, resting calories included, cover the day so far, up to the
    last sync.
    """

    user_profile_id: int
    display_name: str | None
    calendar_date: date
    total_kilocalories: float | None
    active_kilocalories: float | None
    bmr_kilocalories: float | None
    consumed_kilocalories: float | None
    total_steps: int | None
    daily_step_goal: int | None
    total_distance_meters: int | None
    floors_ascended: float | None
    moderate_intensity_minutes: int | None
    vigorous_intensity_minutes: int | None
    resting_heart_rate: int | None
    min_heart_rate: int | None
    max_heart_rate: int | None
    average_stress_level: int | None
    body_battery_most_recent_value: int | None
    body_battery_highest_value: int | None
    body_battery_lowest_value: int | None
    last_sync: datetime | None
    raw: Mapping[str, Any] = field(repr=False)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DailySummary:
        """Build the summary from the decoded JSON body.

        Raises:
            GarminPersonalResponseError: `userProfileId` or `calendarDate` is missing or
                malformed. Other fields are optional.
        """
        user_profile_id = data.get("userProfileId")
        if not isinstance(user_profile_id, int):
            raise GarminPersonalResponseError("Daily summary has no userProfileId")
        try:
            calendar_date = date.fromisoformat(data["calendarDate"])
        except (KeyError, TypeError, ValueError) as err:
            raise GarminPersonalResponseError(
                "Daily summary has no valid calendarDate"
            ) from err
        return cls(
            user_profile_id=user_profile_id,
            display_name=_opt_str(data, "displayName"),
            calendar_date=calendar_date,
            total_kilocalories=_opt_float(data, "totalKilocalories"),
            active_kilocalories=_opt_float(data, "activeKilocalories"),
            bmr_kilocalories=_opt_float(data, "bmrKilocalories"),
            consumed_kilocalories=_opt_float(data, "consumedKilocalories"),
            total_steps=_opt_int(data, "totalSteps"),
            daily_step_goal=_opt_int(data, "dailyStepGoal"),
            total_distance_meters=_opt_int(data, "totalDistanceMeters"),
            floors_ascended=_opt_float(data, "floorsAscended"),
            moderate_intensity_minutes=_opt_int(data, "moderateIntensityMinutes"),
            vigorous_intensity_minutes=_opt_int(data, "vigorousIntensityMinutes"),
            resting_heart_rate=_opt_int(data, "restingHeartRate"),
            min_heart_rate=_opt_int(data, "minHeartRate"),
            max_heart_rate=_opt_int(data, "maxHeartRate"),
            average_stress_level=_opt_int(data, "averageStressLevel"),
            body_battery_most_recent_value=_opt_int(data, "bodyBatteryMostRecentValue"),
            body_battery_highest_value=_opt_int(data, "bodyBatteryHighestValue"),
            body_battery_lowest_value=_opt_int(data, "bodyBatteryLowestValue"),
            last_sync=_opt_gmt_datetime(data, "lastSyncTimestampGMT"),
            raw=data,
        )


def _opt_str(data: Mapping[str, Any], key: str) -> str | None:
    value = data.get(key)
    return value if isinstance(value, str) else None


def _opt_int(data: Mapping[str, Any], key: str) -> int | None:
    value = data.get(key)
    # bool is a subclass of int and is never a valid metric.
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _opt_float(data: Mapping[str, Any], key: str) -> float | None:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def _opt_gmt_datetime(data: Mapping[str, Any], key: str) -> datetime | None:
    value = data.get(key)
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    # Garmin's *GMT fields carry no offset.
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
