"""Keep original uploads private. SQL records establish document ownership."""
from pathlib import Path
from uuid import uuid4

import requests

from app.config import get_settings


class StorageUnavailable(RuntimeError):
    pass


def _request(method, path, **kwargs):
    config = get_settings()
    headers = {"apikey": config.supabase_secret_key, "Content-Type": "application/octet-stream"}
    # Legacy service_role keys are JWTs: Storage needs the bearer header.
    # Modern sb_secret keys are opaque and authenticate through apikey only.
    if config.supabase_secret_key.startswith("eyJ") and config.supabase_secret_key.count(".") == 2:
        headers["Authorization"] = "Bearer " + config.supabase_secret_key
    try:
        response = requests.request(
            method, f"{config.supabase_url}/storage/v1/{path}",
            headers=headers,
            allow_redirects=False, timeout=(4, 30), **kwargs,
        )
    except requests.RequestException:
        raise StorageUnavailable("Private document storage is unreachable.") from None
    if not 200 <= response.status_code < 300:
        # Interpret internally; never echo arbitrary provider response bodies.
        reason = "unclassified storage error"
        try:
            payload = response.json()
            detail = ' '.join(str(payload.get(k, '')) for k in ('code', 'error', 'message')).lower() if isinstance(payload, dict) else ''
            if any(term in detail for term in ('bucket not found', 'nosuchbucket', 'bucketnotfound')):
                reason = "bucket not found or not visible to this credential"
            elif any(term in detail for term in ('invalid api key', 'invalidapikey', 'invalid jwt', 'invalidjwt', 'jwt expired')):
                reason = "API key or token rejected"
            elif any(term in detail for term in ('authorization', 'unauthorized', 'accessdenied', 'permission', 'jwt must be provided')):
                reason = "authorization missing or access denied"
        except (ValueError, TypeError):
            pass
        raise StorageUnavailable(f"Private document storage returned HTTP {response.status_code}: {reason}.")
    return response


def check_bucket():
    config = get_settings()
    try:
        metadata = _request("GET", f"bucket/{config.supabase_storage_bucket}").json()
    except ValueError:
        raise StorageUnavailable("Storage returned invalid bucket metadata.") from None
    if not isinstance(metadata, dict) or metadata.get("public") is not False or metadata.get("id") != config.supabase_storage_bucket:
        raise StorageUnavailable("Configure an existing private document bucket.")


def store_original(user_id, content):
    config = get_settings()
    key = f"{user_id}/{uuid4().hex}"
    if config.app_env == "production":
        check_bucket()
        _request("POST", f"object/{config.supabase_storage_bucket}/{key}", data=content)
    else:
        path = Path(config.upload_dir) / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    return key


def read_original(key):
    config = get_settings()
    if config.app_env == "production":
        return _request("GET", f"object/authenticated/{config.supabase_storage_bucket}/{key}").content
    return (Path(config.upload_dir) / key).read_bytes()


def remove_original(key):
    config = get_settings()
    if config.app_env == "production":
        _request("DELETE", f"object/{config.supabase_storage_bucket}/{key}")
    else:
        (Path(config.upload_dir) / key).unlink(missing_ok=True)
