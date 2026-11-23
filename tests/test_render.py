from app.config import Settings


def test_production_rejects_local_defaults():
    settings = Settings(_env_file=None, app_env="production", app_secret_key="",
                        database_url="sqlite:///test.db", frontend_origin="http://localhost:8501")
    errors = " ".join(settings.startup_issues())
    for name in ("APP_SECRET_KEY", "DATABASE_URL", "FRONTEND_ORIGIN"):
        assert name in errors
