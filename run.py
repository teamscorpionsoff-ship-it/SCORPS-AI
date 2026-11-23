import os, subprocess, sys, time

def main():
    root=os.path.dirname(os.path.abspath(__file__))
    env=os.environ.copy(); env.setdefault('API_BASE_URL','http://127.0.0.1:8000')
    api=subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000'],cwd=root,env=env)
    time.sleep(2)
    ui=subprocess.Popen([sys.executable,'-m','streamlit','run','frontend/Home.py','--server.port','8501'],cwd=root,env=env)
    try: ui.wait()
    except KeyboardInterrupt: pass
    finally:
        ui.terminate(); api.terminate(); ui.wait(); api.wait()
if __name__=='__main__': main()
