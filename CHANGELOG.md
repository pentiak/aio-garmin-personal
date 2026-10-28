# Changelog

## 0.3.0 - 2026-10-28

### Added

- Sleep: `async_get_sleep()` for one night and `async_get_sleep_range()` for up to 32, with
  stage durations, the sleep score and Garmin's sleep need.
- Heart rate variability: `async_get_hrv()` with the night's readings, and
  `async_get_hrv_summaries()` for up to 367 days.
- `async_get_heart_rate()`: the day's readings and resting heart rate.
- `async_get_spo2()`: blood oxygen averages and hourly values.
- `async_get_body_battery()`: levels and the events that charged or drained them, for up to
  31 days.
- Daily statistics for a range of days: `async_get_daily_steps()` and
  `async_get_daily_stress()` (up to 28 days), `async_get_daily_hydration()` (up to 31 days),
  and `async_get_daily_overviews()`, the daily totals of `/usersummary-service/v2/dailysummaries`.
- `async_get_wellness_activities()`: sessions such as breathwork that are not in the activity
  list.
- Weight: `async_get_weight()` with each day's latest entry, or every entry with
  `include_all=True`, and the range's averages; weights are in grams.
- `async_get_weight_goals()`, typed from Garmin's API description.
- `async_get_fitness_age()` with its components, and `async_get_heart_rate_zones()` per sport.
- Activities: `async_get_activity()` for one activity's totals, `async_get_activity_workouts()`
  for the planned workout it followed, and `async_download_activity()` for the original file
  as a ZIP archive.
- `Activity` carries the activity's type and totals (duration, distance, calories, heart rate,
  speed, elevation, training effect and load), shared with `ActivityDetails` as
  `ActivityStats`.
- `async_get_activities()` takes `start_date`, `end_date` and `activity_type` filters.
- `async_get_nutrition()`: the day's logged food by meal, with totals and goals, and
  `async_get_menstrual_cycle()` and `async_get_menstrual_cycle_day()`. All three are typed from
  Garmin's API description.

Range methods raise `ValueError` when `start` is after `end`. Longer ranges than Garmin accepts
raise `GarminPersonalResponseError` with HTTP status 400.

## 0.2.1 - 2026-10-27

### Fixed

- A deleted API key raises `GarminPersonalAuthenticationError`. Garmin's token endpoint answers
  HTTP 404 for it, which raised `GarminPersonalResponseError`.

## 0.2.0 - 2026-10-27

### Added

- `async_get_activities()`, returning `Activity` objects with the owner's full name.

## 0.1.0 - 2026-10-23

### Added

- `GarminPersonalClient` with `async_get_user_settings()` and `async_get_daily_summary()`.
- Exchange of the Personal API key for access tokens, kept in memory and renewed before expiry.
- Exceptions for authentication, rate-limit, connection and response failures.
