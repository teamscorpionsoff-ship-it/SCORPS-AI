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
    raw=kw.pop('raw',False)
    headers=kw.pop('headers',{}); token=st.session_state.get('token')
    if token: headers['Authorization']='Bearer '+token
    try:
        with st.spinner('Connecting to your workspace. The free backend may take a minute to wake up…'):
            r=getattr(requests,method)(API+path,headers=headers,timeout=(10,90),**kw)
        if r.status_code>=400: st.error(r.json().get('detail','Request failed')); return None
        return r.content if raw else r.json()
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
    status=api('/api/config/status') or {}
    a,b,c=st.columns(3); a.metric('Active tasks',len(pending)); b.metric('Completed',len(tasks)-len(pending)); c.metric('AI mode','Live Groq' if status.get('provider')=='groq' else 'Demo')
    st.subheader('Your tasks')
    if tasks: st.dataframe(tasks,use_container_width=True,hide_index=True)
    else: st.info('Nothing on your list yet. Add a task or ask your assistant.')
    if st.button('Plan my tasks'):
        result=api('/api/plan')
        if result: st.dataframe(result['items'],use_container_width=True,hide_index=True)
elif page=='Assistant':
    st.title('Assistant')
    status=api('/api/config/status') or {}
    live=status.get('provider')=='groq'
    st.caption('Live Groq chat. Messages are sent to Groq; no email, calendar or task actions are executed from chat.' if live else 'AI demo uses deterministic actions. Live AI is not enabled in this deployment.')
    if 'chat' not in st.session_state:
        history=api('/api/chat/history')
        if history is None:
            st.info('Chat history could not be loaded. Retry before sending another message.')
            st.stop()
        st.session_state.chat=history
    for msg in st.session_state.chat: st.chat_message(msg['role']).write(msg['content'])
    prompt=st.chat_input('What would you like help with?')
    if prompt:
        result=api('/api/chat','post',json={'message':prompt})
        if result:
            st.session_state.chat.append({'role':'user','content':prompt})
            st.session_state.chat.append({'role':'assistant','content':result['reply']})
            st.rerun()
        else:
            st.warning('No completed response was added. Your message is below so you can copy it and retry.')
            st.code(prompt,language=None)
elif page=='Tasks':
    st.title('Tasks');
    with st.form('new_task',clear_on_submit=True):
        title=st.text_input('Task'); cols=st.columns(3); due=cols[0].text_input('Due date (YYYY-MM-DD)'); priority=cols[1].selectbox('Priority',['low','medium','high','urgent']); duration=cols[2].number_input('Estimated minutes',min_value=0,step=15)
        desc=st.text_area('Notes'); submit=st.form_submit_button('Add task')
    if submit and title:
        if api('/api/tasks','post',json={'title':title,'due_date':due or None,'priority':priority,'duration':int(duration) or None,'description':desc}): st.rerun()
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
    if result:
        if result['items']: st.dataframe(result['items'],use_container_width=True,hide_index=True)
        else: st.success('No active tasks to plan.')
elif page=='Memory':
    st.title('Personal memory'); st.caption('Only store information you choose to save. You can delete it at any time.')
    with st.form('memory'): content=st.text_area('Memory to save'); save=st.form_submit_button('Save memory')
    if save and content:
        if api('/api/memories','post',json={'content':content}): st.rerun()
    for m in api('/api/memories') or []:
        a,b=st.columns([8,1]); a.write(m['content'])
        if b.button('Delete',key='mem'+str(m['id'])): api('/api/memories/'+str(m['id']),'delete'); st.rerun()
elif page=='Research':
    st.title('Research')
    status=api('/api/config/status') or {}
    st.caption('Wikipedia encyclopedia search. Your query is sent to Wikipedia. This is not general web or breaking-news search; no AI-generated citations are used.')
    with st.form('research_search'):
        topic=st.text_input('Search Wikipedia',max_chars=300)
        search=st.form_submit_button('Search sources',disabled=not status.get('search_connected'))
    if not status.get('search_connected'): st.info('Encyclopedia search is disconnected.')
    if search:
        st.session_state.pop('research_results',None)
        result=api('/api/research/search','post',json={'query':topic})
        if result:
            st.session_state.research_results=result
    if st.session_state.get('research_results'):
        result=st.session_state.research_results
        st.caption('Results for: '+result['query'])
        if not result['sources']: st.info('No matching encyclopedia articles. Try different search terms.')
        for source in result['sources']:
            st.subheader(source['title'])
            st.write(source['snippet'])
            st.link_button('Open Wikipedia source',source['url'])
        st.caption('Retrieved: '+result['retrieved_at'])
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
    if f and st.button('Upload document'):
        if api('/api/documents','post',files={'file':(f.name,f.getvalue(),f.type)}): st.rerun()
    docs=api('/api/documents') or []
    st.dataframe(docs,use_container_width=True,hide_index=True)
    for doc in docs:
        a,b=st.columns([4,1])
        if a.button('Prepare download: '+doc['name'],key='download'+str(doc['id'])):
            content=api(f"/api/documents/{doc['id']}/original",raw=True)
            if content is not None: a.download_button('Download original',content,file_name=doc['name'],key='file'+str(doc['id']))
        if b.button('Delete',key='document'+str(doc['id'])):
            if api(f"/api/documents/{doc['id']}",'delete'): st.rerun()
elif page=='Email & Calendar':
    st.title('Email & Calendar')
    google=api('/api/integrations/google/status') or {}
    if not google.get('configured'):
        st.info('Google connection is not available yet. Your drafts still work; the app operator must finish Google setup.')
    st.caption('Gmail sends only after you review and approve an exact message. Calendar access is read-only. Google data is not sent to the AI model.')
    for service,label in [('gmail','Gmail sending'),('calendar','Calendar reading')]:
        connected=google.get(service+'_connected',False)
        st.subheader(label)
        st.caption('Connected' if connected else 'Disconnected')
        if connected:
            if st.button('Disconnect '+label,key='disconnect_'+service):
                if api('/api/integrations/google/'+service,'delete'): st.rerun()
        elif google.get('configured'):
            if st.button('Connect '+label,key='connect_'+service):
                request=api('/api/integrations/google/authorize/'+service,'post')
                if request: st.session_state['google_request_'+service]=request
            request=st.session_state.get('google_request_'+service)
            if request:
                st.link_button('Continue securely with Google',request['url'])
                st.caption('After Google approval, copy the one-time code from the callback page and confirm it here. Do not share it in chat.')
                code=st.text_input('One-time connection code',type='password',key='google_code_'+service)
                if st.button('Confirm '+label,key='confirm_'+service):
                    result=api('/api/integrations/google/confirm','post',json={'request_id':request['request_id'],'confirmation_code':code})
                    if result:
                        del st.session_state['google_request_'+service]
                        st.rerun()
    if google.get('calendar_connected') and st.button('Read next seven days of calendar events'):
        events=api('/api/integrations/google/calendar/events')
        if events is not None: st.session_state.google_events=events['events']
    if google.get('calendar_connected') and 'google_events' in st.session_state:
        if st.session_state.google_events: st.dataframe(st.session_state.google_events,use_container_width=True,hide_index=True)
        else: st.info('No events returned for the next seven days.')
    with st.form('draft'):
        recipient=st.text_input('Recipient (optional)'); subject=st.text_input('Subject'); body=st.text_area('Draft message',height=180); saved=st.form_submit_button('Save draft')
    if saved:
        result=api('/api/drafts','post',json={'recipient':recipient,'subject':subject,'body':body})
        if result: st.success('Draft saved. Nothing was sent.')
    st.subheader('Saved drafts')
    for d in api('/api/drafts') or []:
        with st.expander(d['subject'] or '(no subject)'):
            st.caption(d.get('recipient') or 'No recipient'); st.write(d['body'])
            if st.button('Delete draft',key='draft'+str(d['id'])): api('/api/drafts/'+str(d['id']),'delete'); st.rerun()
            if google.get('gmail_connected') and st.button('Review this email for sending',key='prepare'+str(d['id'])):
                preview=api('/api/integrations/google/gmail/drafts/'+str(d['id'])+'/prepare','post')
                if preview: st.session_state.google_send_preview=preview
    if google.get('gmail_connected') and st.session_state.get('google_send_preview'):
        preview=st.session_state.google_send_preview
        st.subheader('Exact email awaiting your approval')
        st.write('To: '+preview['recipient'])
        st.write('Subject: '+preview['subject'])
        st.text(preview['body'])
        approve=st.checkbox('I approve sending this exact email now',key='send_check'+str(preview['approval_id']))
        if st.button('Send approved email',disabled=not approve):
            result=api('/api/integrations/google/gmail/send/'+str(preview['approval_id']),'post',json={'approve_send':True})
            del st.session_state.google_send_preview
            if result: st.success('Gmail accepted the message.')
            else: st.warning('Check your Sent mail before preparing another send. This operation will not be retried automatically.')
    st.subheader('Pending approvals')
    for item in api('/api/approvals') or []:
        if item['status']=='pending':
            a,b,c=st.columns([5,1,1]); a.write(item['action'])
            if item['action']=='google_send_email': b.caption('Use the email review above to send.')
            elif b.button('Approve',key='approve'+str(item['id'])): api(f"/api/approvals/{item['id']}/approve",'post'); st.rerun()
            if c.button('Reject',key='reject'+str(item['id'])): api(f"/api/approvals/{item['id']}/reject",'post'); st.rerun()
    st.caption('Approval is recorded only; no connected external action is performed.')
elif page=='Settings':
    st.title('Settings'); status=api('/api/config/status'); st.json(status or {})
    st.markdown('Configure provider keys in `.env` on the backend host. Never paste keys into this page. Local demo remains available without keys.')
