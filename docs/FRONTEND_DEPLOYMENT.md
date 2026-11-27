# Streamlit frontend deployment

Use Streamlit Community Cloud with the existing GitHub repository; keep all database, provider and Supabase credentials exclusively in Render.

- Repository: teamscorpionsoff-ship-it/SCORPS-AI
- Branch: deploy/render-free
- Main file: frontend/Home.py
- Python: 3.12
- Advanced settings / Secrets: `API_BASE_URL = "https://scorps-ai.onrender.com"`

The frontend makes authenticated API calls from its Python server. Never put DATABASE_URL, SUPABASE_SECRET_KEY, APP_SECRET_KEY or provider keys in frontend secrets.

After deployment, record the actual HTTPS frontend origin and set Render FRONTEND_ORIGIN to that exact origin without a trailing slash. Verify registration, login, task creation/readback, sign-out, and document isolation using synthetic data. Test on desktop and mobile. AI remains demo until live-provider verification passes. A successful backend health check does not verify these frontend flows.
`nThe UI reads API_BASE_URL from environment variables or Streamlit secrets. Requests allow a 90-second response timeout for Render cold starts and show progress; mutation requests are never automatically retried.
