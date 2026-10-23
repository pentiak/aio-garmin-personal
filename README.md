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

| Method | Endpoint |
|---|---|
| `async_get_user_settings()` | `GET /userprofile-service/userprofile/settings` |
| `async_get_daily_summary(day)` | `GET /usersummary-service/usersummary/daily` |

More endpoints are added as the Home Assistant integration needs them.

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
