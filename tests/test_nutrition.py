from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import date
from typing import Any

import pytest

from aio_garmin_personal import (
    GarminPersonalClient,
    GarminPersonalResponseError,
    NutritionGoals,
    NutritionTotals,
)

from .conftest import FakeGarmin, Reply, load_fixture

DAY = date(2026, 10, 22)
NUTRITION_PATH = "/nutrition-service/food/logs/2026-10-22"
CYCLE_PATH = "/periodichealth-service/menstrualcycle/summary/2026-10-22"
CYCLE_DAY_PATH = "/periodichealth-service/menstrualcycle/dayview/2026-10-22"


async def test_nutrition_is_parsed(
    client: GarminPersonalClient, garmin: FakeGarmin, token: str
) -> None:
    garmin.add("GET", NUTRITION_PATH, Reply(body=load_fixture("nutrition.json")))

    day = await client.async_get_nutrition(DAY)

    assert day is not None
    assert day.calendar_date == DAY
    assert day.totals == NutritionTotals(
        calories=1450, carbs_grams=160.0, protein_grams=80.0, fat_grams=50.0
    )
    assert day.goals == NutritionGoals(
        calories=2200,
        adjusted_calories=2650,
        carbs_grams=250.0,
        protein_grams=120.0,
        fat_grams=75.0,
    )
    (meal,) = day.meals
    assert (meal.meal_id, meal.meal_name) == (1, "Breakfast")
    assert meal.totals.calories == 270
    assert meal.goals.calories == 550
    assert meal.goals.adjusted_calories is None
    (food,) = meal.foods
    assert food.food_name == "Porridge"
    assert food.brand_name == "Example Oats"
    assert food.servings == 1.5
    assert food.nutrition == NutritionTotals(
        calories=270, carbs_grams=45.0, protein_grams=9.0, fat_grams=6.0
    )


async def test_day_without_logged_food(
    client: GarminPersonalClient, garmin: FakeGarmin, token: str
) -> None:
    garmin.add("GET", NUTRITION_PATH, Reply(body=load_fixture("nutrition_empty.json")))

    day = await client.async_get_nutrition(DAY)

    assert day is not None
    assert day.calendar_date == DAY
    assert day.meals == []
    assert day.totals.calories is None
    assert day.goals.calories is None


async def test_menstrual_cycle_is_parsed(
    client: GarminPersonalClient, garmin: FakeGarmin, token: str
) -> None:
    garmin.add("GET", CYCLE_PATH, Reply(body=load_fixture("menstrual_cycle.json")))

    cycle = await client.async_get_menstrual_cycle(DAY)

    assert cycle is not None
    assert cycle.start_date == date(2026, 10, 10)
    assert cycle.end_date is None
    assert cycle.cycle_type == "REGULAR"
    assert cycle.day_in_cycle == 13
    assert cycle.current_phase == 2
    assert cycle.length_of_current_phase == 9
    assert cycle.days_until_next_phase == 2
    assert cycle.period_length == 5
    assert cycle.predicted_cycle_length == 29
    assert cycle.predicted_ovulation_date == date(2026, 10, 24)
    assert cycle.predicted_cycle is False
    assert cycle.pregnancy_cycle is False


async def test_menstrual_cycle_day_reads_dates_in_object_form(
    client: GarminPersonalClient, garmin: FakeGarmin, token: str
) -> None:
    garmin.add(
        "GET", CYCLE_DAY_PATH, Reply(body=load_fixture("menstrual_cycle_day.json"))
    )

    day = await client.async_get_menstrual_cycle_day(DAY)

    assert day is not None
    assert day.cycle is not None
    assert day.cycle.start_date == date(2026, 10, 10)
    assert day.cycle.predicted_ovulation_date == date(2026, 10, 24)
    assert day.log is not None
    assert day.log.calendar_date == DAY
    assert day.log.flow == "NONE"
    # Items that are not strings are left out.
    assert day.log.symptoms == ["HEADACHE"]
    assert day.log.moods == ["CALM"]
    assert day.log.ovulation_day is False


async def test_menstrual_cycle_day_without_parts(
    client: GarminPersonalClient, garmin: FakeGarmin, token: str
) -> None:
    garmin.add(
        "GET",
        CYCLE_DAY_PATH,
        Reply(body='{"daySummary": null, "dayLog": {"symptoms": null}}'),
    )

    day = await client.async_get_menstrual_cycle_day(DAY)

    assert day is not None
    assert day.cycle is None
    assert day.log is not None
    assert day.log.symptoms == []


CALLS: dict[str, tuple[Callable[[GarminPersonalClient], Awaitable[Any]], str]] = {
    "nutrition": (lambda c: c.async_get_nutrition(DAY), NUTRITION_PATH),
    "cycle": (lambda c: c.async_get_menstrual_cycle(DAY), CYCLE_PATH),
    "cycle-day": (lambda c: c.async_get_menstrual_cycle_day(DAY), CYCLE_DAY_PATH),
}


@pytest.mark.parametrize("name", CALLS)
async def test_without_tracking_is_none(
    client: GarminPersonalClient, garmin: FakeGarmin, token: str, name: str
) -> None:
    call, path = CALLS[name]
    garmin.add("GET", path, Reply(status=204))

    assert await call(client) is None


async def test_cycle_array_raises_response_error(
    client: GarminPersonalClient, garmin: FakeGarmin, token: str
) -> None:
    garmin.add("GET", CYCLE_PATH, Reply(body="[]"))

    with pytest.raises(GarminPersonalResponseError, match="is not an object"):
        await client.async_get_menstrual_cycle(DAY)
