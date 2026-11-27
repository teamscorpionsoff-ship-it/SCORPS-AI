# Integrations

## LLM

Default provider is `demo`. To enable Groq, set `LLM_PROVIDER=groq`, `GROQ_API_KEY`, and `GROQ_MODEL_ID` in the backend environment. Gemini settings exist but no live adapter is implemented. Do not enable billing; free access and model quotas must be checked with the provider at setup time. The application currently does not make provider requests.

## Google

Google Gmail, Calendar, and Drive OAuth connectors, scopes, secure refresh-token storage, and redirect handling are not implemented. No Google data is accessed. A production integration needs a Google Cloud OAuth consent setup and exact production redirect URI before it can be considered available.

## Search and storage

Live search is not implemented. The Source Reader can fetch public HTTPS pages and extract text, but it is not a search engine. Production stores original documents in private Supabase Storage. Local development uses UPLOAD_DIR. Existing text-only records have no original attachment. Extracted document text uses the configured SQL database.

## Free deployment evaluation (checked 2026-11-23)

Streamlit Community Cloud documents free deployment. Render documents free web services, but services sleep after 15 minutes idle and the filesystem is ephemeral. Its free PostgreSQL expires after 30 days, so it does not satisfy durable production database requirements. Supabase's current Free plan includes PostgreSQL (500 MB) and file storage (1 GB), but pauses inactive projects after seven days and does not include automatic backups. These are prototype tiers, not guaranteed production availability. The backend supports PostgreSQL. Validate the hosted database and its credentials before deployment.


## Live Groq chat
Set LLM_PROVIDER=groq, GROQ_MODEL_ID to a currently supported model, and GROQ_API_KEY only on the backend. GROQ_FREE_TIER_CONFIRMED=true requires the operator to verify the account is Free with no usage-based billing. Calls have a 45-second response timeout, at most 1000 completion tokens, and no automatic retries or provider switching. Only the current user message and up to six recent messages (3000 characters each) are sent. Stored memories and documents are not sent. Live chat cannot execute tasks or external tools; use the Tasks UI for writes. Provider failures return sanitized 503 errors instead of fabricated demo answers.

Run python -m scripts.evaluate_hosted_llm for a randomized 5–20-case evaluation (up to the available bank size). It records exact model, seed, case IDs, category coverage, observable outputs, deterministic JSON/instruction results and pending rubric review. No real user data is used. Tool-calling acceptance remains inconclusive because the chat adapter executes no tools.
