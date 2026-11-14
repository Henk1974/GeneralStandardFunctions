"""Plaatsnamen omzetten naar coördinaten met OpenStreetMap Nominatim.

Gratis, met een gebruiksbeleid: een eigen User-Agent met contactgegevens,
hooguit één verzoek per seconde (deze client wacht zo nodig zelf) en
resultaten bewaren in plaats van steeds opnieuw vragen. Vermeld de bron:
"© OpenStreetMap-bijdragers".

Voor privacy: rond coördinaten af met ``coarse`` voordat je ze bewaart; met
één decimaal ligt de plek op ongeveer 10 km nauwkeurig, dus geen adres.
"""

from __future__ import annotations

import threading
import time
from typing import Optional, Tuple

import requests

__all__ = ["NominatimError", "NominatimClient", "coarse"]

API_URL = "https://nominatim.openstreetmap.org/search"
MIN_INTERVAL = 1.0


class NominatimError(Exception):
    """Nominatim gaf een foutstatus of een onleesbaar antwoord."""


def coarse(latitude: float, longitude: float, decimals: int = 1) -> Tuple[float, float]:
    """Rond een plek af, zodat er geen precieze locatie bewaard wordt.

    Example:
        >>> coarse(52.0841923, 5.0988034)
        (52.1, 5.1)
    """
    return round(latitude, decimals), round(longitude, decimals)


class NominatimClient:
    """Zoekt de coördinaten van een plaats.

    Args:
        user_agent: Naam en contact van de app (verplicht volgens het beleid).
        timeout: Seconden voordat een verzoek opgeeft.
        api_url: Alleen voor tests.

    Raises:
        ValueError: Geen User-Agent opgegeven.
    """

    _lock = threading.Lock()
    _last_request = 0.0

    def __init__(self, user_agent: str, timeout: float = 5.0, api_url: str = API_URL) -> None:
        if not user_agent:
            raise ValueError("Nominatim vereist een User-Agent met contactgegevens.")
        self._user_agent = user_agent
        self._timeout = timeout
        self._api_url = api_url

    def geocode_city(self, city: str, country_code: Optional[str] = None) -> Optional[Tuple[float, float]]:
        """Coördinaten van een plaats, of ``None`` als hij niet gevonden is.

        Args:
            city: Plaatsnaam, bijv. ``"Utrecht"``.
            country_code: ISO-landcode om binnen te zoeken, bijv. ``"NL"``.

        Raises:
            NominatimError: Foutstatus of onleesbaar antwoord.
            requests.RequestException: Netwerkfout of time-out.
        """
        if not (city or "").strip():
            return None
        params = {"city": city.strip(), "format": "jsonv2", "limit": 1}
        if country_code:
            params["countrycodes"] = country_code.lower()
        with NominatimClient._lock:
            wait = MIN_INTERVAL - (time.monotonic() - NominatimClient._last_request)
            if wait > 0:
                time.sleep(wait)
            NominatimClient._last_request = time.monotonic()
            response = requests.get(
                self._api_url, params=params, headers={"User-Agent": self._user_agent}, timeout=self._timeout
            )
        if response.status_code >= 300:
            raise NominatimError(f"Nominatim gaf status {response.status_code}.")
        try:
            results = response.json()
            if not results:
                return None
            return float(results[0]["lat"]), float(results[0]["lon"])
        except (ValueError, KeyError, TypeError, IndexError) as exc:
            raise NominatimError("Onleesbaar antwoord van Nominatim.") from exc
