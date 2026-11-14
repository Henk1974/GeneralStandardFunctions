"""Jaargetijden: welk seizoen het is op een datum, ook op het zuidelijk halfrond.

Gebruikt de meteorologische indeling (hele maanden): op het noordelijk
halfrond is december t/m februari winter, maart t/m mei lente, juni t/m
augustus zomer en september t/m november herfst. Op het zuidelijk halfrond
is het andersom.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

__all__ = ["WINTER", "SPRING", "SUMMER", "AUTUMN", "SOUTHERN_COUNTRIES", "season_on", "is_southern"]

WINTER, SPRING, SUMMER, AUTUMN = "winter", "spring", "summer", "autumn"

_NORTHERN = {12: WINTER, 1: WINTER, 2: WINTER, 3: SPRING, 4: SPRING, 5: SPRING,
             6: SUMMER, 7: SUMMER, 8: SUMMER, 9: AUTUMN, 10: AUTUMN, 11: AUTUMN}
_OPPOSITE = {WINTER: SUMMER, SUMMER: WINTER, SPRING: AUTUMN, AUTUMN: SPRING}

# ISO-landcodes die (vrijwel) geheel op het zuidelijk halfrond liggen.
SOUTHERN_COUNTRIES = frozenset({
    "AR", "AU", "BO", "BW", "CL", "FJ", "LS", "MG", "MU", "MW", "MZ", "NA",
    "NZ", "PE", "PY", "SZ", "TO", "UY", "WS", "ZA", "ZM", "ZW",
})


def is_southern(country_code: Optional[str]) -> bool:
    """``True`` als het land op het zuidelijk halfrond ligt. Onbekend is noordelijk.

    Example:
        >>> is_southern("au"), is_southern("NL"), is_southern(None)
        (True, False, False)
    """
    return (country_code or "").upper() in SOUTHERN_COUNTRIES


def season_on(day: date, southern: bool = False) -> str:
    """Het meteorologische seizoen op een datum.

    Args:
        day: De datum.
        southern: ``True`` voor het zuidelijk halfrond.

    Returns:
        ``"winter"``, ``"spring"``, ``"summer"`` of ``"autumn"``.

    Example:
        >>> season_on(date(2026, 11, 14))
        'autumn'
        >>> season_on(date(2026, 1, 10), southern=True)
        'summer'
    """
    season = _NORTHERN[day.month]
    return _OPPOSITE[season] if southern else season
