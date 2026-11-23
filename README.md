# Scorpions AI

Scorpions_ai-->Fully an automated AI assistant to keep you ahead

Scorpions AI is a local-first browser-based personal staff MVP for the Homingo Hack Days Agents track, A3: “A personal staff for everyone.” It brings daily conversation, task tracking, tentative scheduling, personal memory, documents, and integration status into one user-specific workspace.

## Capabilities

The UI covers all nine approved areas: conversation/intent, tasks, planning, persistent user-controlled memory, research, bounded workflow/approval tracking, email drafting status, file/document management, and calendar integration status. The local demo implements account sessions, task CRUD, deterministic plans, explicit memory, basic text extraction, and local assistant actions. Research, live LLM calls, Google OAuth, email sending, calendar changes, and production persistent storage are currently disconnected.

## Run locally

Requires Python 3.12+. Run `run.bat` on Windows or `./run.sh` on Linux/macOS. The scripts create `.venv`, install dependencies, copy `.env.example` to `.env` if absent, and start FastAPI plus Streamlit. Open [http://127.0.0.1:8501](http://127.0.0.1:8501); API docs are at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

For manual start: `python -m pip install -r requirements.txt`, copy `.env.example` to `.env`, then `python run.py`. Do not commit `.env`. The demo works without any provider key. A live provider adapter is not yet implemented, even if its keys are configured.

## Test and health check

Run `python -m pytest`, then start the API and run `python scripts/smoke_api.py`; `python scripts/deploy_check.py` probes health and config endpoints. Current checks are limited; see [docs/TEST_PLAN.md](docs/TEST_PLAN.md).

## Deployment status

The Free Python web service is defined in `render.yaml` on branch `deploy/render-free`. Its build command is `python -m pip install -r requirements.txt`. Its start command is `uvicorn app.main:app --host 0.0.0.0 --port $PORT`. Automatic deploys are disabled. Use a Free workspace without a payment method.

Use `deployment/production.env.example` for the backend settings. In the Supabase Free project, create a **private** Storage bucket named `scorpions-documents` with no public object policies. Get the Postgres session-pooler connection URI from Connect, the project URL from the project dashboard, and a backend secret from Settings → API Keys. Set these as `DATABASE_URL`, `SUPABASE_URL`, and `SUPABASE_SECRET_KEY` in Render's secure environment. The database role needs permission to create the scorpions schema and its tables. Retain existing Supabase projects and bucket contents when redeploying. The blueprint generates `APP_SECRET_KEY` and sets production and demo mode. With no frontend origin configured, browsers receive no cross-origin permission. Set `FRONTEND_ORIGIN` once the approved HTTPS frontend exists.

Before provisioning the service, run `python -m scripts.render_preflight` with the production settings injected into a trusted environment. It checks credentials, database TLS, schema-installation privileges and private bucket write/read/delete using one temporary synthetic object. Startup repeats configuration and bucket checks and applies versioned migrations. After deployment, point `API_BASE_URL` at Render's actual HTTPS service URL and run `python scripts/deploy_check.py`. The /health route queries the database. Keep Render management credentials only in the MCP client's environment.

See `docs/` for product, architecture, security, privacy, integrations, implementation status, tests, and demo instructions. Create a strong random `APP_SECRET_KEY` for any shared environment. Secrets belong in the host's secure environment settings, never in frontend code.
