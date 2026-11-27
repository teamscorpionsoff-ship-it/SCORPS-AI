"""Database-backed rolling limits; reserve before each external model attempt."""
import time
from fastapi import HTTPException
from app.config import get_settings
from app.db import session


def reserve(user_id: int):
    config=get_settings()
    now=int(time.time())
    with session() as db:
        if db.postgres:
            db.execute('SELECT pg_advisory_xact_lock(543214713)')
        # On SQLite this first write acquires the writer lock before counting.
        db.execute('INSERT INTO ai_requests(user_id,requested_at) VALUES(?,?)',(user_id,now))
        personal=db.execute('SELECT COUNT(*) AS n FROM ai_requests WHERE user_id=? AND requested_at>?',(user_id,now-3600)).fetchone()['n']
        total=db.execute('SELECT COUNT(*) AS n FROM ai_requests WHERE requested_at>?',(now-86400,)).fetchone()['n']
        if personal>config.ai_user_hourly_limit:
            raise HTTPException(429,'Your hourly AI request limit is reached. Please retry later.',headers={'Retry-After':'3600'})
        if total>config.ai_global_daily_limit:
            raise HTTPException(429,'The shared daily AI allowance is reached. Please retry later.',headers={'Retry-After':'86400'})
