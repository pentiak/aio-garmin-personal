# Changelog

## Unreleased

### Added

- `GarminPersonalClient` with `async_get_user_settings()` and `async_get_daily_summary()`.
- Exchange of the Personal API key for access tokens, kept in memory and renewed before expiry.
- Exceptions for authentication, rate-limit, connection and response failures.
