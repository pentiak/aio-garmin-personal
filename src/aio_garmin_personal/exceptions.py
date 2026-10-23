"""Exceptions raised by the Garmin Connect Personal API client."""


class GarminPersonalError(Exception):
    """Base class for all errors raised by this library."""


class GarminPersonalConnectionError(GarminPersonalError):
    """The API could not be reached, or the request timed out."""


class GarminPersonalAuthenticationError(GarminPersonalError):
    """The API key was rejected: it is wrong, expired or deleted.

    A new key from Garmin Connect is the only fix, so callers should ask the user for one
    instead of retrying.
    """


class GarminPersonalRateLimitError(GarminPersonalError):
    """The API answered HTTP 429."""

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        """Store the delay from the `Retry-After` header, in seconds, when Garmin sends one."""
        super().__init__(message)
        self.retry_after = retry_after


class GarminPersonalResponseError(GarminPersonalError):
    """The API answered with an unexpected status code or an unparseable body."""

    def __init__(self, message: str, status: int | None = None) -> None:
        """Store the HTTP status, or `None` when the status was fine but the body was not."""
        super().__init__(message)
        self.status = status
