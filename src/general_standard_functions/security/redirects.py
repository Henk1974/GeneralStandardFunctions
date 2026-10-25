"""Veilig doorsturen: nooit naar een andere website (open redirect).

Gebruik dit voor elke redirect waarvan het doel van de gebruiker komt,
zoals ``?next=/kelder`` na het inloggen of de ``Referer``-header.
"""

from __future__ import annotations

from typing import Optional
from urllib.parse import urlparse

__all__ = ["safe_next_path", "is_same_host_url"]


def safe_next_path(target: Optional[str], fallback: str) -> str:
    """Geef ``target`` terug als het een pad binnen deze site is, anders ``fallback``.

    Toegestaan zijn alleen paden die met één ``/`` beginnen. ``//evil.com``
    (protocol-relatief), volledige URL's en backslashes worden geweigerd.

    Args:
        target: Het gevraagde doel, bijvoorbeeld de ``next``-parameter.
        fallback: Waar je anders heen gaat, bijvoorbeeld het dashboard.

    Returns:
        Een veilig pad.

    Example:
        >>> safe_next_path("/kelder?sort=naam", "/")
        '/kelder?sort=naam'
        >>> safe_next_path("//evil.example/login", "/")
        '/'
    """
    if target and target.startswith("/") and not target.startswith("//") and "\\" not in target:
        return target
    return fallback


def is_same_host_url(url: Optional[str], host: str) -> bool:
    """Geef aan of een volledige URL naar dezelfde host wijst.

    Args:
        url: Bijvoorbeeld ``request.referrer``.
        host: De eigen host, bijvoorbeeld ``request.host``.

    Returns:
        ``True`` als de host (inclusief poort) precies overeenkomt.

    Example:
        >>> is_same_host_url("https://app.example/kelder", "app.example")
        True
        >>> is_same_host_url("https://evil.example/", "app.example")
        False
    """
    return bool(url) and urlparse(url).netloc == host
