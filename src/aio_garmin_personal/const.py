"""Constants for the Garmin Connect Personal API."""

from typing import Final

DEFAULT_BASE_URL: Final = "https://personal.connectapi.garmin.com"
DEFAULT_REQUEST_TIMEOUT: Final = 30.0

# bandit reads "TOKEN" in the name as a password; this is a URL path.
TOKEN_PATH: Final = "/personalapitoken-service/personal-api/personal-api-key/token"  # noqa: S105
USER_SETTINGS_PATH: Final = "/userprofile-service/userprofile/settings"
DAILY_SUMMARY_PATH: Final = "/usersummary-service/usersummary/daily"
ACTIVITIES_PATH: Final = "/activitylist-service/activities/search/activities"
ACTIVITY_PATH: Final = "/activity-service/activity/{activity_id}"
ACTIVITY_WORKOUTS_PATH: Final = "/activity-service/activity/{activity_id}/workouts"
ACTIVITY_FILE_PATH: Final = "/download-service/files/activity/{activity_id}"
SLEEP_PATH: Final = "/sleep-service/sleep/dailySleep"
SLEEP_RANGE_PATH: Final = "/sleep-service/sleep/dailySleepSummariesByDate"
HRV_PATH: Final = "/hrv-service/hrv/{day}"
HRV_RANGE_PATH: Final = "/hrv-service/hrv/daily/{start}/{end}"
HEART_RATE_PATH: Final = "/wellness-service/wellness/dailyHeartRate"
BODY_BATTERY_PATH: Final = "/wellness-service/wellness/bodyBattery/reports/daily"
SPO2_PATH: Final = "/wellness-service/wellness/daily/spo2acclimation/{day}"
DAILY_STEPS_PATH: Final = "/usersummary-service/stats/steps/daily/{start}/{end}"
DAILY_STRESS_PATH: Final = "/usersummary-service/stats/stress/daily/{start}/{end}"
DAILY_HYDRATION_PATH: Final = "/usersummary-service/stats/hydration/daily/{start}/{end}"
DAILY_OVERVIEWS_PATH: Final = "/usersummary-service/v2/dailysummaries"
WEIGHT_PATH: Final = "/weight-service/weight/range/{start}/{end}"
WEIGHT_GOALS_PATH: Final = "/goal-service/goal/user/effective/weightgoal/{start}/{end}"
FITNESS_AGE_PATH: Final = "/fitnessage-service/fitnessage/v2/{day}"
HEART_RATE_ZONES_PATH: Final = "/biometric-service/heartRateZones/v2"
WELLNESS_ACTIVITIES_PATH: Final = (
    "/wellnessactivity-service/activity/summary/range/{start}/{end}"
)

# Garmin's own client renews a token once it is within an hour of expiry.
TOKEN_REFRESH_MARGIN: Final = 3600.0
