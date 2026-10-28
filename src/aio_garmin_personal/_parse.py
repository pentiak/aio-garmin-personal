"""Lenient readers for fields of decoded JSON; a missing or mistyped field becomes `None`."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from typing import Any

from .exceptions import GarminPersonalResponseError

EMPTY: Mapping[str, Any] = {}


def opt_str(data: Mapping[str, Any], key: str) -> str | None:
    value = data.get(key)
    return value if isinstance(value, str) else None


def opt_bool(data: Mapping[str, Any], key: str) -> bool | None:
    value = data.get(key)
    return value if isinstance(value, bool) else None


def opt_int(data: Mapping[str, Any], key: str) -> int | None:
    value = data.get(key)
    # bool is a subclass of int and is never a valid metric.
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def opt_float(data: Mapping[str, Any], key: str) -> float | None:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def opt_date(data: Mapping[str, Any], key: str) -> date | None:
    value = data.get(key)
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def opt_connect_date(data: Mapping[str, Any], key: str) -> date | None:
    """Read a date sent as a string or, as Garmin's API description has it, an object.

    The object form holds the account-local day in `localDate`. Real responses checked so
    far send plain strings where the description promises the object.
    """
    value = data.get(key)
    if isinstance(value, Mapping):
        return opt_date(value, "localDate")
    return opt_date(data, key)


def opt_str_list(data: Mapping[str, Any], key: str) -> list[str]:
    value = data.get(key)
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def req_date(data: Mapping[str, Any], key: str, what: str) -> date:
    value = opt_date(data, key)
    if value is None:
        raise GarminPersonalResponseError(f"{what} has no valid {key}")
    return value


def opt_gmt_datetime(data: Mapping[str, Any], key: str) -> datetime | None:
    value = data.get(key)
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    # Garmin's *GMT fields carry no offset.
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def epoch_ms_to_utc(value: Any) -> datetime | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    try:
        return datetime.fromtimestamp(value / 1000, UTC)
    except (OverflowError, OSError, ValueError):
        return None


def opt_epoch_ms(data: Mapping[str, Any], key: str) -> datetime | None:
    return epoch_ms_to_utc(data.get(key))


def opt_obj(data: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    """Return a nested object, or an empty mapping so that lookups in it give `None`."""
    value = data.get(key)
    return value if isinstance(value, Mapping) else EMPTY


def opt_objs(data: Mapping[str, Any], key: str) -> list[Mapping[str, Any]]:
    """Return the objects of a nested array, skipping anything that is not an object."""
    value = data.get(key)
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def series(
    data: Mapping[str, Any],
    *,
    rows_field: str,
    descriptors_field: str,
    index_field: str,
    name_field: str,
    value_field: str,
) -> list[tuple[datetime, float]]:
    """Read a time series stored as rows of columns named by a descriptor list.

    Rows without a timestamp or a numeric value are skipped.
    """
    columns: dict[str, int] = {}
    for descriptor in opt_objs(data, descriptors_field):
        index = opt_int(descriptor, index_field)
        name = opt_str(descriptor, name_field)
        if index is not None and name is not None:
            columns[name] = index
    rows = data.get(rows_field)
    time_col = columns.get("timestamp")
    value_col = columns.get(value_field)
    if not isinstance(rows, list) or time_col is None or value_col is None:
        return []
    points: list[tuple[datetime, float]] = []
    for row in rows:
        if not isinstance(row, Sequence) or len(row) <= max(time_col, value_col):
            continue
        when = epoch_ms_to_utc(row[time_col])
        value = row[value_col]
        if (
            when is None
            or isinstance(value, bool)
            or not isinstance(value, int | float)
        ):
            continue
        points.append((when, value))
    return points
