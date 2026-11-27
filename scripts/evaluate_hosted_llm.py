"""Synthetic live-model evaluation through authenticated hosted chat.

Natural-language cases require explicit human rubric review; never use a second
LLM judge or claim text-only tests verify real function-calling execution.
"""
import json
import random
import secrets
from datetime import datetime, timezone
from pathlib import Path
import requests

BASE='https://scorps-ai.onrender.com'


def main():
    bank=json.loads(Path('evaluation/test_bank.json').read_text())
    seed=secrets.randbits(32)
    rng=random.Random(seed)
    count=rng.randint(5,min(20,len(bank)))
    cases=rng.sample(bank,count)
    report={'provider':'groq','model':None,'timestamp':datetime.now(timezone.utc).isoformat(),
            'seed':seed,'case_count':count,'selected_ids':[c['id'] for c in cases],
            'category_coverage':[c['category'] for c in cases], 'results':[],
            'assessment':'PENDING_REVIEW','recommendations':['Review each observable answer against its expected behavior.',
             'Tool execution is unavailable; do not accept this model as a tool-using agent based on text-only results.']}
    for case in cases:
        result={'id':case['id'],'category':case['category'],'expected':case['expected'],'status':'INCONCLUSIVE'}
        try:
            r=requests.post(BASE+'/api/auth/register',json={'email':f'llm-eval-{secrets.token_hex(10)}@example.invalid',
                'name':'Synthetic model evaluation','password':secrets.token_urlsafe(32)},timeout=(10,60))
            if r.status_code!=200: raise ValueError()
            token=r.json()['token']
            r=requests.post(BASE+'/api/chat',headers={'Authorization':'Bearer '+token},
                            json={'message':case['prompt']},timeout=(10,70))
            if r.status_code!=200:
                result['reason']='Hosted provider call failed; HTTP '+str(r.status_code)
            else:
                data=r.json()
                if data.get('mode')!='groq' or not data.get('model'): raise ValueError()
                report['model']=data['model']
                answer=data['reply']
                result['observable_output']=answer
                result['reason']='Explicit rubric review required'
                if case['id']=='instruction-01':
                    result['status']='PASS' if answer.strip()=='READY' else 'FAIL'
                    result['reason']='Exact output assertion'
                elif case['id']=='json-01':
                    try:
                        value=json.loads(answer)
                        valid=isinstance(value,dict) and type(value.get('count')) is int and value['count']==2 and value.get('items')==['tea','rice']
                    except (ValueError,TypeError): valid=False
                    result['status']='PASS' if valid else 'FAIL'
                    result['reason']='JSON type, count and item assertions'
                elif case['id']=='tool-01':
                    result['reason']='Actual function calling unavailable; only textual tool selection observable'
        except Exception:
            result['reason']='Evaluation transport/format error; details suppressed'
        report['results'].append(result)
        print(case['id'], result['status'],flush=True)
    report['counts']={status:sum(r['status']==status for r in report['results']) for status in ('PASS','FAIL','INCONCLUSIVE')}
    report['accuracy']=report['counts']['PASS']/count
    path=Path('evaluation/hosted_report.json')
    path.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('Synthetic report saved:',path)


if __name__=='__main__': main()
