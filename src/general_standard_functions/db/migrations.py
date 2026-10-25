"""Migratie-runner: voer genummerde ``.sql``-bestanden één keer uit, op volgorde.

Elke wijziging aan de database is een nieuw bestand in de map met
migraties, bijvoorbeeld ``021_add_login_lockout.sql``. De runner houdt in de
tabel ``schema_migrations`` bij wat al is uitgevoerd, dus meerdere keren
draaien is veilig. Elk bestand is één transactie: mislukt het, dan blijft
de database zoals hij was en stopt de runner.

Vereist de extra ``postgres`` (psycopg2), tenzij je zelf ``connect`` meegeeft.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, Optional

__all__ = ["pending_migrations", "run_migrations"]

_CREATE_TABLE = """
    CREATE TABLE IF NOT EXISTS schema_migrations (
        version TEXT PRIMARY KEY,
        applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
"""


def pending_migrations(migration_files: list[Path], applied: set[str]) -> list[Path]:
    """Bepaal welke migraties nog moeten, op volgorde van bestandsnaam.

    Args:
        migration_files: Alle migratiebestanden.
        applied: Bestandsnamen die al in ``schema_migrations`` staan.

    Returns:
        De nog niet uitgevoerde bestanden, gesorteerd.

    Example:
        >>> [p.name for p in pending_migrations([Path("002_b.sql"), Path("001_a.sql")], {"001_a.sql"})]
        ['002_b.sql']
    """
    return [path for path in sorted(migration_files, key=lambda p: p.name) if path.name not in applied]


def run_migrations(
    database_url: str,
    migrations_dir: Path,
    connect: Optional[Callable[[str], Any]] = None,
    log: Callable[[str], None] = print,
) -> list[str]:
    """Voer alle nog niet uitgevoerde migraties uit.

    Args:
        database_url: PostgreSQL-verbindingsstring.
        migrations_dir: Map met de ``*.sql``-bestanden.
        connect: Functie die een verbinding opent; standaard
            ``psycopg2.connect``. Voor tests of een andere driver.
        log: Waar voortgangsmeldingen heen gaan; standaard ``print``.

    Returns:
        De namen van de uitgevoerde migraties (leeg als er niets te doen was).

    Raises:
        Exception: De fout van de database bij een mislukte migratie; die
            migratie en alle volgende zijn dan niet uitgevoerd.
    """
    if connect is None:
        import psycopg2

        connect = psycopg2.connect

    migration_files = list(Path(migrations_dir).glob("*.sql"))
    if not migration_files:
        log(f"Geen migraties gevonden in {migrations_dir}.")
        return []

    conn = connect(database_url)
    try:
        with conn.cursor() as cur:
            cur.execute(_CREATE_TABLE)
            cur.execute("SELECT version FROM schema_migrations")
            applied = {row[0] for row in cur.fetchall()}
        conn.commit()

        pending = pending_migrations(migration_files, applied)
        if not pending:
            log(f"Niets te doen: alle {len(migration_files)} migraties al toegepast.")
            return []

        done = []
        for migration_file in pending:
            with conn.cursor() as cur:
                cur.execute(migration_file.read_text(encoding="utf-8"))
                cur.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (migration_file.name,))
            conn.commit()
            done.append(migration_file.name)
            log(f"Toegepast: {migration_file.name}")
        log(f"Klaar: {len(done)} migratie(s) toegepast.")
        return done
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
