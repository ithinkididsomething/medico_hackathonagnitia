"""Database connection layer.

Designed so switching to PostgreSQL/Supabase is configuration only:

    DATABASE_URL=sqlite:///./data/medico.db          # local default
    DATABASE_URL=postgresql://user:pass@host/dbname   # install `psycopg[binary]`

Application code and SQL stay the same:
  * placeholders are written as `?` and adapted to `%s` for PostgreSQL,
  * INSERTs use `RETURNING id` (supported by SQLite 3.35+ and PostgreSQL),
  * results are plain dicts,
  * schema files are chosen per dialect (`schema.sql` / `schema.postgres.sql`).
"""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from ..config import Settings, get_settings

SCHEMA_DIR = Path(__file__).resolve().parent
SCHEMA_FILES = {
    "sqlite": SCHEMA_DIR / "schema.sql",
    "postgresql": SCHEMA_DIR / "schema.postgres.sql",
}


class DatabaseError(RuntimeError):
    """Raised when the configured database cannot be used."""


def dialect_of(url: str) -> str:
    if url.startswith("sqlite:"):
        return "sqlite"
    if url.startswith(("postgres://", "postgresql://")):
        return "postgresql"
    raise DatabaseError(
        f"Unsupported DATABASE_URL scheme: {url.split(':', 1)[0]!r} "
        "(expected sqlite://, postgresql:// or postgres://)"
    )


def _adapt_sql(sql: str, dialect: str) -> str:
    return sql.replace("?", "%s") if dialect == "postgresql" else sql


class _Cursor:
    """Cursor wrapper returning dicts instead of driver-specific rows."""

    def __init__(self, cursor: Any, dialect: str) -> None:
        self._cursor = cursor
        self._dialect = dialect

    @property
    def rowcount(self) -> int:
        return self._cursor.rowcount

    def _as_dict(self, row: Any) -> Any:
        if row is None or isinstance(row, dict):
            return row
        columns = [col[0] for col in (self._cursor.description or [])]
        return dict(zip(columns, row))

    def fetchone(self) -> dict[str, Any] | None:
        return self._as_dict(self._cursor.fetchone())

    def fetchall(self) -> list[dict[str, Any]]:
        return [self._as_dict(row) for row in self._cursor.fetchall()]


class _Connection:
    """Connection wrapper with a uniform execute() API for both dialects."""

    def __init__(self, connection: Any, dialect: str) -> None:
        self._connection = connection
        self.dialect = dialect

    def execute(self, sql: str, params: tuple | list = ()) -> _Cursor:
        return _Cursor(self._connection.execute(_adapt_sql(sql, self.dialect), params), self.dialect)

    def executescript(self, script: str) -> None:
        if self.dialect == "sqlite":
            self._connection.executescript(script)
        else:
            # PostgreSQL accepts multiple statements in a single execute().
            self._connection.execute(script)

    def commit(self) -> None:
        self._connection.commit()

    def rollback(self) -> None:
        self._connection.rollback()

    def close(self) -> None:
        self._connection.close()


def get_connection(settings: Settings | None = None) -> _Connection:
    settings = settings or get_settings()
    url = settings.database_url
    dialect = dialect_of(url)

    if dialect == "sqlite":
        import sqlite3

        path = settings.database_path
        assert path is not None
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = sqlite3.connect(path)
        raw.execute("PRAGMA foreign_keys = ON")
        return _Connection(raw, dialect)

    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover - only without the extra installed
        raise DatabaseError(
            "PostgreSQL URL configured but `psycopg` is not installed. "
            "Run: pip install 'psycopg[binary]'"
        ) from exc
    return _Connection(psycopg.connect(url), dialect)


@contextmanager
def db_session(settings: Settings | None = None) -> Iterator[_Connection]:
    """Yield a connection, committing on success and rolling back on failure."""
    connection = get_connection(settings)
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_db(settings: Settings | None = None) -> str:
    """Create tables (idempotent). Returns the database URL in use."""
    settings = settings or get_settings()
    dialect = dialect_of(settings.database_url)
    schema_path = SCHEMA_FILES[dialect]
    schema_sql = schema_path.read_text(encoding="utf-8")
    with db_session(settings) as connection:
        connection.executescript(schema_sql)
    return settings.database_url


def ping(settings: Settings | None = None) -> tuple[bool, str | None]:
    """Lightweight health probe: (reachable, error message if not)."""
    try:
        with db_session(settings) as connection:
            connection.execute("SELECT 1")
        return True, None
    except Exception as exc:  # pragma: no cover - only on broken local setups
        return False, str(exc)
