"""Stripe-abonnementen via de REST-API, zonder SDK.

Twee delen:

- ``verify_webhook``: controleert de handtekening van een webhook van
  Stripe. Verwerk nooit een webhook zonder deze controle; iedereen kan een
  verzoek naar je webhook-URL sturen.
- ``StripeClient``: afrekenpagina's (Checkout), het klantportaal en het
  wijzigen of opzeggen van abonnementen.

Gebruik alleen de geheime sleutel (``sk_...``) op de server, nooit in de
browser, en commit hem nooit. Prijzen geef je mee als Stripe-prijs-ID's
(``price_...``) uit je eigen serverconfiguratie, nooit uit een formulier.

Vertrouw daarnaast nooit op de inhoud van een webhook alleen: haal het
abonnement met ``get_subscription`` opnieuw op. Dan maakt de volgorde
waarin meldingen binnenkomen ook niet uit.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping, Optional, Sequence

import requests

__all__ = [
    "WebhookSignatureError",
    "StripeError",
    "StripeSubscription",
    "verify_webhook",
    "parse_subscription",
    "StripeClient",
]

API_BASE = "https://api.stripe.com/v1"
DEFAULT_TOLERANCE = 300


class WebhookSignatureError(Exception):
    """De handtekening van een webhook ontbreekt, klopt niet of is te oud."""


class StripeError(Exception):
    """Stripe gaf een foutstatus terug.

    Attributes:
        status: De HTTP-status.
        message: De foutmelding van Stripe.
    """

    def __init__(self, status: int, message: str) -> None:
        super().__init__(f"Stripe-fout ({status}): {message}")
        self.status = status
        self.message = message


@dataclass(frozen=True)
class StripeSubscription:
    """De velden van een Stripe-abonnement die een app nodig heeft.

    Attributes:
        id: ``sub_...``.
        customer: ``cus_...``.
        status: Bijv. ``"active"``, ``"past_due"``, ``"canceled"``.
        items: Paren ``(item_id, price_id)``.
        current_period_end: Einde van de betaalde periode (UTC), of ``None``.
        cancel_at_period_end: Opgezegd tegen het einde van de periode.
        interval: ``"month"`` of ``"year"`` (van het eerste item).
        schedule: ID van een gepland wijzigingsschema (``sub_sched_...``), of ``None``.
        metadata: De metadata van het abonnement.
    """

    id: str
    customer: str
    status: str
    items: tuple = ()
    current_period_end: Optional[datetime] = None
    cancel_at_period_end: bool = False
    interval: Optional[str] = None
    schedule: Optional[str] = None
    metadata: Mapping[str, str] = field(default_factory=dict)

    @property
    def price_ids(self) -> list:
        """De prijs-ID's van alle items."""
        return [price for _item, price in self.items]


def verify_webhook(
    payload: bytes,
    signature_header: str,
    secret: str,
    tolerance: int = DEFAULT_TOLERANCE,
    now: Optional[float] = None,
) -> dict:
    """Controleer de handtekening van een Stripe-webhook en geef de melding terug.

    Stripe ondertekent ``"{tijdstip}.{body}"`` met HMAC-SHA256 en het
    webhookgeheim (``whsec_...``) en stuurt dat mee in de header
    ``Stripe-Signature`` als ``t=...,v1=...``.

    Args:
        payload: De ruwe body, precies zoals ontvangen (niet opnieuw als JSON
            opgebouwd).
        signature_header: De waarde van ``Stripe-Signature``.
        secret: Het webhookgeheim.
        tolerance: Maximale leeftijd in seconden; beschermt tegen het
            opnieuw afspelen van een oude melding.
        now: Huidig tijdstip (Unix-seconden); alleen voor tests.

    Returns:
        De melding als dict.

    Raises:
        WebhookSignatureError: Geen geheim, geen of ongeldige handtekening,
            te oud, of geen geldige JSON.

    Example:
        >>> import hashlib, hmac
        >>> body = b'{"id": "evt_1", "type": "ping"}'
        >>> sig = hmac.new(b"whsec_x", b"100." + body, hashlib.sha256).hexdigest()
        >>> verify_webhook(body, f"t=100,v1={sig}", "whsec_x", now=150)["id"]
        'evt_1'
    """
    if not secret:
        raise WebhookSignatureError("Geen webhookgeheim ingesteld.")
    timestamp, signatures = _parse_signature_header(signature_header or "")
    if timestamp is None or not signatures:
        raise WebhookSignatureError("Handtekening ontbreekt of is onleesbaar.")
    signed = str(timestamp).encode() + b"." + payload
    expected = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    if not any(hmac.compare_digest(expected, given) for given in signatures):
        raise WebhookSignatureError("Handtekening klopt niet.")
    current = time.time() if now is None else now
    if tolerance and abs(current - timestamp) > tolerance:
        raise WebhookSignatureError("Melding is te oud.")
    try:
        event = json.loads(payload)
    except ValueError as exc:
        raise WebhookSignatureError("Melding is geen geldige JSON.") from exc
    if not isinstance(event, dict) or not event.get("id") or not event.get("type"):
        raise WebhookSignatureError("Melding mist id of type.")
    return event


def _parse_signature_header(header: str):
    timestamp, signatures = None, []
    for part in header.split(","):
        key, _sep, value = part.strip().partition("=")
        if key == "t":
            try:
                timestamp = int(value)
            except ValueError:
                return None, []
        elif key == "v1" and value:
            signatures.append(value)
    return timestamp, signatures


def parse_subscription(data: Mapping[str, Any]) -> StripeSubscription:
    """Haal de bruikbare velden uit een Stripe-abonnementsobject.

    Werkt met oude en nieuwe API-versies: sinds 2025 staat het einde van de
    periode per item in plaats van op het abonnement. Een opzegging via
    ``cancel_at`` telt ook als opgezegd.

    Args:
        data: Het abonnement zoals Stripe het teruggeeft.

    Example:
        >>> sub = parse_subscription({"id": "sub_1", "customer": "cus_1", "status": "active",
        ...     "items": {"data": [{"id": "si_1", "price": {"id": "price_1", "recurring": {"interval": "year"}},
        ...                         "current_period_end": 1767225600}]}})
        >>> (sub.price_ids, sub.interval, sub.current_period_end.year)
        (['price_1'], 'year', 2026)
    """
    items, ends, interval = [], [], None
    for item in (data.get("items") or {}).get("data") or []:
        price = item.get("price") or {}
        price_id = price.get("id") if isinstance(price, Mapping) else price
        items.append((item.get("id"), price_id))
        if interval is None and isinstance(price, Mapping):
            interval = (price.get("recurring") or {}).get("interval")
        if item.get("current_period_end"):
            ends.append(item["current_period_end"])
    end = data.get("current_period_end") or (max(ends) if ends else None)
    customer = data.get("customer")
    schedule = data.get("schedule")
    return StripeSubscription(
        id=data["id"],
        customer=customer.get("id") if isinstance(customer, Mapping) else customer,
        status=data.get("status") or "",
        items=tuple(items),
        current_period_end=datetime.fromtimestamp(end, tz=timezone.utc) if end else None,
        cancel_at_period_end=bool(data.get("cancel_at_period_end") or data.get("cancel_at")),
        interval=interval,
        schedule=schedule.get("id") if isinstance(schedule, Mapping) else schedule,
        metadata=dict(data.get("metadata") or {}),
    )


def _encode(params: Mapping[str, Any], prefix: str = "") -> list:
    """Zet geneste parameters om naar Stripes formulier-notatie, bijv.
    ``line_items[0][price]``. ``None`` wordt weggelaten, ``True`` wordt ``"true"``.

    Example:
        >>> _encode({"a": {"b": [{"c": 1}]}, "d": True, "e": None})
        [('a[b][0][c]', '1'), ('d', 'true')]
    """
    pairs = []
    for key, value in params.items():
        name = f"{prefix}[{key}]" if prefix else str(key)
        if value is None:
            continue
        if isinstance(value, Mapping):
            pairs.extend(_encode(value, name))
        elif isinstance(value, (list, tuple)):
            pairs.extend(_encode({str(i): item for i, item in enumerate(value)}, name))
        elif isinstance(value, bool):
            pairs.append((name, "true" if value else "false"))
        else:
            pairs.append((name, str(value)))
    return pairs


class StripeClient:
    """Praat met de Stripe-API voor abonnementen.

    Args:
        secret_key: De geheime sleutel (``sk_test_...`` of ``sk_live_...``).
        timeout: Seconden voordat een verzoek opgeeft.
        api_base: Basis-URL van de API; alleen voor tests.
    """

    def __init__(self, secret_key: str, timeout: float = 15.0, api_base: str = API_BASE) -> None:
        if not secret_key:
            raise ValueError("Geen Stripe-sleutel opgegeven.")
        self._secret_key = secret_key
        self._timeout = timeout
        self._api_base = api_base.rstrip("/")

    def _request(self, method: str, path: str, params: Optional[Mapping[str, Any]] = None,
                 idempotency_key: Optional[str] = None) -> dict:
        headers = {"Authorization": f"Bearer {self._secret_key}"}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        pairs = _encode(params or {})
        response = requests.request(
            method,
            f"{self._api_base}{path}",
            params=pairs if method == "GET" else None,
            data=pairs if method != "GET" else None,
            headers=headers,
            timeout=self._timeout,
        )
        try:
            body = response.json()
        except ValueError:
            body = {}
        if response.status_code >= 300:
            message = (body.get("error") or {}).get("message") or response.text[:200]
            raise StripeError(response.status_code, message)
        return body

    def create_checkout_session(
        self,
        prices: Sequence[str],
        success_url: str,
        cancel_url: str,
        client_reference_id: str,
        customer: Optional[str] = None,
        customer_email: Optional[str] = None,
        metadata: Optional[Mapping[str, str]] = None,
        locale: Optional[str] = None,
    ) -> dict:
        """Maak een afrekenpagina voor een nieuw abonnement.

        Stuur de gebruiker daarna naar ``result["url"]``. De rechten geef je
        pas als de webhook laat zien dat het abonnement actief is, niet als
        de gebruiker terugkomt op ``success_url``.

        Args:
            prices: Prijs-ID's; het eerste is het plan, de rest add-ons.
            success_url: Terug na betalen.
            cancel_url: Terug na afbreken.
            client_reference_id: Jouw eigen ID van de gebruiker.
            customer: Bestaande Stripe-klant (``cus_...``), zodat er geen
                tweede klant ontstaat.
            customer_email: E-mailadres om vooraf in te vullen als er nog
                geen klant is.
            metadata: Komt op het abonnement terecht (bijv. jouw gebruikers-ID).
            locale: Taal van de afrekenpagina, bijv. ``"nl"``; leeg is automatisch.

        Returns:
            Het sessie-object van Stripe, met ``url``.

        Raises:
            StripeError: Stripe weigerde het verzoek.
            requests.RequestException: Netwerkfout of time-out.
        """
        params = {
            "mode": "subscription",
            "line_items": [{"price": price, "quantity": 1} for price in prices],
            "success_url": success_url,
            "cancel_url": cancel_url,
            "client_reference_id": client_reference_id,
            "customer": customer,
            "customer_email": None if customer else customer_email,
            "subscription_data": {"metadata": dict(metadata or {})},
            "metadata": dict(metadata or {}),
            "locale": locale,
        }
        return self._request("POST", "/checkout/sessions", params)

    def create_portal_session(self, customer: str, return_url: str, locale: Optional[str] = None) -> dict:
        """Maak een sessie in het klantportaal van Stripe (betaalgegevens,
        facturen, opzeggen). Stuur de gebruiker naar ``result["url"]``.

        Raises:
            StripeError: Stripe weigerde het verzoek (bijv. portaal niet ingesteld).
        """
        return self._request(
            "POST", "/billing_portal/sessions", {"customer": customer, "return_url": return_url, "locale": locale}
        )

    def get_subscription(self, subscription_id: str) -> StripeSubscription:
        """Haal een abonnement op, met de actuele status.

        Raises:
            StripeError: Bestaat niet of geen toegang.
        """
        return parse_subscription(self._request("GET", f"/subscriptions/{subscription_id}"))

    def change_items(
        self,
        subscription_id: str,
        replace: Optional[Mapping[str, str]] = None,
        add: Sequence[str] = (),
        remove: Sequence[str] = (),
        idempotency_key: Optional[str] = None,
    ) -> StripeSubscription:
        """Wijzig direct de items van een abonnement (een upgrade of een add-on erbij).

        Het verschil wordt meteen gefactureerd (``always_invoice``). Lukt die
        betaling niet, dan weigert Stripe de hele wijziging
        (``error_if_incomplete``), zodat er nooit rechten zonder betaling zijn.

        Args:
            subscription_id: ``sub_...``.
            replace: Item-ID naar nieuwe prijs-ID.
            add: Prijs-ID's om toe te voegen.
            remove: Item-ID's om te verwijderen.
            idempotency_key: Voorkomt dat een herhaald verzoek dubbel wordt uitgevoerd.

        Raises:
            StripeError: Stripe weigerde de wijziging, bijv. omdat de betaling mislukte.
        """
        items = [{"id": item, "price": price} for item, price in (replace or {}).items()]
        items += [{"price": price, "quantity": 1} for price in add]
        items += [{"id": item, "deleted": True} for item in remove]
        params = {
            "items": items,
            "proration_behavior": "always_invoice",
            "payment_behavior": "error_if_incomplete",
        }
        return parse_subscription(
            self._request("POST", f"/subscriptions/{subscription_id}", params, idempotency_key)
        )

    def schedule_change_at_period_end(self, subscription: StripeSubscription, prices: Sequence[str]) -> str:
        """Plan een wijziging (bijv. een downgrade) die pas ingaat aan het eind
        van de betaalde periode. Tot dan blijven de huidige items en rechten.

        Werkt met een abonnementsschema van Stripe: de huidige fase loopt tot
        het einde van de periode, daarna volgen de nieuwe prijzen en geeft
        het schema het abonnement weer vrij.

        Args:
            subscription: Het actuele abonnement (van ``get_subscription``).
            prices: De prijs-ID's na de wijziging.

        Returns:
            Het ID van het schema.

        Raises:
            StripeError: Stripe weigerde het schema.
            ValueError: Het abonnement heeft geen einde van de periode.
        """
        if subscription.current_period_end is None:
            raise ValueError("Abonnement zonder einde van de periode.")
        schedule = (
            self._request("GET", f"/subscription_schedules/{subscription.schedule}")
            if subscription.schedule
            else self._request("POST", "/subscription_schedules", {"from_subscription": subscription.id})
        )
        current = (schedule.get("phases") or [{}])[0]
        start = (schedule.get("current_phase") or {}).get("start_date") or current.get("start_date")
        end = int(subscription.current_period_end.timestamp())
        params = {
            "end_behavior": "release",
            "phases": [
                {
                    "items": [{"price": price, "quantity": 1} for price in subscription.price_ids],
                    "start_date": start,
                    "end_date": end,
                },
                {"items": [{"price": price, "quantity": 1} for price in prices], "start_date": end},
            ],
            "proration_behavior": "none",
        }
        return self._request("POST", f"/subscription_schedules/{schedule['id']}", params)["id"]

    def release_schedule(self, schedule_id: str) -> None:
        """Haal een gepland wijzigingsschema weg; het abonnement blijft zoals het nu is.

        Raises:
            StripeError: Stripe weigerde het verzoek.
        """
        self._request("POST", f"/subscription_schedules/{schedule_id}/release")

    def set_cancel_at_period_end(self, subscription_id: str, cancel: bool) -> StripeSubscription:
        """Zeg op tegen het einde van de betaalde periode, of trek een opzegging in.

        Raises:
            StripeError: Stripe weigerde het verzoek.
        """
        return parse_subscription(
            self._request("POST", f"/subscriptions/{subscription_id}", {"cancel_at_period_end": cancel})
        )

    def cancel_now(self, subscription_id: str) -> StripeSubscription:
        """Beëindig een abonnement direct (de rechten vervallen meteen).
        Een terugbetaling doe je apart, in het Stripe-dashboard.

        Raises:
            StripeError: Stripe weigerde het verzoek.
        """
        return parse_subscription(self._request("DELETE", f"/subscriptions/{subscription_id}"))
