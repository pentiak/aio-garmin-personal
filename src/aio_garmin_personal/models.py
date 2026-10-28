"""Typed views of the Personal API responses."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from ._parse import opt_float, opt_gmt_datetime, opt_int, opt_obj, opt_str
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
            display_name=opt_str(data, "displayName"),
            time_zone=opt_str(data, "timeZone"),
            measurement_system=opt_str(data, "measurementSystem"),
            raw=data,
        )


@dataclass(frozen=True, kw_only=True)
class ActivityStats:
    """The measured totals of an activity, shared by `Activity` and `ActivityDetails`.

    Durations are in seconds, distances and elevations in metres, speeds in metres per
    second, calories in kilocalories and heart rates in beats per minute. A metric the
    activity did not record is `None`.
    """

    activity_type: str | None
    duration_seconds: float | None
    moving_duration_seconds: float | None
    elapsed_duration_seconds: float | None
    distance_meters: float | None
    calories: float | None
    average_heart_rate: float | None
    max_heart_rate: float | None
    average_speed: float | None
    max_speed: float | None
    elevation_gain_meters: float | None
    elevation_loss_meters: float | None
    steps: int | None
    average_power: float | None
    aerobic_training_effect: float | None
    anaerobic_training_effect: float | None
    training_load: float | None
    moderate_intensity_minutes: int | None
    vigorous_intensity_minutes: int | None


def activity_stats(
    totals: Mapping[str, Any], activity_type: str | None, aerobic_key: str
) -> dict[str, Any]:
    """Read the `ActivityStats` fields from an object of activity totals."""
    return {
        "activity_type": activity_type,
        "duration_seconds": opt_float(totals, "duration"),
        "moving_duration_seconds": opt_float(totals, "movingDuration"),
        "elapsed_duration_seconds": opt_float(totals, "elapsedDuration"),
        "distance_meters": opt_float(totals, "distance"),
        "calories": opt_float(totals, "calories"),
        "average_heart_rate": opt_float(totals, "averageHR"),
        "max_heart_rate": opt_float(totals, "maxHR"),
        "average_speed": opt_float(totals, "averageSpeed"),
        "max_speed": opt_float(totals, "maxSpeed"),
        "elevation_gain_meters": opt_float(totals, "elevationGain"),
        "elevation_loss_meters": opt_float(totals, "elevationLoss"),
        "steps": opt_int(totals, "steps"),
        "average_power": opt_float(totals, "averagePower")
        if "averagePower" in totals
        else opt_float(totals, "avgPower"),
        "aerobic_training_effect": opt_float(totals, aerobic_key),
        "anaerobic_training_effect": opt_float(totals, "anaerobicTrainingEffect"),
        "training_load": opt_float(totals, "activityTrainingLoad"),
        "moderate_intensity_minutes": opt_int(totals, "moderateIntensityMinutes"),
        "vigorous_intensity_minutes": opt_int(totals, "vigorousIntensityMinutes"),
    }


def require_activity_id(data: Mapping[str, Any]) -> int:
    """Return `activityId`, which identifies the activity in every activity response."""
    activity_id = data.get("activityId")
    if isinstance(activity_id, bool) or not isinstance(activity_id, int):
        raise GarminPersonalResponseError("Activity has no activityId")
    return activity_id


@dataclass(frozen=True, kw_only=True)
class Activity(ActivityStats):
    """One recorded activity from `/activitylist-service/activities/search/activities`.

    `activity_type` is Garmin's type key, such as `running`. `owner_full_name` is the
    account holder's name as entered in Garmin Connect; it may be missing. The start and
    end coordinates are only in `raw`; treat them as location data.
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
        return cls(
            activity_id=require_activity_id(data),
            activity_name=opt_str(data, "activityName"),
            start_time_gmt=opt_gmt_datetime(data, "startTimeGMT"),
            owner_display_name=opt_str(data, "ownerDisplayName"),
            owner_full_name=opt_str(data, "ownerFullName"),
            raw=data,
            **activity_stats(
                data,
                opt_str(opt_obj(data, "activityType"), "typeKey"),
                "aerobicTrainingEffect",
            ),
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
            display_name=opt_str(data, "displayName"),
            calendar_date=calendar_date,
            total_kilocalories=opt_float(data, "totalKilocalories"),
            active_kilocalories=opt_float(data, "activeKilocalories"),
            bmr_kilocalories=opt_float(data, "bmrKilocalories"),
            consumed_kilocalories=opt_float(data, "consumedKilocalories"),
            total_steps=opt_int(data, "totalSteps"),
            daily_step_goal=opt_int(data, "dailyStepGoal"),
            total_distance_meters=opt_int(data, "totalDistanceMeters"),
            floors_ascended=opt_float(data, "floorsAscended"),
            moderate_intensity_minutes=opt_int(data, "moderateIntensityMinutes"),
            vigorous_intensity_minutes=opt_int(data, "vigorousIntensityMinutes"),
            resting_heart_rate=opt_int(data, "restingHeartRate"),
            min_heart_rate=opt_int(data, "minHeartRate"),
            max_heart_rate=opt_int(data, "maxHeartRate"),
            average_stress_level=opt_int(data, "averageStressLevel"),
            body_battery_most_recent_value=opt_int(data, "bodyBatteryMostRecentValue"),
            body_battery_highest_value=opt_int(data, "bodyBatteryHighestValue"),
            body_battery_lowest_value=opt_int(data, "bodyBatteryLowestValue"),
            last_sync=opt_gmt_datetime(data, "lastSyncTimestampGMT"),
            raw=data,
        )
