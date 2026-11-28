"""Key-free encyclopedia search with source links, never fabricated citations."""
from datetime import datetime, timezone
import requests
from bs4 import BeautifulSoup


class ResearchUnavailable(RuntimeError):
    pass


def search_wikipedia(query: str):
    try:
        response=requests.get('https://en.wikipedia.org/w/api.php',
            params={'action':'query','list':'search','srsearch':query,'srlimit':5,
                    'srnamespace':0,'srprop':'snippet','format':'json','formatversion':2},
            headers={'User-Agent':'ScorpionsAI/0.2 (https://github.com/teamscorpionsoff-ship-it/SCORPS-AI; encyclopedia research)'},
            timeout=(5,20),allow_redirects=False)
    except requests.RequestException:
        raise ResearchUnavailable('Wikipedia search is unavailable or timed out. Try again later.') from None
    if response.status_code==429:
        raise ResearchUnavailable('Wikipedia requested a pause. Wait before searching again.')
    if response.status_code!=200:
        raise ResearchUnavailable('Wikipedia could not complete this search. Try again later.')
    try:
        data=response.json()
        if 'error' in data: raise ValueError()
        rows=data['query']['search']
        if not isinstance(rows,list): raise ValueError()
        sources=[]
        for row in rows[:5]:
            ident=row['pageid']
            title=row['title']
            snippet=row['snippet']
            if type(ident) is not int or ident<=0 or not isinstance(title,str) or not isinstance(snippet,str): raise ValueError()
            sources.append({'title':title[:300], 'url':f'https://en.wikipedia.org/?curid={ident}',
                            'snippet':BeautifulSoup(snippet,'html.parser').get_text(' ',strip=True)[:1000]})
    except (ValueError,KeyError,TypeError):
        raise ResearchUnavailable('Wikipedia returned an unexpected search response.') from None
    return {'provider':'wikipedia','query':query,'sources':sources,'retrieved_at':datetime.now(timezone.utc).isoformat(),
            'note':'Encyclopedia search only. Snippets are excerpts, not verified AI conclusions or general web/news coverage.'}
