from unittest.mock import Mock
import pytest
import requests
from pydantic import ValidationError
from fastapi import HTTPException
from app.config import get_settings
from app.main import ResearchIn,research_search
from app.services.research import search_wikipedia,ResearchUnavailable


def test_search_returns_only_real_page_id_links_and_plain_snippets(monkeypatch):
    response=Mock(status_code=200)
    response.json.return_value={'query':{'search':[{'pageid':123,'title':'Synthetic page','snippet':'A <span>sample</span>.'}]}}
    get=Mock(return_value=response)
    monkeypatch.setattr(requests,'get',get)
    result=search_wikipedia('Synthetic topic')
    assert result['sources'][0]['url']=='https://en.wikipedia.org/?curid=123'
    assert '<span>' not in result['sources'][0]['snippet']
    assert get.call_args.args[0]=='https://en.wikipedia.org/w/api.php'
    assert get.call_args.kwargs['params']['srlimit']==5
    assert get.call_args.kwargs['allow_redirects'] is False


@pytest.mark.parametrize('status',[403,429,500,302])
def test_provider_errors_are_sanitized(monkeypatch,status):
    monkeypatch.setattr(requests,'get',Mock(return_value=Mock(status_code=status,text='private-detail')))
    with pytest.raises(ResearchUnavailable) as error: search_wikipedia('synthetic')
    assert 'private-detail' not in str(error.value)


def test_no_results_are_explicit(monkeypatch):
    response=Mock(status_code=200)
    response.json.return_value={'query':{'search':[]}}
    monkeypatch.setattr(requests,'get',Mock(return_value=response))
    assert search_wikipedia('synthetic')['sources']==[]


def test_malformed_provider_response_is_not_trusted(monkeypatch):
    response=Mock(status_code=200)
    response.json.return_value={'query':{'search':[{'pageid':'javascript:bad','title':'Synthetic','snippet':'x'}]}}
    monkeypatch.setattr(requests,'get',Mock(return_value=response))
    with pytest.raises(ResearchUnavailable): search_wikipedia('synthetic')


@pytest.mark.parametrize('query',[' ','x','x'*301])
def test_search_validation(query):
    with pytest.raises(ValidationError): ResearchIn(query=query)


def test_disconnected_search_never_calls_provider(monkeypatch):
    monkeypatch.setattr(get_settings(),'web_search_provider','')
    get=Mock()
    monkeypatch.setattr(requests,'get',get)
    with pytest.raises(HTTPException) as error: research_search(ResearchIn(query='synthetic'),{'id':1})
    assert error.value.status_code==503
    get.assert_not_called()
