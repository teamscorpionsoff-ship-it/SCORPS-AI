from unittest.mock import Mock
import pytest
import requests
from app.config import get_settings
from app.services.llm import complete, ModelUnavailable


@pytest.fixture
def configured(monkeypatch):
    s=get_settings()
    for name,value in [('groq_api_key','synthetic-secret'),('groq_model_id','synthetic-model'),('groq_free_tier_confirmed',True)]:
        monkeypatch.setattr(s,name,value)


def test_no_calls_without_free_plan_confirmation(monkeypatch):
    monkeypatch.setattr(get_settings(),'groq_free_tier_confirmed',False)
    post=Mock()
    monkeypatch.setattr(requests,'post',post)
    with pytest.raises(ModelUnavailable): complete([])
    post.assert_not_called()


@pytest.mark.parametrize('status',[401,403,429,500])
def test_provider_errors_never_echo_secrets(configured,monkeypatch,status):
    response=Mock(status_code=status,text='synthetic-secret')
    monkeypatch.setattr(requests,'post',Mock(return_value=response))
    with pytest.raises(ModelUnavailable) as error: complete([])
    assert 'synthetic-secret' not in str(error.value)


def test_bounded_completion(configured,monkeypatch):
    response=Mock(status_code=200)
    response.json.return_value={'choices':[{'message':{'content':'Synthetic answer'}}]}
    post=Mock(return_value=response)
    monkeypatch.setattr(requests,'post',post)
    assert complete([{'role':'user','content':'Synthetic prompt'}],max_tokens=9999)=='Synthetic answer'
    assert post.call_args.kwargs['json']['max_completion_tokens']==1000
    assert post.call_args.kwargs['allow_redirects'] is False


def test_tool_calls_are_not_executed(configured,monkeypatch):
    response=Mock(status_code=200)
    response.json.return_value={'choices':[{'message':{'tool_calls':[{}],'content':None}}]}
    monkeypatch.setattr(requests,'post',Mock(return_value=response))
    with pytest.raises(ModelUnavailable): complete([])
