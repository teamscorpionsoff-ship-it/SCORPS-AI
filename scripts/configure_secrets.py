"""Set selected local .env values without echoing credentials to the terminal."""
from getpass import getpass
from pathlib import Path
import os, re

ROOT=Path(__file__).resolve().parents[1]
ENV=ROOT/'.env'
ALLOWED={'APP_SECRET_KEY','GROQ_API_KEY','GROQ_MODEL_ID','GEMINI_API_KEY','GEMINI_MODEL_ID','WEB_SEARCH_PROVIDER','WEB_SEARCH_API_KEY','GOOGLE_CLIENT_ID','GOOGLE_CLIENT_SECRET','TOKEN_ENCRYPTION_KEY'}

def main():
    if not ENV.exists(): ENV.write_text((ROOT/'.env.example').read_text(encoding='utf-8'),encoding='utf-8')
    lines=ENV.read_text(encoding='utf-8').splitlines()
    existing={}
    for line in lines:
        m=re.match(r'^\s*([A-Z][A-Z0-9_]*)=(.*)$',line)
        if m: existing[m.group(1)]=m.group(2)
    print('Enter a variable name from: '+', '.join(sorted(ALLOWED)))
    key=input('Variable name (blank to finish): ').strip().upper()
    while key:
        if key not in ALLOWED:
            print('That variable is not allowed.'); key=input('Variable name (blank to finish): ').strip().upper(); continue
        if existing.get(key) and input('A value exists. Replace it? [y/N] ').strip().lower()!='y':
            key=input('Variable name (blank to finish): ').strip().upper(); continue
        value=getpass(f'Enter {key} (input hidden): ')
        if '\n' in value or '\r' in value: print('Values cannot contain newline characters.')
        else: existing[key]=value
        key=input('Variable name (blank to finish): ').strip().upper()
    updated=[]; seen=set()
    for line in lines:
        m=re.match(r'^\s*([A-Z][A-Z0-9_]*)=',line)
        if m and m.group(1) in existing:
            name=m.group(1); updated.append(name+'='+existing[name]); seen.add(name)
        else: updated.append(line)
    for name,value in existing.items():
        if name not in seen: updated.append(name+'='+value)
    ENV.write_text('\n'.join(updated)+'\n',encoding='utf-8')
    try:
        if os.name!='nt': ENV.chmod(0o600)
    except OSError: pass
    print('Saved local configuration. Values were not displayed.')

if __name__=='__main__': main()
