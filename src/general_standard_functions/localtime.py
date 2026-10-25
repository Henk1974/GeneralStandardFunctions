"""Tijdstippen opslaan in UTC en tonen in lokale (standaard Nederlandse) tijd.

Afspraak: in de database staat altijd UTC (``TIMESTAMPTZ``). Pas bij het
tonen zet je om naar lokale tijd, en wat de gebruiker invult zet je terug
naar UTC. Zomer- en wintertijd gaan dan vanzelf goed. Alle functies hebben
een ``tz``-argument; standaard is dat ``DEFAULT_TIMEZONE`` (Europe/Amsterdam).
"""

from __future__ import annotations

from datetime import datetime, timezone, tzinfo
from typing import Optional
from zoneinfo import ZoneInfo

from general_standard_functions.i18n import _

__all__ = [
    "DEFAULT_TIMEZONE",
    "EMPTY_PLACEHOLDER",
    "to_local",
    "format_local",
    "format_local_nl",
    "InvalidLocalDatetimeError",
    "parse_local_datetime",
]

DEFAULT_TIMEZONE = ZoneInfo("Europe/Amsterdam")
EMPTY_PLACEHOLDER = "—"

_DAYS_NL = ["ma", "di", "wo", "do", "vr", "za", "zo"]
_MONTHS_NL = ["jan", "feb", "mrt", "apr", "mei", "jun", "jul", "aug", "sep", "okt", "nov", "dec"]


def to_local(value: Optional[datetime], tz: tzinfo = DEFAULT_TIMEZONE) -> Optional[datetime]:
    """Zet een tijdstip om naar lokale tijd.

    Args:
        value: Het tijdstip; zonder tijdzone ("naive") geldt het als UTC,
            omdat de database in UTC opslaat.
        tz: De doeltijdzone.

    Returns:
        Hetzelfde moment in ``tz``, of ``None`` als ``value`` ``None`` is.

    Example:
        >>> to_local(datetime(2026, 7, 1, 18, 0)).hour
        20
    """
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(tz)


def format_local(
    value: Optional[datetime], fmt: str = "%Y-%m-%d %H:%M", tz: tzinfo = DEFAULT_TIMEZONE
) -> str:
    """Formatteer een tijdstip in lokale tijd, geschikt als Jinja-filter.

    Args:
        value: Het tijdstip (naive = UTC).
        fmt: ``strftime``-formaat.
        tz: De tijdzone waarin je het wilt tonen.

    Returns:
        De opgemaakte tekst, of ``EMPTY_PLACEHOLDER`` ("—") als er geen
        tijdstip is.

    Example:
        >>> format_local(datetime(2026, 1, 15, 18, 0, tzinfo=timezone.utc))
        '2026-01-15 19:00'
    """
    local = to_local(value, tz)
    return local.strftime(fmt) if local else EMPTY_PLACEHOLDER


def format_local_nl(value: Optional[datetime], with_time: bool = True, tz: tzinfo = DEFAULT_TIMEZONE) -> str:
    """Formatteer een tijdstip met Nederlandse dag- en maandnamen.

    Werkt los van de taalinstelling (locale) van de server.

    Args:
        value: Het tijdstip (naive = UTC).
        with_time: Ook uren en minuten tonen.
        tz: De tijdzone waarin je het wilt tonen.

    Returns:
        Bijvoorbeeld "za 14 nov 2026, 20:00", of "—" als er geen tijdstip is.

    Example:
        >>> format_local_nl(datetime(2026, 11, 14, 19, 0, tzinfo=timezone.utc))
        'za 14 nov 2026, 20:00'
    """
    local = to_local(value, tz)
    if local is None:
        return EMPTY_PLACEHOLDER
    text = f"{_DAYS_NL[local.weekday()]} {local.day} {_MONTHS_NL[local.month - 1]} {local.year}"
    return f"{text}, {local:%H:%M}" if with_time else text


class InvalidLocalDatetimeError(ValueError):
    """Er is geen geldige datum/tijd ingevuld."""


def parse_local_datetime(text: str, tz: tzinfo = DEFAULT_TIMEZONE) -> datetime:
    """Lees een ingevulde lokale datum/tijd en geef UTC terug voor opslag.

    Bedoeld voor de waarde van ``<input type="datetime-local">``, zoals
    "2026-11-14T20:00". Bevat de tekst al een tijdzone, dan wordt die
    gerespecteerd.

    Args:
        text: De ingevulde datum/tijd (ISO 8601).
        tz: De tijdzone waarin de gebruiker denkt.

    Returns:
        Het moment in UTC, met tijdzone.

    Raises:
        InvalidLocalDatetimeError: Leeg of geen geldig formaat.

    Example:
        >>> parse_local_datetime("2026-11-14T20:00")
        datetime.datetime(2026, 11, 14, 19, 0, tzinfo=datetime.timezone.utc)
    """
    try:
        parsed = datetime.fromisoformat((text or "").strip())
    except ValueError as exc:
        raise InvalidLocalDatetimeError(_("Vul een geldige datum en tijd in.")) from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=tz)
    return parsed.astimezone(timezone.utc)
