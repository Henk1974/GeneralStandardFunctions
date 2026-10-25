"""Eenvoudige robotcontrole voor openbare formulieren, zonder externe dienst.

Drie lagen, zonder sessie of database:

1. een rekensom, met het antwoord in een ondertekend token (itsdangerous);
2. een honeypot-veld dat mensen niet zien en bots wel invullen;
3. een tijdslot: niet te snel (bot) en niet te laat (verlopen) verzonden.

Gebruik: ``create_challenge`` bij het tonen van het formulier (zet de vraag
in beeld en het token in een verborgen veld, plus een verborgen leeg
honeypot-veld), en ``verify_challenge`` bij het verzenden. Teken met de
geheime sleutel van de app (bijv. Flask ``secret_key``).
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Optional

from itsdangerous import BadSignature, URLSafeSerializer

from general_standard_functions.i18n import _

__all__ = [
    "MIN_SECONDS",
    "MAX_SECONDS",
    "DEFAULT_SALT",
    "CaptchaError",
    "HoneypotTriggered",
    "Challenge",
    "create_challenge",
    "verify_challenge",
]

MIN_SECONDS = 3
MAX_SECONDS = 2 * 60 * 60
DEFAULT_SALT = "contact-captcha"


class CaptchaError(ValueError):
    """Fout antwoord, of het token is ongeldig, te snel of verlopen.

    De tekst is geschikt om aan de gebruiker te tonen.
    """


class HoneypotTriggered(Exception):
    """Het verborgen veld is ingevuld: vrijwel zeker een bot.

    Doe alsof het gelukt is (geen foutmelding), zodat de bot niets leert.
    """


@dataclass(frozen=True)
class Challenge:
    """Een controlevraag.

    Attributes:
        question: De tekst voor de gebruiker, zoals "Hoeveel is 3 + 4?".
        token: Ondertekend token voor het verborgen formulierveld.
    """

    question: str
    token: str


def create_challenge(
    secret_key: str,
    now: Optional[float] = None,
    rng: Optional[random.Random] = None,
    salt: str = DEFAULT_SALT,
) -> Challenge:
    """Maak een nieuwe controlevraag (som van twee getallen van 2 t/m 9).

    Args:
        secret_key: Geheime sleutel om het token te ondertekenen.
        now: Tijdstip (Unix-seconden); standaard nu. Voor tests.
        rng: Bron van willekeurige getallen; standaard ``random.SystemRandom``. Voor tests.
        salt: Onderscheidt formulieren; gebruik per formulier een eigen salt.

    Returns:
        Een ``Challenge`` met vraag en token.
    """
    rng = rng or random.SystemRandom()
    a = rng.randint(2, 9)
    b = rng.randint(2, 9)
    issued_at = int(now if now is not None else time.time())
    token = URLSafeSerializer(secret_key, salt=salt).dumps({"s": a + b, "t": issued_at})
    return Challenge(question=_("Hoeveel is %(a)s + %(b)s?", a=a, b=b), token=token)


def verify_challenge(
    secret_key: str,
    token: str,
    answer: str,
    honeypot: str,
    now: Optional[float] = None,
    salt: str = DEFAULT_SALT,
) -> None:
    """Controleer alle drie de lagen; geen uitzondering betekent: een mens.

    Args:
        secret_key: Dezelfde sleutel als bij ``create_challenge``.
        token: Het token uit het verborgen veld.
        answer: Het antwoord van de gebruiker.
        honeypot: De inhoud van het honeypot-veld (hoort leeg te zijn).
        now: Tijdstip (Unix-seconden); standaard nu. Voor tests.
        salt: Dezelfde salt als bij ``create_challenge``.

    Raises:
        HoneypotTriggered: Het honeypot-veld is ingevuld.
        CaptchaError: Ongeldig of vervalst token, binnen ``MIN_SECONDS`` of
            na ``MAX_SECONDS`` verzonden, of een fout antwoord.
    """
    if honeypot and honeypot.strip():
        raise HoneypotTriggered()

    try:
        payload = URLSafeSerializer(secret_key, salt=salt).loads(token or "")
        expected = int(payload["s"])
        issued_at = int(payload["t"])
    except (BadSignature, KeyError, TypeError, ValueError) as exc:
        raise CaptchaError(_("De controlevraag is ongeldig. Probeer het opnieuw.")) from exc

    elapsed = (now if now is not None else time.time()) - issued_at
    if elapsed < MIN_SECONDS:
        raise CaptchaError(_("Dat ging wel erg snel. Probeer het nog eens."))
    if elapsed > MAX_SECONDS:
        raise CaptchaError(_("De controlevraag is verlopen. Beantwoord de nieuwe vraag."))

    try:
        given = int((answer or "").strip())
    except ValueError as exc:
        raise CaptchaError(_("Vul bij de controlevraag een getal in.")) from exc
    if given != expected:
        raise CaptchaError(_("Het antwoord op de controlevraag klopt niet."))
