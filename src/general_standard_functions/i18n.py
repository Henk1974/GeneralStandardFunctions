"""Vertaalhaak voor de meldingen van dit pakket (en van een app zelf).

De meldingen in dit pakket zijn Nederlands; dat is de brontekst. Zonder
verdere instellingen komt die tekst ongewijzigd terug, dus een app in één
taal hoeft niets te doen. Een meertalige app registreert één keer een
vertaalfunctie met ``set_translator``, bijvoorbeeld de ``gettext`` en
``ngettext`` van Flask-Babel; vanaf dan gaat elke melding daar doorheen.

Variabele delen staan als ``%(naam)s`` in de brontekst en worden pas ná het
vertalen ingevuld, zodat een vertaling ze op een andere plek in de zin kan
zetten. Een extractietool als ``pybabel extract`` vindt de teksten via de
namen ``_``, ``ngettext`` en ``N_``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Optional

__all__ = ["Translator", "PluralTranslator", "set_translator", "gettext", "ngettext", "N_", "_"]

Translator = Callable[[str], str]
PluralTranslator = Callable[[str, str, int], str]

_translator: Optional[Translator] = None
_plural_translator: Optional[PluralTranslator] = None


def set_translator(translator: Optional[Translator], plural_translator: Optional[PluralTranslator] = None) -> None:
    """Registreer de functies die een brontekst vertalen.

    Args:
        translator: Krijgt de brontekst (met ``%(naam)s`` er nog in) en geeft
            de vertaling terug. ``None`` zet het vertalen weer uit.
        plural_translator: Krijgt enkelvoud, meervoud en aantal en geeft de
            juiste vertaalde vorm terug. Zonder deze functie kiest
            ``ngettext`` zelf tussen de Nederlandse vormen.

    Example:
        >>> set_translator({"Hallo": "Hello"}.get)
        >>> gettext("Hallo")
        'Hello'
        >>> set_translator(None)
        >>> gettext("Hallo")
        'Hallo'
    """
    global _translator, _plural_translator
    _translator = translator
    _plural_translator = plural_translator


def gettext(message: str, **params: object) -> str:
    """Vertaal ``message`` en vul daarna de variabelen in.

    Args:
        message: De Nederlandse brontekst, eventueel met ``%(naam)s``.
        **params: De waarden voor de variabelen.

    Returns:
        De vertaalde tekst met ingevulde variabelen; zonder vertaler de
        brontekst zelf. Geeft de vertaler niets terug, dan ook de brontekst.

    Example:
        >>> gettext("Minimaal %(n)s tekens.", n=10)
        'Minimaal 10 tekens.'
    """
    text = (_translator(message) if _translator else None) or message
    return text % params if params else text


def ngettext(singular: str, plural: str, n: int, **params: object) -> str:
    """Vertaal een tekst met een enkelvoud en een meervoud.

    Args:
        singular: De Nederlandse tekst voor precies één.
        plural: De Nederlandse tekst voor nul of meer dan één.
        n: Het aantal; ook beschikbaar als ``%(n)s`` in de tekst.
        **params: Overige variabelen.

    Returns:
        De juiste vorm, vertaald en met ingevulde variabelen.

    Example:
        >>> ngettext("%(n)s minuut", "%(n)s minuten", 1)
        '1 minuut'
        >>> ngettext("%(n)s minuut", "%(n)s minuten", 15)
        '15 minuten'
    """
    if _plural_translator:
        text = _plural_translator(singular, plural, n)
    else:
        text = singular if n == 1 else plural
    return text % {"n": n, **params}


def N_(message: str) -> str:
    """Markeer een tekst voor vertaling zonder hem nu te vertalen.

    Voor vaste tabellen die bij het importeren al bestaan, zoals labels per
    status: vertaal de waarde pas bij het tonen, met ``gettext``.

    Example:
        >>> LABELS = {"open": N_("Openstaand")}
        >>> gettext(LABELS["open"])
        'Openstaand'
    """
    return message


_ = gettext
