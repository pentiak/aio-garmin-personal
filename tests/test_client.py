from __future__ import annotations

from datetime import UTC, date, datetime
import time

import aiohttp
import pytest

from aio_garmin_personal import (
    GarminPersonalAuthenticationError,
    GarminPersonalClient,
    GarminPersonalConnectionError,
    GarminPersonalRateLimitError,
    GarminPersonalResponseError,
)

from .conftest import (
    SETTINGS_PATH,
    SUMMARY_PATH,
    TOKEN_PATH,
    FakeGarmin,
    Reply,
    load_fixture,
    make_jwt,
)

DAY = date(2026, 10, 23)


@pytest.fixture
def token(garmin: FakeGarmin) -> str:
    value = make_jwt(time.time() + 86_400)
    garmin.add("POST", TOKEN_PATH, Reply(body=value))
    return value


async def test_daily_summary_is_parsed(
    client: GarminPersonalClient, garmin: FakeGarmin, token: str
) -> None:
    garmin.add("GET", SUMMARY_PATH, Reply(body=load_fixture("daily_summary.json")))

    summary = await client.async_get_daily_summary(DAY)

    assert summary is not None
    assert summary.user_profile_id == 123456789
    assert summary.display_name is None
    assert summary.calendar_date == DAY
    assert summary.total_kilocalories == 655.0
    assert summary.active_kilocalories == 22.0
    assert summary.bmr_kilocalories == 633.0
    assert summary.consumed_kilocalories is None
    assert summary.total_steps == 418
    assert summary.daily_step_goal == 8000
    assert summary.total_distance_meters == 327
    assert summary.floors_ascended == 1.0
    assert summary.resting_heart_rate == 55
    assert summary.average_stress_level == 21
    assert summary.body_battery_most_recent_value == 72
    assert summary.body_battery_highest_value == 74
    assert summary.body_battery_lowest_value == 19
    assert summary.last_sync == datetime(2026, 10, 23, 6, 12, 48, 317000, tzinfo=UTC)
    (call,) = garmin.calls("GET", SUMMARY_PATH)
    assert call.query == {"calendarDate": "2026-10-23"}
    assert call.headers["Authorization"] == f"Bearer {token}"


async def test_day_without_data_has_no_metrics(
    client: GarminPersonalClient, garmin: FakeGarmin, token: str
) -> None:
    garmin.add(
        "GET", SUMMARY_PATH, Reply(body=load_fixture("daily_summary_empty.json"))
    )

    summary = await client.async_get_daily_summary(date(2026, 10, 24))

    assert summary is not None
    assert summary.user_profile_id == 123456789
    assert summary.display_name == "00000000-0000-4000-8000-000000000000"
    assert summary.calendar_date == date(2026, 10, 24)
    assert summary.total_kilocalories is None
    assert summary.total_steps is None
    assert summary.body_battery_most_recent_value is None
    assert summary.last_sync is None


async def test_user_settings_are_parsed(
    client: GarminPersonalClient, garmin: FakeGarmin, token: str
) -> None:
    garmin.add("GET", SETTINGS_PATH, Reply(body=load_fixture("user_settings.json")))

    settings = await client.async_get_user_settings()

    assert settings.display_name == "00000000-0000-4000-8000-000000000000"
    assert settings.time_zone == "Europe/Berlin"
    assert settings.measurement_system == "metric"


async def test_token_is_exchanged_once_for_several_requests(
    client: GarminPersonalClient, garmin: FakeGarmin, token: str
) -> None:
    garmin.add("GET", SETTINGS_PATH, Reply(body=load_fixture("user_settings.json")))
    garmin.add("GET", SUMMARY_PATH, Reply(body=load_fixture("daily_summary.json")))

    await client.async_get_user_settings()
    await client.async_get_daily_summary(DAY)

    assert len(garmin.calls("POST", TOKEN_PATH)) == 1


@pytest.mark.parametrize("status", [200, 204])
async def test_empty_daily_summary_is_none(
    client: GarminPersonalClient, garmin: FakeGarmin, token: str, status: int
) -> None:
    garmin.add("GET", SUMMARY_PATH, Reply(status=status))

    assert await client.async_get_daily_summary(DAY) is None


async def test_unauthorized_retries_once_with_new_token(
    client: GarminPersonalClient, garmin: FakeGarmin
) -> None:
    stale, fresh = (
        make_jwt(time.time() + 86_400, "stale"),
        make_jwt(time.time() + 86_400, "fresh"),
    )
    garmin.add("POST", TOKEN_PATH, Reply(body=stale))
    garmin.add("POST", TOKEN_PATH, Reply(body=fresh))
    garmin.add("GET", SUMMARY_PATH, Reply(status=401))
    garmin.add("GET", SUMMARY_PATH, Reply(body=load_fixture("daily_summary.json")))

    summary = await client.async_get_daily_summary(DAY)

    assert summary is not None
    assert [c.headers["Authorization"] for c in garmin.calls("GET", SUMMARY_PATH)] == [
        f"Bearer {stale}",
        f"Bearer {fresh}",
    ]


async def test_unauthorized_twice_raises_authentication_error(
    client: GarminPersonalClient, garmin: FakeGarmin, token: str
) -> None:
    garmin.add("GET", SUMMARY_PATH, Reply(status=401))

    with pytest.raises(GarminPersonalAuthenticationError):
        await client.async_get_daily_summary(DAY)

    assert len(garmin.calls("GET", SUMMARY_PATH)) == 2


async def test_rate_limit_raises_with_retry_after(
    client: GarminPersonalClient, garmin: FakeGarmin, token: str
) -> None:
    garmin.add("GET", SUMMARY_PATH, Reply(status=429, headers={"Retry-After": "60"}))

    with pytest.raises(GarminPersonalRateLimitError) as err:
        await client.async_get_daily_summary(DAY)

    assert err.value.retry_after == 60.0


@pytest.mark.parametrize("status", [403, 404, 500])
async def test_other_statuses_raise_response_error(
    client: GarminPersonalClient, garmin: FakeGarmin, token: str, status: int
) -> None:
    garmin.add("GET", SUMMARY_PATH, Reply(status=status))

    with pytest.raises(GarminPersonalResponseError) as err:
        await client.async_get_daily_summary(DAY)

    assert err.value.status == status


@pytest.mark.parametrize(
    "body",
    ["{not json", "[]", '{"calendarDate": "2026-10-22"}', '{"userProfileId": 1}'],
    ids=["invalid-json", "array", "no-user-id", "no-date"],
)
async def test_malformed_daily_summary_raises_response_error(
    client: GarminPersonalClient, garmin: FakeGarmin, token: str, body: str
) -> None:
    garmin.add("GET", SUMMARY_PATH, Reply(body=body))

    with pytest.raises(GarminPersonalResponseError):
        await client.async_get_daily_summary(DAY)


async def test_settings_that_are_not_an_object_raise_response_error(
    client: GarminPersonalClient, garmin: FakeGarmin, token: str
) -> None:
    garmin.add("GET", SETTINGS_PATH, Reply(body="[]"))

    with pytest.raises(GarminPersonalResponseError):
        await client.async_get_user_settings()


async def test_timeout_raises_connection_error(
    session: aiohttp.ClientSession, garmin: FakeGarmin, token: str
) -> None:
    garmin.add("GET", SUMMARY_PATH, Reply(body="{}", delay=1))
    client = GarminPersonalClient(
        session, "key", base_url=garmin.base_url, request_timeout=0.2
    )

    with pytest.raises(GarminPersonalConnectionError):
        await client.async_get_daily_summary(DAY)


async def test_unexpected_field_types_become_none(
    client: GarminPersonalClient, garmin: FakeGarmin, token: str
) -> None:
    garmin.add(
        "GET",
        SUMMARY_PATH,
        Reply(
            body='{"userProfileId": 1, "calendarDate": "2026-10-22", "totalSteps": 5000.0,'
            ' "restingHeartRate": true, "totalKilocalories": "lots", "maxHeartRate": 12.5,'
            ' "lastSyncTimestampGMT": "yesterday", "displayName": 7}'
        ),
    )

    summary = await client.async_get_daily_summary(DAY)

    assert summary is not None
    assert summary.total_steps == 5000
    assert summary.resting_heart_rate is None
    assert summary.total_kilocalories is None
    assert summary.max_heart_rate is None
    assert summary.last_sync is None
    assert summary.display_name is None


async def test_timestamp_with_offset_is_kept(
    client: GarminPersonalClient, garmin: FakeGarmin, token: str
) -> None:
    garmin.add(
        "GET",
        SUMMARY_PATH,
        Reply(
            body='{"userProfileId": 1, "calendarDate": "2026-10-23",'
            ' "lastSyncTimestampGMT": "2026-10-22T10:00:00+02:00"}'
        ),
    )

    summary = await client.async_get_daily_summary(DAY)

    assert summary is not None
    assert summary.last_sync == datetime(2026, 10, 22, 8, 0, tzinfo=UTC)
