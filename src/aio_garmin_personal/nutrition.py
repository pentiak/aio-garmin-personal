"""Typed views of the food log and menstrual cycle responses.

Typed from Garmin's API description: the account the library was checked against logs no
food and does not track a cycle, so field names and units are Garmin's documented ones, not
confirmed against real data. Everything is also in `raw`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from ._parse import (
    opt_bool,
    opt_connect_date,
    opt_date,
    opt_float,
    opt_int,
    opt_obj,
    opt_objs,
    opt_str,
    opt_str_list,
)


@dataclass(frozen=True, kw_only=True)
class NutritionTotals:
    """Calories in kilocalories and macronutrients in grams."""

    calories: int | None
    carbs_grams: float | None
    protein_grams: float | None
    fat_grams: float | None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> NutritionTotals:
        """Build the totals from a nutrition content object."""
        return cls(
            calories=opt_int(data, "calories"),
            carbs_grams=opt_float(data, "carbs"),
            protein_grams=opt_float(data, "protein"),
            fat_grams=opt_float(data, "fat"),
        )


@dataclass(frozen=True, kw_only=True)
class NutritionGoals:
    """Daily intake goals. `adjusted_calories` adds the calories burned in activities."""

    calories: int | None
    adjusted_calories: int | None
    carbs_grams: float | None
    protein_grams: float | None
    fat_grams: float | None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> NutritionGoals:
        """Build the goals from a nutrition goals object."""
        return cls(
            calories=opt_int(data, "calories"),
            adjusted_calories=opt_int(data, "adjustedCalories"),
            carbs_grams=opt_float(data, "carbs"),
            protein_grams=opt_float(data, "protein"),
            fat_grams=opt_float(data, "fat"),
        )


@dataclass(frozen=True, kw_only=True)
class LoggedFood:
    """One logged food. `nutrition` covers the logged quantity, `servings` servings."""

    food_name: str | None
    brand_name: str | None
    servings: float | None
    nutrition: NutritionTotals
    raw: Mapping[str, Any] = field(repr=False)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> LoggedFood:
        """Build the food from one element of a meal's `loggedFoods`."""
        metadata = opt_obj(data, "foodMetaData")
        return cls(
            food_name=opt_str(metadata, "foodName"),
            brand_name=opt_str(metadata, "brandName"),
            servings=opt_float(data, "servingQty"),
            nutrition=NutritionTotals.from_dict(opt_obj(data, "nutritionContent")),
            raw=data,
        )


@dataclass(frozen=True, kw_only=True)
class Meal:
    """One meal of the day, such as breakfast, with what was logged for it."""

    meal_id: int | None
    meal_name: str | None
    totals: NutritionTotals
    goals: NutritionGoals
    foods: list[LoggedFood]
    raw: Mapping[str, Any] = field(repr=False)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Meal:
        """Build the meal from one element of `mealDetails`."""
        meal = opt_obj(data, "meal")
        return cls(
            meal_id=opt_int(meal, "mealId"),
            meal_name=opt_str(meal, "mealName"),
            totals=NutritionTotals.from_dict(opt_obj(data, "mealNutritionContent")),
            goals=NutritionGoals.from_dict(opt_obj(data, "mealNutritionGoals")),
            foods=[
                LoggedFood.from_dict(item) for item in opt_objs(data, "loggedFoods")
            ],
            raw=data,
        )


@dataclass(frozen=True, kw_only=True)
class DailyNutrition:
    """One day's food log from `/nutrition-service/food/logs/{date}`.

    A day without logged food has no meals and every total `None`.
    """

    calendar_date: date | None
    totals: NutritionTotals
    goals: NutritionGoals
    meals: list[Meal]
    raw: Mapping[str, Any] = field(repr=False)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DailyNutrition:
        """Build the day from the decoded JSON body."""
        return cls(
            calendar_date=opt_date(data, "mealDate"),
            totals=NutritionTotals.from_dict(opt_obj(data, "dailyNutritionContent")),
            goals=NutritionGoals.from_dict(opt_obj(data, "dailyNutritionGoals")),
            meals=[Meal.from_dict(item) for item in opt_objs(data, "mealDetails")],
            raw=data,
        )


@dataclass(frozen=True, kw_only=True)
class MenstrualCycle:
    """The cycle a day belongs to, from `/periodichealth-service/menstrualcycle/summary`.

    `current_phase` is Garmin's phase number. Lengths are in days. `predicted_cycle` is
    true for a cycle Garmin predicts rather than one that was logged.
    """

    start_date: date | None
    end_date: date | None
    cycle_type: str | None
    day_in_cycle: int | None
    current_phase: int | None
    length_of_current_phase: int | None
    days_until_next_phase: int | None
    period_length: int | None
    predicted_cycle_length: int | None
    predicted_ovulation_date: date | None
    predicted_cycle: bool | None
    pregnancy_cycle: bool | None
    raw: Mapping[str, Any] = field(repr=False)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> MenstrualCycle:
        """Build the cycle from a cycle summary object."""
        return cls(
            start_date=opt_connect_date(data, "startDate"),
            end_date=opt_connect_date(data, "endDate"),
            cycle_type=opt_str(data, "cycleType"),
            day_in_cycle=opt_int(data, "dayInCycle"),
            current_phase=opt_int(data, "currentPhase"),
            length_of_current_phase=opt_int(data, "lengthOfCurrentPhase"),
            days_until_next_phase=opt_int(data, "daysUntilNextPhase"),
            period_length=opt_int(data, "periodLength"),
            predicted_cycle_length=opt_int(data, "predictedCycleLength"),
            predicted_ovulation_date=opt_connect_date(data, "predictedOvulationDate"),
            predicted_cycle=opt_bool(data, "predictedCycle"),
            pregnancy_cycle=opt_bool(data, "pregnancyCycle"),
            raw=data,
        )


@dataclass(frozen=True, kw_only=True)
class MenstrualCycleDayLog:
    """What was logged for one day of the cycle.

    `flow` is Garmin's flow level key; `symptoms` and `moods` are Garmin's keys too. Free
    text notes and the other logged items are only in `raw`.
    """

    calendar_date: date | None
    flow: str | None
    symptoms: list[str]
    moods: list[str]
    ovulation_day: bool | None
    raw: Mapping[str, Any] = field(repr=False)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> MenstrualCycleDayLog:
        """Build the log from a day log object."""
        return cls(
            calendar_date=opt_connect_date(data, "calendarDate"),
            flow=opt_str(data, "flow"),
            symptoms=opt_str_list(data, "symptoms"),
            moods=opt_str_list(data, "moods"),
            ovulation_day=opt_bool(data, "ovulationDay"),
            raw=data,
        )


@dataclass(frozen=True, kw_only=True)
class MenstrualCycleDay:
    """One day from `/periodichealth-service/menstrualcycle/dayview/{calendarDate}`."""

    cycle: MenstrualCycle | None
    log: MenstrualCycleDayLog | None
    raw: Mapping[str, Any] = field(repr=False)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> MenstrualCycleDay:
        """Build the day from the decoded JSON body."""
        summary = data.get("daySummary")
        log = data.get("dayLog")
        return cls(
            cycle=MenstrualCycle.from_dict(summary)
            if isinstance(summary, Mapping)
            else None,
            log=MenstrualCycleDayLog.from_dict(log)
            if isinstance(log, Mapping)
            else None,
            raw=data,
        )
