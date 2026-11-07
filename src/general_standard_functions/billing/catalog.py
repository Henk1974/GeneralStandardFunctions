"""Plannen, add-ons en de rechten die ze geven, op één plek.

Een plan is het basisabonnement (bijv. Gratis, Pro, Super); een add-on komt
er los bij en mag alleen bij bepaalde plannen (bijv. een extra functie bij
Pro). Prijzen staan in centen, zodat er nooit afrondingsfouten ontstaan.
Rechten zijn functies (``features``) en limieten (``limits``, ``None`` is
onbeperkt).

Voorbeeld::

    CATALOG = Catalog(
        plans=[
            Plan("free", "Gratis", rank=0, limits={"items": 20}),
            Plan("pro", "Pro", rank=1, prices={"month": 149, "year": 1499}, limits={"items": 250}),
        ],
        addons=[AddOn("extra", "Extra", prices={"month": 99}, features={"groups"}, plans={"pro"})],
        default_plan="free",
    )
    CATALOG.entitlements("pro", ["extra"]).has("groups")  # True
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping, Optional

__all__ = ["INTERVALS", "Plan", "AddOn", "Entitlements", "Catalog", "UnknownProductError", "format_cents"]

INTERVALS = ("month", "year")


class UnknownProductError(ValueError):
    """Een plan of add-on bestaat niet in de catalogus, of een add-on mag niet bij dit plan."""


@dataclass(frozen=True)
class Plan:
    """Een basisabonnement.

    Attributes:
        code: Vaste, korte naam voor de database, bijv. ``"pro"``.
        name: Naam om te tonen.
        rank: Hoger is uitgebreider; bepaalt wat een upgrade is.
        prices: Prijs in centen per interval (``"month"``, ``"year"``);
            leeg voor een gratis plan.
        limits: Limieten, bijv. ``{"items": 250}``; ``None`` is onbeperkt.
        features: Functies die bij dit plan horen.
    """

    code: str
    name: str
    rank: int
    prices: Mapping[str, int] = field(default_factory=dict)
    limits: Mapping[str, Optional[int]] = field(default_factory=dict)
    features: frozenset = frozenset()

    @property
    def is_free(self) -> bool:
        """``True`` als het plan geen prijs heeft."""
        return not self.prices


@dataclass(frozen=True)
class AddOn:
    """Een uitbreiding bovenop een plan.

    Attributes:
        code: Vaste, korte naam, bijv. ``"extra"``.
        name: Naam om te tonen.
        prices: Prijs in centen per interval.
        features: Functies die de add-on toevoegt.
        plans: Codes van de plannen waarbij de add-on mag.
    """

    code: str
    name: str
    prices: Mapping[str, int] = field(default_factory=dict)
    features: frozenset = frozenset()
    plans: frozenset = frozenset()


@dataclass(frozen=True)
class Entitlements:
    """De rechten die iemand op dit moment heeft.

    Attributes:
        plan: Code van het plan waar de rechten vandaan komen (het hoogste).
        addons: Codes van de actieve add-ons.
        features: Alle functies samen.
        limits: Alle limieten; een naam die ontbreekt is onbeperkt.
    """

    plan: str
    addons: frozenset = frozenset()
    features: frozenset = frozenset()
    limits: Mapping[str, Optional[int]] = field(default_factory=dict)

    def has(self, feature: str) -> bool:
        """``True`` als de functie bij deze rechten hoort.

        Example:
            >>> Entitlements("pro", features=frozenset({"groups"})).has("groups")
            True
        """
        return feature in self.features

    def limit(self, name: str) -> Optional[int]:
        """De limiet met deze naam; ``None`` is onbeperkt.

        Example:
            >>> Entitlements("free", limits={"items": 20}).limit("items")
            20
            >>> Entitlements("free").limit("items") is None
            True
        """
        return self.limits.get(name)

    def merge(self, other: "Entitlements", ranks: Mapping[str, int]) -> "Entitlements":
        """Combineer twee bronnen van rechten (bijv. een cadeau en een betaald
        abonnement): alle functies samen en per limiet de ruimste.

        Args:
            other: De andere rechten.
            ranks: Rang per plancode, om het plan van de uitkomst te kiezen.

        Example:
            >>> a = Entitlements("free", limits={"items": 20})
            >>> b = Entitlements("pro", features=frozenset({"x"}), limits={"items": 250})
            >>> m = a.merge(b, {"free": 0, "pro": 1})
            >>> (m.plan, m.limit("items"), m.has("x"))
            ('pro', 250, True)
        """
        names = set(self.limits) | set(other.limits)
        limits = {}
        for name in names:
            mine, theirs = self.limits.get(name), other.limits.get(name)
            if name in self.limits and name in other.limits:
                limits[name] = None if mine is None or theirs is None else max(mine, theirs)
            else:
                limits[name] = None  # één van beide heeft geen limiet: onbeperkt
        plan = max((self.plan, other.plan), key=lambda code: ranks.get(code, -1))
        return Entitlements(plan, self.addons | other.addons, self.features | other.features, limits)


class Catalog:
    """Alle plannen en add-ons van een app.

    Args:
        plans: De plannen; codes moeten uniek zijn.
        addons: De add-ons.
        default_plan: Code van het plan voor wie niets heeft (meestal gratis).

    Raises:
        ValueError: Dubbele codes, onbekend standaardplan, een onbekend
            interval of een add-on bij een plan dat niet bestaat.
    """

    def __init__(self, plans: Iterable[Plan], addons: Iterable[AddOn] = (), default_plan: str = "free") -> None:
        plans, addons = list(plans), list(addons)
        self._plans = {plan.code: plan for plan in plans}
        self._addons = {addon.code: addon for addon in addons}
        self.default_plan = default_plan
        self._check(plans, addons)

    def _check(self, plans, addons) -> None:
        if len(self._plans) != len(plans) or len(self._addons) != len(addons):
            raise ValueError("Elke plan- en add-oncode mag maar één keer voorkomen.")
        if self.default_plan not in self._plans:
            raise ValueError(f"Standaardplan {self.default_plan!r} bestaat niet.")
        for product in [*plans, *addons]:
            unknown = set(product.prices) - set(INTERVALS)
            if unknown:
                raise ValueError(f"Onbekend interval bij {product.code!r}: {sorted(unknown)}.")
        for addon in addons:
            if not set(addon.plans) <= set(self._plans):
                raise ValueError(f"Add-on {addon.code!r} verwijst naar een onbekend plan.")

    @property
    def plans(self) -> list:
        """Alle plannen, van laag naar hoog."""
        return sorted(self._plans.values(), key=lambda plan: plan.rank)

    @property
    def addons(self) -> list:
        """Alle add-ons, in de volgorde van opgeven."""
        return list(self._addons.values())

    @property
    def ranks(self) -> dict:
        """Rang per plancode."""
        return {code: plan.rank for code, plan in self._plans.items()}

    def plan(self, code: str) -> Plan:
        """Het plan met deze code.

        Raises:
            UnknownProductError: Bestaat niet.
        """
        try:
            return self._plans[code]
        except KeyError:
            raise UnknownProductError(f"Onbekend plan: {code!r}.") from None

    def addon(self, code: str) -> AddOn:
        """De add-on met deze code.

        Raises:
            UnknownProductError: Bestaat niet.
        """
        try:
            return self._addons[code]
        except KeyError:
            raise UnknownProductError(f"Onbekende add-on: {code!r}.") from None

    def addon_allowed(self, plan_code: str, addon_code: str) -> bool:
        """``True`` als de add-on bij dit plan mag."""
        return addon_code in self._addons and plan_code in self._addons[addon_code].plans

    def entitlements(self, plan_code: Optional[str] = None, addon_codes: Iterable[str] = ()) -> Entitlements:
        """De rechten van een plan met add-ons.

        Add-ons die niet bij het plan mogen of niet bestaan, tellen niet mee:
        zo geeft een vergeten add-on na een upgrade of downgrade nooit
        ongemerkt rechten.

        Args:
            plan_code: Code van het plan; ``None`` of onbekend is het
                standaardplan.
            addon_codes: Codes van de add-ons.

        Returns:
            De rechten.
        """
        plan = self._plans.get(plan_code or self.default_plan) or self._plans[self.default_plan]
        addons = [self._addons[code] for code in addon_codes if self.addon_allowed(plan.code, code)]
        features = frozenset(plan.features).union(*(addon.features for addon in addons))
        return Entitlements(plan.code, frozenset(a.code for a in addons), features, dict(plan.limits))

    def price(self, code: str, interval: str) -> int:
        """De prijs in centen van een plan of add-on voor dit interval.

        Raises:
            UnknownProductError: Product of interval bestaat niet.
        """
        product = self._plans.get(code) or self._addons.get(code)
        if product is None or interval not in product.prices:
            raise UnknownProductError(f"Geen prijs voor {code!r} per {interval!r}.")
        return product.prices[interval]


def format_cents(cents: int, decimal_separator: str = ",") -> str:
    """Zet een bedrag in centen om naar tekst met twee decimalen, zonder valuta.

    Args:
        cents: Bedrag in centen.
        decimal_separator: Scheidingsteken voor de decimalen.

    Example:
        >>> format_cents(149)
        '1,49'
        >>> format_cents(2499, ".")
        '24.99'
    """
    sign = "-" if cents < 0 else ""
    whole, rest = divmod(abs(cents), 100)
    return f"{sign}{whole}{decimal_separator}{rest:02d}"
