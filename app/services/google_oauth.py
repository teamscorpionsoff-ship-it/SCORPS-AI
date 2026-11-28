"""Google OAuth with PKCE, browser binding, account confirmation and encrypted tokens."""
import base64
import hashlib
import json
import secrets
import time
from urllib.parse import urlencode,urlsplit
import requests
from cryptography.fernet import Fernet,InvalidToken
from fastapi import HTTPException
from app.config import get_settings
from app.db import session

SCOPES={'gmail':'https://www.googleapis.com/auth/gmail.send',
        'calendar':'https://www.googleapis.com/auth/calendar.events.owned.readonly'}
COOKIE='scorpions_google_nonce'
COOKIE_PATH='/api/integrations/google'


def digest(value): return hashlib.sha256(value.encode()).hexdigest()


def configuration_ready():
    s=get_settings()
    u=urlsplit(s.google_redirect_uri)
    try: Fernet(s.token_encryption_key.encode())
    except (ValueError,TypeError): return False
    local=u.hostname in ('127.0.0.1','localhost') and s.app_env!='production'
    return bool(s.google_client_id and s.google_client_secret and u.hostname and
                (u.scheme=='https' or (local and u.scheme=='http')) and
                not(u.username or u.password or u.query or u.fragment) and
                u.path=='/api/integrations/google/callback')


def require_setup():
    if not configuration_ready():
        raise HTTPException(503,'Google connection requires GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI and a valid TOKEN_ENCRYPTION_KEY on the backend.')


def encrypt(payload):
    return Fernet(get_settings().token_encryption_key.encode()).encrypt(json.dumps(payload).encode()).decode()


def decrypt(payload):
    try: return json.loads(Fernet(get_settings().token_encryption_key.encode()).decrypt(payload.encode()))
    except (InvalidToken,ValueError,TypeError):
        raise HTTPException(503,'Google token storage cannot be read. Restore the encryption key or disconnect and reconnect.') from None


def status(uid):
    with session() as db:
        services={r['service'] for r in db.execute('SELECT service FROM google_tokens WHERE user_id=?',(uid,)).fetchall()}
    return {'configured':configuration_ready(),'gmail_connected':'gmail' in services,'calendar_connected':'calendar' in services}


def start(uid,service):
    require_setup()
    if service not in SCOPES: raise HTTPException(422,'Choose gmail or calendar.')
    state=secrets.token_urlsafe(32)
    verifier=secrets.token_urlsafe(48)
    now=int(time.time())
    with session() as db:
        db.execute('DELETE FROM google_oauth_flows WHERE created_at<?',(now-900,))
        db.execute('DELETE FROM google_oauth_flows WHERE user_id=? AND service=?',(uid,service))
        db.execute('INSERT INTO google_oauth_flows(state_hash,user_id,service,verifier_cipher,created_at) VALUES(?,?,?,?,?)',
                   (digest(state),uid,service,encrypt(verifier),now))
    u=urlsplit(get_settings().google_redirect_uri)
    return {'request_id':digest(state),'url':f'{u.scheme}://{u.netloc}/api/integrations/google/begin?'+urlencode({'ticket':state})}


def preview(ticket):
    """Validate a landing link without consuming it during GET or link preview."""
    require_setup()
    with session() as db:
        row=db.execute('SELECT * FROM google_oauth_flows WHERE state_hash=?',(digest(ticket),)).fetchone()
        if not row or row['used'] or row['browser_hash'] or row['created_at']<time.time()-600:
            raise HTTPException(400,'Connection link expired or already used. Start again from your workspace.')
    return row['service']


def begin(ticket):
    require_setup()
    nonce=secrets.token_urlsafe(32)
    with session() as db:
        row=db.execute('SELECT * FROM google_oauth_flows WHERE state_hash=?',(digest(ticket),)).fetchone()
        if not row or row['used'] or row['browser_hash'] or row['created_at']<time.time()-600:
            raise HTTPException(400,'Connection link expired or already used. Start again from your workspace.')
        verifier=decrypt(row['verifier_cipher'])
        changed=db.execute('UPDATE google_oauth_flows SET browser_hash=? WHERE state_hash=? AND browser_hash IS NULL AND used=0',(digest(nonce),digest(ticket)))
        if not changed.rowcount: raise HTTPException(400,'Connection link already used.')
    challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
    s=get_settings()
    url='https://accounts.google.com/o/oauth2/v2/auth?'+urlencode({
        'client_id':s.google_client_id,'redirect_uri':s.google_redirect_uri,'response_type':'code',
        'scope':SCOPES[row['service']],'state':ticket,'access_type':'offline','prompt':'consent select_account',
        'code_challenge':challenge,'code_challenge_method':'S256'})
    return url,nonce


def token_request(data):
    s=get_settings()
    try:
        r=requests.post('https://oauth2.googleapis.com/token',data={**data,'client_id':s.google_client_id,'client_secret':s.google_client_secret},timeout=(5,20),allow_redirects=False)
    except requests.RequestException:
        raise HTTPException(503,'Google authorization is temporarily unavailable. Retry the connection flow.') from None
    if r.status_code!=200:
        raise HTTPException(401,'Google authorization was rejected or expired. Reconnect from your workspace.')
    try:
        p=r.json()
        if not isinstance(p.get('access_token'),str) or not p['access_token'] or p.get('token_type','').lower()!='bearer': raise ValueError()
        expiry=int(p.get('expires_in',3600))
        if not 0<expiry<=86400: raise ValueError()
        return {**p,'expires_at':int(time.time())+expiry}
    except (ValueError,TypeError,AttributeError):
        raise HTTPException(503,'Google returned an invalid token response.') from None


def callback(state,nonce,code,error):
    require_setup()
    with session() as db:
        row=db.execute('SELECT * FROM google_oauth_flows WHERE state_hash=?',(digest(state),)).fetchone()
        if not row or row['used'] or row['created_at']<time.time()-600 or not nonce or not secrets.compare_digest(row['browser_hash'] or '',digest(nonce)):
            raise HTTPException(400,'Invalid or expired Google connection. Start again from your workspace.')
        changed=db.execute('UPDATE google_oauth_flows SET used=1 WHERE state_hash=? AND used=0',(digest(state),))
        if not changed.rowcount: raise HTTPException(400,'Connection already processed.')
    if error or not code: raise HTTPException(400,'Google access was not granted. You can retry from your workspace.')
    tokens=token_request({'grant_type':'authorization_code','code':code,'redirect_uri':get_settings().google_redirect_uri,'code_verifier':decrypt(row['verifier_cipher'])})
    scopes=set(tokens.get('scope','').split())
    if SCOPES[row['service']] not in scopes or not tokens.get('refresh_token'):
        raise HTTPException(400,'Google did not grant the required offline permission. Reconnect and approve the requested scope.')
    confirmation=secrets.token_hex(8)
    with session() as db:
        db.execute('UPDATE google_oauth_flows SET pending_cipher=?,confirm_hash=? WHERE state_hash=?',
                   (encrypt(tokens),digest(confirmation),digest(state)))
    return confirmation


def confirm(uid,request_id,confirmation):
    require_setup()
    valid=False
    with session() as db:
        if db.postgres: db.execute('SELECT pg_advisory_xact_lock(?)',(700000000+uid,))
        row=db.execute('SELECT * FROM google_oauth_flows WHERE state_hash=? AND user_id=?',(request_id,uid)).fetchone()
        if row and row['pending_cipher'] and row['created_at']>=time.time()-900 and row['attempts']<5:
            changed=db.execute('UPDATE google_oauth_flows SET attempts=attempts+1 WHERE state_hash=? AND attempts<5',(request_id,))
            valid=bool(changed.rowcount) and secrets.compare_digest(row['confirm_hash'],digest(confirmation.strip()))
            if valid:
                db.execute('INSERT INTO google_tokens(user_id,service,payload_cipher) VALUES(?,?,?) ON CONFLICT(user_id,service) DO UPDATE SET payload_cipher=excluded.payload_cipher',
                           (uid,row['service'],row['pending_cipher']))
                db.execute('DELETE FROM google_oauth_flows WHERE state_hash=?',(request_id,))
    if not valid: raise HTTPException(400,'Invalid, expired or already-used confirmation code. Start again if needed.')
    return {'connected':True}


def access_token(uid,service):
    require_setup()
    with session() as db:
        row=db.execute('SELECT payload_cipher FROM google_tokens WHERE user_id=? AND service=?',(uid,service)).fetchone()
    if not row: raise HTTPException(409,'Connect the required Google service first.')
    tokens=decrypt(row['payload_cipher'])
    if tokens['expires_at']<=time.time()+60:
        updated=token_request({'grant_type':'refresh_token','refresh_token':tokens['refresh_token']})
        tokens.update(updated)
        with session() as db:
            db.execute('UPDATE google_tokens SET payload_cipher=? WHERE user_id=? AND service=? AND payload_cipher=?',
                       (encrypt(tokens),uid,service,row['payload_cipher']))
    return tokens['access_token']


def disconnect(uid,service):
    if service not in SCOPES: raise HTTPException(422,'Choose gmail or calendar.')
    # Deleting locally immediately prevents all subsequent API access. Project
    # consent can additionally be removed in the Google Account permissions UI.
    with session() as db:
        db.execute('DELETE FROM google_tokens WHERE user_id=? AND service=?',(uid,service))
        db.execute('DELETE FROM google_oauth_flows WHERE user_id=? AND service=?',(uid,service))
    return {'disconnected':True,'note':'Local tokens removed. You may also revoke Scorpions AI in your Google Account connections.'}
