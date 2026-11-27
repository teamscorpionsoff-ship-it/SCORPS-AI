from concurrent.futures import ThreadPoolExecutor
import pytest
from fastapi import HTTPException
from app.config import get_settings
from app.db import init_db, session
from app.main import chat, chat_history, ChatIn
from app.services.ai_usage import reserve
from app.services import llm


@pytest.fixture
def database(tmp_path,monkeypatch):
    s=get_settings()
    monkeypatch.setattr(s,'app_env','development')
    monkeypatch.setattr(s,'database_url','sqlite:///'+str(tmp_path/'chat.db'))
    monkeypatch.setattr(s,'ai_user_hourly_limit',2)
    monkeypatch.setattr(s,'ai_global_daily_limit',3)
    monkeypatch.setattr(s,'llm_provider','groq')
    init_db()
    return s


def test_history_order_limit_and_user_isolation(database):
    with session() as db:
        for i in range(105):
            db.execute('INSERT INTO messages(user_id,role,content) VALUES(?,?,?)',(1,'user',str(i)))
        db.execute('INSERT INTO messages(user_id,role,content) VALUES(?,?,?)',(2,'user','private-other-user'))
    history=chat_history({'id':1})
    assert len(history)==100 and history[0]['content']=='5' and history[-1]['content']=='104'
    assert all(x['content']!='private-other-user' for x in history)


def test_limits_survive_reinitialization_and_global_limit(database):
    reserve(1)
    init_db()
    reserve(1)
    with pytest.raises(HTTPException) as error: reserve(1)
    assert error.value.status_code==429
    reserve(2)
    with pytest.raises(HTTPException) as error: reserve(3)
    assert 'shared daily' in error.value.detail
    with session() as db:
        assert db.execute('SELECT COUNT(*) AS n FROM ai_requests').fetchone()['n']==3


def test_concurrent_reservations_cannot_exceed_limit(database):
    def attempt(_):
        try: reserve(1); return True
        except HTTPException: return False
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert sum(pool.map(attempt,range(6)))==2


def test_provider_failure_does_not_create_completed_history(database,monkeypatch):
    def fail(*a,**k): raise llm.ModelUnavailable('Synthetic timeout')
    monkeypatch.setattr(llm,'complete',fail)
    with pytest.raises(HTTPException) as error: chat(ChatIn(message='synthetic'),{'id':1})
    assert error.value.status_code==503
    assert chat_history({'id':1})==[]
    with session() as db:
        assert db.execute('SELECT COUNT(*) AS n FROM ai_requests').fetchone()['n']==1


def test_live_context_is_scoped_and_quota_precedes_model(database,monkeypatch):
    with session() as db:
        db.execute('INSERT INTO messages(user_id,role,content) VALUES(?,?,?)',(2,'user','other-private'))
    calls=[]
    def complete(messages):
        calls.append(messages)
        return 'Synthetic response'
    monkeypatch.setattr(llm,'complete',complete)
    for _ in range(2): chat(ChatIn(message='synthetic'),{'id':1})
    with pytest.raises(HTTPException): chat(ChatIn(message='blocked'),{'id':1})
    assert len(calls)==2 and 'other-private' not in str(calls)
    assert len(chat_history({'id':1}))==4
