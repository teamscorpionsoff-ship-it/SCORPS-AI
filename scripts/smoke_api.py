import json, urllib.request, uuid

BASE='http://127.0.0.1:8000'
def call(path,method='GET',payload=None,token=None):
    data=json.dumps(payload).encode() if payload is not None else None
    headers={'Content-Type':'application/json'}
    if token: headers['Authorization']='Bearer '+token
    request=urllib.request.Request(BASE+path,data=data,headers=headers,method=method)
    try:
        with urllib.request.urlopen(request,timeout=8) as response: return response.status,json.loads(response.read())
    except urllib.error.HTTPError as exc: return exc.code,json.loads(exc.read())

def main():
    assert call('/health')[1]['status']=='ok'
    tag=uuid.uuid4().hex
    _,a=call('/api/auth/register','POST',{'email':tag+'@example.test','name':'Demo','password':'synthetic demo password 123'})
    _,b=call('/api/auth/register','POST',{'email':tag+'b@example.test','name':'Other','password':'synthetic demo password 456'})
    code,task=call('/api/tasks','POST',{'title':'Smoke test task','priority':'high','duration':30},a['token'])
    assert code==200 and task['title']=='Smoke test task'
    assert call('/api/tasks','GET',token=b['token'])[1]==[]
    assert call('/api/plan','GET',token=a['token'])[0]==200
    code,draft=call('/api/drafts','POST',{'recipient':'demo@example.test','subject':'Demo','body':'Synthetic draft only.'},a['token'])
    assert code==200 and call('/api/drafts','GET',token=b['token'])[1]==[]
    assert call('/api/drafts/'+str(draft['id']),'DELETE',token=a['token'])[0]==200
    code,approval=call('/api/approvals?action=Local%20demo%20operation','POST',None,a['token'])
    assert code==200
    assert call(f"/api/approvals/{approval['id']}/approve",'POST',None,a['token'])[1]['status']=='approved'
    assert call('/api/tasks/'+str(task['id']),'DELETE',token=b['token'])[0]==404
    assert call('/api/tasks/'+str(task['id']),'DELETE',token=a['token'])[0]==200
    print('API smoke passed: health, registration, task, plan, and user isolation.')
if __name__=='__main__': main()
