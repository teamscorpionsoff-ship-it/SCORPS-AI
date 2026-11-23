"""Produce deployment diagnostics without copying server-controlled strings to logs."""
import re

import psycopg


class DatabaseSetupError(RuntimeError):
    pass


def diagnostic(stage: str, error: psycopg.Error) -> DatabaseSetupError:
    state = error.sqlstate or ""
    if not re.fullmatch(r"[0-9A-Z]{5}", state):
        state = ""
    # libpq often supplies no SQLSTATE before a session is established. Match
    # known messages internally and output only our own fixed descriptions.
    message = str(error).lower()
    if state.startswith("28") or "password authentication failed" in message or "no password supplied" in message:
        reason = "authentication rejected; check the pooler role and database credentials"
    elif "tenant or user not found" in message:
        reason = "pooler rejected the project/role mapping; check the Session pooler user and project"
    elif state == "42501":
        reason = "permission denied; check the role privileges for this initialization step"
    elif state == "53300" or "maxclients" in message or "too many clients" in message:
        reason = "database or pooler connection limit reached"
    elif state == "3D000":
        reason = "requested database does not exist"
    elif any(term in message for term in ("certificate", "ssl", "tls")):
        reason = "TLS transport or certificate error; check server TLS and client trust configuration"
    elif any(term in message for term in ("resolve host", "translate host", "getaddrinfo", "name resolution")):
        reason = "DNS resolution failed"
    elif any(term in message for term in ("timed out", "timeout expired", "connection refused", "network is unreachable", "no route to host")):
        reason = "connection timed out, was refused, or had no network route"
    elif stage == "connection options":
        reason = "libpq could not parse the connection options"
    else:
        reason = "unclassified driver error; correlate the timestamp with Supabase pooler and PostgreSQL logs"
    return DatabaseSetupError(f"PostgreSQL [{stage}] {type(error).__name__} SQLSTATE={state or 'unavailable'}: {reason}.")
