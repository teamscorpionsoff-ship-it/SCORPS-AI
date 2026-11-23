"""Produce deployment diagnostics without copying server-controlled strings to logs."""
import re
import socket

import psycopg
from psycopg.conninfo import conninfo_to_dict


def dns_detail(url: str) -> str:
    """Inspect only after a connection DNS failure; never return connection data."""
    try:
        options = conninfo_to_dict(url)
    except psycopg.Error:
        return "connection options could not be parsed"
    host = options.get("host", "")
    # Limit this probe to single DNS hosts. Never print even an invalid host:
    # an unescaped password can become part of the parsed hostname.
    if not host or len(host) > 253 or any(
        not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label)
        for label in host.rstrip(".").split(".")
    ):
        return "parsed host is not a single valid DNS name; check URI password percent-encoding and host formatting"
    try:
        socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as error:
        if error.errno == socket.EAI_AGAIN:
            return "resolver reports a temporary failure"
        if error.errno == socket.EAI_NONAME:
            return "resolver reports no address for the parsed hostname"
        return "resolver failed with another address lookup error"
    except OSError:
        return "resolver failed at the operating system level"
    return "hostname resolved on diagnostic recheck; initial resolution failure may be intermittent"


class DatabaseSetupError(RuntimeError):
    pass


def diagnostic(stage: str, error: psycopg.Error, *, url: str | None = None) -> DatabaseSetupError:
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
        if url is not None:
            reason += "; " + dns_detail(url)
    elif any(term in message for term in ("timed out", "timeout expired", "connection refused", "network is unreachable", "no route to host")):
        reason = "connection timed out, was refused, or had no network route"
    elif stage == "connection options":
        reason = "libpq could not parse the connection options"
    else:
        reason = "unclassified driver error; correlate the timestamp with Supabase pooler and PostgreSQL logs"
    return DatabaseSetupError(f"PostgreSQL [{stage}] {type(error).__name__} SQLSTATE={state or 'unavailable'}: {reason}.")
