"""Wanneer geeft een betaald abonnement rechten?

De status komt van de betaalprovider (de namen zijn die van Stripe, maar ook
bruikbaar voor andere providers). Regels:

- ``active`` en ``trialing``: rechten;
- ``past_due``: de betaling is mislukt en de provider probeert het opnieuw;
  rechten blijven tot de provider het abonnement beëindigt;
- al het andere (``canceled``, ``unpaid``, ``incomplete``, ...): geen rechten.

Daarnaast vervallen de rechten als de betaalde periode al langer dan
``grace`` voorbij is. Dat vangt een gemiste melding van de provider op: een
abonnement blijft dan nooit eindeloos gratis doorlopen.

Opzeggen tegen het einde van de periode (``cancel_at_period_end``) houdt de
rechten tot die datum; daarna meldt de provider ``canceled``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

__all__ = ["ACCESS_STATUSES", "DEFAULT_GRACE", "SubscriptionState", "grants_access"]

ACCESS_STATUSES = frozenset({"active", "trialing", "past_due"})
DEFAULT_GRACE = timedelta(days=3)


@dataclass(frozen=True)
class SubscriptionState:
    """Wat de app over een betaald abonnement weet.

    Attributes:
        plan: Code van het basisplan.
        addons: Codes van de add-ons.
        status: Status bij de provider, bijv. ``"active"``.
        current_period_end: Einde van de betaalde periode (met tijdzone).
        cancel_at_period_end: Opgezegd; loopt af op ``current_period_end``.
        interval: ``"month"`` of ``"year"``.
    """

    plan: str
    addons: frozenset = field(default_factory=frozenset)
    status: str = "active"
    current_period_end: Optional[datetime] = None
    cancel_at_period_end: bool = False
    interval: Optional[str] = None


def grants_access(state: Optional[SubscriptionState], now: datetime, grace: timedelta = DEFAULT_GRACE) -> bool:
    """``True`` als dit abonnement op ``now`` rechten geeft.

    Args:
        state: Het abonnement, of ``None`` als er geen is.
        now: Het huidige moment (met tijdzone).
        grace: Hoe lang na het einde van de periode de rechten nog blijven
            als de provider (nog) niets heeft gemeld.

    Example:
        >>> from datetime import timezone
        >>> end = datetime(2026, 2, 1, tzinfo=timezone.utc)
        >>> grants_access(SubscriptionState("pro", current_period_end=end), datetime(2026, 1, 15, tzinfo=timezone.utc))
        True
        >>> grants_access(SubscriptionState("pro", status="canceled", current_period_end=end),
        ...               datetime(2026, 1, 15, tzinfo=timezone.utc))
        False
        >>> grants_access(SubscriptionState("pro", current_period_end=end), datetime(2026, 3, 1, tzinfo=timezone.utc))
        False
    """
    if state is None or state.status not in ACCESS_STATUSES:
        return False
    if state.current_period_end is not None and now > state.current_period_end + grace:
        return False
    return True
