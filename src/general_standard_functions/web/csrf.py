"""CSRF-bescherming voor alle formulieren van een Flask-app, zonder extra pakket.

Werking: per sessie één willekeurig token in de (ondertekende) Flask-sessie.
Elk formulier stuurt het mee als verborgen veld ``csrf_token``. Bij elk
POST/PUT/PATCH/DELETE-verzoek worden beide vergeleken. Een andere website
kan het token niet lezen en dus geen formulier namens een ingelogde
gebruiker versturen.

Gebruik::

    init_csrf(app, fallback_endpoint="web.dashboard")

en zet in elk ``<form method="post">`` de regel ``{{ csrf_field() }}``.
Zet daarnaast ``SESSION_COOKIE_SAMESITE = "Lax"`` en in productie
``SESSION_COOKIE_SECURE = True``. In tests kun je de controle uitzetten met
``app.config["CSRF_ENABLED"] = False``.
"""

from __future__ import annotations

import hmac
import secrets

from flask import Flask, flash, redirect, request, session, url_for
from markupsafe import Markup, escape

from general_standard_functions.security.redirects import is_same_host_url

__all__ = ["FIELD_NAME", "INVALID_TOKEN_MESSAGE", "get_csrf_token", "csrf_field", "init_csrf"]

FIELD_NAME = "csrf_token"
INVALID_TOKEN_MESSAGE = "Je sessie is verlopen of het formulier is ongeldig. Probeer het nog eens."

_SESSION_KEY = "_csrf_token"
_UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def get_csrf_token() -> str:
    """Geef het CSRF-token van de huidige sessie; maak er een als het er nog niet is.

    Returns:
        Het token (ook beschikbaar in templates als ``csrf_token()``).
    """
    token = session.get(_SESSION_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        session[_SESSION_KEY] = token
    return token


def csrf_field() -> Markup:
    """Geef het verborgen formulierveld met het token.

    Returns:
        ``<input type="hidden" name="csrf_token" value="...">`` als veilige
        HTML; in templates ``{{ csrf_field() }}``.
    """
    return Markup(f'<input type="hidden" name="{FIELD_NAME}" value="{escape(get_csrf_token())}">')


def init_csrf(app: Flask, fallback_endpoint: str) -> None:
    """Zet CSRF-controle aan voor alle onveilige verzoeken van de app.

    Registreert ``csrf_field`` en ``csrf_token`` als Jinja-globals en een
    ``before_request``-controle. Bij een ontbrekend of fout token volgt een
    flash-melding (``INVALID_TOKEN_MESSAGE``) en een redirect terug naar de
    vorige pagina van deze site, of anders naar ``fallback_endpoint``.

    Args:
        app: De Flask-app.
        fallback_endpoint: Endpoint om naartoe te sturen als de vorige
            pagina onbekend of van een andere site is, bijv. ``"web.dashboard"``.
    """
    app.jinja_env.globals["csrf_field"] = csrf_field
    app.jinja_env.globals["csrf_token"] = get_csrf_token

    @app.before_request
    def _check_csrf():
        if request.method not in _UNSAFE_METHODS or not app.config.get("CSRF_ENABLED", True):
            return None
        expected = session.get(_SESSION_KEY)
        given = request.form.get(FIELD_NAME, "")
        if expected and given and hmac.compare_digest(str(expected), str(given)):
            return None
        flash(INVALID_TOKEN_MESSAGE, "error")
        referrer = request.referrer
        if is_same_host_url(referrer, request.host):
            return redirect(referrer)
        return redirect(url_for(fallback_endpoint))
