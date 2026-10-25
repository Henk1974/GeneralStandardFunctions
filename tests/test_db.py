from unittest.mock import MagicMock

import pytest

from general_standard_functions.db.migrations import run_migrations
from general_standard_functions.db.request_scope import ScopedConnections


def _fake_connection():
    conn = MagicMock()
    conn.closed = 0
    conn.close.side_effect = lambda: setattr(conn, "closed", 1)
    return conn


@pytest.fixture
def made():
    return []


@pytest.fixture
def connections(made):
    def connect():
        conn = _fake_connection()
        made.append(conn)
        return conn

    return ScopedConnections(connect, name="test")


def _executed(conn):
    return [call.args[0] for call in conn.cursor.return_value.__enter__.return_value.execute.call_args_list]


def test_invalid_name_is_refused():
    with pytest.raises(ValueError):
        ScopedConnections(lambda: None, name="drop table; --")


def test_outside_scope_each_block_gets_own_connection(connections, made):
    for _ in range(2):
        with connections.connection():
            pass
    assert len(made) == 2 and all(c.commit.called and c.close.called for c in made)


def test_inside_scope_connection_is_reused_and_closed_at_end(connections, made):
    token = connections.begin_request_scope()
    for _ in range(5):
        with connections.connection():
            pass
    assert len(made) == 1 and made[0].commit.call_count == 5 and not made[0].close.called
    connections.end_request_scope(token)
    assert made[0].close.called


def test_scope_without_database_use_opens_nothing(connections, made):
    connections.end_request_scope(connections.begin_request_scope())
    assert made == []


def test_error_rolls_back_only_that_block(connections, made):
    token = connections.begin_request_scope()
    with pytest.raises(ValueError):
        with connections.connection():
            raise ValueError("fout")
    with connections.connection():
        pass
    assert made[0].rollback.called and made[0].commit.call_count == 1 and len(made) == 1
    connections.end_request_scope(token)


def test_broken_connection_is_replaced(connections, made):
    token = connections.begin_request_scope()
    with pytest.raises(RuntimeError):
        with connections.connection() as conn:
            conn.rollback.side_effect = RuntimeError("verbinding weg")
            raise RuntimeError("netwerkfout")
    with connections.connection():
        pass
    assert len(made) == 2
    connections.end_request_scope(token)


def test_nested_block_uses_savepoint(connections, made):
    token = connections.begin_request_scope()
    with connections.connection():
        with pytest.raises(ValueError):
            with connections.connection():
                raise ValueError("fout in genest blok")
    executed = _executed(made[0])
    assert executed[:2] == ["SAVEPOINT test_sp_1", "ROLLBACK TO SAVEPOINT test_sp_1"]
    assert made[0].commit.call_count == 1
    connections.end_request_scope(token)


# --- migraties -----------------------------------------------------------


@pytest.fixture
def migrations_dir(tmp_path):
    (tmp_path / "002_tweede.sql").write_text("SELECT 2;", encoding="utf-8")
    (tmp_path / "001_eerste.sql").write_text("SELECT 1;", encoding="utf-8")
    return tmp_path


def _db_with_applied(applied):
    conn = _fake_connection()
    cursor = conn.cursor.return_value.__enter__.return_value
    cursor.fetchall.return_value = [(name,) for name in applied]
    return conn, cursor


def test_runs_pending_migrations_in_order(migrations_dir):
    conn, cursor = _db_with_applied(["001_eerste.sql"])
    done = run_migrations("postgresql://x", migrations_dir, connect=lambda url: conn, log=lambda _m: None)
    assert done == ["002_tweede.sql"]
    executed = [call.args[0] for call in cursor.execute.call_args_list]
    assert "SELECT 2;" in executed and "SELECT 1;" not in executed
    assert conn.close.called


def test_nothing_to_do(migrations_dir):
    conn, _ = _db_with_applied(["001_eerste.sql", "002_tweede.sql"])
    messages = []
    assert run_migrations("postgresql://x", migrations_dir, connect=lambda url: conn, log=messages.append) == []
    assert "Niets te doen" in messages[0]


def test_failed_migration_rolls_back_and_stops(migrations_dir):
    conn, cursor = _db_with_applied([])
    cursor.execute.side_effect = lambda sql, *a: (_ for _ in ()).throw(RuntimeError("syntax")) if sql == "SELECT 1;" else None
    with pytest.raises(RuntimeError):
        run_migrations("postgresql://x", migrations_dir, connect=lambda url: conn, log=lambda _m: None)
    assert conn.rollback.called
    executed = [call.args[0] for call in cursor.execute.call_args_list]
    assert "SELECT 2;" not in executed


def test_empty_folder(tmp_path):
    assert run_migrations("postgresql://x", tmp_path, connect=lambda url: pytest.fail("geen verbinding nodig"), log=lambda _m: None) == []
