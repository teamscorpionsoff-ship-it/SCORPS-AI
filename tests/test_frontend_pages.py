from pathlib import Path
from unittest.mock import Mock
import pytest
from streamlit.testing.v1 import AppTest
import requests


@pytest.mark.parametrize('page', ['Overview','Assistant','Tasks','Planner','Memory','Research','Documents','Email & Calendar','Settings'])
def test_workspace_pages_render_without_errors(monkeypatch,page):
    monkeypatch.setenv('API_BASE_URL','https://backend.example')
    def response(url,**kwargs):
        result=Mock(status_code=200)
        data=[]
        if url.endswith('/api/plan'): data={'items':[]}
        if url.endswith('/api/config/status'): data={'mode':'production','provider':'demo','issues':[]}
        result.json.return_value=data
        return result
    monkeypatch.setattr(requests,'get',response)
    app=AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'frontend/Home.py'))
    app.session_state['token']='synthetic-test-token'
    app.session_state['user']={'name':'Synthetic'}
    app.run(timeout=15)
    app.sidebar.radio[0].set_value(page).run(timeout=15)
    assert not app.exception


def test_failed_task_submission_preserves_error(monkeypatch):
    monkeypatch.setenv('API_BASE_URL','https://backend.example')
    response=Mock(status_code=200)
    response.json.return_value=[]
    monkeypatch.setattr(requests,'get',Mock(return_value=response))
    def fail(*a,**k): raise requests.ConnectionError()
    monkeypatch.setattr(requests,'post',fail)
    app=AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'frontend/Home.py'))
    app.session_state['token']='synthetic-test-token'
    app.session_state['user']={'name':'Synthetic'}
    app.run().sidebar.radio[0].set_value('Tasks').run()
    app.text_input[0].set_value('Synthetic task')
    next(b for b in app.button if b.label=='Add task').click().run()
    assert app.error
