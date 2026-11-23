import psycopg
import pytest
import socket

from app.db import get_settings, session
from app.db_errors import DatabaseSetupError, diagnostic


@pytest.mark.parametrize("code,expected", [
    (socket.EAI_AGAIN, "temporary failure"),
    (socket.EAI_NONAME, "no address"),
    (socket.EAI_FAIL, "another address lookup error"),
])
def test_dns_probe_redacts_resolver_and_uri(monkeypatch, code, expected):
    def fail(*args, **kwargs):
        raise socket.gaierror(code, "private-resolver-detail")
    monkeypatch.setattr(socket, "getaddrinfo", fail)
    result = str(diagnostic("connect", psycopg.OperationalError("failed to resolve host"),
                            url="postgresql://synthetic:synthetic-secret@private.example/db"))
    assert expected in result
    assert all(value not in result for value in ("private.example", "synthetic", "private-resolver-detail"))


def test_invalid_parsed_host_is_not_resolved(monkeypatch):
    def unexpected(*args, **kwargs):
        pytest.fail("Malformed host must not be resolved")
    monkeypatch.setattr(socket, "getaddrinfo", unexpected)
    result = str(diagnostic("connect", psycopg.OperationalError("failed to resolve host"),
                            url="postgresql://user:synthetic@secret@private.example/db"))
    assert "host is not a single valid DNS name" in result
    assert "synthetic" not in result and "secret@" not in result


def test_dns_recheck_can_succeed(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(socket.AF_INET,)])
    result = str(diagnostic("connect", psycopg.OperationalError("failed to resolve host"),
                            url="postgresql://user:synthetic@private.example/db"))
    assert "resolved on diagnostic recheck" in result


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
