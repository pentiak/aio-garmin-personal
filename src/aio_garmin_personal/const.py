"""Constants for the Garmin Connect Personal API."""

from typing import Final

DEFAULT_BASE_URL: Final = "https://personal.connectapi.garmin.com"
DEFAULT_REQUEST_TIMEOUT: Final = 30.0

# bandit reads "TOKEN" in the name as a password; this is a URL path.
TOKEN_PATH: Final = "/personalapitoken-service/personal-api/personal-api-key/token"  # noqa: S105
USER_SETTINGS_PATH: Final = "/userprofile-service/userprofile/settings"
DAILY_SUMMARY_PATH: Final = "/usersummary-service/usersummary/daily"
ACTIVITIES_PATH: Final = "/activitylist-service/activities/search/activities"

# Garmin's own client renews a token once it is within an hour of expiry.
TOKEN_REFRESH_MARGIN: Final = 3600.0
