"""Tests for feed date range parsing."""

from datetime import datetime, timezone

import pytest

from feed.date_range import parse_date_range


class TestParseDateRange:
    def test_explicit_from_and_to_override_range(self):
        """Explicit from/to params override the range preset."""
        from_dt, to_dt = parse_date_range(
            range_param="",
            from_param="2024-01-01T00:00:00Z",
            to_param="2024-06-30T23:59:59Z",
            default_range="last_month",
        )
        assert from_dt is not None
        assert to_dt is not None
        assert from_dt.year == 2024
        assert from_dt.month == 1
        assert to_dt.month == 6

    def test_from_only_sets_from_and_no_to(self):
        """Only from param produces a bounded from with open to."""
        from_dt, to_dt = parse_date_range(
            range_param="",
            from_param="2024-01-01T00:00:00Z",
            to_param="",
            default_range="last_month",
        )
        assert from_dt is not None
        assert to_dt is None

    def test_today_preset(self):
        """'today' preset returns start of today as from, no to."""
        from_dt, to_dt = parse_date_range(
            range_param="today",
            from_param="",
            to_param="",
            default_range="last_month",
        )
        now = datetime.now(tz=timezone.utc)
        assert from_dt is not None
        assert from_dt.year == now.year
        assert from_dt.month == now.month
        assert from_dt.day == now.day
        assert from_dt.hour == 0
        assert to_dt is None

    def test_last_week_preset(self):
        """'last_week' returns a date 7 days in the past."""
        from_dt, _ = parse_date_range("last_week", "", "", "last_month")
        assert from_dt is not None
        now = datetime.now(tz=timezone.utc)
        delta = now - from_dt
        assert 6 <= delta.days <= 8

    def test_last_month_preset(self):
        """'last_month' returns a date approximately 1 month in the past."""
        from_dt, _ = parse_date_range("last_month", "", "", "last_month")
        assert from_dt is not None
        now = datetime.now(tz=timezone.utc)
        delta = now - from_dt
        assert 28 <= delta.days <= 32

    def test_last_3_months_preset(self):
        """'last_3_months' returns a date approximately 3 months in the past."""
        from_dt, _ = parse_date_range("last_3_months", "", "", "last_month")
        assert from_dt is not None
        now = datetime.now(tz=timezone.utc)
        delta = now - from_dt
        assert 85 <= delta.days <= 95

    def test_last_6_months_preset(self):
        """'last_6_months' returns a date approximately 6 months in the past."""
        from_dt, _ = parse_date_range("last_6_months", "", "", "last_month")
        assert from_dt is not None
        now = datetime.now(tz=timezone.utc)
        delta = now - from_dt
        assert 175 <= delta.days <= 185

    def test_last_year_preset(self):
        """'last_year' returns a date approximately 365 days in the past."""
        from_dt, _ = parse_date_range("last_year", "", "", "last_month")
        assert from_dt is not None
        now = datetime.now(tz=timezone.utc)
        delta = now - from_dt
        assert 364 <= delta.days <= 367

    def test_default_range_used_when_no_range_or_params(self):
        """When range_param is empty and no from/to, use default_range."""
        from_dt, _ = parse_date_range("", "", "", "today")
        assert from_dt is not None
        now = datetime.now(tz=timezone.utc)
        assert from_dt.date() == now.date()

    def test_invalid_range_raises_value_error(self):
        """An unrecognised range preset should raise ValueError."""
        with pytest.raises(ValueError, match="invalid range"):
            parse_date_range("bad_range", "", "", "last_month")

    def test_invalid_from_raises_value_error(self):
        """A malformed from ISO 8601 string should raise ValueError."""
        with pytest.raises(ValueError):
            parse_date_range("", "not-a-date", "", "last_month")
