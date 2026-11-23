# Integrations

## LLM

Default provider is `demo`. To enable Groq, set `LLM_PROVIDER=groq`, `GROQ_API_KEY`, and `GROQ_MODEL_ID` in the backend environment. Gemini settings exist but no live adapter is implemented. Do not enable billing; free access and model quotas must be checked with the provider at setup time. The application currently does not make provider requests.

## Google

Google Gmail, Calendar, and Drive OAuth connectors, scopes, secure refresh-token storage, and redirect handling are not implemented. No Google data is accessed. A production integration needs a Google Cloud OAuth consent setup and exact production redirect URI before it can be considered available.

## Search and storage

Live search is not implemented. The Source Reader can fetch public HTTPS pages and extract text, but it is not a search engine. Production stores original documents in private Supabase Storage. Local development uses UPLOAD_DIR. Existing text-only records have no original attachment. Extracted document text uses the configured SQL database.

## Free deployment evaluation (checked 2026-11-23)

Streamlit Community Cloud documents free deployment. Render documents free web services, but services sleep after 15 minutes idle and the filesystem is ephemeral. Its free PostgreSQL expires after 30 days, so it does not satisfy durable production database requirements. Supabase's current Free plan includes PostgreSQL (500 MB) and file storage (1 GB), but pauses inactive projects after seven days and does not include automatic backups. These are prototype tiers, not guaranteed production availability. The backend supports PostgreSQL. Validate the hosted database and its credentials before deployment.
