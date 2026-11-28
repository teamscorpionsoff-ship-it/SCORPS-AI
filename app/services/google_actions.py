"""Fixed Google API operations. Email approval is immutable and single use."""
import base64
from datetime import datetime,timedelta,timezone
from email.message import EmailMessage
import json
import re
import requests
from fastapi import HTTPException
from app.db import session
from app.services.google_oauth import access_token


def prepare_email(uid,draft_id):
    with session() as db:
        draft=db.execute('SELECT recipient,subject,body FROM drafts WHERE id=? AND user_id=?',(draft_id,uid)).fetchone()
        if not draft: raise HTTPException(404,'Draft not found.')
        snapshot=dict(draft)
        if not re.fullmatch(r'[^@\s,<>]+@[^@\s,<>]+\.[^@\s,<>]+',snapshot['recipient']) or any(c in snapshot['subject'] for c in '\r\n'):
            raise HTTPException(422,'Use a single recipient email address and a subject without line breaks.')
        if not snapshot['subject'].strip() or not snapshot['body'].strip():
            raise HTTPException(422,'Add a subject and message before preparing to send.')
        ident=db.execute('INSERT INTO approvals(user_id,action,payload) VALUES(?,?,?) RETURNING id',
                         (uid,'google_send_email',json.dumps(snapshot))).fetchone()['id']
    return {'approval_id':ident,**snapshot}


def send_email(uid,approval_id):
    token=access_token(uid,'gmail')
    with session() as db:
        # Claim atomically before contacting Gmail. No duplicate/retry execution.
        row=db.execute("UPDATE approvals SET status='executing' WHERE id=? AND user_id=? AND action='google_send_email' AND status='pending' RETURNING payload",
                       (approval_id,uid)).fetchone()
        if not row: raise HTTPException(409,'Email approval was already used or is unavailable. Nothing was sent again.')
    snapshot=json.loads(row['payload'])
    message=EmailMessage()
    message['To']=snapshot['recipient']
    message['Subject']=snapshot['subject']
    message.set_content(snapshot['body'])
    outcome='unknown'
    try:
        response=requests.post('https://gmail.googleapis.com/gmail/v1/users/me/messages/send',
            headers={'Authorization':'Bearer '+token},
            json={'raw':base64.urlsafe_b64encode(message.as_bytes()).decode()},
            timeout=(5,30),allow_redirects=False)
        if response.status_code==200:
            outcome='completed'
        elif 400<=response.status_code<500:
            outcome='failed'
    except requests.RequestException:
        pass
    with session() as db:
        db.execute('UPDATE approvals SET status=? WHERE id=? AND user_id=?',(outcome,approval_id,uid))
    if outcome!='completed':
        raise HTTPException(503,'Gmail did not confirm delivery. Check Sent mail before preparing another send; this approval cannot be retried.')
    return {'sent':True,'message':'Gmail accepted the message.'}


def calendar_events(uid):
    token=access_token(uid,'calendar')
    now=datetime.now(timezone.utc)
    try:
        response=requests.get('https://www.googleapis.com/calendar/v3/calendars/primary/events',
            headers={'Authorization':'Bearer '+token},params={'timeMin':now.isoformat(),
                'timeMax':(now+timedelta(days=7)).isoformat(),'maxResults':20,'singleEvents':'true','orderBy':'startTime'},
            timeout=(5,20),allow_redirects=False)
    except requests.RequestException:
        raise HTTPException(503,'Google Calendar is temporarily unavailable.') from None
    if response.status_code!=200:
        raise HTTPException(503,'Google Calendar could not return events. Check permissions or reconnect.')
    try:
        return {'events':[{'title':row.get('summary','Untitled'),'start':row.get('start',{}),'end':row.get('end',{})} for row in response.json().get('items',[])[:20]]}
    except (TypeError,ValueError,AttributeError):
        raise HTTPException(503,'Google Calendar returned an invalid response.') from None
