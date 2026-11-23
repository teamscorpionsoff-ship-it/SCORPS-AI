"""Transactional persistence for local SQLite and hosted PostgreSQL."""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

import psycopg
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row

from app.config import get_settings
from app.db_errors import diagnostic

MIGRATIONS = Path(__file__).resolve().parents[1] / "migrations"


class Database:
    def __init__(self, connection):
        self.connection = connection
        self.postgres = isinstance(connection, psycopg.Connection)

    def execute(self, statement, parameters=()):
        # Application SQL is static. User values are always bound separately.
        if self.postgres:
            statement = statement.replace("?", "%s")
        return self.connection.execute(statement, parameters)


@contextmanager
def session():
    settings = get_settings()
    url = settings.database_url
    if url.startswith("sqlite:///") and settings.app_env != "production":
        path = Path(url.removeprefix("sqlite:///"))
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(path)
        connection.row_factory = sqlite3.Row
    elif url.startswith(("postgres://", "postgresql://")):
        stage = "connection options"
        try:
            options = {}
            if settings.app_env == "production":
                mode = conninfo_to_dict(url).get("sslmode")
                if mode not in ("verify-ca", "verify-full"):
                    options["sslmode"] = "require"
            stage = "connect"
            connection = psycopg.connect(url, connect_timeout=5, row_factory=dict_row, **options)
        except psycopg.Error as error:
            raise diagnostic(stage, error) from None
    else:
        raise RuntimeError("Configure a PostgreSQL DATABASE_URL for production.")
    try:
        database = Database(connection)
        if database.postgres:
            try:
                database.execute("SET LOCAL search_path TO scorpions")
            except psycopg.Error as error:
                raise diagnostic("session setup", error) from None
        yield database
        connection.commit()
    except Exception:
        try:
            connection.rollback()
        except psycopg.Error:
            pass  # Preserve the original failure if the server disconnected.
        raise
    finally:
        connection.close()


def init_db():
    stage = "open transaction"
    try:
        with session() as database:
            directory = MIGRATIONS
            if database.postgres:
                # Serialize migrations if multiple web instances start together.
                stage = "migration lock"
                database.execute("SELECT pg_advisory_xact_lock(543214712)")
                stage = "schema setup"
                if not database.execute("SELECT 1 FROM pg_namespace WHERE nspname='scorpions'").fetchone():
                    database.execute("CREATE SCHEMA scorpions")
                directory = MIGRATIONS / "postgres"
            stage = "migration ledger"
            database.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY)")
            applied = {row["version"] for row in database.execute("SELECT version FROM schema_migrations")}
            for migration in sorted(directory.glob("*.sql")):
                if migration.name not in applied:
                    stage = f"migration {migration.name}"
                    for statement in migration.read_text(encoding="utf-8").split(";"):
                        if statement.strip():
                            database.execute(statement)
                    database.execute("INSERT INTO schema_migrations (version) VALUES (?)", (migration.name,))
            stage = "migration commit"
    except psycopg.Error as error:
        raise diagnostic(stage, error) from None
