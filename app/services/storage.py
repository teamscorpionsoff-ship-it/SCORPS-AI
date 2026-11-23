"""Keep original uploads private. SQL records establish document ownership."""
from pathlib import Path
from uuid import uuid4

import requests

from app.config import get_settings


class StorageUnavailable(RuntimeError):
    pass


def _request(method, path, **kwargs):
    config = get_settings()
    try:
        response = requests.request(
            method, f"{config.supabase_url}/storage/v1/{path}",
            headers={"apikey": config.supabase_secret_key, "Content-Type": "application/octet-stream"},
            allow_redirects=False, timeout=(4, 30), **kwargs,
        )
    except requests.RequestException:
        raise StorageUnavailable("Private document storage is unreachable.") from None
    if not 200 <= response.status_code < 300:
        raise StorageUnavailable(f"Private document storage returned HTTP {response.status_code}.")
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
