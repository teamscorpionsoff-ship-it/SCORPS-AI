"""Check an existing deployment without writing application data."""
import json
import os
import sys
import urllib.error
import urllib.request
from urllib.parse import urlsplit


def check(base):
    url = urlsplit(base)
    local = url.hostname in {"localhost", "127.0.0.1", "::1"}
    if not url.hostname or url.username or url.password or url.query or url.fragment or url.path:
        raise ValueError("API_BASE_URL must be the backend origin.")
    if url.scheme != "https" and not (local and url.scheme == "http"):
        raise ValueError("A public backend requires HTTPS.")
    with urllib.request.urlopen(base + "/health", timeout=90) as response:
        health = json.load(response)
        if response.status != 200 or health.get("status") != "ok":
            raise ValueError("Backend health check failed.")
        if not local and (health.get("mode") != "production" or health.get("provider_configured") is not True):
            raise ValueError("Public backend did not report healthy production configuration.")
    try:
        with urllib.request.urlopen(base + "/api/me", timeout=15):
            raise ValueError("Unauthenticated access was accepted.")
    except urllib.error.HTTPError as error:
        if error.code != 401:
            raise ValueError("Authentication check failed.") from None
    print("Backend health and authentication verified.")


if __name__ == "__main__":
    try:
        check(os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/"))
    except (ValueError, OSError) as error:
        print("Deployment check failed:", type(error).__name__)
        sys.exit(1)
