from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from general_standard_functions.localtime import (
    InvalidLocalDatetimeError,
    format_local,
    format_local_nl,
    parse_local_datetime,
    to_local,
)


def test_winter_and_summer_time():
    assert format_local(datetime(2026, 1, 15, 18, 0, tzinfo=timezone.utc)) == "2026-01-15 19:00"
    assert format_local(datetime(2026, 10, 1, 18, 0, tzinfo=timezone.utc)) == "2026-10-01 20:00"


def test_conversion_can_cross_midnight():
    assert format_local(datetime(2026, 12, 31, 23, 30, tzinfo=timezone.utc), "%Y-%m-%d") == "2027-01-01"


def test_naive_datetime_is_treated_as_utc():
    assert format_local(datetime(2026, 1, 15, 18, 0)) == "2026-01-15 19:00"


def test_none_shows_dash():
    assert format_local(None) == "—"
    assert format_local_nl(None) == "—"
    assert to_local(None) is None


def test_dutch_names():
    assert format_local_nl(datetime(2026, 11, 14, 19, 0, tzinfo=timezone.utc)) == "za 14 nov 2026, 20:00"
    assert format_local_nl(datetime(2026, 7, 4, 18, 0, tzinfo=timezone.utc), with_time=False) == "za 4 jul 2026"


def test_other_timezone():
    london = ZoneInfo("Europe/London")
    assert format_local(datetime(2026, 1, 15, 18, 0, tzinfo=timezone.utc), tz=london) == "2026-01-15 18:00"
    assert parse_local_datetime("2026-01-15T18:00", tz=london) == datetime(2026, 1, 15, 18, 0, tzinfo=timezone.utc)


def test_parse_local_input_to_utc():
    assert parse_local_datetime("2026-11-14T20:00") == datetime(2026, 11, 14, 19, 0, tzinfo=timezone.utc)
    assert parse_local_datetime("2026-07-04T20:00") == datetime(2026, 7, 4, 18, 0, tzinfo=timezone.utc)
    assert parse_local_datetime("2026-07-04T20:00+00:00") == datetime(2026, 7, 4, 20, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize("bad", ["", "morgen", None])
def test_parse_rejects_invalid(bad):
    with pytest.raises(InvalidLocalDatetimeError):
        parse_local_datetime(bad)
