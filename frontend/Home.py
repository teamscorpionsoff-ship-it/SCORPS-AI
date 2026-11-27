import os, requests, streamlit as st
from html import escape
from urllib.parse import urlsplit

st.set_page_config(page_title='Scorpions AI',page_icon='🦂',layout='wide')
API=os.getenv('API_BASE_URL','')
if not API:
    try:
        API=st.secrets.get('API_BASE_URL','')
    except FileNotFoundError:
        API=''
API=(API or 'http://127.0.0.1:8000').rstrip('/')
api_origin=urlsplit(API)
if api_origin.username or api_origin.password or api_origin.query or api_origin.fragment or api_origin.path:
    st.error('API_BASE_URL must contain only the backend origin, with no credentials, path or query.')
    st.stop()
st.markdown('''<style>
.stApp{background:#0b1020;color:#f2f4fb}.block-container{max-width:1120px;padding-top:2rem}
[data-testid="stSidebar"]{background:#11182b}.hero{padding:28px;border:1px solid #27324a;border-radius:18px;background:linear-gradient(125deg,#192444,#11182b)}
.muted{color:#aab4ca}.stButton>button{border-radius:10px}
</style>''',unsafe_allow_html=True)
def api(path,method='get',**kw):
    headers=kw.pop('headers',{}); token=st.session_state.get('token')
    if token: headers['Authorization']='Bearer '+token
    try:
        with st.spinner('Connecting to your workspace. The free backend may take a minute to wake up…'):
            r=getattr(requests,method)(API+path,headers=headers,timeout=(10,90),**kw)
        if r.status_code>=400: st.error(r.json().get('detail','Request failed')); return None
        return r.json()
    except requests.Timeout: st.error('The backend request timed out. Retry after the Render service finishes waking up.'); return None
    except requests.ConnectionError:
        if api_origin.hostname in ('localhost','127.0.0.1'):
            st.error('The frontend is configured for a local backend. In Manage app → Settings → Secrets, set API_BASE_URL to the public Render origin, then reboot this app.')
        else: st.error('The frontend could not connect to the configured backend. Check API_BASE_URL in Streamlit app settings.')
        return None
    except requests.RequestException: st.error('The backend request failed. Verify the API origin in Streamlit app settings.'); return None
    except ValueError: st.error('The backend returned an unexpected response. Please retry shortly.'); return None

st.sidebar.markdown('## 🦂 Scorpions AI')
st.sidebar.caption('Backend: '+(api_origin.hostname or 'invalid origin'))
if 'token' not in st.session_state:
    mode=st.sidebar.radio('Account',['Sign in','Create account'])
    with st.form('auth'):
        email=st.text_input('Email'); name=st.text_input('Name') if mode=='Create account' else ''
        password=st.text_input('Password',type='password'); go=st.form_submit_button(mode)
    if go:
        payload={'email':email,'password':password}
        if mode=='Create account': payload['name']=name
        result=api('/api/auth/'+('login' if mode=='Sign in' else 'register'),'post',json=payload)
        if result: st.session_state.token=result['token']; st.session_state.user=result['user']; st.rerun()
    st.markdown('<div class="hero"><h1>Personal staff for everyone.</h1><p class="muted">One intelligent assistant for tasks, plans, research and everyday work.</p><b>AI demo available · Workspace data is stored by your configured backend.</b></div>',unsafe_allow_html=True)
    st.stop()

user=st.session_state.get('user') or api('/api/me') or {'name':'there'}
page=st.sidebar.radio('Workspace',['Overview','Assistant','Tasks','Planner','Memory','Research','Documents','Email & Calendar','Settings'])
st.sidebar.caption('Signed in as '+user.get('name','user'))
if st.sidebar.button('Sign out'): st.session_state.clear(); st.rerun()

if page=='Overview':
    st.markdown(f'<div class="hero"><h1>Good to see you, {escape(user.get("name","there"))}.</h1><p class="muted">Your personal workspace, organized in one place.</p></div>',unsafe_allow_html=True)
    tasks=api('/api/tasks') or []; pending=[t for t in tasks if t['status']!='completed']
    a,b,c=st.columns(3); a.metric('Active tasks',len(pending)); b.metric('Completed',len(tasks)-len(pending)); c.metric('Mode','Local demo')
    st.subheader('Your tasks'); st.dataframe(tasks,use_container_width=True,hide_index=True) if tasks else st.info('Nothing on your list yet. Add a task or ask your assistant.')
    if st.button('Plan my tasks'):
        result=api('/api/plan')
        if result: st.dataframe(result['items'],use_container_width=True,hide_index=True)
elif page=='Assistant':
    st.title('Assistant'); st.caption('Demo mode uses deterministic local actions. Live model calls require credentials in your local .env.')
    if 'chat' not in st.session_state: st.session_state.chat=[]
    for msg in st.session_state.chat: st.chat_message(msg['role']).write(msg['content'])
    prompt=st.chat_input('What would you like help with?')
    if prompt:
        st.session_state.chat.append({'role':'user','content':prompt})
        result=api('/api/chat','post',json={'message':prompt}); reply=(result or {}).get('reply','Something went wrong.')
        st.session_state.chat.append({'role':'assistant','content':reply}); st.rerun()
elif page=='Tasks':
    st.title('Tasks');
    with st.form('new_task',clear_on_submit=True):
        title=st.text_input('Task'); cols=st.columns(3); due=cols[0].text_input('Due date (YYYY-MM-DD)'); priority=cols[1].selectbox('Priority',['low','medium','high','urgent']); duration=cols[2].number_input('Estimated minutes',min_value=0,step=15)
        desc=st.text_area('Notes'); submit=st.form_submit_button('Add task')
    if submit and title: api('/api/tasks','post',json={'title':title,'due_date':due or None,'priority':priority,'duration':int(duration) or None,'description':desc}); st.rerun()
    items=api('/api/tasks') or []
    for t in items:
        cols=st.columns([5,1,1]); cols[0].write(f"**{t['title']}** · {t['priority']} · {t['status']} · {t.get('due_date') or 'No due date'}")
        if t['status']!='completed' and cols[1].button('Complete',key=f"done{t['id']}"):
            t.update(status='completed'); api(f"/api/tasks/{t['id']}",'put',json={k:t.get(k) for k in ('title','description','priority','status','due_date','duration','category')}); st.rerun()
        if cols[2].button('Delete',key=f"del{t['id']}"): api(f"/api/tasks/{t['id']}",'delete'); st.rerun()
    if not items: st.info('No tasks yet. Use the form above to add your first.')
elif page=='Planner':
    st.title('Planner'); st.info('Tentative local plan; no connected calendar. Missing durations are estimated as 60 minutes.')
    result=api('/api/plan')
    if result: st.dataframe(result['items'],use_container_width=True,hide_index=True) if result['items'] else st.success('No active tasks to plan.')
elif page=='Memory':
    st.title('Personal memory'); st.caption('Only store information you choose to save. You can delete it at any time.')
    with st.form('memory'): content=st.text_area('Memory to save'); save=st.form_submit_button('Save memory')
    if save and content: api('/api/memories','post',json={'content':content}); st.rerun()
    for m in api('/api/memories') or []:
        a,b=st.columns([8,1]); a.write(m['content'])
        if b.button('Delete',key='mem'+str(m['id'])): api('/api/memories/'+str(m['id']),'delete'); st.rerun()
elif page=='Research':
    st.title('Research'); topic=st.text_input('Research question')
    st.info('Live web search is disconnected until a verified no-cost search provider is configured. No sources or citations are fabricated.')
    st.subheader('Read public source pages (HTTPS only)'); url=st.text_input('Source URL');
    if st.button('Read source',disabled=not url):
        sources=api('/api/research/read','post',json={'urls':[url]})
        if sources:
            for source in sources:
                st.markdown(f"### {source['title'] or source['final_url']}")
                st.caption(source.get('canonical_url') or source['final_url'])
                if source.get('error'): st.error(source['error'])
                st.write(source.get('text') or 'No readable text extracted.')
elif page=='Documents':
    st.title('Documents'); st.caption('Documents are stored privately by your configured backend. Upload only files you choose to share with this application.')
    f=st.file_uploader('Upload PDF, DOCX, TXT, MD or CSV',type=['pdf','docx','txt','md','csv'])
    if f and st.button('Upload document'): api('/api/documents','post',files={'file':(f.name,f.getvalue(),f.type)}); st.rerun()
    st.dataframe(api('/api/documents') or [],use_container_width=True,hide_index=True)
elif page=='Email & Calendar':
    st.title('Email & Calendar'); st.warning('Google is disconnected. Drafts stay local; no messages are sent and calendar events are not modified.')
    with st.form('draft'):
        recipient=st.text_input('Recipient (optional)'); subject=st.text_input('Subject'); body=st.text_area('Draft message',height=180); saved=st.form_submit_button('Save draft locally')
    if saved:
        api('/api/drafts','post',json={'recipient':recipient,'subject':subject,'body':body}); st.success('Saved locally. Nothing was sent.'); st.rerun()
    st.subheader('Saved drafts')
    for d in api('/api/drafts') or []:
        with st.expander(d['subject'] or '(no subject)'):
            st.caption(d.get('recipient') or 'No recipient'); st.write(d['body'])
            if st.button('Delete draft',key='draft'+str(d['id'])): api('/api/drafts/'+str(d['id']),'delete'); st.rerun()
    st.subheader('Pending approvals')
    for item in api('/api/approvals') or []:
        if item['status']=='pending':
            a,b,c=st.columns([5,1,1]); a.write(item['action'])
            if b.button('Approve',key='approve'+str(item['id'])): api(f"/api/approvals/{item['id']}/approve",'post'); st.rerun()
            if c.button('Reject',key='reject'+str(item['id'])): api(f"/api/approvals/{item['id']}/reject",'post'); st.rerun()
    st.caption('Approval is recorded locally only; no connected external action is performed.')
elif page=='Settings':
    st.title('Settings'); status=api('/api/config/status'); st.json(status or {})
    st.markdown('Configure provider keys in `.env` on the backend host. Never paste keys into this page. Local demo remains available without keys.')
