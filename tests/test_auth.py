from __future__ import annotations

import aiohttp
import pytest

from aio_garmin_personal import (
    GarminPersonalAuthenticationError,
    GarminPersonalConnectionError,
    GarminPersonalRateLimitError,
    GarminPersonalResponseError,
    TokenProvider,
)
from aio_garmin_personal.auth import jwt_expiry, parse_retry_after

from .conftest import API_KEY, NOW, TOKEN_PATH, FakeGarmin, Reply, make_jwt


class FakeClock:
    def __init__(self, now: float) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


def provider(
    session: aiohttp.ClientSession,
    garmin: FakeGarmin,
    clock: FakeClock,
    request_timeout: float = 2,
) -> TokenProvider:
    return TokenProvider(
        session,
        API_KEY,
        base_url=garmin.base_url,
        request_timeout=request_timeout,
        clock=clock,
    )


async def test_exchanges_key_with_api_key_header(
    session: aiohttp.ClientSession, garmin: FakeGarmin
) -> None:
    token = make_jwt(NOW + 86_400)
    garmin.add("POST", TOKEN_PATH, Reply(body=f"{token}\n"))

    result = await provider(session, garmin, FakeClock(NOW)).async_get_token()

    assert result == token
    (call,) = garmin.calls("POST", TOKEN_PATH)
    assert call.headers["Authorization"] == "ApiKey test-api-key"


async def test_reuses_token_until_refresh_margin(
    session: aiohttp.ClientSession, garmin: FakeGarmin
) -> None:
    first, second = (
        make_jwt(NOW + 86_400, "first"),
        make_jwt(NOW + 2 * 86_400, "second"),
    )
    garmin.add("POST", TOKEN_PATH, Reply(body=first))
    garmin.add("POST", TOKEN_PATH, Reply(body=second))
    clock = FakeClock(NOW)
    tokens = provider(session, garmin, clock)

    assert await tokens.async_get_token() == first
    clock.now = NOW + 86_400 - 3_601
    assert await tokens.async_get_token() == first
    clock.now = NOW + 86_400 - 3_600
    assert await tokens.async_get_token() == second
    assert len(garmin.calls("POST", TOKEN_PATH)) == 2


async def test_invalidate_forces_new_exchange(
    session: aiohttp.ClientSession, garmin: FakeGarmin
) -> None:
    first, second = make_jwt(NOW + 86_400, "first"), make_jwt(NOW + 86_400, "second")
    garmin.add("POST", TOKEN_PATH, Reply(body=first))
    garmin.add("POST", TOKEN_PATH, Reply(body=second))
    tokens = provider(session, garmin, FakeClock(NOW))

    await tokens.async_get_token()
    tokens.invalidate()

    assert await tokens.async_get_token() == second


@pytest.mark.parametrize("status", [401, 403])
async def test_rejected_key_raises_authentication_error(
    session: aiohttp.ClientSession, garmin: FakeGarmin, status: int
) -> None:
    garmin.add("POST", TOKEN_PATH, Reply(status=status))

    with pytest.raises(GarminPersonalAuthenticationError):
        await provider(session, garmin, FakeClock(NOW)).async_get_token()


async def test_rate_limit_carries_retry_after(
    session: aiohttp.ClientSession, garmin: FakeGarmin
) -> None:
    garmin.add("POST", TOKEN_PATH, Reply(status=429, headers={"Retry-After": "120"}))

    with pytest.raises(GarminPersonalRateLimitError) as err:
        await provider(session, garmin, FakeClock(NOW)).async_get_token()

    assert err.value.retry_after == 120.0


async def test_server_error_raises_response_error(
    session: aiohttp.ClientSession, garmin: FakeGarmin
) -> None:
    garmin.add("POST", TOKEN_PATH, Reply(status=503))

    with pytest.raises(GarminPersonalResponseError) as err:
        await provider(session, garmin, FakeClock(NOW)).async_get_token()

    assert err.value.status == 503


async def test_non_jwt_body_raises_response_error(
    session: aiohttp.ClientSession, garmin: FakeGarmin
) -> None:
    garmin.add("POST", TOKEN_PATH, Reply(body="<html>maintenance</html>"))

    with pytest.raises(GarminPersonalResponseError):
        await provider(session, garmin, FakeClock(NOW)).async_get_token()


async def test_unreachable_server_raises_connection_error(
    session: aiohttp.ClientSession,
) -> None:
    tokens = TokenProvider(
        session,
        API_KEY,
        base_url="http://127.0.0.1:9",
        request_timeout=2,
        clock=FakeClock(NOW),
    )

    with pytest.raises(GarminPersonalConnectionError):
        await tokens.async_get_token()


async def test_timeout_raises_connection_error(
    session: aiohttp.ClientSession, garmin: FakeGarmin
) -> None:
    garmin.add("POST", TOKEN_PATH, Reply(body=make_jwt(NOW + 86_400), delay=1))

    with pytest.raises(GarminPersonalConnectionError):
        await provider(
            session, garmin, FakeClock(NOW), request_timeout=0.1
        ).async_get_token()


def test_empty_key_is_rejected(session: aiohttp.ClientSession) -> None:
    with pytest.raises(ValueError, match="api_key"):
        TokenProvider(session, "  ", base_url="http://unused", request_timeout=5)


def test_jwt_expiry_reads_exp_claim() -> None:
    assert jwt_expiry(make_jwt(1_900_000_000)) == 1_900_000_000.0


@pytest.mark.parametrize(
    "token",
    [
        "not-a-jwt",
        "a.!!!.c",
        "eyJhbGciOiJub25lIn0.eyJzdWIiOiJ4In0.sig",
        "eyJhbGciOiJub25lIn0.eyJleHAiOiJzb29uIn0.sig",
        "eyJhbGciOiJub25lIn0.eyJleHAiOnRydWV9.sig",
    ],
    ids=["no-segments", "bad-base64", "no-exp", "string-exp", "bool-exp"],
)
def test_jwt_expiry_rejects_malformed_tokens(token: str) -> None:
    with pytest.raises(GarminPersonalResponseError):
        jwt_expiry(token)


@pytest.mark.parametrize(
    ("header", "expected"),
    [(None, None), ("30", 30.0), ("-1", None), ("Wed, 21 Oct 2026 07:28:00 GMT", None)],
)
def test_parse_retry_after(header: str | None, expected: float | None) -> None:
    assert parse_retry_after(header) == expected
