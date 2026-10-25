"""Eén databaseverbinding per webverzoek, met een transactie per blok.

Een nieuwe verbinding openen kost (zeker serverless) tientallen
milliseconden. ``ScopedConnections`` hergebruikt daarom binnen één verzoek
dezelfde verbinding; buiten een verzoek (scripts, CLI) krijgt elk blok een
eigen verbinding. Elk ``with connection()``-blok is één transactie: commit bij
succes, rollback bij een fout. Een genest blok krijgt een savepoint, zodat
een fout daarin de buitenste transactie heel laat.

Werkt met elke DB-API-verbinding (psycopg2, psycopg 3, ...): je geeft zelf
de functie die een verbinding opent. Gebruik in een Flask-app::

    connections = ScopedConnections(lambda: psycopg2.connect(DATABASE_URL), name="bierkelder")

    @app.before_request
    def _open():
        g.db_scope = connections.begin_request_scope()

    @app.teardown_request
    def _close(_exc):
        connections.end_request_scope(g.pop("db_scope"))

    with connections.connection() as conn:
        ...
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Any, Optional

__all__ = ["ScopedConnections"]

_NAME_RE = re.compile(r"^[a-z_][a-z0-9_]*$")


class _RequestScope:
    """De gedeelde verbinding van één verzoek en hoe diep we genest zitten."""

    def __init__(self) -> None:
        self.conn: Optional[Any] = None
        self.depth = 0


class ScopedConnections:
    """Beheert databaseverbindingen per verzoek.

    Args:
        connect: Functie zonder argumenten die een nieuwe verbinding opent.
        name: Korte naam (kleine letters, cijfers, ``_``) voor de
            contextvar en de savepoints.

    Raises:
        ValueError: ``name`` is geen geldige SQL-naam.
    """

    def __init__(self, connect: Callable[[], Any], name: str = "app") -> None:
        if not _NAME_RE.match(name):
            raise ValueError(f"Ongeldige naam {name!r}: gebruik kleine letters, cijfers en _.")
        self._connect = connect
        self._name = name
        self._scope: ContextVar[Optional[_RequestScope]] = ContextVar(f"{name}_db_scope", default=None)

    def begin_request_scope(self) -> Token:
        """Start de scope van een verzoek.

        De verbinding wordt pas bij het eerste gebruik geopend, dus een
        verzoek zonder database kost niets.

        Returns:
            Een token voor ``end_request_scope``.
        """
        return self._scope.set(_RequestScope())

    def end_request_scope(self, token: Token) -> None:
        """Sluit de scope: draai open werk terug en sluit de verbinding.

        Args:
            token: Het token van ``begin_request_scope``.
        """
        scope = self._scope.get()
        try:
            if scope is not None and scope.conn is not None and not scope.conn.closed:
                try:
                    scope.conn.rollback()
                finally:
                    scope.conn.close()
        finally:
            self._scope.reset(token)

    @contextmanager
    def connection(self) -> Iterator[Any]:
        """Geef een verbinding voor één transactie.

        Yields:
            De verbinding. Commit gebeurt automatisch aan het eind van het
            blok, rollback bij een uitzondering (die daarna doorgaat).
        """
        scope = self._scope.get()
        if scope is None:
            yield from self._own_connection()
        elif scope.depth > 0:
            yield from self._savepoint(scope)
        else:
            yield from self._shared_connection(scope)

    def _own_connection(self) -> Iterator[Any]:
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _shared_connection(self, scope: _RequestScope) -> Iterator[Any]:
        if scope.conn is None or scope.conn.closed:
            scope.conn = self._connect()
        conn = scope.conn
        scope.depth = 1
        try:
            yield conn
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:  # noqa: BLE001 - verbinding kapot: weggooien, volgende keer een nieuwe
                self._discard(scope)
            raise
        finally:
            scope.depth = 0

    def _savepoint(self, scope: _RequestScope) -> Iterator[Any]:
        conn = scope.conn
        name = f"{self._name}_sp_{scope.depth}"
        scope.depth += 1
        try:
            with conn.cursor() as cur:
                cur.execute(f"SAVEPOINT {name}")
            try:
                yield conn
            except Exception:
                with conn.cursor() as cur:
                    cur.execute(f"ROLLBACK TO SAVEPOINT {name}")
                raise
            with conn.cursor() as cur:
                cur.execute(f"RELEASE SAVEPOINT {name}")
        finally:
            scope.depth -= 1

    @staticmethod
    def _discard(scope: _RequestScope) -> None:
        try:
            scope.conn.close()
        except Exception:  # noqa: BLE001 - al kapot; sluiten mag mislukken
            pass
        scope.conn = None
