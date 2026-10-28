"""Typed views of the weight, weight goal, fitness age and heart rate zone responses.

Each model types the fields a caller is likely to use and keeps the whole object in `raw`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from ._parse import (
    opt_bool,
    opt_date,
    opt_epoch_ms,
    opt_float,
    opt_int,
    opt_obj,
    opt_objs,
    opt_str,
    req_date,
)


@dataclass(frozen=True, kw_only=True)
class WeightEntry:
    """One weight measurement. Weight is in grams, whatever the profile's unit system.

    `source_type` says how it was entered, for example `MANUAL`. Body composition fields are
    `None` unless a scale that measures them recorded the entry.
    """

    calendar_date: date | None
    time_gmt: datetime | None
    weight_grams: float | None
    bmi: float | None
    body_fat_percent: float | None
    body_water_percent: float | None
    source_type: str | None
    raw: Mapping[str, Any] = field(repr=False)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> WeightEntry:
        """Build the entry from one decoded weight object."""
        return cls(
            calendar_date=opt_date(data, "calendarDate"),
            time_gmt=opt_epoch_ms(data, "timestampGMT"),
            weight_grams=opt_float(data, "weight"),
            bmi=opt_float(data, "bmi"),
            body_fat_percent=opt_float(data, "bodyFat"),
            body_water_percent=opt_float(data, "bodyWater"),
            source_type=opt_str(data, "sourceType"),
            raw=data,
        )


@dataclass(frozen=True, kw_only=True)
class DailyWeight:
    """The weight entries of one day.

    `entries` is empty unless the range was requested with `include_all=True`.
    """

    calendar_date: date
    entry_count: int | None
    min_weight_grams: float | None
    max_weight_grams: float | None
    latest: WeightEntry | None
    entries: list[WeightEntry]
    raw: Mapping[str, Any] = field(repr=False)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DailyWeight:
        """Build the day from one element of `dailyWeightSummaries`.

        Raises:
            GarminPersonalResponseError: `summaryDate` is missing or malformed.
        """
        latest = data.get("latestWeight")
        return cls(
            calendar_date=req_date(data, "summaryDate", "Daily weight"),
            entry_count=opt_int(data, "numOfWeightEntries"),
            min_weight_grams=opt_float(data, "minWeight"),
            max_weight_grams=opt_float(data, "maxWeight"),
            latest=WeightEntry.from_dict(latest)
            if isinstance(latest, Mapping)
            else None,
            entries=[
                WeightEntry.from_dict(item)
                for item in opt_objs(data, "allWeightMetrics")
            ],
            raw=data,
        )


@dataclass(frozen=True, kw_only=True)
class WeightRange:
    """Weight from `/weight-service/weight/range/{startDate}/{endDate}`.

    `days` holds only the days with an entry. The averages cover the whole range.
    """

    days: list[DailyWeight]
    average_weight_grams: float | None
    average_bmi: float | None
    average_body_fat_percent: float | None
    raw: Mapping[str, Any] = field(repr=False)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> WeightRange:
        """Build the range from the decoded JSON body.

        Raises:
            GarminPersonalResponseError: a day's `summaryDate` is missing or malformed.
        """
        average = opt_obj(data, "totalAverage")
        return cls(
            days=[
                DailyWeight.from_dict(item)
                for item in opt_objs(data, "dailyWeightSummaries")
            ],
            average_weight_grams=opt_float(average, "weight"),
            average_bmi=opt_float(average, "bmi"),
            average_body_fat_percent=opt_float(average, "bodyFat"),
            raw=data,
        )


@dataclass(frozen=True, kw_only=True)
class WeightGoal:
    """A weight goal in effect during the requested range, in grams.

    Typed from Garmin's API description: not yet checked against an account with a goal.
    """

    goal_name: str | None
    goal_type: str | None
    category: str | None
    goal_value_grams: float | None
    start_date: date | None
    end_date: date | None
    tracking_period_type: str | None
    raw: Mapping[str, Any] = field(repr=False)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> WeightGoal:
        """Build the goal from one element of `userGoals`."""
        return cls(
            goal_name=opt_str(data, "goalName"),
            goal_type=opt_str(data, "userGoalType"),
            category=opt_str(data, "userGoalCategory"),
            goal_value_grams=opt_float(data, "goalValue"),
            start_date=opt_date(data, "startDate"),
            end_date=opt_date(data, "endDate"),
            tracking_period_type=opt_str(data, "trackingPeriodType"),
            raw=data,
        )


@dataclass(frozen=True, kw_only=True)
class WeightGoalRange:
    """A target band for weight in effect during the requested range, in grams.

    Typed from Garmin's API description: not yet checked against an account with a goal.
    """

    low_grams: float | None
    high_grams: float | None
    start_date: date | None
    end_date: date | None
    raw: Mapping[str, Any] = field(repr=False)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> WeightGoalRange:
        """Build the band from one element of `userGoalRanges`."""
        return cls(
            low_grams=opt_float(data, "lowWeightGoalInGrams"),
            high_grams=opt_float(data, "highWeightGoalInGrams"),
            start_date=opt_date(data, "startDate"),
            end_date=opt_date(data, "endDate"),
            raw=data,
        )


@dataclass(frozen=True, kw_only=True)
class WeightGoals:
    """Weight goals from `/goal-service/goal/user/effective/weightgoal/{start}/{end}`."""

    goals: list[WeightGoal]
    ranges: list[WeightGoalRange]
    raw: Mapping[str, Any] = field(repr=False)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> WeightGoals:
        """Build the goals from the decoded JSON body."""
        return cls(
            goals=[WeightGoal.from_dict(item) for item in opt_objs(data, "userGoals")],
            ranges=[
                WeightGoalRange.from_dict(item)
                for item in opt_objs(data, "userGoalRanges")
            ],
            raw=data,
        )


@dataclass(frozen=True, kw_only=True)
class FitnessAgeComponent:
    """One input to the fitness age, such as resting heart rate or BMI.

    `stale` is true when the input has not been measured recently.
    """

    value: float | None
    target_value: float | None
    potential_age: float | None
    stale: bool | None
    raw: Mapping[str, Any] = field(repr=False)


@dataclass(frozen=True, kw_only=True)
class FitnessAge:
    """Fitness age from `/fitnessage-service/fitnessage/v2/{calendarDate}`.

    `components` maps Garmin's component names, such as `rhr` and `bmi`, to their values.
    `invalid_reason` explains a missing fitness age.
    """

    fitness_age: float | None
    chronological_age: int | None
    achievable_fitness_age: float | None
    previous_fitness_age: float | None
    components: dict[str, FitnessAgeComponent]
    invalid_reason: str | None
    raw: Mapping[str, Any] = field(repr=False)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> FitnessAge:
        """Build the fitness age from the decoded JSON body."""
        components = {
            name: FitnessAgeComponent(
                value=opt_float(item, "value"),
                target_value=opt_float(item, "targetValue"),
                potential_age=opt_float(item, "potentialAge"),
                stale=opt_bool(item, "stale"),
                raw=item,
            )
            for name, item in opt_obj(data, "components").items()
            if isinstance(item, Mapping)
        }
        return cls(
            fitness_age=opt_float(data, "fitnessAge"),
            chronological_age=opt_int(data, "chronologicalAge"),
            achievable_fitness_age=opt_float(data, "achievableFitnessAge"),
            previous_fitness_age=opt_float(data, "previousFitnessAge"),
            components=components,
            invalid_reason=opt_str(data, "invalidReason"),
            raw=data,
        )


@dataclass(frozen=True, kw_only=True)
class HeartRateZones:
    """Heart rate zones for one sport, from `/biometric-service/heartRateZones/v2`.

    `sport` is `DEFAULT` for the zones used by sports without their own. `zone_floors`
    holds the lower bound of zones 1 to 5 in beats per minute.
    """

    sport: str | None
    training_method: str | None
    zone_floors: tuple[int | None, int | None, int | None, int | None, int | None]
    max_heart_rate: int | None
    resting_heart_rate: int | None
    lactate_threshold_heart_rate: int | None
    raw: Mapping[str, Any] = field(repr=False)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> HeartRateZones:
        """Build the zones from one element of the decoded JSON array."""
        return cls(
            sport=opt_str(data, "sport"),
            training_method=opt_str(data, "trainingMethod"),
            zone_floors=(
                opt_int(data, "zone1Floor"),
                opt_int(data, "zone2Floor"),
                opt_int(data, "zone3Floor"),
                opt_int(data, "zone4Floor"),
                opt_int(data, "zone5Floor"),
            ),
            max_heart_rate=opt_int(data, "maxHeartRateUsed"),
            resting_heart_rate=opt_int(data, "restingHeartRateUsed"),
            lactate_threshold_heart_rate=opt_int(data, "lactateThresholdHeartRateUsed"),
            raw=data,
        )
