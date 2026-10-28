from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime
from typing import Any

import pytest

from aio_garmin_personal import (
    BodyBatteryEvent,
    DailyHeartRate,
    GarminPersonalClient,
    GarminPersonalResponseError,
    HeartRateSample,
    HrvReading,
)

from .conftest import FakeGarmin, Reply, load_fixture

DAY = date(2026, 10, 22)
START = date(2026, 10, 21)

SLEEP_PATH = "/sleep-service/sleep/dailySleep"
SLEEP_RANGE_PATH = "/sleep-service/sleep/dailySleepSummariesByDate"
HRV_PATH = "/hrv-service/hrv/2026-10-22"
HRV_RANGE_PATH = "/hrv-service/hrv/daily/2026-10-21/2026-10-22"
HEART_RATE_PATH = "/wellness-service/wellness/dailyHeartRate"
BODY_BATTERY_PATH = "/wellness-service/wellness/bodyBattery/reports/daily"
SPO2_PATH = "/wellness-service/wellness/daily/spo2acclimation/2026-10-22"
STEPS_PATH = "/usersummary-service/stats/steps/daily/2026-10-21/2026-10-22"
STRESS_PATH = "/usersummary-service/stats/stress/daily/2026-10-21/2026-10-22"
HYDRATION_PATH = "/usersummary-service/stats/hydration/daily/2026-10-21/2026-10-22"
OVERVIEWS_PATH = "/usersummary-service/v2/dailysummaries"
WELLNESS_ACTIVITIES_PATH = (
    "/wellnessactivity-service/activity/summary/range/2026-10-21/2026-10-22"
)

Call = Callable[[GarminPersonalClient], Awaitable[Any]]

SINGLE_DAY: dict[str, tuple[Call, str]] = {
    "sleep": (lambda c: c.async_get_sleep(DAY), SLEEP_PATH),
    "hrv": (lambda c: c.async_get_hrv(DAY), HRV_PATH),
    "heart_rate": (lambda c: c.async_get_heart_rate(DAY), HEART_RATE_PATH),
    "spo2": (lambda c: c.async_get_spo2(DAY), SPO2_PATH),
}
RANGES: dict[
    str, tuple[Callable[[GarminPersonalClient, date, date], Awaitable[Any]], str]
] = {
    "sleep_range": (lambda c, s, e: c.async_get_sleep_range(s, e), SLEEP_RANGE_PATH),
    "hrv_summaries": (lambda c, s, e: c.async_get_hrv_summaries(s, e), HRV_RANGE_PATH),
    "body_battery": (lambda c, s, e: c.async_get_body_battery(s, e), BODY_BATTERY_PATH),
    "daily_steps": (lambda c, s, e: c.async_get_daily_steps(s, e), STEPS_PATH),
    "daily_stress": (lambda c, s, e: c.async_get_daily_stress(s, e), STRESS_PATH),
    "daily_hydration": (
        lambda c, s, e: c.async_get_daily_hydration(s, e),
        HYDRATION_PATH,
    ),
    "daily_overviews": (
        lambda c, s, e: c.async_get_daily_overviews(s, e),
        OVERVIEWS_PATH,
    ),
    "wellness_activities": (
        lambda c, s, e: c.async_get_wellness_activities(s, e),
        WELLNESS_ACTIVITIES_PATH,
    ),
}


def utc(year: int, month: int, day: int, hour: int, minute: int) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=UTC)


async def test_sleep_is_parsed(
    client: GarminPersonalClient, garmin: FakeGarmin, token: str
) -> None:
    garmin.add("GET", SLEEP_PATH, Reply(body=load_fixture("sleep.json")))

    sleep = await client.async_get_sleep(DAY)

    assert sleep is not None
    assert sleep.calendar_date == DAY
    assert sleep.sleep_start_time_gmt == utc(2026, 10, 21, 21, 30)
    assert sleep.sleep_end_time_gmt == utc(2026, 10, 22, 5, 0)
    assert sleep.sleep_seconds == 27000
    assert sleep.nap_seconds == 0
    assert sleep.deep_sleep_seconds == 5400
    assert sleep.light_sleep_seconds == 15600
    assert sleep.rem_sleep_seconds == 6000
    assert sleep.awake_sleep_seconds == 900
    assert sleep.unmeasurable_sleep_seconds == 0
    assert sleep.awake_count == 2
    assert sleep.score == 81
    assert sleep.score_qualifier == "GOOD"
    assert sleep.average_heart_rate == 51.0
    assert sleep.average_respiration == 14.0
    assert sleep.average_spo2 == 94.0
    assert sleep.lowest_spo2 == 88
    assert sleep.average_stress == 15.0
    assert sleep.sleep_need_minutes == 500
    assert sleep.window_confirmed is True
    (call,) = garmin.calls("GET", SLEEP_PATH)
    assert call.query == {"date": "2026-10-22"}


async def test_day_without_sleep_is_none(
    client: GarminPersonalClient, garmin: FakeGarmin, token: str
) -> None:
    garmin.add("GET", SLEEP_PATH, Reply(body=load_fixture("sleep_empty.json")))

    assert await client.async_get_sleep(DAY) is None


async def test_sleep_range_is_parsed(
    client: GarminPersonalClient, garmin: FakeGarmin, token: str
) -> None:
    garmin.add("GET", SLEEP_RANGE_PATH, Reply(body=load_fixture("sleep_range.json")))

    first, second = await client.async_get_sleep_range(START, DAY)

    assert (first.calendar_date, first.score) == (START, 74)
    assert (second.calendar_date, second.score) == (DAY, 81)
    (call,) = garmin.calls("GET", SLEEP_RANGE_PATH)
    assert call.query == {"startDate": "2026-10-21", "endDate": "2026-10-22"}


async def test_sleep_range_leaves_out_days_without_sleep(
    client: GarminPersonalClient, garmin: FakeGarmin, token: str
) -> None:
    garmin.add(
        "GET",
        SLEEP_RANGE_PATH,
        Reply(
            body=f"[{load_fixture('sleep_empty.json')}, {load_fixture('sleep.json')}]"
        ),
    )

    (night,) = await client.async_get_sleep_range(START, DAY)

    assert night.calendar_date == DAY


async def test_hrv_is_parsed(
    client: GarminPersonalClient, garmin: FakeGarmin, token: str
) -> None:
    garmin.add("GET", HRV_PATH, Reply(body=load_fixture("hrv.json")))

    hrv = await client.async_get_hrv(DAY)

    assert hrv is not None
    assert hrv.summary is not None
    assert hrv.summary.calendar_date == DAY
    assert hrv.summary.last_night_average == 52
    assert hrv.summary.last_night_5_min_high == 71
    assert hrv.summary.weekly_average == 48
    assert hrv.summary.status == "BALANCED"
    assert hrv.summary.feedback_phrase == "HRV_BALANCED_2"
    assert hrv.summary.baseline_low_upper == 38
    assert hrv.summary.baseline_balanced_low == 42
    assert hrv.summary.baseline_balanced_upper == 58
    # The reading without a value is skipped.
    assert hrv.readings == [
        HrvReading(time_gmt=utc(2026, 10, 21, 21, 35), value=49),
        HrvReading(time_gmt=utc(2026, 10, 21, 21, 40), value=55),
    ]
    assert hrv.sleep_start_time_gmt == utc(2026, 10, 21, 21, 30)
    assert hrv.sleep_end_time_gmt == utc(2026, 10, 22, 5, 0)


async def test_day_without_hrv_is_none(
    client: GarminPersonalClient, garmin: FakeGarmin, token: str
) -> None:
    garmin.add("GET", HRV_PATH, Reply(status=204))

    assert await client.async_get_hrv(DAY) is None


async def test_hrv_without_summary(
    client: GarminPersonalClient, garmin: FakeGarmin, token: str
) -> None:
    garmin.add("GET", HRV_PATH, Reply(body='{"hrvSummary": null, "hrvReadings": null}'))

    hrv = await client.async_get_hrv(DAY)

    assert hrv is not None
    assert hrv.summary is None
    assert hrv.readings == []


async def test_hrv_summaries_are_parsed(
    client: GarminPersonalClient, garmin: FakeGarmin, token: str
) -> None:
    garmin.add("GET", HRV_RANGE_PATH, Reply(body=load_fixture("hrv_summaries.json")))

    first, second = await client.async_get_hrv_summaries(START, DAY)

    assert (first.calendar_date, first.last_night_average, first.status) == (
        START,
        45,
        "UNBALANCED",
    )
    assert (second.calendar_date, second.last_night_average, second.status) == (
        DAY,
        52,
        "BALANCED",
    )


async def test_heart_rate_is_parsed(
    client: GarminPersonalClient, garmin: FakeGarmin, token: str
) -> None:
    garmin.add("GET", HEART_RATE_PATH, Reply(body=load_fixture("heart_rate.json")))

    day = await client.async_get_heart_rate(DAY)

    assert day is not None
    assert day.calendar_date == DAY
    assert day.resting_heart_rate == 53
    assert day.min_heart_rate == 46
    assert day.max_heart_rate == 142
    assert day.last_seven_days_avg_resting_heart_rate == 54
    # The interval without a reading is left out.
    assert day.samples == [
        HeartRateSample(time_gmt=utc(2026, 10, 21, 22, 0), bpm=58),
        HeartRateSample(time_gmt=utc(2026, 10, 21, 22, 4), bpm=55),
    ]
    (call,) = garmin.calls("GET", HEART_RATE_PATH)
    assert call.query == {"date": "2026-10-22"}


async def test_heart_rate_day_without_data(
    client: GarminPersonalClient, garmin: FakeGarmin, token: str
) -> None:
    garmin.add(
        "GET", HEART_RATE_PATH, Reply(body=load_fixture("heart_rate_empty.json"))
    )

    day = await client.async_get_heart_rate(date(2026, 10, 25))

    assert day is not None
    assert day.calendar_date == date(2026, 10, 25)
    assert day.resting_heart_rate is None
    assert day.samples == []


@pytest.mark.parametrize(
    ("descriptors", "rows"),
    [
        ([{"key": "timestamp", "index": 0}, {"key": "heartrate", "index": 1}], [[1]]),
        (
            [{"key": "timestamp", "index": 0}, {"key": "heartrate", "index": 1}],
            [[1, True]],
        ),
        (
            [{"key": "timestamp", "index": 0}, {"key": "heartrate", "index": 1}],
            [[None, 60]],
        ),
        (
            [{"key": "timestamp", "index": 0}, {"key": "heartrate", "index": 1}],
            [[10**20, 60]],
        ),
        ([{"key": "timestamp", "index": 0}, {"key": "heartrate", "index": 1}], ["ab"]),
        ([{"key": "timestamp", "index": 0}], [[1_800_000_000_000, 60]]),
        ([{"key": "timestamp"}, {"key": "heartrate", "index": 1}], [[1, 60]]),
        (None, [[1_800_000_000_000, 60]]),
    ],
    ids=[
        "short-row",
        "bool-value",
        "no-timestamp",
        "timestamp-out-of-range",
        "row-not-a-list",
        "no-value-column",
        "descriptor-without-index",
        "no-descriptors",
    ],
)
def test_unusable_heart_rate_rows_are_skipped(descriptors: Any, rows: Any) -> None:
    day = DailyHeartRate.from_dict(
        {"heartRateValueDescriptors": descriptors, "heartRateValues": rows}
    )

    assert day.samples == []


async def test_body_battery_is_parsed(
    client: GarminPersonalClient, garmin: FakeGarmin, token: str
) -> None:
    garmin.add("GET", BODY_BATTERY_PATH, Reply(body=load_fixture("body_battery.json")))

    (day,) = await client.async_get_body_battery(START, DAY)

    assert day.calendar_date == DAY
    assert day.charged == 61
    assert day.drained == 48
    assert [(s.time_gmt, s.level) for s in day.levels] == [
        (utc(2026, 10, 21, 22, 0), 30),
        (utc(2026, 10, 22, 5, 0), 86),
    ]
    assert day.events == [
        BodyBatteryEvent(
            event_type="SLEEP",
            start_time_gmt=utc(2026, 10, 21, 21, 30),
            duration_ms=27_000_000,
            impact=56,
            feedback_type="NONE",
        )
    ]
    (call,) = garmin.calls("GET", BODY_BATTERY_PATH)
    assert call.query == {"startDate": "2026-10-21", "endDate": "2026-10-22"}


async def test_spo2_is_parsed(
    client: GarminPersonalClient, garmin: FakeGarmin, token: str
) -> None:
    garmin.add("GET", SPO2_PATH, Reply(body=load_fixture("spo2.json")))

    day = await client.async_get_spo2(DAY)

    assert day is not None
    assert day.calendar_date == DAY
    assert day.average == 95.0
    assert day.lowest == 87
    assert day.latest == 96
    assert day.latest_time_gmt == utc(2026, 10, 22, 5, 0)
    assert day.average_during_sleep == 94.0
    assert day.last_seven_days_average == 94.5
    assert [(s.time_gmt, s.value) for s in day.hourly_averages] == [
        (utc(2026, 10, 21, 22, 0), 95.0),
        (utc(2026, 10, 21, 23, 0), 93.5),
    ]


async def test_daily_steps_are_parsed(
    client: GarminPersonalClient, garmin: FakeGarmin, token: str
) -> None:
    garmin.add("GET", STEPS_PATH, Reply(body=load_fixture("daily_steps.json")))

    first, second = await client.async_get_daily_steps(START, DAY)

    assert (
        first.calendar_date,
        first.total_steps,
        first.total_distance_meters,
        first.step_goal,
    ) == (START, 9120, 7140, 8000)
    assert (second.calendar_date, second.total_steps) == (DAY, 4310)


async def test_daily_stress_is_parsed(
    client: GarminPersonalClient, garmin: FakeGarmin, token: str
) -> None:
    garmin.add("GET", STRESS_PATH, Reply(body=load_fixture("daily_stress.json")))

    (day,) = await client.async_get_daily_stress(START, DAY)

    assert day.calendar_date == DAY
    assert day.overall_level == 27
    assert day.rest_seconds == 30000
    assert day.low_stress_seconds == 18000
    assert day.medium_stress_seconds == 7200
    assert day.high_stress_seconds == 1800


async def test_daily_hydration_is_parsed(
    client: GarminPersonalClient, garmin: FakeGarmin, token: str
) -> None:
    garmin.add("GET", HYDRATION_PATH, Reply(body=load_fixture("daily_hydration.json")))

    (day,) = await client.async_get_daily_hydration(START, DAY)

    assert day.calendar_date == DAY
    assert day.intake_ml == 1750.0
    assert day.goal_ml == 2500.0
    assert day.sweat_loss_ml == 420.0
    assert day.activity_intake_ml == 500.0


async def test_daily_overviews_are_parsed(
    client: GarminPersonalClient, garmin: FakeGarmin, token: str
) -> None:
    garmin.add("GET", OVERVIEWS_PATH, Reply(body=load_fixture("daily_overviews.json")))

    (day,) = await client.async_get_daily_overviews(START, DAY)

    assert day.calendar_date == DAY
    assert day.includes_wellness_data is True
    assert day.includes_activity_data is True
    assert day.total_kilocalories == 2260
    assert day.active_kilocalories == 610
    assert day.resting_kilocalories == 1650
    assert day.steps == 9120
    assert day.step_goal == 8000
    assert day.total_distance_meters == 7140.0
    assert day.floors_ascended == 6
    assert day.floors_descended == 5
    assert day.moderate_intensity_minutes == 20
    assert day.vigorous_intensity_minutes == 15
    assert day.intensity_minutes_goal == 150
    assert day.resting_heart_rate == 53
    assert day.min_heart_rate == 46
    assert day.max_heart_rate == 142
    assert day.average_stress_level == 27
    assert day.max_stress_level == 91
    assert day.body_battery_latest == 38
    assert day.body_battery_highest == 86
    assert day.body_battery_lowest == 25
    assert day.body_battery_charged == 61
    assert day.body_battery_drained == 48
    assert day.average_spo2 == 95
    assert day.lowest_spo2 == 87
    assert day.average_respiration == 14
    assert day.hydration_ml == 0
    assert day.hydration_goal_ml == 2500
    (call,) = garmin.calls("GET", OVERVIEWS_PATH)
    assert call.query == {"startDate": "2026-10-21", "endDate": "2026-10-22"}


async def test_wellness_activities_are_parsed(
    client: GarminPersonalClient, garmin: FakeGarmin, token: str
) -> None:
    garmin.add(
        "GET",
        WELLNESS_ACTIVITIES_PATH,
        Reply(body=load_fixture("wellness_activities.json")),
    )

    (session,) = await client.async_get_wellness_activities(START, DAY)

    assert session.activity_name == "Breathwork"
    assert session.activity_type == "BREATHWORK"
    assert session.calendar_date == DAY
    assert session.start_time_gmt == utc(2026, 10, 22, 19, 0)
    assert session.end_time_gmt == utc(2026, 10, 22, 19, 10)


@pytest.mark.parametrize("name", RANGES)
async def test_reversed_range_is_rejected_without_a_request(
    client: GarminPersonalClient, garmin: FakeGarmin, name: str
) -> None:
    call, _ = RANGES[name]

    with pytest.raises(ValueError, match="start must not be after end"):
        await call(client, DAY, START)

    assert garmin.requests == []


@pytest.mark.parametrize("name", RANGES)
async def test_single_day_range_is_allowed(
    client: GarminPersonalClient, garmin: FakeGarmin, token: str, name: str
) -> None:
    call, path = RANGES[name]
    single_day_path = path.replace("2026-10-21", "2026-10-22")
    garmin.add("GET", single_day_path, Reply(status=204))

    assert await call(client, DAY, DAY) == []
    assert len(garmin.calls("GET", single_day_path)) == 1


@pytest.mark.parametrize("name", RANGES)
async def test_empty_range_body_is_an_empty_list(
    client: GarminPersonalClient, garmin: FakeGarmin, token: str, name: str
) -> None:
    call, path = RANGES[name]
    garmin.add("GET", path, Reply(status=200))

    assert await call(client, START, DAY) == []


@pytest.mark.parametrize("name", ["sleep", "hrv", "heart_rate", "spo2"])
async def test_empty_single_day_body_is_none(
    client: GarminPersonalClient, garmin: FakeGarmin, token: str, name: str
) -> None:
    call, path = SINGLE_DAY[name]
    garmin.add("GET", path, Reply(status=204))

    assert await call(client) is None


@pytest.mark.parametrize("name", SINGLE_DAY)
async def test_single_day_array_raises_response_error(
    client: GarminPersonalClient, garmin: FakeGarmin, token: str, name: str
) -> None:
    call, path = SINGLE_DAY[name]
    garmin.add("GET", path, Reply(body="[]"))

    with pytest.raises(GarminPersonalResponseError, match="is not an object"):
        await call(client)


@pytest.mark.parametrize(
    ("name", "body"),
    [
        ("sleep_range", "{}"),
        ("sleep_range", "[1]"),
        ("hrv_summaries", "[]"),
        ("hrv_summaries", '{"hrvSummaries": {}}'),
        ("body_battery", "{}"),
        ("daily_steps", "{}"),
        ("daily_stress", '["x"]'),
        ("daily_hydration", "{}"),
        ("daily_overviews", "[]"),
        ("daily_overviews", '{"data": null}'),
        ("wellness_activities", "{}"),
    ],
)
async def test_malformed_range_raises_response_error(
    client: GarminPersonalClient,
    garmin: FakeGarmin,
    token: str,
    name: str,
    body: str,
) -> None:
    call, path = RANGES[name]
    garmin.add("GET", path, Reply(body=body))

    with pytest.raises(GarminPersonalResponseError):
        await call(client, START, DAY)


@pytest.mark.parametrize(
    ("name", "body"),
    [
        ("sleep_range", '[{"calendarDate": "22 October"}]'),
        ("hrv_summaries", '{"hrvSummaries": [{"lastNightAvg": 50}]}'),
        ("body_battery", '[{"date": "yesterday"}]'),
        ("daily_steps", '[{"totalSteps": 1}]'),
        ("daily_stress", '[{"calendarDate": 20261022}]'),
        ("daily_hydration", "[{}]"),
        ("daily_overviews", '{"data": [{}]}'),
    ],
)
async def test_day_without_a_date_raises_response_error(
    client: GarminPersonalClient,
    garmin: FakeGarmin,
    token: str,
    name: str,
    body: str,
) -> None:
    call, path = RANGES[name]
    garmin.add("GET", path, Reply(body=body))

    with pytest.raises(GarminPersonalResponseError, match="no valid"):
        await call(client, START, DAY)


async def test_unexpected_field_types_become_none(
    client: GarminPersonalClient, garmin: FakeGarmin, token: str
) -> None:
    garmin.add(
        "GET",
        SLEEP_PATH,
        Reply(
            body='{"calendarDate": "2026-10-22", "sleepTimeSeconds": "long",'
            ' "sleepStartTimestampGMT": true, "sleepScores": [], "sleepNeed": null,'
            ' "sleepWindowConfirmed": "yes"}'
        ),
    )

    sleep = await client.async_get_sleep(DAY)

    assert sleep is not None
    assert sleep.sleep_seconds is None
    assert sleep.sleep_start_time_gmt is None
    assert sleep.score is None
    assert sleep.sleep_need_minutes is None
    assert sleep.window_confirmed is None
