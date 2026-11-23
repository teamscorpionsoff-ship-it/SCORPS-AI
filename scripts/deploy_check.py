import os, sys, urllib.request

base=os.getenv('API_BASE_URL','http://127.0.0.1:8000').rstrip('/')
checks=['/health','/api/config/status']
failed=False
for path in checks:
    try:
        with urllib.request.urlopen(base+path,timeout=10) as response:
            print(f'{path}: HTTP {response.status}')
            if response.status!=200: failed=True
    except Exception as exc:
        print(f'{path}: unavailable ({type(exc).__name__})'); failed=True
sys.exit(1 if failed else 0)
