"""Een veilige foutpagina: de gebruiker ziet nooit SQL of een stacktrace.

Een onverwachte fout gaat met alle details naar de serverlog; de gebruiker
krijgt een vriendelijke pagina. Maak die template bij voorkeur zónder het
gewone basislayout, zodat hij ook werkt als de database de oorzaak is (een
layout die de ingelogde gebruiker of tellers ophaalt, faalt dan opnieuw).
"""

from __future__ import annotations

from flask import Flask, render_template, request

__all__ = ["register_error_page"]


def register_error_page(app: Flask, template: str, status: int = 500) -> None:
    """Toon ``template`` bij een fout met ``status`` en log de details.

    Bij 500 vangt dit ook elke onverwachte uitzondering op (zolang
    ``PROPAGATE_EXCEPTIONS`` uit staat, zoals in productie).

    Args:
        app: De Flask-app.
        template: De template, bijv. ``"fout.html"``.
        status: De HTTP-status, standaard 500.
    """

    @app.errorhandler(status)
    def _error_page(error):
        app.logger.error(
            "Fout %s bij %s %s",
            status,
            request.method,
            request.path,
            exc_info=getattr(error, "original_exception", None) or error,
        )
        return render_template(template), status
