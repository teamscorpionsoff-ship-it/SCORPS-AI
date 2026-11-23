import ipaddress, socket
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse
import requests
import trafilatura
from bs4 import BeautifulSoup
from app.models.source import Source

def _validate(url: str):
    parsed=urlparse(url)
    if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password: raise ValueError('Only public HTTPS source URLs are allowed.')
    try: addresses={x[4][0] for x in socket.getaddrinfo(parsed.hostname,None)}
    except OSError: raise ValueError('Source host could not be resolved.')
    if not addresses or any(not ipaddress.ip_address(addr).is_global for addr in addresses): raise ValueError('Private or reserved network addresses are blocked.')

def read_source(url: str) -> Source:
    original=url; current=url; response=None
    for _ in range(4):
        _validate(current)
        response=requests.get(current,timeout=(4,12),allow_redirects=False,headers={'User-Agent':'ScorpionsAI/0.1 (source reader)'})
        if response.is_redirect:
            if not response.headers.get('Location'): raise ValueError('Invalid redirect target.')
            current=urljoin(current,response.headers['Location']); continue
        break
    if response is None or response.is_redirect: raise ValueError('Too many redirects.')
    response.raise_for_status()
    if 'text/html' not in response.headers.get('Content-Type','').lower(): raise ValueError('Source is not HTML.')
    content=trafilatura.extract(response.text,include_comments=False,include_tables=True) or ''
    soup=BeautifulSoup(response.text,'html.parser')
    title=soup.title.get_text(' ',strip=True) if soup.title else ''
    canonical=soup.find('link',rel='canonical')
    if not content: content=soup.get_text(' ',strip=True)
    return Source(original_url=original,final_url=response.url or current,canonical_url=urljoin(current,canonical['href']) if canonical and canonical.get('href') else None,title=title,text=content[:100000],retrieved_at=datetime.now(timezone.utc),status_code=response.status_code)

def read_sources(urls: list[str]) -> list[Source]:
    if len(urls)>10: raise ValueError('Read at most 10 sources at once.')
    results=[]
    for url in urls:
        try: results.append(read_source(url))
        except Exception as exc: results.append(Source(original_url=url,final_url=url,title='',text='',error=str(exc)))
    return results
