"""Run as python -m scripts.render_preflight using the intended hosted settings."""
from app.config import get_settings
from app.db import session
from app.db_errors import DatabaseSetupError, diagnostic
import psycopg
from secrets import token_bytes
from getpass import getpass
import os
import sys

from app.services.storage import StorageUnavailable, read_original, remove_original, store_original


def main():
    settings = get_settings()
    if settings.app_env != "production":
        print("Preflight requires APP_ENV=production.")
        return 1
    issues = settings.startup_issues()
    if issues:
        print("\n".join(issues))
        return 1
    try:
        with session() as db:
            row = db.execute(
                "SELECT CASE WHEN EXISTS (SELECT FROM pg_namespace WHERE nspname='scorpions') "
                "THEN has_schema_privilege('scorpions','USAGE') AND has_schema_privilege('scorpions','CREATE') "
                "ELSE has_database_privilege(current_user,current_database(),'CREATE') END AS can_migrate"
            ).fetchone()
            if not row["can_migrate"]:
                print("Schema setup requires database CREATE for a new schema, or USAGE and CREATE on the existing scorpions schema.")
                return 1
            # Verify the client connection, including when using a TLS pooler.
            if not db.connection.pgconn.ssl_in_use:
                print("The PostgreSQL client connection requires TLS.")
                return 1
        probe = token_bytes(32)
        key = store_original(0, probe)
        try:
            if read_original(key) != probe:
                print("Private bucket read-back failed.")
                return 1
        finally:
            remove_original(key)
    except (DatabaseSetupError, StorageUnavailable) as error:
        print(str(error))
        return 1
    except psycopg.Error as error:
        print(diagnostic("preflight", error))
        return 1
    except Exception:
        print("PostgreSQL preflight failed. Check the connection URL and database permissions.")
        return 1
    print("Production configuration, database TLS, and private bucket write/read/delete verified.")
    return 0


if __name__ == "__main__":
    if sys.argv[1:] == ["--prompt"]:
        if not sys.stdin.isatty():
            sys.exit("Run --prompt from an interactive terminal with hidden input.")
        os.environ.update(APP_ENV="production", LLM_PROVIDER="demo", FRONTEND_ORIGIN="",
                          APP_SECRET_KEY=token_bytes(32).hex(), SUPABASE_STORAGE_BUCKET="scorpions-documents")
        for name in ("SUPABASE_URL", "DATABASE_URL", "SUPABASE_SECRET_KEY"):
            os.environ[name] = getpass(f"{name} (hidden): ").strip()
        get_settings.cache_clear()
    elif sys.argv[1:]:
        sys.exit("Usage: python -m scripts.render_preflight [--prompt]")
    raise SystemExit(main())
