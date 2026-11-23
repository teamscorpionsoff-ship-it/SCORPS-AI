"""Select a reproducible randomized 5-20-case live evaluation sample.

The execution adapter is intentionally gated until a real provider adapter is implemented.
This script never substitutes demo output for model evaluation.
"""
import json, os, random, secrets, sys
from datetime import datetime, timezone
from pathlib import Path

bank=json.loads(Path('evaluation/test_bank.json').read_text(encoding='utf-8'))
seed=int(os.getenv('LLM_EVAL_SEED',secrets.randbits(32)))
rng=random.Random(seed); n=rng.randint(5,min(20,len(bank)))
categories={}
for case in bank: categories.setdefault(case['category'],[]).append(case)
selected=[]
for category in rng.sample(list(categories),min(n,len(categories))): selected.append(rng.choice(categories[category]))
remaining=[c for c in bank if c not in selected]; selected.extend(rng.sample(remaining,n-len(selected)))
report={'provider':os.getenv('LLM_PROVIDER','demo'),'model':os.getenv('GROQ_MODEL_ID',''),'timestamp':datetime.now(timezone.utc).isoformat(),'seed':seed,'selected_ids':[c['id'] for c in selected],'case_count':n,'status':'BLOCKED','reason':'Live provider adapter or genuine credentials unavailable; no mock evaluation is claimed.','results':[]}
Path('evaluation').mkdir(exist_ok=True); out=Path('evaluation/latest_report.json'); out.write_text(json.dumps(report,indent=2),encoding='utf-8')
print(f"BLOCKED: selected {n} reproducible cases (seed {seed}); live LLM execution is not available. Report: {out}")
sys.exit(2)
