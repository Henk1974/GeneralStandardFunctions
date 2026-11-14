"""Weersverwachting van het Noorse meteorologisch instituut (MET Norway).

De API (api.met.no, Locationforecast 2.0) is gratis, wereldwijd en ook voor
commercieel gebruik toegestaan, onder twee voorwaarden:

- elk verzoek heeft een eigen, herkenbare User-Agent met contactgegevens
  van de app (bijv. ``"MijnApp/1.0 https://mijnapp.nl/contact"``);
- bewaar antwoorden tot hun ``Expires``-tijd en vraag niet vaker; rond
  coördinaten af (hooguit 4 decimalen, liever minder), zodat buren dezelfde
  cache delen.

Vermeld de bron: "Weergegevens: MET Norway" (licentie CC BY 4.0).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, List, Mapping, Optional, Sequence

import requests

__all__ = ["MetNoError", "ForecastPoint", "Forecast", "MetNoClient", "parse_timeseries", "point_at"]

API_URL = "https://api.met.no/weatherapi/locationforecast/2.0/compact"


class MetNoError(Exception):
    """De weer-API gaf een foutstatus of een onleesbaar antwoord."""


@dataclass(frozen=True)
class ForecastPoint:
    """Het weer op één moment.

    Attributes:
        time: Tijdstip (UTC).
        temperature: Luchttemperatuur in °C.
        wind_speed: Wind in m/s.
        precipitation: Neerslag in mm in het uur erna (``None`` als onbekend).
        symbol: Weersymbool van MET Norway, bijv. ``"rain"`` of ``"clearsky_night"``.
    """

    time: datetime
    temperature: Optional[float]
    wind_speed: Optional[float]
    precipitation: Optional[float]
    symbol: Optional[str]


@dataclass(frozen=True)
class Forecast:
    """Een verwachting met de tijd tot wanneer hij geldig is.

    Attributes:
        points: Weer per tijdstip, oplopend.
        expires: Niet opnieuw vragen vóór dit moment (UTC); ``None`` als onbekend.
        raw: Het ruwe antwoord, om te bewaren en later met
            ``parse_timeseries`` opnieuw te lezen.
    """

    points: List[ForecastPoint]
    expires: Optional[datetime]
    raw: dict


def parse_timeseries(data: Mapping[str, Any]) -> List[ForecastPoint]:
    """Lees de tijdreeks uit een antwoord van Locationforecast.

    Example:
        >>> parse_timeseries({"properties": {"timeseries": [{"time": "2026-11-14T18:00:00Z", "data": {
        ...     "instant": {"details": {"air_temperature": 3.4, "wind_speed": 2.8}},
        ...     "next_1_hours": {"summary": {"symbol_code": "rain"}, "details": {"precipitation_amount": 1.2}}}}]}})
        ... # doctest: +NORMALIZE_WHITESPACE
        [ForecastPoint(time=datetime.datetime(2026, 11, 14, 18, 0, tzinfo=datetime.timezone.utc),
                       temperature=3.4, wind_speed=2.8, precipitation=1.2, symbol='rain')]
    """
    points = []
    for item in ((data.get("properties") or {}).get("timeseries")) or []:
        values = item.get("data") or {}
        details = (values.get("instant") or {}).get("details") or {}
        period = values.get("next_1_hours") or values.get("next_6_hours") or {}
        points.append(ForecastPoint(
            time=datetime.fromisoformat(item["time"].replace("Z", "+00:00")),
            temperature=details.get("air_temperature"),
            wind_speed=details.get("wind_speed"),
            precipitation=(period.get("details") or {}).get("precipitation_amount"),
            symbol=(period.get("summary") or {}).get("symbol_code"),
        ))
    return points


def point_at(points: Sequence[ForecastPoint], moment: datetime) -> Optional[ForecastPoint]:
    """Het tijdstip in de verwachting dat het dichtst bij ``moment`` ligt.

    Example:
        >>> from datetime import timedelta
        >>> start = datetime(2026, 11, 14, 18, tzinfo=timezone.utc)
        >>> pts = [ForecastPoint(start + timedelta(hours=h), h, None, None, None) for h in range(4)]
        >>> point_at(pts, start + timedelta(hours=2, minutes=20)).temperature
        2
    """
    if not points:
        return None
    return min(points, key=lambda point: abs((point.time - moment).total_seconds()))


class MetNoClient:
    """Haalt verwachtingen op bij api.met.no.

    Args:
        user_agent: Naam en contact van de app (verplicht volgens de voorwaarden).
        timeout: Seconden voordat een verzoek opgeeft; houd dit kort, het weer
            is meestal een extraatje.
        api_url: Alleen voor tests.

    Raises:
        ValueError: Geen User-Agent opgegeven.
    """

    def __init__(self, user_agent: str, timeout: float = 4.0, api_url: str = API_URL) -> None:
        if not user_agent:
            raise ValueError("MET Norway vereist een User-Agent met contactgegevens.")
        self._user_agent = user_agent
        self._timeout = timeout
        self._api_url = api_url

    def forecast(self, latitude: float, longitude: float) -> Forecast:
        """De verwachting voor een plek (afgerond op 4 decimalen).

        Raises:
            MetNoError: Foutstatus of onleesbaar antwoord.
            requests.RequestException: Netwerkfout of time-out.
        """
        response = requests.get(
            self._api_url,
            params={"lat": round(latitude, 4), "lon": round(longitude, 4)},
            headers={"User-Agent": self._user_agent},
            timeout=self._timeout,
        )
        if response.status_code >= 300:
            raise MetNoError(f"Weer-API gaf status {response.status_code}.")
        try:
            data = response.json()
            points = parse_timeseries(data)
        except (ValueError, KeyError, TypeError) as exc:
            raise MetNoError("Onleesbaar antwoord van de weer-API.") from exc
        return Forecast(points, _expires(response.headers.get("Expires")), data)


def _expires(header: Optional[str]) -> Optional[datetime]:
    if not header:
        return None
    try:
        return parsedate_to_datetime(header).astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None
