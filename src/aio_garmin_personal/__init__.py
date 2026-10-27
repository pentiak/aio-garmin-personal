"""Asynchronous client for the Garmin Connect Personal API."""

from .auth import AccessToken, TokenProvider
from .client import GarminPersonalClient
from .const import DEFAULT_BASE_URL
from .exceptions import (
    GarminPersonalAuthenticationError,
    GarminPersonalConnectionError,
    GarminPersonalError,
    GarminPersonalRateLimitError,
    GarminPersonalResponseError,
)
from .models import Activity, DailySummary, UserSettings

__all__ = [
    "DEFAULT_BASE_URL",
    "AccessToken",
    "Activity",
    "DailySummary",
    "GarminPersonalAuthenticationError",
    "GarminPersonalClient",
    "GarminPersonalConnectionError",
    "GarminPersonalError",
    "GarminPersonalRateLimitError",
    "GarminPersonalResponseError",
    "TokenProvider",
    "UserSettings",
]
