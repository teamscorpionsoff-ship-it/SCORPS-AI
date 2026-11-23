# Scorpions AI

Scorpions AI is a local-first browser-based personal staff MVP for the Homingo Hack Days Agents track, A3: “A personal staff for everyone.” It brings daily conversation, task tracking, tentative scheduling, personal memory, documents, and integration status into one user-specific workspace.

## Capabilities

The UI covers all nine approved areas: conversation/intent, tasks, planning, persistent user-controlled memory, research, bounded workflow/approval tracking, email drafting status, file/document management, and calendar integration status. The local demo implements account sessions, task CRUD, deterministic plans, explicit memory, basic text extraction, and local assistant actions. Research, live LLM calls, Google OAuth, email sending, calendar changes, and production persistent storage are currently disconnected.

## Run locally

Requires Python 3.12+. Run `run.bat` on Windows or `./run.sh` on Linux/macOS. The scripts create `.venv`, install dependencies, copy `.env.example` to `.env` if absent, and start FastAPI plus Streamlit. Open [http://127.0.0.1:8501](http://127.0.0.1:8501); API docs are at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

For manual start: `python -m pip install -r requirements.txt`, copy `.env.example` to `.env`, then `python run.py`. Do not commit `.env`. The demo works without any provider key. A live provider adapter is not yet implemented, even if its keys are configured.

## Test and health check

Run `python -m pytest`, then start the API and run `python scripts/smoke_api.py`; `python scripts/deploy_check.py` probes health and config endpoints. Current checks are limited; see [docs/TEST_PLAN.md](docs/TEST_PLAN.md).

## Deployment status

The root render.yaml defines a Free Python web service. Build with `python -m pip install -r requirements.txt` and start with `uvicorn app.main:app --host 0.0.0.0 --port $PORT`. The blueprint sets APP_ENV=production and LLM_PROVIDER=demo and generates APP_SECRET_KEY. In Render's Environment panel, supply DATABASE_URL for a durable PostgreSQL database and FRONTEND_ORIGIN for the approved HTTPS frontend origin (no path or trailing slash). The database role must be able to create the private scorpions schema and its tables. Production uses TLS. Keep the Render management key in the MCP client's environment. Verify GET /health after deployment. It reads the migration table and returns 503 if the database is unavailable.

See `docs/` for product, architecture, security, privacy, integrations, implementation status, tests, and demo instructions. Create a strong random `APP_SECRET_KEY` for any shared environment. Secrets belong in the host's secure environment settings, never in frontend code.
