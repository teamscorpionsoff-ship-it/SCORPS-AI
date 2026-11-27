from datetime import datetime, timedelta, timezone
import json, logging, os, re
from typing import Optional, Literal
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from app.config import get_settings
from app.db import init_db, session
from app.auth import current_user, hash_password, verify_password, issue_token
from app.services import storage
from fastapi.responses import JSONResponse, Response

settings=get_settings()
logging.basicConfig(level=settings.log_level, format='%(asctime)s %(levelname)s %(name)s %(message)s')
@asynccontextmanager
async def lifespan(_app):
    startup()
    yield
app=FastAPI(title=settings.app_name, version='0.1.0', lifespan=lifespan)

@app.exception_handler(storage.StorageUnavailable)
async def storage_error(request, error):
    return JSONResponse(status_code=503, content={"detail": str(error)})
origins = [settings.frontend_origin] if settings.frontend_origin else []
if settings.app_env != "production":
    origins.extend(["http://127.0.0.1:8501", "http://localhost:8501"])
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=False, allow_methods=['GET','POST','PUT','DELETE'], allow_headers=['Authorization','Content-Type'])

def startup():
    issues = settings.startup_issues()
    if issues and settings.app_env == 'production':
        raise RuntimeError(' '.join(issues))
    for issue in issues:
        logging.warning('%s', issue)
    if settings.app_env == 'production':
        storage.check_bucket()
    init_db()

class Register(BaseModel): email: str; name: str=Field(min_length=1,max_length=100); password: str=Field(min_length=10,max_length=200)
class Login(BaseModel): email: str; password: str
class TaskIn(BaseModel):
    title: str=Field(min_length=1,max_length=250)
    description: str=''
    priority: Literal['low','medium','high','urgent']='medium'
    status: Literal['pending','in_progress','completed','cancelled','blocked']='pending'
    due_date: Optional[str]=None
    duration: Optional[int]=Field(default=None,gt=0)
    category: str='personal'

    @field_validator('due_date')
    @classmethod
    def valid_date(cls, value):
        if value is not None:
            from datetime import date
            if date.fromisoformat(value).isoformat()!=value:
                raise ValueError('Use YYYY-MM-DD for due dates.')
        return value
class MemoryIn(BaseModel): content: str=Field(min_length=1,max_length=3000); kind: str='note'
class ChatIn(BaseModel): message: str=Field(min_length=1,max_length=5000)
class SourceIn(BaseModel): urls: list[str]=Field(min_length=1,max_length=10)
class DraftIn(BaseModel): recipient: str=''; subject: str=Field(max_length=500); body: str=Field(max_length=20000)

@app.get('/health')
def health():
    try:
        with session() as database:
            database.execute('SELECT version FROM schema_migrations LIMIT 1').fetchone()
    except Exception:
        raise HTTPException(503, 'Database unavailable.') from None
    return {'status':'ok','mode':settings.app_env,'provider':settings.llm_provider,'provider_configured':not settings.startup_issues()}
@app.get('/api/config/status')
def config_status(): return {'mode':settings.app_env,'provider':settings.llm_provider,'issues':settings.startup_issues(),'google_connected':False,'search_connected':bool(settings.web_search_provider and settings.web_search_api_key)}
@app.post('/api/auth/register')
def register(body:Register):
    with session() as d:
        try: new_id=d.execute('INSERT INTO users(email,name,password_hash) VALUES(?,?,?) RETURNING id',(body.email.lower(),body.name,hash_password(body.password))).fetchone()['id']
        except Exception: raise HTTPException(409,'An account with that email already exists.')
    return {'token':issue_token(new_id),'user':{'id':new_id,'email':body.email.lower(),'name':body.name}}
@app.post('/api/auth/login')
def login(body:Login):
    with session() as d: row=d.execute('SELECT * FROM users WHERE email=?',(body.email.lower(),)).fetchone()
    if not row or not verify_password(body.password,row['password_hash']): raise HTTPException(401,'Email or password is incorrect.')
    return {'token':issue_token(row['id']),'user':{'id':row['id'],'email':row['email'],'name':row['name']}}
@app.get('/api/me')
def me(u=Depends(current_user)): return u

@app.get('/api/tasks')
def tasks(u=Depends(current_user), status:Optional[str]=None):
    with session() as d: rows=d.execute('SELECT * FROM tasks WHERE user_id=?'+(' AND status=?' if status else '')+' ORDER BY due_date IS NULL,due_date,id DESC',(u['id'],status) if status else (u['id'],)).fetchall()
    return [dict(r) for r in rows]
@app.post('/api/tasks')
def add_task(body:TaskIn,u=Depends(current_user)):
    if body.priority not in ['low','medium','high','urgent'] or body.status not in ['pending','in_progress','completed','cancelled','blocked']: raise HTTPException(422,'Invalid priority or status.')
    with session() as d:
        new_id=d.execute('INSERT INTO tasks(user_id,title,description,priority,status,due_date,duration,category) VALUES(?,?,?,?,?,?,?,?) RETURNING id',(u['id'],body.title,body.description,body.priority,body.status,body.due_date,body.duration,body.category)).fetchone()['id']
        return dict(d.execute('SELECT * FROM tasks WHERE id=?',(new_id,)).fetchone())
@app.put('/api/tasks/{task_id}')
def update_task(task_id:int,body:TaskIn,u=Depends(current_user)):
    with session() as d:
        cur=d.execute('UPDATE tasks SET title=?,description=?,priority=?,status=?,due_date=?,duration=?,category=? WHERE id=? AND user_id=?',(body.title,body.description,body.priority,body.status,body.due_date,body.duration,body.category,task_id,u['id']))
        if not cur.rowcount: raise HTTPException(404,'Task not found.')
        return dict(d.execute('SELECT * FROM tasks WHERE id=?',(task_id,)).fetchone())
@app.delete('/api/tasks/{task_id}')
def delete_task(task_id:int,u=Depends(current_user)):
    with session() as d: cur=d.execute('DELETE FROM tasks WHERE id=? AND user_id=?',(task_id,u['id']))
    if not cur.rowcount: raise HTTPException(404,'Task not found.')
    return {'deleted':True}
@app.get('/api/memories')
def memories(u=Depends(current_user)):
    with session() as d: return [dict(r) for r in d.execute('SELECT * FROM memories WHERE user_id=? ORDER BY id DESC',(u['id'],)).fetchall()]
@app.post('/api/memories')
def add_memory(body:MemoryIn,u=Depends(current_user)):
    with session() as d:
        new_id=d.execute('INSERT INTO memories(user_id,content,kind) VALUES(?,?,?) RETURNING id',(u['id'],body.content,body.kind)).fetchone()['id']; return dict(d.execute('SELECT * FROM memories WHERE id=?',(new_id,)).fetchone())
@app.delete('/api/memories/{memory_id}')
def delete_memory(memory_id:int,u=Depends(current_user)):
    with session() as d: cur=d.execute('DELETE FROM memories WHERE id=? AND user_id=?',(memory_id,u['id']))
    if not cur.rowcount: raise HTTPException(404,'Memory not found.')
    return {'deleted':True}

def plan(tasks, start=None, hours=8):
    """Simple deterministic earliest-deadline priority plan; no calendar writes."""
    now=start or datetime.now(timezone.utc); cursor=now
    deadline=now+timedelta(hours=hours)
    out=[]
    for t in sorted((x for x in tasks if x['status'] not in ('completed','cancelled')),key=lambda x:(x.get('due_date') or '9999', {'urgent':0,'high':1,'medium':2,'low':3}.get(x.get('priority'),2))):
        mins=t.get('duration') or 60
        if mins>hours*60: out.append({'task':t['title'],'status':'needs_duration_or_split'}); continue
        if cursor+timedelta(minutes=mins)>deadline:
            out.append({'task':t['title'],'status':'outside_planning_window'})
            continue
        out.append({'task':t['title'],'start':cursor.isoformat(),'end':(cursor+timedelta(minutes=mins)).isoformat(),'tentative':not bool(t.get('duration'))})
        cursor+=timedelta(minutes=mins+10)
    return out
@app.get('/api/plan')
def get_plan(u=Depends(current_user)):
    with session() as d: ts=[dict(r) for r in d.execute('SELECT * FROM tasks WHERE user_id=?',(u['id'],)).fetchall()]
    return {'items':plan(ts),'note':'Tentative local plan; Google Calendar is disconnected.'}


@app.get('/api/chat/history')
def chat_history(u=Depends(current_user)):
    with session() as d:
        rows=d.execute('SELECT role,content,created_at FROM messages WHERE user_id=? ORDER BY id DESC LIMIT 100',(u['id'],)).fetchall()
    return [dict(row) for row in reversed(rows)]

@app.post('/api/chat')
def chat(body:ChatIn,u=Depends(current_user)):
    text=body.message; low=text.lower()
    if settings.llm_provider=='groq':
        from app.services.llm import complete, SYSTEM, ModelUnavailable
        from app.services.ai_usage import reserve
        reserve(u['id'])
        # Only this user's recent chat is sent. Memories/documents/credentials
        # are never injected, and generated text cannot invoke app mutations.
        with session() as d:
            recent=d.execute('SELECT role,content FROM messages WHERE user_id=? ORDER BY id DESC LIMIT 6',(u['id'],)).fetchall()
        history=[{'role':r['role'],'content':r['content'][:3000]} for r in reversed(recent)]
        try:
            answer=complete([{'role':'system','content':SYSTEM}]+history+[{'role':'user','content':text}])
        except ModelUnavailable as error:
            raise HTTPException(503,str(error)) from None
        with session() as d:
            for role,content in [('user',text),('assistant',answer)]:
                d.execute('INSERT INTO messages(user_id,role,content) VALUES(?,?,?)',(u['id'],role,content))
        return {'reply':answer,'mode':'groq','model':settings.groq_model_id}
    if settings.llm_provider!='demo':
        raise HTTPException(503,'The selected AI provider is not supported by this build.')
    with session() as d:
        d.execute('INSERT INTO messages(user_id,role,content) VALUES(?,?,?)',(u['id'],'user',text))
        tasks=[dict(r) for r in d.execute('SELECT * FROM tasks WHERE user_id=? AND status!=? ORDER BY due_date LIMIT 8',(u['id'],'completed')).fetchall()]
        mem=[r['content'] for r in d.execute('SELECT content FROM memories WHERE user_id=? ORDER BY id DESC LIMIT 5',(u['id'],)).fetchall()]
    if any(k in low for k in ['add task','create task','remind me to','need to ']):
        title=re.sub(r'^(please\s+)?(add task|create task|remind me to|i need to)\s*','',text,flags=re.I).strip().capitalize()
        if title:
            with session() as d: d.execute('INSERT INTO tasks(user_id,title) VALUES(?,?)',(u['id'],title))
            answer=f"I added “{title}” to your task list. Add a due date and duration to include it in a realistic plan."
        else: answer='What task should I add?'
    elif 'plan' in low or 'schedule' in low or 'today' in low:
        answer='Here is a tentative plan based on your active tasks: '+json.dumps(plan(tasks),ensure_ascii=False)+'. I do not have access to your calendar yet, so please review conflicts before relying on these times.'
    elif 'remember' in low and ('my ' in low or 'i prefer' in low):
        with session() as d: d.execute('INSERT INTO memories(user_id,content,kind) VALUES(?,?,?)',(u['id'],text,'user-requested'))
        answer='Saved that as a personal memory. You can review or delete it under Memory.'
    elif 'research' in low or 'search' in low:
        answer='Research is ready in disconnected mode. Configure a verified free search provider to fetch live sources; I will not invent citations. You can open Research to enter a topic and source URLs.'
    elif any(k in low for k in ['email','meeting','document','calendar']):
        answer='I can help prepare this locally, but the related Google service is disconnected. Drafts and demo workflows never send email or change your calendar without an explicit approval step and authorized connection.'
    else:
        answer=f"Hi {u['name']} — I’m Scorpions AI in local demo mode. I can manage tasks, draft tentative plans, and keep memories you explicitly ask me to save. I currently have {len(tasks)} active task(s) and {len(mem)} saved memory item(s). Configure a supported model in .env for live AI responses."
    with session() as d: d.execute('INSERT INTO messages(user_id,role,content) VALUES(?,?,?)',(u['id'],'assistant',answer))
    return {'reply':answer,'mode':'demo' if settings.llm_provider=='demo' else settings.llm_provider}

@app.post('/api/documents')
async def upload(file:UploadFile=File(...),u=Depends(current_user)):
    raw=await file.read(settings.max_upload_size_mb*1024*1024+1)
    if len(raw)>settings.max_upload_size_mb*1024*1024: raise HTTPException(413,'File exceeds configured upload size.')
    name=os.path.basename(file.filename or 'upload.txt'); ext=name.lower().rsplit('.',1)[-1]
    try:
        if ext=='pdf':
            from pypdf import PdfReader
            import io
            content='\n'.join(p.extract_text() or '' for p in PdfReader(io.BytesIO(raw)).pages)
        elif ext=='docx':
            from docx import Document
            import io
            content='\n'.join(p.text for p in Document(io.BytesIO(raw)).paragraphs)
        elif ext in ('txt','md','csv'): content=raw.decode('utf-8')
        else: raise HTTPException(415,'Supported formats: PDF, DOCX, TXT, MD, CSV.')
    except HTTPException: raise
    except Exception: raise HTTPException(422,'Could not extract text from this file.')
    key = storage.store_original(u['id'], raw)
    try:
        with session() as d:
            row = d.execute('INSERT INTO documents(user_id,name,extracted_text,object_key) VALUES(?,?,?,?) RETURNING id',
                            (u['id'], name, content[:200000], key)).fetchone()
    except Exception:
        storage.remove_original(key)
        raise
    return {'id': row['id'], 'name': name, 'characters': len(content), 'message': 'Document saved.'}

@app.get('/api/documents/{doc_id}/original')
def download_document(doc_id: int, u=Depends(current_user)):
    with session() as d:
        row = d.execute('SELECT object_key FROM documents WHERE id=? AND user_id=?', (doc_id, u['id'])).fetchone()
    if not row or not row['object_key']:
        raise HTTPException(404, 'Original document unavailable.')
    return Response(storage.read_original(row['object_key']), media_type='application/octet-stream',
                    headers={'Content-Disposition': 'attachment', 'Cache-Control': 'no-store'})
@app.get('/api/documents')
def documents(u=Depends(current_user)):
    with session() as d: return [dict(id=r['id'],name=r['name'],characters=len(r['extracted_text']),created_at=r['created_at']) for r in d.execute('SELECT * FROM documents WHERE user_id=? ORDER BY id DESC',(u['id'],)).fetchall()]
@app.delete('/api/documents/{doc_id}')
def delete_document(doc_id:int,u=Depends(current_user)):
    with session() as d:
        row = d.execute('DELETE FROM documents WHERE id=? AND user_id=? RETURNING object_key', (doc_id, u['id'])).fetchone()
        if not row:
            raise HTTPException(404, 'Document not found.')
        if row['object_key']:
            storage.remove_original(row['object_key'])
    return {'deleted':True}
@app.get('/api/integrations')
def integrations(u=Depends(current_user)):
    return {'google':{'connected':False,'message':'Google OAuth setup is not enabled in this build.'},'research':{'connected':bool(settings.web_search_provider and settings.web_search_api_key)},'llm':{'provider':settings.llm_provider,'configured':not settings.startup_issues()}}
@app.post('/api/research/read')
def research_read(body:SourceIn,u=Depends(current_user)):
    from app.services.source_reader import read_sources
    try: return [s.model_dump(mode='json') for s in read_sources(body.urls)]
    except ValueError as exc: raise HTTPException(422,str(exc))
@app.post('/api/approvals')
def create_approval(action:str,u=Depends(current_user)):
    with session() as d:
        new_id=d.execute('INSERT INTO approvals(user_id,action) VALUES(?,?) RETURNING id',(u['id'],action)).fetchone()['id']; return {'id':new_id,'status':'pending','action':action}
@app.get('/api/approvals')
def list_approvals(u=Depends(current_user)):
    with session() as d: return [dict(r) for r in d.execute('SELECT * FROM approvals WHERE user_id=? ORDER BY id DESC',(u['id'],)).fetchall()]
@app.post('/api/approvals/{approval_id}/{decision}')
def decide_approval(approval_id:int,decision:str,u=Depends(current_user)):
    if decision not in ('approve','reject'): raise HTTPException(422,'Decision must be approve or reject.')
    with session() as d:
        cur=d.execute('UPDATE approvals SET status=? WHERE id=? AND user_id=? AND status=?',( 'approved' if decision=='approve' else 'rejected',approval_id,u['id'],'pending'))
        if not cur.rowcount: raise HTTPException(404,'Pending approval not found.')
        return dict(d.execute('SELECT * FROM approvals WHERE id=?',(approval_id,)).fetchone())
@app.get('/api/drafts')
def list_drafts(u=Depends(current_user)):
    with session() as d: return [dict(r) for r in d.execute('SELECT id,recipient,subject,body,status,created_at,updated_at FROM drafts WHERE user_id=? ORDER BY id DESC',(u['id'],)).fetchall()]
@app.post('/api/drafts')
def save_draft(body:DraftIn,u=Depends(current_user)):
    with session() as d:
        new_id=d.execute('INSERT INTO drafts(user_id,recipient,subject,body) VALUES(?,?,?,?) RETURNING id',(u['id'],body.recipient,body.subject,body.body)).fetchone()['id']
        return dict(d.execute('SELECT id,recipient,subject,body,status,created_at,updated_at FROM drafts WHERE id=?',(new_id,)).fetchone())
@app.delete('/api/drafts/{draft_id}')
def delete_draft(draft_id:int,u=Depends(current_user)):
    with session() as d: cur=d.execute('DELETE FROM drafts WHERE id=? AND user_id=?',(draft_id,u['id']))
    if not cur.rowcount: raise HTTPException(404,'Draft not found.')
    return {'deleted':True}
