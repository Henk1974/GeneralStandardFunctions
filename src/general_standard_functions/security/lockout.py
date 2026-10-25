"""Inlogpogingen beperken: wanneer blokkeren, wanneer verplicht resetten.

Alleen de beslisregels, zonder database: de app slaat per account zelf het
aantal mislukte pogingen en ``locked_until`` op (in de database, niet in het
geheugen: serverless instanties delen geen geheugen) en vraagt na elke
mislukte poging ``decide_after_failure`` wat er moet gebeuren.

Standaardbeleid: na 3 fouten 15 minuten blokkeren, na nog eens 3 fouten
alleen nog inloggen na een nieuw wachtwoord via de mail. Een geslaagde login
zet de teller en ``locked_until`` terug.

Volgorde in de inlogfunctie van de app:

1. reset verplicht? weigeren;
2. ``is_locked(locked_until, now)``? weigeren met ``minutes_left``;
3. pas dan het wachtwoord controleren; fout? teller ophogen en
   ``decide_after_failure`` toepassen; goed? teller terugzetten.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

__all__ = [
    "LockoutPolicy",
    "DEFAULT_LOCKOUT_POLICY",
    "LockoutAction",
    "LockoutDecision",
    "decide_after_failure",
    "is_locked",
    "minutes_left",
]


@dataclass(frozen=True)
class LockoutPolicy:
    """Hoe streng inlogpogingen worden beperkt.

    Attributes:
        max_attempts: Fouten per ronde; na de eerste ronde volgt de
            blokkade, na de tweede de verplichte reset.
        lockout_minutes: Duur van de tijdelijke blokkade.
    """

    max_attempts: int = 3
    lockout_minutes: int = 15


DEFAULT_LOCKOUT_POLICY = LockoutPolicy()


class LockoutAction(Enum):
    """Wat de app na een mislukte poging moet doen.

    Values:
        WARN: Alleen melden, met het aantal resterende pogingen.
        LOCK: ``locked_until`` opslaan en de gebruiker laten wachten.
        REQUIRE_RESET: Account blokkeren tot er een nieuw wachtwoord is;
            mail de herstel-link.
    """

    WARN = "warn"
    LOCK = "lock"
    REQUIRE_RESET = "require_reset"


@dataclass(frozen=True)
class LockoutDecision:
    """De uitkomst van ``decide_after_failure``.

    Attributes:
        action: Wat de app moet doen.
        attempts_left: Pogingen tot de volgende stap (alleen bij ``WARN``).
        locked_until: Tot wanneer geblokkeerd (alleen bij ``LOCK``).
        reset_follows: ``True`` als de volgende stap de verplichte reset is
            in plaats van de tijdelijke blokkade; handig voor de melding.
    """

    action: LockoutAction
    attempts_left: int = 0
    locked_until: Optional[datetime] = None
    reset_follows: bool = False


def decide_after_failure(
    failed_count: int,
    lock_already_used: bool,
    now: datetime,
    policy: LockoutPolicy = DEFAULT_LOCKOUT_POLICY,
) -> LockoutDecision:
    """Bepaal het gevolg van een mislukte inlogpoging.

    Args:
        failed_count: Het aantal mislukte pogingen, inclusief deze. Hoog het
            in de database atomair op (``UPDATE ... SET n = n + 1
            RETURNING n``), zodat gelijktijdige pogingen goed tellen.
        lock_already_used: Of de tijdelijke blokkade al eens is gezet sinds
            de laatste geslaagde login (bijv. ``locked_until is not None``).
            Zo wordt er nooit twee keer geblokkeerd.
        now: Het huidige moment, met tijdzone.
        policy: Het beleid.

    Returns:
        Een ``LockoutDecision``.

    Example:
        >>> from datetime import timezone
        >>> now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        >>> decide_after_failure(1, False, now).attempts_left
        2
        >>> decide_after_failure(3, False, now).action
        <LockoutAction.LOCK: 'lock'>
        >>> decide_after_failure(6, True, now).action
        <LockoutAction.REQUIRE_RESET: 'require_reset'>
    """
    if failed_count >= 2 * policy.max_attempts:
        return LockoutDecision(LockoutAction.REQUIRE_RESET)
    if failed_count >= policy.max_attempts and not lock_already_used:
        return LockoutDecision(
            LockoutAction.LOCK, locked_until=now + timedelta(minutes=policy.lockout_minutes)
        )
    return LockoutDecision(
        LockoutAction.WARN,
        attempts_left=policy.max_attempts - failed_count % policy.max_attempts,
        reset_follows=failed_count >= policy.max_attempts,
    )


def is_locked(locked_until: Optional[datetime], now: datetime) -> bool:
    """Geef aan of een account op dit moment tijdelijk geblokkeerd is.

    Args:
        locked_until: Het opgeslagen eindmoment, of ``None``.
        now: Het huidige moment, met tijdzone.

    Returns:
        ``True`` zolang ``locked_until`` in de toekomst ligt.
    """
    return locked_until is not None and locked_until > now


def minutes_left(locked_until: datetime, now: datetime) -> int:
    """Bereken de resterende wachttijd in hele minuten, naar boven afgerond.

    Args:
        locked_until: Het eindmoment van de blokkade.
        now: Het huidige moment.

    Returns:
        Minimaal 1, zodat de melding nooit "0 minuten" zegt.

    Example:
        >>> from datetime import timezone
        >>> now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        >>> minutes_left(now + timedelta(seconds=30), now)
        1
    """
    return max(1, math.ceil((locked_until - now).total_seconds() / 60))
