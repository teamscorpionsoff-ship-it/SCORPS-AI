"""Authenticated Google connection endpoints and safe OAuth browser callbacks."""
from fastapi import APIRouter,Depends,Request,HTTPException
from fastapi.responses import HTMLResponse,RedirectResponse
from pydantic import BaseModel,Field
from app.auth import current_user
from app.config import get_settings
from app.services import google_oauth as google

router=APIRouter(prefix='/api/integrations/google')
HEADERS={'Cache-Control':'no-store','Referrer-Policy':'no-referrer',
         'Content-Security-Policy':"default-src 'none'; frame-ancestors 'none'; base-uri 'none'"}


class ConfirmIn(BaseModel):
    request_id: str=Field(min_length=64,max_length=64)
    confirmation_code: str=Field(min_length=16,max_length=16)


class SendIn(BaseModel):
    approve_send: bool=False


@router.get('/status')
def status(u=Depends(current_user)): return google.status(u['id'])


@router.post('/authorize/{service}')
def authorize(service:str,u=Depends(current_user)): return google.start(u['id'],service)


@router.get('/begin',include_in_schema=False)
def begin(ticket:str):
    if len(ticket)>200: raise HTTPException(400,'Invalid connection link.')
    url,nonce=google.begin(ticket)
    response=RedirectResponse(url,status_code=303,headers=HEADERS)
    response.set_cookie(google.COOKIE,nonce,max_age=600,secure=get_settings().app_env=='production',
                        httponly=True,samesite='lax',path=google.COOKIE_PATH)
    return response


@router.get('/callback',include_in_schema=False)
def callback(request:Request,state:str='',code:str='',error:str=''):
    try:
        confirmation=google.callback(state,request.cookies.get(google.COOKIE),code,error)
        # No provider tokens, state or authorization code are rendered.
        html='<h1>Confirm your Google connection</h1><p>Return to the Scorpions AI workspace where you started connecting. Enter this one-time code there:</p><pre>'+confirmation+'</pre><p>If you did not start this connection, close this page. Do not share this code with anyone.</p>'
        response=HTMLResponse(html,headers=HEADERS)
    except HTTPException as exc:
        response=HTMLResponse('<h1>Google connection incomplete</h1><p>Return to your workspace and start again. No new connection was activated.</p>',status_code=exc.status_code,headers=HEADERS)
    response.delete_cookie(google.COOKIE,path=google.COOKIE_PATH)
    return response


@router.post('/confirm')
def confirm(body:ConfirmIn,u=Depends(current_user)):
    return google.confirm(u['id'],body.request_id,body.confirmation_code)


@router.delete('/{service}')
def disconnect(service:str,u=Depends(current_user)): return google.disconnect(u['id'],service)


@router.get('/calendar/events')
def events(u=Depends(current_user)):
    from app.services.google_actions import calendar_events
    return calendar_events(u['id'])


@router.post('/gmail/drafts/{draft_id}/prepare')
def prepare(draft_id:int,u=Depends(current_user)):
    from app.services.google_actions import prepare_email
    return prepare_email(u['id'],draft_id)


@router.post('/gmail/send/{approval_id}')
def send(approval_id:int,body:SendIn,u=Depends(current_user)):
    if not body.approve_send: raise HTTPException(422,'Explicit approval is required to send this email.')
    from app.services.google_actions import send_email
    return send_email(u['id'],approval_id)
