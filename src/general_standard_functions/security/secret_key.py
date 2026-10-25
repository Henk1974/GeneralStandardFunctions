"""Controle op de geheime sessiesleutel van een webapp.

Met een bekende of korte sleutel kan iedereen sessiecookies vervalsen en
zo als willekeurige gebruiker ingelogd raken. Roep
``ensure_production_secret_key`` aan bij het opstarten.
Een goede sleutel maak je met ``python -c "import secrets; print(secrets.token_hex(32))"``.
"""

from __future__ import annotations

__all__ = [
    "DEV_SECRET_KEY_PLACEHOLDER",
    "MIN_SECRET_KEY_LENGTH",
    "InsecureSecretKeyError",
    "ensure_production_secret_key",
]

DEV_SECRET_KEY_PLACEHOLDER = "dev-secret-change-me"
MIN_SECRET_KEY_LENGTH = 32


class InsecureSecretKeyError(RuntimeError):
    """De sleutel is in productie leeg, de standaardwaarde of te kort."""


def ensure_production_secret_key(
    secret_key: str,
    is_production: bool,
    placeholder: str = DEV_SECRET_KEY_PLACEHOLDER,
    min_length: int = MIN_SECRET_KEY_LENGTH,
) -> None:
    """Weiger op te starten met een onveilige sleutel in productie.

    Lokaal (``is_production=False``) mag alles, zodat ontwikkelen zonder
    extra instellingen kan.

    Args:
        secret_key: De ingestelde sleutel.
        is_production: Of de app in productie draait (op Vercel bijv.
            ``bool(os.environ.get("VERCEL"))``).
        placeholder: De bekende ontwikkelwaarde die nooit live mag.
        min_length: Minimale lengte in productie.

    Raises:
        InsecureSecretKeyError: In productie met een lege, standaard of te
            korte sleutel.
    """
    if not is_production:
        return
    if not secret_key or secret_key == placeholder or len(secret_key) < min_length:
        raise InsecureSecretKeyError(
            "De geheime sleutel (bijv. FLASK_SECRET_KEY) is in productie niet of niet goed ingesteld. "
            f"Zet een willekeurige waarde van minstens {min_length} tekens in de omgevingsvariabelen."
        )
