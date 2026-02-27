"""Date range parsing for feed filtering."""

from datetime import datetime, timedelta, timezone


def parse_date_range(
    range_param: str,
    from_param: str,
    to_param: str,
    default_range: str,
) -> tuple[datetime | None, datetime | None]:
    """Parse date range parameters into from/to datetime bounds.

    Explicit from/to (ISO 8601) override the range preset. When both are
    absent, the range_param preset is used; if that is empty, default_range
    is used.

    Args:
        range_param: A preset range name (e.g. "last_month").
        from_param: ISO 8601 start date string (optional).
        to_param: ISO 8601 end date string (optional).
        default_range: Fallback preset when range_param is empty.

    Returns:
        Tuple of (from_dt, to_dt). Either may be None (open-ended).

    Raises:
        ValueError: For invalid ISO 8601 strings or unknown range presets.
    """
    if from_param or to_param:
        from_dt = _parse_iso(from_param) if from_param else None
        to_dt = _parse_iso(to_param) if to_param else None
        return from_dt, to_dt

    preset = range_param or default_range
    return _apply_preset(preset), None


def _parse_iso(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError(f"invalid ISO 8601 date: {value!r}")


def _apply_preset(preset: str) -> datetime:
    now = datetime.now(tz=timezone.utc)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    presets = {
        "today": today,
        "last_week": today - timedelta(days=7),
        "last_month": today.replace(month=today.month - 1)
        if today.month > 1
        else today.replace(year=today.year - 1, month=12),
        "last_3_months": _subtract_months(today, 3),
        "last_6_months": _subtract_months(today, 6),
        "last_year": today.replace(year=today.year - 1),
    }

    if preset not in presets:
        raise ValueError(f"invalid range: {preset!r}")
    return presets[preset]


def _subtract_months(dt: datetime, months: int) -> datetime:
    total_months = dt.year * 12 + (dt.month - 1) - months
    year, month = divmod(total_months, 12)
    return dt.replace(year=year, month=month + 1)
