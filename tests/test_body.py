from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime
from typing import Any

import pytest

from aio_garmin_personal import GarminPersonalClient, GarminPersonalResponseError

from .conftest import FakeGarmin, Reply, load_fixture

START = date(2026, 10, 20)
END = date(2026, 10, 22)
WEIGHT_PATH = "/weight-service/weight/range/2026-10-20/2026-10-22"
GOALS_PATH = "/goal-service/goal/user/effective/weightgoal/2026-10-20/2026-10-22"
FITNESS_AGE_PATH = "/fitnessage-service/fitnessage/v2/2026-10-22"
ZONES_PATH = "/biometric-service/heartRateZones/v2"


async def test_weight_is_parsed(
    client: GarminPersonalClient, garmin: FakeGarmin, token: str
) -> None:
    garmin.add("GET", WEIGHT_PATH, Reply(body=load_fixture("weight_range.json")))

    weight = await client.async_get_weight(START, END, include_all=True)

    assert weight.average_weight_grams == 72300.0
    assert weight.average_bmi is None
    first, second = weight.days
    assert first.calendar_date == START
    assert first.entry_count == 1
    assert second.calendar_date == END
    assert second.entry_count == 2
    assert second.min_weight_grams == 72100.0
    assert second.max_weight_grams == 72300.0
    assert second.latest is not None
    assert second.latest.calendar_date == END
    assert second.latest.time_gmt == datetime(2026, 10, 22, 5, 40, tzinfo=UTC)
    assert second.latest.weight_grams == 72100.0
    assert second.latest.body_fat_percent is None
    assert second.latest.source_type == "MANUAL"
    assert [e.weight_grams for e in second.entries] == [72300.0, 72100.0]
    (call,) = garmin.calls("GET", WEIGHT_PATH)
    assert call.query == {"includeAll": "true"}


async def test_weight_asks_for_the_latest_entry_by_default(
    client: GarminPersonalClient, garmin: FakeGarmin, token: str
) -> None:
    garmin.add("GET", WEIGHT_PATH, Reply(body='{"dailyWeightSummaries": []}'))

    weight = await client.async_get_weight(START, END)

    assert weight.days == []
    (call,) = garmin.calls("GET", WEIGHT_PATH)
    assert call.query == {"includeAll": "false"}


async def test_weight_day_without_date_raises_response_error(
    client: GarminPersonalClient, garmin: FakeGarmin, token: str
) -> None:
    garmin.add(
        "GET", WEIGHT_PATH, Reply(body='{"dailyWeightSummaries": [{"minWeight": 1}]}')
    )

    with pytest.raises(GarminPersonalResponseError, match="no valid summaryDate"):
        await client.async_get_weight(START, END)


async def test_weight_goals_are_parsed(
    client: GarminPersonalClient, garmin: FakeGarmin, token: str
) -> None:
    garmin.add("GET", GOALS_PATH, Reply(body=load_fixture("weight_goals.json")))

    goals = await client.async_get_weight_goals(START, END)

    (goal,) = goals.goals
    assert goal.goal_name == "weight"
    assert goal.goal_type == "WEIGHT_GRAMS"
    assert goal.category == "MANUAL"
    assert goal.goal_value_grams == 70000.0
    assert goal.start_date == date(2026, 9, 1)
    assert goal.end_date is None
    assert goal.tracking_period_type == "DAILY"
    (band,) = goals.ranges
    assert band.low_grams == 69000.0
    assert band.high_grams == 71000.0
    assert band.start_date == date(2026, 9, 1)
    assert band.end_date == date(2026, 12, 31)


async def test_fitness_age_is_parsed(
    client: GarminPersonalClient, garmin: FakeGarmin, token: str
) -> None:
    garmin.add("GET", FITNESS_AGE_PATH, Reply(body=load_fixture("fitness_age.json")))

    age = await client.async_get_fitness_age(END)

    assert age is not None
    assert age.fitness_age == 35.5
    assert age.chronological_age == 40
    assert age.previous_fitness_age == 36.0
    assert age.achievable_fitness_age is None
    assert age.invalid_reason is None
    # The component that is not an object is left out.
    assert sorted(age.components) == [
        "bmi",
        "rhr",
        "vigorousDaysAvg",
        "vigorousMinutesAvg",
    ]
    assert age.components["rhr"].value == 53.0
    assert age.components["bmi"].stale is True
    assert age.components["bmi"].target_value is None


async def test_heart_rate_zones_are_parsed(
    client: GarminPersonalClient, garmin: FakeGarmin, token: str
) -> None:
    garmin.add("GET", ZONES_PATH, Reply(body=load_fixture("heart_rate_zones.json")))

    default, running = await client.async_get_heart_rate_zones()

    assert default.sport == "DEFAULT"
    assert default.training_method == "LACTATE_THRESHOLD"
    assert default.zone_floors == (109, 136, 150, 162, 170)
    assert default.max_heart_rate == 188
    assert default.resting_heart_rate == 53
    assert default.lactate_threshold_heart_rate == 168
    assert running.sport == "RUNNING"
    assert running.zone_floors == (110, 138, 152, 164, None)


async def test_empty_bodies(
    client: GarminPersonalClient, garmin: FakeGarmin, token: str
) -> None:
    for path in (WEIGHT_PATH, GOALS_PATH, FITNESS_AGE_PATH, ZONES_PATH):
        garmin.add("GET", path, Reply(status=204))

    weight = await client.async_get_weight(START, END)
    goals = await client.async_get_weight_goals(START, END)

    assert (weight.days, weight.average_weight_grams) == ([], None)
    assert (goals.goals, goals.ranges) == ([], [])
    assert await client.async_get_fitness_age(END) is None
    assert await client.async_get_heart_rate_zones() == []


CALLS: dict[str, tuple[Callable[[GarminPersonalClient], Awaitable[Any]], str, str]] = {
    "weight": (lambda c: c.async_get_weight(START, END), WEIGHT_PATH, "[]"),
    "goals": (lambda c: c.async_get_weight_goals(START, END), GOALS_PATH, "[]"),
    "fitness-age": (lambda c: c.async_get_fitness_age(END), FITNESS_AGE_PATH, "[]"),
    "zones": (lambda c: c.async_get_heart_rate_zones(), ZONES_PATH, "{}"),
}


@pytest.mark.parametrize("name", CALLS)
async def test_wrong_shape_raises_response_error(
    client: GarminPersonalClient, garmin: FakeGarmin, token: str, name: str
) -> None:
    call, path, body = CALLS[name]
    garmin.add("GET", path, Reply(body=body))

    with pytest.raises(GarminPersonalResponseError):
        await call(client)


async def test_reversed_ranges_are_rejected(
    client: GarminPersonalClient, garmin: FakeGarmin
) -> None:
    with pytest.raises(ValueError, match="start must not be after end"):
        await client.async_get_weight(END, START)
    with pytest.raises(ValueError, match="start must not be after end"):
        await client.async_get_weight_goals(END, START)

    assert garmin.requests == []
