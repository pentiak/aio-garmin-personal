# Changelog

## Unreleased

### Fixed

- A deleted API key raises `GarminPersonalAuthenticationError`. Garmin's token endpoint answers
  HTTP 404 for it, which raised `GarminPersonalResponseError`.

## 0.2.0 - 2026-10-27

### Added

- `async_get_activities()`, returning `Activity` objects with the owner's full name.

## 0.1.0 - 2026-10-23

### Added

- `GarminPersonalClient` with `async_get_user_settings()` and `async_get_daily_summary()`.
- Exchange of the Personal API key for access tokens, kept in memory and renewed before expiry.
- Exceptions for authentication, rate-limit, connection and response failures.
