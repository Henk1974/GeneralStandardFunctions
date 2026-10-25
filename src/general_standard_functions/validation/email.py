"""E-mailadressen controleren en normaliseren.

Twee niveaus: alleen het formaat (bijvoorbeeld voor een contactformulier),
of het formaat plus een lijst toegestane domeinen (bijvoorbeeld bij
registratie, als drempel tegen wegwerpadressen). Beide geven het adres in
kleine letters en zonder witruimte terug, zodat je het zo kunt opslaan en
vergelijken.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

__all__ = [
    "MAX_EMAIL_LENGTH",
    "InvalidEmailError",
    "normalize_email_format",
    "normalize_email",
]

MAX_EMAIL_LENGTH = 255

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class InvalidEmailError(ValueError):
    """Het e-mailadres is leeg, ongeldig of heeft een niet-toegestaan domein."""


def normalize_email_format(email: str) -> str:
    """Controleer alleen het formaat van een e-mailadres en normaliseer het.

    Bewust eenvoudig: precies één ``@``, een punt in het domein, geen
    witruimte en maximaal ``MAX_EMAIL_LENGTH`` tekens. Of het adres echt
    bestaat, blijkt pas als je er een mail naartoe stuurt.

    Args:
        email: Het ingevulde adres, mag witruimte en hoofdletters bevatten.

    Returns:
        Het adres in kleine letters, zonder witruimte rondom.

    Raises:
        InvalidEmailError: Het adres is leeg of heeft geen geldig formaat.

    Example:
        >>> normalize_email_format("  Henk@Example.COM ")
        'henk@example.com'
    """
    stripped = (email or "").strip().lower()
    if not stripped:
        raise InvalidEmailError("E-mailadres is verplicht.")
    if len(stripped) > MAX_EMAIL_LENGTH or not _EMAIL_RE.match(stripped):
        raise InvalidEmailError(f"{email.strip()!r} is geen geldig e-mailadres.")
    return stripped


def normalize_email(email: str, allowed_domains: Iterable[str], rejection_hint: str = "") -> str:
    """Controleer formaat én domein van een e-mailadres en normaliseer het.

    Args:
        email: Het ingevulde adres.
        allowed_domains: Domeinen die zijn toegestaan, zoals
            ``{"gmail.com", "outlook.com"}``. Hoofdletters maken niet uit.
        rejection_hint: Optionele tekst achter de foutmelding bij een
            niet-toegestaan domein, zoals "Gebruik een Gmail-adres.".

    Returns:
        Het adres in kleine letters, zonder witruimte rondom.

    Raises:
        InvalidEmailError: Het adres is leeg, ongeldig of het domein staat
            niet in ``allowed_domains``.

    Example:
        >>> normalize_email("Henk@Gmail.com", {"gmail.com"})
        'henk@gmail.com'
    """
    clean = normalize_email_format(email)
    domain = clean.rsplit("@", 1)[-1]
    if domain not in {allowed.lower() for allowed in allowed_domains}:
        message = f"E-mailadressen van domein {domain!r} worden niet ondersteund."
        raise InvalidEmailError(f"{message} {rejection_hint}".strip())
    return clean
