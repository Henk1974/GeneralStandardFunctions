from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from general_standard_functions.geo import nominatim
from general_standard_functions.geo.nominatim import NominatimClient, NominatimError, coarse
from general_standard_functions.weather.metno import MetNoClient, MetNoError

FORECAST = {"properties": {"timeseries": [
    {"time": "2026-11-14T18:00:00Z", "data": {
        "instant": {"details": {"air_temperature": 3.4, "wind_speed": 2.8}},
        "next_1_hours": {"summary": {"symbol_code": "rain"}, "details": {"precipitation_amount": 1.2}}}},
    {"time": "2026-11-15T06:00:00Z", "data": {
        "instant": {"details": {"air_temperature": 1.0, "wind_speed": 5.0}},
        "next_6_hours": {"summary": {"symbol_code": "cloudy"}, "details": {"precipitation_amount": 0.0}}}},
]}}


def _response(status=200, body=None, headers=None):
    response = MagicMock(status_code=status, headers=headers or {})
    response.json.return_value = body
    return response


def test_forecast_sends_user_agent_and_rounds_coordinates():
    with patch("general_standard_functions.weather.metno.requests.get",
               return_value=_response(body=FORECAST, headers={"Expires": "Sat, 14 Nov 2026 18:48:24 GMT"})) as get:
        forecast = MetNoClient("Test/1.0 https://example.org").forecast(52.084192, 5.098803)
    assert get.call_args.kwargs["headers"]["User-Agent"] == "Test/1.0 https://example.org"
    assert get.call_args.kwargs["params"] == {"lat": 52.0842, "lon": 5.0988}
    assert forecast.expires == datetime(2026, 11, 14, 18, 48, 24, tzinfo=timezone.utc)
    assert [p.symbol for p in forecast.points] == ["rain", "cloudy"]  # valt terug op next_6_hours
    assert forecast.raw == FORECAST


def test_forecast_error_status_raises():
    with patch("general_standard_functions.weather.metno.requests.get", return_value=_response(status=403)):
        with pytest.raises(MetNoError):
            MetNoClient("Test").forecast(52.1, 5.1)


def test_user_agent_is_required():
    with pytest.raises(ValueError):
        MetNoClient("")
    with pytest.raises(ValueError):
        NominatimClient("")


def test_geocode_city_within_country(monkeypatch):
    monkeypatch.setattr(nominatim, "MIN_INTERVAL", 0)
    with patch("general_standard_functions.geo.nominatim.requests.get",
               return_value=_response(body=[{"lat": "52.0841923", "lon": "5.0988034"}])) as get:
        assert NominatimClient("Test").geocode_city(" Utrecht ", "NL") == (52.0841923, 5.0988034)
    assert get.call_args.kwargs["params"]["city"] == "Utrecht"
    assert get.call_args.kwargs["params"]["countrycodes"] == "nl"


def test_unknown_or_empty_city_gives_none(monkeypatch):
    monkeypatch.setattr(nominatim, "MIN_INTERVAL", 0)
    with patch("general_standard_functions.geo.nominatim.requests.get", return_value=_response(body=[])) as get:
        assert NominatimClient("Test").geocode_city("Nergensdorp") is None
        assert NominatimClient("Test").geocode_city("  ") is None
    assert get.call_count == 1  # een lege naam vraagt niets


def test_geocode_error_raises(monkeypatch):
    monkeypatch.setattr(nominatim, "MIN_INTERVAL", 0)
    with patch("general_standard_functions.geo.nominatim.requests.get", return_value=_response(status=429)):
        with pytest.raises(NominatimError):
            NominatimClient("Test").geocode_city("Utrecht")


def test_requests_are_spaced_one_second_apart(monkeypatch):
    sleeps = []
    monkeypatch.setattr(nominatim.time, "sleep", sleeps.append)
    with patch("general_standard_functions.geo.nominatim.requests.get", return_value=_response(body=[])):
        client = NominatimClient("Test")
        client.geocode_city("A")
        client.geocode_city("B")
    assert sleeps and 0 < sleeps[-1] <= 1.0


def test_coarse_location_hides_the_address():
    assert coarse(52.0841923, 5.0988034) == (52.1, 5.1)
