"""Typed views of one activity's summary and the workouts it followed."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from ._parse import opt_float, opt_gmt_datetime, opt_int, opt_obj, opt_objs, opt_str
from .models import ActivityStats, activity_stats, require_activity_id


@dataclass(frozen=True, kw_only=True)
class ActivityDetails(ActivityStats):
    """One activity from `/activity-service/activity/{activityId}`.

    The totals match those in the activity list. `time_zone` is the IANA zone the
    activity was recorded in. Splits, sensors and the start and end coordinates are only
    in `raw`; treat the coordinates as location data.
    """

    activity_id: int
    activity_name: str | None
    location_name: str | None
    time_zone: str | None
    start_time_gmt: datetime | None
    raw: Mapping[str, Any] = field(repr=False)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ActivityDetails:
        """Build the activity from the decoded JSON body.

        Raises:
            GarminPersonalResponseError: `activityId` is missing or not an integer.
        """
        summary = opt_obj(data, "summaryDTO")
        return cls(
            activity_id=require_activity_id(data),
            activity_name=opt_str(data, "activityName"),
            location_name=opt_str(data, "locationName"),
            time_zone=opt_str(opt_obj(data, "timeZoneUnitDTO"), "timeZone"),
            start_time_gmt=opt_gmt_datetime(summary, "startTimeGMT"),
            raw=data,
            **activity_stats(
                summary,
                opt_str(opt_obj(data, "activityTypeDTO"), "typeKey"),
                "trainingEffect",
            ),
        )


@dataclass(frozen=True, kw_only=True)
class WorkoutStep:
    """One step of a planned workout.

    `duration_type` says what ends the step: `TIME` (`duration_value` in seconds),
    `DISTANCE` (metres), `REPS` (a count), `OPEN`, or `REPEAT_UNTIL_STEPS_CMPLT`, where
    `duration_value` is the index of the step to repeat from. `target_type` is what the
    step aims for, such as `SPEED` or `HEART_RATE`, with the band from `target_low` to
    `target_high`.
    """

    step_index: int | None
    intensity: str | None
    duration_type: str | None
    duration_value: float | None
    target_type: str | None
    target_low: float | None
    target_high: float | None
    notes: str | None
    raw: Mapping[str, Any] = field(repr=False)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> WorkoutStep:
        """Build the step from one element of a workout's `steps`."""
        return cls(
            step_index=opt_int(data, "stepIndex"),
            intensity=opt_str(data, "intensity"),
            duration_type=opt_str(data, "durationType"),
            duration_value=opt_float(data, "durationValue"),
            target_type=opt_str(data, "targetType"),
            target_low=opt_float(data, "targetValueLow"),
            target_high=opt_float(data, "targetValueHigh"),
            notes=opt_str(data, "notes"),
            raw=data,
        )


@dataclass(frozen=True, kw_only=True)
class ActivityWorkout:
    """A planned workout the activity followed, from `/activity-service/activity/{id}/workouts`."""

    workout_name: str | None
    sport: str | None
    created_time_gmt: datetime | None
    steps: list[WorkoutStep]
    raw: Mapping[str, Any] = field(repr=False)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ActivityWorkout:
        """Build the workout from one element of the decoded JSON array."""
        return cls(
            workout_name=opt_str(data, "workoutName"),
            sport=opt_str(data, "sport"),
            created_time_gmt=opt_gmt_datetime(data, "timeCreated"),
            steps=[WorkoutStep.from_dict(step) for step in opt_objs(data, "steps")],
            raw=data,
        )
