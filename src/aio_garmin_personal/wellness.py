"""Typed views of the sleep, heart, stress, Body Battery and daily statistics responses.

Each model types the fields a caller is likely to use and keeps the whole object in `raw`.
Times end in `_time_gmt` and are timezone-aware UTC. The wall-clock times in the account's
time zone are only in `raw`.
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
    opt_gmt_datetime,
    opt_int,
    opt_obj,
    opt_objs,
    opt_str,
    req_date,
    series,
)


@dataclass(frozen=True, kw_only=True)
class DailySleep:
    """One night from `/sleep-service/sleep/dailySleep` or `dailySleepSummariesByDate`.

    `calendar_date` is the day the sleep ended on. Durations are in seconds.
    `sleep_need_minutes` is Garmin's estimate of the sleep needed for that day.
    """

    calendar_date: date
    sleep_start_time_gmt: datetime | None
    sleep_end_time_gmt: datetime | None
    sleep_seconds: int | None
    nap_seconds: int | None
    deep_sleep_seconds: int | None
    light_sleep_seconds: int | None
    rem_sleep_seconds: int | None
    awake_sleep_seconds: int | None
    unmeasurable_sleep_seconds: int | None
    awake_count: int | None
    score: int | None
    score_qualifier: str | None
    average_heart_rate: float | None
    average_respiration: float | None
    average_spo2: float | None
    lowest_spo2: int | None
    average_stress: float | None
    sleep_need_minutes: int | None
    window_confirmed: bool | None
    raw: Mapping[str, Any] = field(repr=False)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DailySleep:
        """Build the night from one decoded sleep object.

        Raises:
            GarminPersonalResponseError: `calendarDate` is missing or malformed.
        """
        overall = opt_obj(opt_obj(data, "sleepScores"), "overall")
        return cls(
            calendar_date=req_date(data, "calendarDate", "Sleep"),
            sleep_start_time_gmt=opt_epoch_ms(data, "sleepStartTimestampGMT"),
            sleep_end_time_gmt=opt_epoch_ms(data, "sleepEndTimestampGMT"),
            sleep_seconds=opt_int(data, "sleepTimeSeconds"),
            nap_seconds=opt_int(data, "napTimeSeconds"),
            deep_sleep_seconds=opt_int(data, "deepSleepSeconds"),
            light_sleep_seconds=opt_int(data, "lightSleepSeconds"),
            rem_sleep_seconds=opt_int(data, "remSleepSeconds"),
            awake_sleep_seconds=opt_int(data, "awakeSleepSeconds"),
            unmeasurable_sleep_seconds=opt_int(data, "unmeasurableSleepSeconds"),
            awake_count=opt_int(data, "awakeCount"),
            score=opt_int(overall, "value"),
            score_qualifier=opt_str(overall, "qualifierKey"),
            average_heart_rate=opt_float(data, "avgHeartRate"),
            average_respiration=opt_float(data, "averageRespirationValue"),
            average_spo2=opt_float(data, "averageSpO2Value"),
            lowest_spo2=opt_int(data, "lowestSpO2Value"),
            average_stress=opt_float(data, "avgSleepStress"),
            sleep_need_minutes=opt_int(opt_obj(data, "sleepNeed"), "actual"),
            window_confirmed=opt_bool(data, "sleepWindowConfirmed"),
            raw=data,
        )


@dataclass(frozen=True, kw_only=True)
class HrvSummary:
    """Overnight heart rate variability for one day, in milliseconds.

    `status` is Garmin's assessment against the personal baseline, for example
    `BALANCED`. The `baseline_*` fields are the boundaries of the baseline ranges.
    """

    calendar_date: date
    last_night_average: int | None
    last_night_5_min_high: int | None
    weekly_average: int | None
    status: str | None
    feedback_phrase: str | None
    baseline_low_upper: int | None
    baseline_balanced_low: int | None
    baseline_balanced_upper: int | None
    raw: Mapping[str, Any] = field(repr=False)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> HrvSummary:
        """Build the summary from one decoded HRV summary object.

        Raises:
            GarminPersonalResponseError: `calendarDate` is missing or malformed.
        """
        baseline = opt_obj(data, "baseline")
        return cls(
            calendar_date=req_date(data, "calendarDate", "HRV summary"),
            last_night_average=opt_int(data, "lastNightAvg"),
            last_night_5_min_high=opt_int(data, "lastNight5MinHigh"),
            weekly_average=opt_int(data, "weeklyAvg"),
            status=opt_str(data, "status"),
            feedback_phrase=opt_str(data, "feedbackPhrase"),
            baseline_low_upper=opt_int(baseline, "lowUpper"),
            baseline_balanced_low=opt_int(baseline, "balancedLow"),
            baseline_balanced_upper=opt_int(baseline, "balancedUpper"),
            raw=data,
        )


@dataclass(frozen=True, kw_only=True)
class HrvReading:
    """One HRV measurement taken during sleep, in milliseconds."""

    time_gmt: datetime
    value: int


@dataclass(frozen=True, kw_only=True)
class DailyHrv:
    """One night of HRV from `/hrv-service/hrv/{calendarDate}`, with every reading."""

    summary: HrvSummary | None
    readings: list[HrvReading]
    sleep_start_time_gmt: datetime | None
    sleep_end_time_gmt: datetime | None
    raw: Mapping[str, Any] = field(repr=False)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DailyHrv:
        """Build the night from the decoded JSON body; unusable readings are skipped."""
        summary = data.get("hrvSummary")
        readings = []
        for item in opt_objs(data, "hrvReadings"):
            time_gmt = opt_gmt_datetime(item, "readingTimeGMT")
            value = opt_int(item, "hrvValue")
            if time_gmt is not None and value is not None:
                readings.append(HrvReading(time_gmt=time_gmt, value=value))
        return cls(
            summary=HrvSummary.from_dict(summary)
            if isinstance(summary, Mapping)
            else None,
            readings=readings,
            sleep_start_time_gmt=opt_gmt_datetime(data, "sleepStartTimestampGMT"),
            sleep_end_time_gmt=opt_gmt_datetime(data, "sleepEndTimestampGMT"),
            raw=data,
        )


@dataclass(frozen=True, kw_only=True)
class HeartRateSample:
    """One heart rate reading in beats per minute."""

    time_gmt: datetime
    bpm: int


@dataclass(frozen=True, kw_only=True)
class DailyHeartRate:
    """One day of heart rate from `/wellness-service/wellness/dailyHeartRate`.

    `samples` holds the day's readings in time order; intervals without a reading are left
    out. A day without data has every field `None` and no samples.
    """

    calendar_date: date | None
    resting_heart_rate: int | None
    min_heart_rate: int | None
    max_heart_rate: int | None
    last_seven_days_avg_resting_heart_rate: int | None
    samples: list[HeartRateSample]
    raw: Mapping[str, Any] = field(repr=False)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DailyHeartRate:
        """Build the day from the decoded JSON body."""
        points = series(
            data,
            rows_field="heartRateValues",
            descriptors_field="heartRateValueDescriptors",
            index_field="index",
            name_field="key",
            value_field="heartrate",
        )
        return cls(
            calendar_date=opt_date(data, "calendarDate"),
            resting_heart_rate=opt_int(data, "restingHeartRate"),
            min_heart_rate=opt_int(data, "minHeartRate"),
            max_heart_rate=opt_int(data, "maxHeartRate"),
            last_seven_days_avg_resting_heart_rate=opt_int(
                data, "lastSevenDaysAvgRestingHeartRate"
            ),
            samples=[
                HeartRateSample(time_gmt=when, bpm=int(value)) for when, value in points
            ],
            raw=data,
        )


@dataclass(frozen=True, kw_only=True)
class BodyBatterySample:
    """One Body Battery level on the 0 to 100 scale."""

    time_gmt: datetime
    level: int


@dataclass(frozen=True, kw_only=True)
class BodyBatteryEvent:
    """Something that charged or drained Body Battery, such as sleep or an activity.

    `impact` is the change it caused on the 0 to 100 scale.
    """

    event_type: str | None
    start_time_gmt: datetime | None
    duration_ms: int | None
    impact: int | None
    feedback_type: str | None


@dataclass(frozen=True, kw_only=True)
class DailyBodyBattery:
    """One day from `/wellness-service/wellness/bodyBattery/reports/daily`."""

    calendar_date: date
    charged: int | None
    drained: int | None
    levels: list[BodyBatterySample]
    events: list[BodyBatteryEvent]
    raw: Mapping[str, Any] = field(repr=False)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DailyBodyBattery:
        """Build the day from one element of the decoded JSON array.

        Raises:
            GarminPersonalResponseError: `date` is missing or malformed.
        """
        points = series(
            data,
            rows_field="bodyBatteryValuesArray",
            descriptors_field="bodyBatteryValueDescriptorDTOList",
            index_field="bodyBatteryValueDescriptorIndex",
            name_field="bodyBatteryValueDescriptorKey",
            value_field="bodyBatteryLevel",
        )
        return cls(
            calendar_date=req_date(data, "date", "Body Battery report"),
            charged=opt_int(data, "charged"),
            drained=opt_int(data, "drained"),
            levels=[
                BodyBatterySample(time_gmt=when, level=int(value))
                for when, value in points
            ],
            events=[
                BodyBatteryEvent(
                    event_type=opt_str(event, "eventType"),
                    start_time_gmt=opt_gmt_datetime(event, "eventStartTimeGmt"),
                    duration_ms=opt_int(event, "durationInMilliseconds"),
                    impact=opt_int(event, "bodyBatteryImpact"),
                    feedback_type=opt_str(event, "feedbackType"),
                )
                for event in opt_objs(data, "bodyBatteryActivityEvent")
            ],
            raw=data,
        )


@dataclass(frozen=True, kw_only=True)
class SpO2Sample:
    """One blood oxygen saturation value in percent."""

    time_gmt: datetime
    value: float


@dataclass(frozen=True, kw_only=True)
class DailySpO2:
    """One day from `/wellness-service/wellness/daily/spo2acclimation/{calendarDate}`.

    Values are blood oxygen saturation in percent. `hourly_averages` holds one value per
    hour that had readings. A day without data has every field `None`.
    """

    calendar_date: date | None
    average: float | None
    lowest: int | None
    latest: int | None
    latest_time_gmt: datetime | None
    average_during_sleep: float | None
    last_seven_days_average: float | None
    hourly_averages: list[SpO2Sample]
    raw: Mapping[str, Any] = field(repr=False)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DailySpO2:
        """Build the day from the decoded JSON body."""
        points = series(
            data,
            rows_field="spO2HourlyAverages",
            descriptors_field="spO2HourlyAveragesDescriptorList",
            index_field="spo2ValueDescIndex",
            name_field="spo2ValueDescKey",
            value_field="spo2Level",
        )
        return cls(
            calendar_date=opt_date(data, "calendarDate"),
            average=opt_float(data, "averageSpO2"),
            lowest=opt_int(data, "lowestSpO2"),
            latest=opt_int(data, "latestSpO2"),
            latest_time_gmt=opt_gmt_datetime(data, "latestSpO2TimestampGMT"),
            average_during_sleep=opt_float(data, "avgSleepSpO2"),
            last_seven_days_average=opt_float(data, "lastSevenDaysAvgSpO2"),
            hourly_averages=[
                SpO2Sample(time_gmt=when, value=float(value)) for when, value in points
            ],
            raw=data,
        )


@dataclass(frozen=True, kw_only=True)
class DailySteps:
    """One day from `/usersummary-service/stats/steps/daily/{startDate}/{endDate}`."""

    calendar_date: date
    total_steps: int | None
    total_distance_meters: int | None
    step_goal: int | None
    raw: Mapping[str, Any] = field(repr=False)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DailySteps:
        """Build the day from one element of the decoded JSON array.

        Raises:
            GarminPersonalResponseError: `calendarDate` is missing or malformed.
        """
        return cls(
            calendar_date=req_date(data, "calendarDate", "Daily steps"),
            total_steps=opt_int(data, "totalSteps"),
            total_distance_meters=opt_int(data, "totalDistance"),
            step_goal=opt_int(data, "stepGoal"),
            raw=data,
        )


@dataclass(frozen=True, kw_only=True)
class DailyStress:
    """One day from `/usersummary-service/stats/stress/daily/{startDate}/{endDate}`.

    `overall_level` is on Garmin's 0 to 100 stress scale; durations are in seconds.
    """

    calendar_date: date
    overall_level: int | None
    rest_seconds: int | None
    low_stress_seconds: int | None
    medium_stress_seconds: int | None
    high_stress_seconds: int | None
    raw: Mapping[str, Any] = field(repr=False)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DailyStress:
        """Build the day from one element of the decoded JSON array.

        Raises:
            GarminPersonalResponseError: `calendarDate` is missing or malformed.
        """
        values = opt_obj(data, "values")
        return cls(
            calendar_date=req_date(data, "calendarDate", "Daily stress"),
            overall_level=opt_int(values, "overallStressLevel"),
            rest_seconds=opt_int(values, "restStressDuration"),
            low_stress_seconds=opt_int(values, "lowStressDuration"),
            medium_stress_seconds=opt_int(values, "mediumStressDuration"),
            high_stress_seconds=opt_int(values, "highStressDuration"),
            raw=data,
        )


@dataclass(frozen=True, kw_only=True)
class DailyHydration:
    """One day from `/usersummary-service/stats/hydration/daily/{startDate}/{endDate}`.

    Volumes are in millilitres. Typed from Garmin's API description: not yet checked
    against an account that logs hydration.
    """

    calendar_date: date
    intake_ml: float | None
    goal_ml: float | None
    sweat_loss_ml: float | None
    activity_intake_ml: float | None
    raw: Mapping[str, Any] = field(repr=False)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DailyHydration:
        """Build the day from one element of the decoded JSON array.

        Raises:
            GarminPersonalResponseError: `calendarDate` is missing or malformed.
        """
        return cls(
            calendar_date=req_date(data, "calendarDate", "Daily hydration"),
            intake_ml=opt_float(data, "valueInML"),
            goal_ml=opt_float(data, "goalInML"),
            sweat_loss_ml=opt_float(data, "sweatLossInML"),
            activity_intake_ml=opt_float(data, "activityIntakeInML"),
            raw=data,
        )


@dataclass(frozen=True, kw_only=True)
class DailyOverview:
    """One day from `/usersummary-service/v2/dailysummaries`.

    The same totals as `DailySummary`, grouped differently and available for a range of
    days. Calories are kilocalories, distances metres, and stress on the 0 to 100 scale.
    Totals cover the day up to the last sync.
    """

    calendar_date: date
    includes_wellness_data: bool | None
    includes_activity_data: bool | None
    total_kilocalories: int | None
    active_kilocalories: int | None
    resting_kilocalories: int | None
    steps: int | None
    step_goal: int | None
    total_distance_meters: float | None
    floors_ascended: int | None
    floors_descended: int | None
    moderate_intensity_minutes: int | None
    vigorous_intensity_minutes: int | None
    intensity_minutes_goal: int | None
    resting_heart_rate: int | None
    min_heart_rate: int | None
    max_heart_rate: int | None
    average_stress_level: int | None
    max_stress_level: int | None
    body_battery_latest: int | None
    body_battery_highest: int | None
    body_battery_lowest: int | None
    body_battery_charged: int | None
    body_battery_drained: int | None
    average_spo2: int | None
    lowest_spo2: int | None
    average_respiration: int | None
    hydration_ml: int | None
    hydration_goal_ml: int | None
    raw: Mapping[str, Any] = field(repr=False)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DailyOverview:
        """Build the day from one element of the response's `data` array.

        Raises:
            GarminPersonalResponseError: `calendarDate` is missing or malformed.
        """
        calories = opt_obj(data, "calories")
        movement = opt_obj(data, "movement")
        steps = opt_obj(movement, "steps")
        intensity = opt_obj(data, "intensityMinutes")
        heart_rate = opt_obj(data, "heartRate")
        stress = opt_obj(data, "stress")
        body_battery = opt_obj(data, "bodyBattery")
        pulse_ox = opt_obj(data, "pulseOx")
        hydration = opt_obj(data, "hydration")
        return cls(
            calendar_date=req_date(data, "calendarDate", "Daily overview"),
            includes_wellness_data=opt_bool(data, "includesWellnessData"),
            includes_activity_data=opt_bool(data, "includesActivityData"),
            total_kilocalories=opt_int(calories, "burnedTotal"),
            active_kilocalories=opt_int(calories, "burnedActive"),
            resting_kilocalories=opt_int(calories, "burnedResting"),
            steps=opt_int(steps, "value"),
            step_goal=opt_int(steps, "goal"),
            total_distance_meters=opt_float(steps, "distanceInMeters"),
            floors_ascended=opt_int(opt_obj(movement, "floorsAscended"), "value"),
            floors_descended=opt_int(opt_obj(movement, "floorsDescended"), "value"),
            moderate_intensity_minutes=opt_int(intensity, "moderate"),
            vigorous_intensity_minutes=opt_int(intensity, "vigorous"),
            intensity_minutes_goal=opt_int(intensity, "goal"),
            resting_heart_rate=opt_int(heart_rate, "restingValue"),
            min_heart_rate=opt_int(heart_rate, "minValue"),
            max_heart_rate=opt_int(heart_rate, "maxValue"),
            average_stress_level=opt_int(stress, "avgLevel"),
            max_stress_level=opt_int(stress, "maxLevel"),
            body_battery_latest=opt_int(body_battery, "latestValue"),
            body_battery_highest=opt_int(body_battery, "maxValue"),
            body_battery_lowest=opt_int(body_battery, "minValue"),
            body_battery_charged=opt_int(body_battery, "chargedValue"),
            body_battery_drained=opt_int(body_battery, "drainedValue"),
            average_spo2=opt_int(pulse_ox, "avgValue"),
            lowest_spo2=opt_int(pulse_ox, "minValue"),
            average_respiration=opt_int(opt_obj(data, "respiration"), "avgValue"),
            hydration_ml=opt_int(hydration, "consumedInMl"),
            hydration_goal_ml=opt_int(hydration, "goalInMl"),
            raw=data,
        )


@dataclass(frozen=True, kw_only=True)
class WellnessActivity:
    """A session recorded outside the activity list, such as a breathwork or relax session.

    From `/wellnessactivity-service/activity/summary/range/{fromDate}/{untilDate}`.
    `activity_type` is Garmin's key for the kind of session.
    """

    activity_name: str | None
    activity_type: str | None
    calendar_date: date | None
    start_time_gmt: datetime | None
    end_time_gmt: datetime | None
    raw: Mapping[str, Any] = field(repr=False)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> WellnessActivity:
        """Build the session from one element of the decoded JSON array."""
        return cls(
            activity_name=opt_str(data, "activityName"),
            activity_type=opt_str(data, "wellnessActivityType"),
            calendar_date=opt_date(data, "calendarDate"),
            start_time_gmt=opt_gmt_datetime(data, "startTimestampGMT"),
            end_time_gmt=opt_gmt_datetime(data, "endTimestampGMT"),
            raw=data,
        )
