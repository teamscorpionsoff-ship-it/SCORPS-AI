import base64, hashlib, hmac, json, os, time
from pathlib import Path
from tempfile import NamedTemporaryFile
from fastapi import Header, HTTPException
from app.config import get_settings
from app.db import session

def _secret():
    s=get_settings()
    if s.app_secret_key:
        return s.app_secret_key.encode()
    if s.app_env == 'production':
        raise RuntimeError('APP_SECRET_KEY is required in production.')
    path = Path('storage') / 'local-session.key'
    if not path.exists():
        path.parent.mkdir(exist_ok=True)
        with NamedTemporaryFile(dir=path.parent, delete=False) as temp:
            temp.write(os.urandom(32))
        try:
            # Publish only a fully written key, even if two workers start together.
            os.link(temp.name, path)
        except FileExistsError:
            pass
        finally:
            os.unlink(temp.name)
    return path.read_bytes()
def hash_password(password: str) -> str:
    salt=os.urandom(16); key=hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 240000)
    return base64.urlsafe_b64encode(salt+key).decode()
def verify_password(password: str, encoded: str) -> bool:
    try:
        raw=base64.urlsafe_b64decode(encoded); return hmac.compare_digest(raw[16:], hashlib.pbkdf2_hmac('sha256', password.encode(), raw[:16], 240000))
    except Exception: return False
def issue_token(uid: int) -> str:
    body=base64.urlsafe_b64encode(json.dumps({'sub':uid,'exp':int(time.time())+86400}).encode()).decode().rstrip('=')
    sig=hmac.new(_secret(), body.encode(), hashlib.sha256).hexdigest(); return body+'.'+sig
def current_user(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.startswith('Bearer '): raise HTTPException(401, 'Sign in to continue.')
    try:
        body,sig=authorization[7:].split('.',1)
        if not hmac.compare_digest(sig,hmac.new(_secret(),body.encode(),hashlib.sha256).hexdigest()): raise ValueError()
        data=json.loads(base64.urlsafe_b64decode(body+'==='))
        if data['exp']<time.time(): raise ValueError()
        with session() as d: row=d.execute('SELECT id,email,name FROM users WHERE id=?',(data['sub'],)).fetchone()
        if not row: raise ValueError()
        return dict(row)
    except Exception: raise HTTPException(401,'Your session expired. Please sign in again.')
