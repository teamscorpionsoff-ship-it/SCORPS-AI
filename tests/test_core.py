from app.main import plan
from app.main import tasks, add_task, delete_task, TaskIn
from app.config import get_settings
from app.db import init_db

def test_plan_orders_urgent_and_marks_unknown_duration():
    result=plan([{'title':'Later','priority':'low','status':'pending','due_date':None,'duration':30},{'title':'Now','priority':'urgent','status':'pending','due_date':'2026-01-01','duration':None}])
    assert result[0]['task']=='Now' and result[0]['tentative'] is True
    assert result[1]['task']=='Later'

def test_plan_does_not_place_oversized_task():
    result=plan([{'title':'Big','priority':'high','status':'pending','duration':6000}])
    assert result[0]['status']=='needs_duration_or_split'

def test_task_routes_scope_data_to_user(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "database_url", "sqlite:///" + str(tmp_path / "test.db"))
    monkeypatch.setattr(get_settings(), "app_env", "development")
    init_db()
    a={'id':90001}; b={'id':90002}
    item=add_task(TaskIn(title='Private task',priority='high'),a)
    try:
        assert item['title']=='Private task'
        assert all(t['id']!=item['id'] for t in tasks(b))
        try: delete_task(item['id'],b)
        except Exception as exc: assert getattr(exc,'status_code',None)==404
        else: assert False, 'cross-user delete should fail'
    finally: delete_task(item['id'],a)
