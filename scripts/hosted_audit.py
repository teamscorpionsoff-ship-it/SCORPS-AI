"""Synthetic hosted acceptance checks; never print tokens or passwords."""
import json
import secrets
from pathlib import Path
import requests

BASE = 'https://scorps-ai.onrender.com'
REPORT = Path('storage/hosted-audit.json')


def main():
    results = []
    def call(method, path, token=None, **kwargs):
        return requests.request(method, BASE+path, headers={'Authorization': 'Bearer '+token} if token else {}, timeout=(10,90), **kwargs)
    def check(name, fn):
        try:
            assert fn()
            results.append({'check':name,'status':'PASS'})
        except Exception as e:
            results.append({'check':name,'status':'FAIL','type':type(e).__name__})
        print(name, results[-1]['status'], flush=True)
    check('production health', lambda: call('GET','/health').json()['mode']=='production')
    check('anonymous denied', lambda: call('GET','/api/me').status_code==401)
    accounts=[]
    for _ in range(2):
        body={'email':f'audit-{secrets.token_hex(8)}@example.invalid','name':'Synthetic audit','password':secrets.token_urlsafe(24)}
        r=call('POST','/api/auth/register',json=body)
        if r.status_code!=200:
            raise RuntimeError('Synthetic registration failed; details suppressed')
        accounts.append((body,r.json()['token']))
    a,b=accounts[0][1],accounts[1][1]
    check('login',lambda:call('POST','/api/auth/login',json={k:accounts[0][0][k] for k in ('email','password')}).status_code==200)
    check('bad password rejected',lambda:call('POST','/api/auth/login',json={'email':accounts[0][0]['email'],'password':'wrong-synthetic'}).status_code==401)
    for route,payload in [('tasks',{'title':'Synthetic task','duration':30}),('memories',{'content':'Synthetic memory'}),('drafts',{'subject':'Synthetic draft','body':'No message will be sent.'})]:
        r=call('POST','/api/'+route,a,json=payload)
        check(route+' create',lambda:r.status_code==200)
        if r.status_code!=200: continue
        ident=r.json()['id']
        check(route+' readback',lambda:any(x['id']==ident for x in call('GET','/api/'+route,a).json()))
        check(route+' isolation',lambda:all(x['id']!=ident for x in call('GET','/api/'+route,b).json()))
        check(route+' cross-user delete denied',lambda:call('DELETE',f'/api/{route}/{ident}',b).status_code==404)
        if route=='tasks':
            check('planner',lambda:bool(call('GET','/api/plan',a).json()['items']))
            check('invalid task update rejected',lambda:call('PUT',f'/api/tasks/{ident}',a,json={'title':'Synthetic','priority':'INVALID','duration':-1}).status_code==422)
        check(route+' delete',lambda:call('DELETE',f'/api/{route}/{ident}',a).status_code==200)
    r=call('POST','/api/documents',a,files={'file':('synthetic.txt',b'Synthetic audit document','text/plain')})
    check('private document upload',lambda:r.status_code==200)
    if r.status_code==200:
        ident=r.json()['id']
        check('document readback',lambda:call('GET',f'/api/documents/{ident}/original',a).content==b'Synthetic audit document')
        check('document isolation',lambda:call('GET',f'/api/documents/{ident}/original',b).status_code==404)
        check('document delete',lambda:call('DELETE',f'/api/documents/{ident}',a).status_code==200)
    check('unsupported upload rejected',lambda:call('POST','/api/documents',a,files={'file':('synthetic.exe',b'synthetic')}).status_code==415)
    check('demo chat',lambda:call('POST','/api/chat',a,json={'message':'hello'}).json()['mode']=='demo')
    check('research blocks local URL',lambda:bool(call('POST','/api/research/read',a,json={'urls':['http://127.0.0.1/']}).json()[0]['error']))
    check('integrations report',lambda:call('GET','/api/integrations',a).status_code==200)
    r=call('POST','/api/approvals?action=synthetic-no-operation',a)
    if r.status_code==200:
        ident=r.json()['id']
        check('approval isolation',lambda:call('POST',f'/api/approvals/{ident}/approve',b).status_code==404)
        check('approval decision',lambda:call('POST',f'/api/approvals/{ident}/reject',a).status_code==200)
        check('approval replay denied',lambda:call('POST',f'/api/approvals/{ident}/approve',a).status_code==404)
    check('unapproved CORS denied',lambda:'access-control-allow-origin' not in requests.options(BASE+'/api/tasks',headers={'Origin':'https://invalid.example','Access-Control-Request-Method':'GET'},timeout=20).headers)
    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text(json.dumps(results,indent=2))


if __name__=='__main__':
    main()
