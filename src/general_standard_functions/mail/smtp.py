"""E-mail versturen via SMTP, alleen met de standaardbibliotheek.

Gemaakt voor Gmail met een app-wachtwoord (``smtp.gmail.com``, poort 587,
STARTTLS), maar werkt met elke SMTP-server. Laat je eigen code afhangen van
het protocol ``Mailer``, niet van ``SmtpMailer`` zelf; dan kun je in tests
een nep-mailer meegeven en lokaal zonder mail werken (``mailer=None``).
"""

from __future__ import annotations

import smtplib
from email.message import EmailMessage
from typing import Optional, Protocol

__all__ = ["Mailer", "MailError", "header_safe", "SmtpMailer"]


class Mailer(Protocol):
    """Alles met deze ``send``-methode kan mail versturen."""

    def send(
        self,
        to: str,
        subject: str,
        body: str,
        reply_to: Optional[str] = None,
        from_name: Optional[str] = None,
    ) -> None:
        """Verstuur één tekstmail; zie ``SmtpMailer.send``."""


class MailError(Exception):
    """Versturen is mislukt: verbinding, inloggen of geweigerd door de server."""


def header_safe(value: str) -> str:
    """Maak tekst veilig voor een mailheader (geen regeleinden).

    Zonder dit kan iemand via een formulierveld extra headers toevoegen,
    zoals ``Bcc:`` (header-injectie).

    Args:
        value: Bijvoorbeeld een onderwerp of naam uit een formulier.

    Returns:
        De tekst op één regel, met enkele spaties.

    Example:
        >>> header_safe("Hoi\\r\\nBcc: spam@example.com")
        'Hoi Bcc: spam@example.com'
    """
    return " ".join((value or "").replace("\r", " ").replace("\n", " ").split())


class SmtpMailer:
    """Verstuurt tekstmails via één SMTP-account.

    Args:
        host: SMTP-server, bijv. ``"smtp.gmail.com"``.
        port: Poort, bijv. 587 (STARTTLS).
        username: Het account, tevens afzenderadres.
        password: Wachtwoord; bij Gmail een app-wachtwoord.
        timeout: Seconden voordat een verbinding opgeeft.
        default_from_name: Weergavenaam als ``send`` er geen meekrijgt,
            bijv. de naam van de app.
    """

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        timeout: float = 15.0,
        default_from_name: str = "",
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._timeout = timeout
        self._default_from_name = default_from_name

    def send(
        self,
        to: str,
        subject: str,
        body: str,
        reply_to: Optional[str] = None,
        from_name: Optional[str] = None,
    ) -> None:
        """Verstuur één tekstmail.

        ``From`` is altijd het eigen account (Gmail staat geen ander adres
        toe); alleen de weergavenaam verschilt, zoals "Henk via Bierkelder".
        Antwoorden gaat naar ``reply_to``.

        Args:
            to: Ontvanger.
            subject: Onderwerp.
            body: Tekst (platte tekst).
            reply_to: Optioneel antwoordadres.
            from_name: Optionele weergavenaam van de afzender.

        Raises:
            MailError: Verbinden, inloggen of versturen is mislukt.
        """
        msg = EmailMessage()
        display = header_safe(from_name or self._default_from_name).replace('"', "'")
        msg["From"] = f'"{display}" <{self._username}>' if display else self._username
        msg["To"] = header_safe(to)
        msg["Subject"] = header_safe(subject)
        if reply_to:
            msg["Reply-To"] = header_safe(reply_to)
        msg.set_content(body)

        try:
            with smtplib.SMTP(self._host, self._port, timeout=self._timeout) as smtp:
                smtp.starttls()
                smtp.login(self._username, self._password)
                smtp.send_message(msg)
        except (smtplib.SMTPException, OSError) as exc:
            raise MailError(f"Versturen via {self._host} mislukt: {exc}") from exc
