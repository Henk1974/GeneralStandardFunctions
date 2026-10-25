"""Geheime tokens voor links in mails (uitnodigen, wachtwoord herstellen).

Patroon: maak met ``new_token`` een token, zet dat in de link en sla in de
database alleen ``hash_token(token)`` op. Lekt de database, dan zijn de links
daarmee niet te gebruiken. Bij het openen van de link zoek je op de hash.
"""

from __future__ import annotations

import hashlib
import secrets

__all__ = ["new_token", "hash_token"]


def new_token(nbytes: int = 32) -> str:
    """Maak een onvoorspelbaar token dat veilig in een URL past.

    Args:
        nbytes: Aantal willekeurige bytes; 32 is ruim voldoende.

    Returns:
        Een URL-veilige tekst van ongeveer ``1.3 * nbytes`` tekens.

    Example:
        >>> len(new_token()) >= 43
        True
    """
    return secrets.token_urlsafe(nbytes)


def hash_token(token: str) -> str:
    """Bereken de SHA-256-hash van een token, voor opslag in de database.

    Voor willekeurige tokens is een snelle hash genoeg; wachtwoorden hash je
    juist met een trage functie (``werkzeug.security``).

    Args:
        token: Het token uit de link.

    Returns:
        64 hexadecimale tekens; past in een ``VARCHAR(64)``.

    Example:
        >>> hash_token("abc")[:12]
        'ba7816bf8f01'
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
