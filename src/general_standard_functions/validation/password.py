"""Wachtwoordbeleid: lengte, verplichte tekensoorten en een zwakke-lijst.

Het beleid is een ``PasswordPolicy``; elke app kiest zijn eigen eisen of
gebruikt ``DEFAULT_POLICY`` (minimaal 10 tekens, met een hoofdletter, een
cijfer en een speciaal teken). Laat elke plek waar een wachtwoord wordt
gekozen (registreren, wijzigen, herstellen) door ``validate_password`` gaan.
Het hashen zelf hoort hier niet: gebruik daarvoor
``werkzeug.security.generate_password_hash`` (scrypt).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = [
    "COMMON_WEAK_PASSWORDS",
    "PasswordPolicy",
    "DEFAULT_POLICY",
    "InvalidPasswordError",
    "validate_password",
]

# Kleine vaste lijst overduidelijk zwakke wachtwoorden, geen volledige
# database met gelekte wachtwoorden (dat vraagt een externe dienst).
COMMON_WEAK_PASSWORDS = frozenset(
    {
        "password",
        "password1",
        "wachtwoord",
        "wachtwoord1",
        "12345678",
        "123456789",
        "1234567890",
        "qwertyuiop",
        "letmein123",
        "welkom123",
        "iloveyou",
    }
)

_UPPERCASE_RE = re.compile(r"[A-ZÀ-ÖØ-Þ]")
_DIGIT_RE = re.compile(r"[0-9]")
_SPECIAL_RE = re.compile(r"[^A-Za-z0-9À-ÖØ-öø-ÿ]")


@dataclass(frozen=True)
class PasswordPolicy:
    """De eisen waaraan een wachtwoord moet voldoen.

    Attributes:
        min_length: Minimaal aantal tekens.
        require_uppercase: Minstens één hoofdletter (ook À-Þ).
        require_digit: Minstens één cijfer.
        require_special: Minstens één teken dat geen letter of cijfer is.
        weak_passwords: Verboden wachtwoorden, in kleine letters; de
            vergelijking negeert hoofdletters.
    """

    min_length: int = 10
    require_uppercase: bool = True
    require_digit: bool = True
    require_special: bool = True
    weak_passwords: frozenset[str] = COMMON_WEAK_PASSWORDS


DEFAULT_POLICY = PasswordPolicy()


class InvalidPasswordError(ValueError):
    """Het wachtwoord voldoet niet aan het beleid; de tekst zegt waarom."""


def validate_password(password: str, policy: PasswordPolicy = DEFAULT_POLICY) -> None:
    """Controleer een wachtwoord tegen het beleid.

    De controles lopen in vaste volgorde (lengte, zwakke-lijst, hoofdletter,
    cijfer, speciaal teken) en de eerste die faalt bepaalt de melding, zodat
    de gebruiker steeds één duidelijke opdracht krijgt.

    Args:
        password: Het gekozen wachtwoord.
        policy: Het beleid; standaard ``DEFAULT_POLICY``.

    Raises:
        InvalidPasswordError: Het wachtwoord is te kort, staat op de
            zwakke-lijst of mist een verplichte tekensoort. De melding is
            geschikt om aan de gebruiker te tonen.

    Example:
        >>> validate_password("Correct1-Horse")  # geldig: geen uitzondering
        >>> validate_password("kort", PasswordPolicy(min_length=12))
        Traceback (most recent call last):
        ...
        InvalidPasswordError: Wachtwoord moet minimaal 12 tekens lang zijn.
    """
    if password is None or len(password) < policy.min_length:
        raise InvalidPasswordError(f"Wachtwoord moet minimaal {policy.min_length} tekens lang zijn.")

    if password.lower() in policy.weak_passwords:
        raise InvalidPasswordError(
            "Dit wachtwoord is te makkelijk te raden. Kies iets unieks, bijvoorbeeld een korte zin."
        )

    if policy.require_uppercase and not _UPPERCASE_RE.search(password):
        raise InvalidPasswordError("Wachtwoord moet minstens één hoofdletter bevatten.")

    if policy.require_digit and not _DIGIT_RE.search(password):
        raise InvalidPasswordError("Wachtwoord moet minstens één cijfer bevatten.")

    if policy.require_special and not _SPECIAL_RE.search(password):
        raise InvalidPasswordError("Wachtwoord moet minstens één speciaal teken bevatten (bijv. ! ? # @ % -).")
