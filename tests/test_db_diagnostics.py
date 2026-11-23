import psycopg
import pytest

from app.db import get_settings, session
from app.db_errors import DatabaseSetupError, diagnostic


@pytest.mark.parametrize("error,expected", [
    (psycopg.OperationalError("password authentication failed"), "authentication rejected"),
    (psycopg.OperationalError("could not translate host name"), "DNS resolution"),
    (psycopg.OperationalError("connection refused"), "network route"),
    (psycopg.OperationalError("certificate verify failed"), "TLS transport"),
    (psycopg.errors.InsufficientPrivilege("permission denied"), "42501"),
    (psycopg.OperationalError("unexpected reply"), "unclassified"),
])
def test_classification_never_echoes_raw_detail(error, expected):
    error.args = (str(error) + " private-detail-to-redact",)
    result = str(diagnostic("connect", error))
    assert expected in result and type(error).__name__ in result
    assert "private-detail-to-redact" not in result


@pytest.mark.parametrize("requested,effective", [("disable", "require"), ("verify-full", "verify-full")])
def test_connect_failure_preserves_production_tls(monkeypatch, requested, effective):
    settings = get_settings()
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "database_url", f"postgresql://localhost/db?sslmode={requested}")
    def fail(url, **options):
        assert options.get("sslmode", requested) == effective
        raise psycopg.OperationalError("connection refused: private-detail-to-redact")
    monkeypatch.setattr(psycopg, "connect", fail)
    with pytest.raises(DatabaseSetupError, match=r"\[connect\] OperationalError") as caught:
        with session():
            pytest.fail("Connection should have failed")
    assert "private-detail-to-redact" not in str(caught.value)
