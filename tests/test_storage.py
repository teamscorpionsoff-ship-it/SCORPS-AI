import asyncio
import io
from unittest.mock import Mock

import pytest
from fastapi import HTTPException, UploadFile

from app import main
from app.db import init_db
from app.services import storage


@pytest.mark.parametrize('key,bearer', [('eyJsynthetic.payload.signature', True), ('sb_secret_synthetic', False)])
def test_key_type_authentication_headers(monkeypatch, key, bearer):
    monkeypatch.setattr(main.settings, 'supabase_secret_key', key)
    request = Mock(return_value=Mock(status_code=200))
    monkeypatch.setattr(storage.requests, 'request', request)
    storage._request('GET', 'bucket/test')
    headers = request.call_args.kwargs['headers']
    assert headers['apikey'] == key
    assert ('Authorization' in headers) is bearer
    if bearer:
        assert headers['Authorization'] == 'Bearer ' + key


@pytest.mark.parametrize('message,expected', [
    ('Bucket not found', 'bucket not found or not visible'),
    ('Invalid API key', 'API key or token rejected'),
    ('jwt must be provided', 'authorization missing or access denied'),
    ('other', 'unclassified storage error'),
])
def test_storage_failure_redacts_provider_detail(monkeypatch, message, expected):
    response = Mock(status_code=400)
    response.json.return_value = {'message': message + ' synthetic-secret'}
    monkeypatch.setattr(storage.requests, 'request', Mock(return_value=response))
    with pytest.raises(storage.StorageUnavailable) as error:
        storage._request('GET', 'bucket/test')
    assert expected in str(error.value)
    assert 'synthetic-secret' not in str(error.value)


def test_original_lifecycle_and_ownership(tmp_path, monkeypatch):
    monkeypatch.setattr(main.settings, 'app_env', 'development')
    monkeypatch.setattr(main.settings, 'database_url', f'sqlite:///{tmp_path}/data.db')
    monkeypatch.setattr(main.settings, 'upload_dir', str(tmp_path / 'files'))
    init_db()
    owner = {'id': 1}
    file = UploadFile(io.BytesIO(b'example'), filename='notes.txt')
    doc = asyncio.run(main.upload(file, owner))['id']
    init_db()
    assert main.download_document(doc, owner).body == b'example'
    with pytest.raises(HTTPException) as error:
        main.download_document(doc, {'id': 2})
    assert error.value.status_code == 404
    main.delete_document(doc, owner)
    assert not list((tmp_path / 'files').rglob('*.txt'))
    assert not any(p.is_file() for p in (tmp_path / 'files').rglob('*'))


def test_supabase_adapter(monkeypatch):
    monkeypatch.setattr(main.settings, 'app_env', 'production')
    monkeypatch.setattr(main.settings, 'supabase_url', 'https://sample.supabase.co')
    response = Mock(status_code=200, content=b'abc')
    response.json.return_value = {'id': main.settings.supabase_storage_bucket, 'public': False}
    request = Mock(return_value=response)
    monkeypatch.setattr(storage.requests, 'request', request)
    key = storage.store_original(7, b'abc')
    assert key.startswith('7/')
    assert storage.read_original(key) == b'abc'
    storage.remove_original(key)
    assert [call.args[0] for call in request.call_args_list] == ['GET', 'POST', 'GET', 'DELETE']
    assert all(call.kwargs['allow_redirects'] is False for call in request.call_args_list)
    response.json.return_value['public'] = True
    with pytest.raises(storage.StorageUnavailable):
        storage.store_original(7, b'abc')
    assert request.call_args.args[0] == 'GET'
