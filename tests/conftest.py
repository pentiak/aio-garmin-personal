from __future__ import annotations

import asyncio
import base64
from collections import defaultdict
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
import json
from pathlib import Path
import time
from typing import Any

import aiohttp
from aiohttp import web
from aiohttp.test_utils import TestServer
import pytest

from aio_garmin_personal import GarminPersonalClient

TOKEN_PATH = "/personalapitoken-service/personal-api/personal-api-key/token"  # noqa: S105
SUMMARY_PATH = "/usersummary-service/usersummary/daily"
SETTINGS_PATH = "/userprofile-service/userprofile/settings"
ACTIVITIES_PATH = "/activitylist-service/activities/search/activities"
API_KEY = "test-api-key"
NOW = 1_800_000_000.0
FIXTURES = Path(__file__).parent / "fixtures"


def make_jwt(exp: float, subject: str = "token") -> str:
    def segment(data: dict[str, Any]) -> str:
        return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()

    return f"{segment({'alg': 'none'})}.{segment({'exp': exp, 'sub': subject})}.sig"


def load_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


@dataclass
class Reply:
    status: int = 200
    body: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    delay: float = 0.0


@dataclass
class Recorded:
    method: str
    path: str
    query: dict[str, str]
    headers: dict[str, str]


class FakeGarmin:
    """A local HTTP server that answers each route with queued replies, in order.

    The last reply queued for a route is repeated once the queue is exhausted.
    """

    def __init__(self) -> None:
        self.replies: dict[tuple[str, str], list[Reply]] = defaultdict(list)
        self.requests: list[Recorded] = []
        self.base_url = ""

    def add(self, method: str, path: str, reply: Reply) -> None:
        self.replies[(method, path)].append(reply)

    def calls(self, method: str, path: str) -> list[Recorded]:
        return [r for r in self.requests if r.method == method and r.path == path]

    async def handle(self, request: web.Request) -> web.Response:
        self.requests.append(
            Recorded(
                request.method, request.path, dict(request.query), dict(request.headers)
            )
        )
        queue = self.replies.get((request.method, request.path))
        if not queue:
            return web.Response(status=599, text="no reply queued")
        reply = queue.pop(0) if len(queue) > 1 else queue[0]
        if reply.delay:
            await asyncio.sleep(reply.delay)
        return web.Response(status=reply.status, text=reply.body, headers=reply.headers)


@pytest.fixture
async def garmin() -> AsyncIterator[FakeGarmin]:
    fake = FakeGarmin()
    app = web.Application()
    app.router.add_route("*", "/{tail:.*}", fake.handle)
    server = TestServer(app)
    await server.start_server()
    fake.base_url = str(server.make_url("")).rstrip("/")
    yield fake
    await server.close()


@pytest.fixture
async def session() -> AsyncIterator[aiohttp.ClientSession]:
    async with aiohttp.ClientSession() as client_session:
        yield client_session


@pytest.fixture
def client(session: aiohttp.ClientSession, garmin: FakeGarmin) -> GarminPersonalClient:
    return GarminPersonalClient(
        session, API_KEY, base_url=garmin.base_url, request_timeout=2
    )


@pytest.fixture
def token(garmin: FakeGarmin) -> str:
    value = make_jwt(time.time() + 86_400)
    garmin.add("POST", TOKEN_PATH, Reply(body=value))
    return value
