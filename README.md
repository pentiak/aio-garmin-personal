# aio-garmin-personal

Asynchronous Python client for the
[Garmin Connect Personal API](https://developer.garmin.com/gc-developer-program/personal/personal-api),
the read-only API Garmin offers to individual account holders for their own data.

It was written as the dependency of a Home Assistant integration, so it follows Home Assistant's
rules for libraries: `asyncio` with `aiohttp`, a caller-supplied `ClientSession`, full type hints,
and one exception type per kind of failure.

This is not a Garmin product.

## Installation

```shell
pip install aio-garmin-personal
```

## Usage

Create a Personal API key in Garmin Connect (Settings → Personal API Key). Garmin shows it once.

```python
import asyncio
from datetime import date

import aiohttp

from aio_garmin_personal import GarminPersonalClient


async def main() -> None:
    async with aiohttp.ClientSession() as session:
        client = GarminPersonalClient(session, "<your Personal API key>")
        summary = await client.async_get_daily_summary(date.today())
        if summary is not None:
            print(
                summary.total_kilocalories,
                summary.active_kilocalories,
                summary.total_steps,
            )


asyncio.run(main())
```

The client exchanges the key for an access token on the first request, keeps the token in
memory, and exchanges the key again an hour before the token expires. It never writes the key or
the token to disk.

## Errors

| Exception | Raised when |
|---|---|
| `GarminPersonalAuthenticationError` | Garmin rejects the key: wrong, expired or deleted |
| `GarminPersonalRateLimitError` | Garmin answers HTTP 429; `retry_after` holds the delay in seconds if sent |
| `GarminPersonalConnectionError` | Garmin cannot be reached or the request times out |
| `GarminPersonalResponseError` | Any other failure status, or a body the client cannot parse |

All of them derive from `GarminPersonalError`.

## Supported endpoints

| Method | Endpoint | Longest range |
|---|---|---|
| `async_get_user_settings()` | `GET /userprofile-service/userprofile/settings` | |
| `async_get_daily_summary(day)` | `GET /usersummary-service/usersummary/daily` | |
| `async_get_daily_overviews(start, end)` | `GET /usersummary-service/v2/dailysummaries` | a few months |
| `async_get_daily_steps(start, end)` | `GET /usersummary-service/stats/steps/daily/{start}/{end}` | 28 days |
| `async_get_daily_stress(start, end)` | `GET /usersummary-service/stats/stress/daily/{start}/{end}` | 28 days |
| `async_get_daily_hydration(start, end)` | `GET /usersummary-service/stats/hydration/daily/{start}/{end}` | 31 days |
| `async_get_sleep(day)` | `GET /sleep-service/sleep/dailySleep` | |
| `async_get_sleep_range(start, end)` | `GET /sleep-service/sleep/dailySleepSummariesByDate` | 32 days |
| `async_get_hrv(day)` | `GET /hrv-service/hrv/{day}` | |
| `async_get_hrv_summaries(start, end)` | `GET /hrv-service/hrv/daily/{start}/{end}` | 367 days |
| `async_get_heart_rate(day)` | `GET /wellness-service/wellness/dailyHeartRate` | |
| `async_get_spo2(day)` | `GET /wellness-service/wellness/daily/spo2acclimation/{day}` | |
| `async_get_body_battery(start, end)` | `GET /wellness-service/wellness/bodyBattery/reports/daily` | 31 days |
| `async_get_wellness_activities(start, end)` | `GET /wellnessactivity-service/activity/summary/range/{start}/{end}` | |
| `async_get_weight(start, end, include_all=)` | `GET /weight-service/weight/range/{start}/{end}` | |
| `async_get_weight_goals(start, end)` | `GET /goal-service/goal/user/effective/weightgoal/{start}/{end}` | |
| `async_get_fitness_age(day)` | `GET /fitnessage-service/fitnessage/v2/{day}` | |
| `async_get_heart_rate_zones()` | `GET /biometric-service/heartRateZones/v2` | |
| `async_get_activities(limit=, start=, start_date=, end_date=, activity_type=)` | `GET /activitylist-service/activities/search/activities` | |
| `async_get_activity(activity_id)` | `GET /activity-service/activity/{activity_id}` | |
| `async_get_activity_workouts(activity_id)` | `GET /activity-service/activity/{activity_id}/workouts` | |
| `async_download_activity(activity_id)` | `GET /download-service/files/activity/{activity_id}` | |

Ranges include both ends. A range longer than Garmin accepts raises
`GarminPersonalResponseError` with status 400; the limits are Garmin's and may change. Each
returned object types the commonly used fields and keeps the whole response in `raw`.

## Development

```shell
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pre-commit install
.venv/bin/pytest
.venv/bin/pre-commit run --all-files
```

Releases are built and published to PyPI by the `release` workflow when a `vX.Y.Z` tag is pushed.

## License

Apache License 2.0.
