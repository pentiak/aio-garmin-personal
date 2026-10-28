from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from aio_garmin_personal import (
    GarminPersonalAuthenticationError,
    GarminPersonalClient,
    GarminPersonalResponseError,
)

from .conftest import (
    ACTIVITIES_PATH,
    TOKEN_PATH,
    FakeGarmin,
    Reply,
    load_fixture,
    make_jwt,
)

ACTIVITY_PATH = "/activity-service/activity/10000000001"
WORKOUTS_PATH = "/activity-service/activity/10000000001/workouts"
FILE_PATH = "/download-service/files/activity/10000000001"
ZIP = b"PK\x03\x04 made-up archive bytes"


async def test_activity_list_carries_the_totals(
    client: GarminPersonalClient, garmin: FakeGarmin, token: str
) -> None:
    garmin.add("GET", ACTIVITIES_PATH, Reply(body=load_fixture("activities.json")))

    run, ride = await client.async_get_activities(limit=2)

    assert run.activity_type == "running"
    assert run.duration_seconds == 2701.3
    assert run.moving_duration_seconds == 2690.0
    assert run.elapsed_duration_seconds == 2750.5
    assert run.distance_meters == 8012.4
    assert run.calories == 610.0
    assert run.average_heart_rate == 148.0
    assert run.max_heart_rate == 171.0
    assert run.average_speed == 2.966
    assert run.max_speed == 3.9
    assert run.elevation_gain_meters == 54.0
    assert run.elevation_loss_meters == 52.0
    assert run.steps == 7400
    assert run.average_power == 265.0
    assert run.aerobic_training_effect == 3.2
    assert run.anaerobic_training_effect == 0.8
    assert run.training_load == 112.5
    assert run.moderate_intensity_minutes == 10
    assert run.vigorous_intensity_minutes == 33
    assert ride.activity_type == "cycling"
    assert ride.calories is None
    assert ride.average_power is None


async def test_activity_list_filters_are_sent(
    client: GarminPersonalClient, garmin: FakeGarmin, token: str
) -> None:
    garmin.add("GET", ACTIVITIES_PATH, Reply(body="[]"))

    await client.async_get_activities(
        limit=50,
        start=10,
        start_date=date(2026, 10, 1),
        end_date=date(2026, 10, 22),
        activity_type="running",
    )

    (call,) = garmin.calls("GET", ACTIVITIES_PATH)
    assert call.query == {
        "start": "10",
        "limit": "50",
        "startDate": "2026-10-01",
        "endDate": "2026-10-22",
        "activityType": "running",
    }


async def test_activity_list_accepts_one_date_bound(
    client: GarminPersonalClient, garmin: FakeGarmin, token: str
) -> None:
    garmin.add("GET", ACTIVITIES_PATH, Reply(body="[]"))

    await client.async_get_activities(end_date=date(2026, 10, 22))

    (call,) = garmin.calls("GET", ACTIVITIES_PATH)
    assert call.query == {"start": "0", "limit": "20", "endDate": "2026-10-22"}


async def test_activity_list_rejects_reversed_dates(
    client: GarminPersonalClient, garmin: FakeGarmin
) -> None:
    with pytest.raises(ValueError, match="start must not be after end"):
        await client.async_get_activities(
            start_date=date(2026, 10, 22), end_date=date(2026, 10, 1)
        )

    assert garmin.requests == []


async def test_activity_is_parsed(
    client: GarminPersonalClient, garmin: FakeGarmin, token: str
) -> None:
    garmin.add("GET", ACTIVITY_PATH, Reply(body=load_fixture("activity.json")))

    activity = await client.async_get_activity(10000000001)

    assert activity is not None
    assert activity.activity_id == 10000000001
    assert activity.activity_name == "Morning Run"
    assert activity.activity_type == "running"
    assert activity.location_name == "Example Town"
    assert activity.time_zone == "Europe/Berlin"
    assert activity.start_time_gmt == datetime(2026, 10, 22, 5, 15, 2, tzinfo=UTC)
    assert activity.distance_meters == 8012.4
    assert activity.duration_seconds == 2701.3
    assert activity.average_power == 265.0
    assert activity.aerobic_training_effect == 3.2
    assert activity.training_load == 112.5


async def test_activity_without_id_raises_response_error(
    client: GarminPersonalClient, garmin: FakeGarmin, token: str
) -> None:
    garmin.add("GET", ACTIVITY_PATH, Reply(body='{"activityName": "Run"}'))

    with pytest.raises(GarminPersonalResponseError, match="no activityId"):
        await client.async_get_activity(10000000001)


async def test_unknown_activity_raises_response_error_with_404(
    client: GarminPersonalClient, garmin: FakeGarmin, token: str
) -> None:
    garmin.add("GET", ACTIVITY_PATH, Reply(status=404, body="{}"))

    with pytest.raises(GarminPersonalResponseError) as err:
        await client.async_get_activity(10000000001)

    assert err.value.status == 404


async def test_empty_activity_body_is_none(
    client: GarminPersonalClient, garmin: FakeGarmin, token: str
) -> None:
    garmin.add("GET", ACTIVITY_PATH, Reply(status=204))

    assert await client.async_get_activity(10000000001) is None


async def test_workouts_are_parsed(
    client: GarminPersonalClient, garmin: FakeGarmin, token: str
) -> None:
    garmin.add("GET", WORKOUTS_PATH, Reply(body=load_fixture("activity_workouts.json")))

    (workout,) = await client.async_get_activity_workouts(10000000001)

    assert workout.workout_name == "Intervals"
    assert workout.sport == "RUNNING"
    assert workout.created_time_gmt == datetime(2026, 10, 21, 18, 0, tzinfo=UTC)
    warmup, interval, repeat = workout.steps
    assert (warmup.step_index, warmup.intensity, warmup.duration_type) == (
        0,
        "WARMUP",
        "TIME",
    )
    assert warmup.duration_value == 600.0
    assert warmup.target_type == "OPEN"
    assert interval.target_type == "SPEED"
    assert (interval.target_low, interval.target_high) == (3.3, 3.6)
    assert interval.notes == "Steady"
    assert repeat.duration_type == "REPEAT_UNTIL_STEPS_CMPLT"
    assert repeat.duration_value == 1.0
    assert repeat.intensity is None


async def test_activity_without_workout_has_none(
    client: GarminPersonalClient, garmin: FakeGarmin, token: str
) -> None:
    garmin.add("GET", WORKOUTS_PATH, Reply(body="[]"))

    assert await client.async_get_activity_workouts(10000000001) == []


async def test_activity_file_is_downloaded(
    client: GarminPersonalClient, garmin: FakeGarmin, token: str
) -> None:
    garmin.add(
        "GET",
        FILE_PATH,
        Reply(body=ZIP, headers={"Content-Type": "application/x-zip-compressed"}),
    )

    assert await client.async_download_activity(10000000001) == ZIP
    (call,) = garmin.calls("GET", FILE_PATH)
    assert call.headers["Accept"] == "*/*"
    assert call.headers["Authorization"] == f"Bearer {token}"


async def test_empty_activity_file_raises_response_error(
    client: GarminPersonalClient, garmin: FakeGarmin, token: str
) -> None:
    garmin.add("GET", FILE_PATH, Reply(status=200))

    with pytest.raises(GarminPersonalResponseError, match="returned no file"):
        await client.async_download_activity(10000000001)


async def test_download_retries_once_with_a_new_token(
    client: GarminPersonalClient, garmin: FakeGarmin
) -> None:
    garmin.add("POST", TOKEN_PATH, Reply(body=make_jwt(2_000_000_000, "stale")))
    garmin.add("POST", TOKEN_PATH, Reply(body=make_jwt(2_000_000_000, "fresh")))
    garmin.add("GET", FILE_PATH, Reply(status=401))
    garmin.add("GET", FILE_PATH, Reply(body=ZIP))

    assert await client.async_download_activity(10000000001) == ZIP
    assert len(garmin.calls("POST", TOKEN_PATH)) == 2


async def test_download_with_rejected_key_raises_authentication_error(
    client: GarminPersonalClient, garmin: FakeGarmin, token: str
) -> None:
    garmin.add("GET", FILE_PATH, Reply(status=401))

    with pytest.raises(GarminPersonalAuthenticationError):
        await client.async_download_activity(10000000001)
