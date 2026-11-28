import json
import logging
from unittest.mock import Mock
from urllib.parse import parse_qs,urlsplit
from cryptography.fernet import Fernet
from fastapi import HTTPException
import pytest
import requests
from app.config import get_settings
from app.db import init_db,session
from app.services import google_oauth as google,google_actions as actions


@pytest.fixture
def configured(tmp_path,monkeypatch):
    s=get_settings()
    for k,v in {'app_env':'development','database_url':'sqlite:///'+str(tmp_path/'google.db'),
                'google_client_id':'synthetic-client','google_client_secret':'synthetic-client-secret',
                'google_redirect_uri':'http://127.0.0.1:8000/api/integrations/google/callback',
                'token_encryption_key':Fernet.generate_key().decode()}.items(): monkeypatch.setattr(s,k,v)
    init_db()
    response=Mock(status_code=200)
    response.json.return_value={'access_token':'synthetic-access','refresh_token':'synthetic-refresh',
        'scope':google.SCOPES['gmail'],'token_type':'Bearer','expires_in':3600}
    post=Mock(return_value=response)
    monkeypatch.setattr(requests,'post',post)
    return s,post,response


def pending_connection(uid=1):
    start=google.start(uid,'gmail')
    state=parse_qs(urlsplit(start['url']).query)['ticket'][0]
    auth,nonce=google.begin(state)
    code=google.callback(state,nonce,'synthetic-authorization-code','')
    return start,state,nonce,code,auth


def test_connection_requires_separate_owner_confirmation(configured):
    start,state,nonce,code,auth=pending_connection()
    assert not google.status(1)['gmail_connected']
    with pytest.raises(HTTPException): google.confirm(2,start['request_id'],code)
    google.confirm(1,start['request_id'],code)
    assert google.status(1)['gmail_connected']
    assert not google.status(2)['gmail_connected']
    with pytest.raises(HTTPException): google.confirm(1,start['request_id'],code)
    params=parse_qs(urlsplit(auth).query)
    assert params['scope']==[google.SCOPES['gmail']]
    assert params['access_type']==['offline'] and params['code_challenge_method']==['S256']
    with session() as db:
        cipher=db.execute('SELECT payload_cipher FROM google_tokens WHERE user_id=1').fetchone()['payload_cipher']
    assert 'synthetic-refresh' not in cipher and 'synthetic-access' not in cipher


def test_browser_binding_and_callback_replay(configured):
    start=google.start(1,'gmail')
    state=parse_qs(urlsplit(start['url']).query)['ticket'][0]
    _,nonce=google.begin(state)
    with pytest.raises(HTTPException): google.begin(state)
    with pytest.raises(HTTPException): google.callback(state,'wrong-browser','code','')
    configured[1].assert_not_called()
    google.callback(state,nonce,'code','')
    with pytest.raises(HTTPException): google.callback(state,nonce,'code','')
    assert configured[1].call_count==1


def test_confirmation_failures_are_counted_and_locked(configured):
    start,_,_,correct,_=pending_connection()
    for _ in range(5):
        with pytest.raises(HTTPException): google.confirm(1,start['request_id'],'0'*16)
    with pytest.raises(HTTPException): google.confirm(1,start['request_id'],correct)
    assert not google.status(1)['gmail_connected']


def test_expired_flow_and_denied_consent(configured):
    start=google.start(1,'calendar')
    state=parse_qs(urlsplit(start['url']).query)['ticket'][0]
    with session() as db: db.execute('UPDATE google_oauth_flows SET created_at=0')
    with pytest.raises(HTTPException): google.begin(state)
    start=google.start(1,'gmail')
    state=parse_qs(urlsplit(start['url']).query)['ticket'][0]
    _,nonce=google.begin(state)
    with pytest.raises(HTTPException): google.callback(state,nonce,'','access_denied')
    configured[1].assert_not_called()


def test_missing_scope_never_connects(configured):
    configured[2].json.return_value['scope']='unrelated'
    with pytest.raises(HTTPException): pending_connection()
    assert not google.status(1)['gmail_connected']


def test_refresh_and_local_disconnect(configured):
    start,_,_,code,_=pending_connection()
    google.confirm(1,start['request_id'],code)
    with session() as db:
        p=google.decrypt(db.execute('SELECT payload_cipher FROM google_tokens WHERE user_id=1').fetchone()['payload_cipher'])
        p['expires_at']=0
        db.execute('UPDATE google_tokens SET payload_cipher=? WHERE user_id=1',(google.encrypt(p),))
    configured[2].json.return_value={'access_token':'new-synthetic-access','expires_in':3600,'token_type':'Bearer'}
    assert google.access_token(1,'gmail')=='new-synthetic-access'
    assert configured[1].call_args.kwargs['data']['grant_type']=='refresh_token'
    with session() as db:
        p=google.decrypt(db.execute('SELECT payload_cipher FROM google_tokens WHERE user_id=1').fetchone()['payload_cipher'])
    assert p['refresh_token']=='synthetic-refresh'
    google.disconnect(2,'gmail')
    assert google.status(1)['gmail_connected']
    google.disconnect(1,'gmail')
    with pytest.raises(HTTPException): google.access_token(1,'gmail')


def test_setup_validation_and_access_logs(configured,monkeypatch):
    from app.main import app
    assert google.configuration_ready()
    monkeypatch.setattr(configured[0],'token_encryption_key','bad')
    assert not google.configuration_ready()
    with pytest.raises(HTTPException): google.start(1,'gmail')
    assert logging.getLogger('uvicorn.access').disabled


def test_callback_cookie_and_no_tokens_in_response(configured):
    from fastapi.testclient import TestClient
    from app.main import app
    start=google.start(1,'gmail')
    with TestClient(app) as client:
        first=client.get(start['url'].replace('http://127.0.0.1:8000',''),follow_redirects=False)
        assert first.status_code==303
        assert 'HttpOnly' in first.headers['set-cookie'] and 'SameSite=lax' in first.headers['set-cookie']
        state=parse_qs(urlsplit(first.headers['location']).query)['state'][0]
        done=client.get('/api/integrations/google/callback',params={'state':state,'code':'synthetic-code'})
        assert done.status_code==200
        assert done.headers['cache-control']=='no-store'
        assert 'synthetic-access' not in done.text and 'synthetic-refresh' not in done.text


def make_draft():
    with session() as db:
        return db.execute('INSERT INTO drafts(user_id,recipient,subject,body) VALUES(?,?,?,?) RETURNING id',
                          (1,'synthetic@example.invalid','Synthetic subject','Synthetic body')).fetchone()['id']


def test_approved_snapshot_is_immutable_and_single_use(configured,monkeypatch):
    monkeypatch.setattr(actions,'access_token',lambda *args:'synthetic-access')
    draft=make_draft()
    preview=actions.prepare_email(1,draft)
    with session() as db: db.execute('UPDATE drafts SET subject=? WHERE id=?',('Changed after preview',draft))
    assert actions.send_email(1,preview['approval_id'])['sent']
    payload=configured[1].call_args.kwargs['json']
    import base64
    raw=base64.urlsafe_b64decode(payload['raw']).decode()
    assert 'Synthetic subject' in raw and 'Changed after preview' not in raw
    with pytest.raises(HTTPException): actions.send_email(1,preview['approval_id'])
    assert configured[1].call_count==1


def test_timeout_marks_unknown_and_blocks_replay(configured,monkeypatch):
    monkeypatch.setattr(actions,'access_token',lambda *args:'synthetic-access')
    ident=actions.prepare_email(1,make_draft())['approval_id']
    configured[1].side_effect=requests.Timeout('secret-detail')
    with pytest.raises(HTTPException) as error: actions.send_email(1,ident)
    assert 'secret-detail' not in error.value.detail
    with pytest.raises(HTTPException): actions.send_email(1,ident)
    assert configured[1].call_count==1
    with session() as db: assert db.execute('SELECT status FROM approvals WHERE id=?',(ident,)).fetchone()['status']=='unknown'


def test_email_cross_user_access_and_header_injection(configured,monkeypatch):
    monkeypatch.setattr(actions,'access_token',lambda *args:'synthetic-access')
    draft=make_draft()
    with pytest.raises(HTTPException): actions.prepare_email(2,draft)
    preview=actions.prepare_email(1,draft)
    with pytest.raises(HTTPException): actions.send_email(2,preview['approval_id'])
    configured[1].assert_not_called()
    with session() as db: db.execute('UPDATE drafts SET subject=? WHERE id=?',('Bad\nBcc: injected',draft))
    with pytest.raises(HTTPException): actions.prepare_email(1,draft)


def test_calendar_is_read_only_and_excludes_unneeded_fields(configured,monkeypatch):
    monkeypatch.setattr(actions,'access_token',lambda *args:'synthetic-access')
    response=Mock(status_code=200)
    response.json.return_value={'items':[{'summary':'Synthetic meeting','start':{'date':'2026-12-01'},'end':{'date':'2026-12-02'},'attendees':['private-synthetic'],'description':'not-needed'}]}
    get=Mock(return_value=response)
    monkeypatch.setattr(requests,'get',get)
    result=actions.calendar_events(1)
    assert 'attendees' not in str(result) and 'not-needed' not in str(result)
    assert get.call_args.args[0].endswith('/calendars/primary/events')
    assert get.call_args.kwargs['params']['maxResults']==20
    configured[1].assert_not_called()


def test_routes_require_authentication_and_explicit_send_confirmation(configured,monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.auth import current_user
    with TestClient(app) as client:
        assert client.get('/api/integrations/google/status').status_code==401
        assert client.post('/api/integrations/google/authorize/gmail').status_code==401
        app.dependency_overrides[current_user]=lambda:{'id':1}
        try:
            assert client.post('/api/integrations/google/gmail/send/1',json={'approve_send':False}).status_code==422
        finally: app.dependency_overrides.clear()
    configured[1].assert_not_called()
