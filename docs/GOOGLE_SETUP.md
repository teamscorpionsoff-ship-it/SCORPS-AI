# Connect Gmail and Google Calendar

The connection code is implemented; real Google authorization must be verified with an operator-owned OAuth client. Existing workspace, AI, drafts and research continue working without Google credentials. No Google service is claimed live until the actual consent and API flows pass.

## Google Cloud setup

1. Open https://console.cloud.google.com/ and select an existing suitable project or create one without enabling billing. Keep Workspace API usage on the no-cost Standard Tier; do not enroll in Scaled Tier, link billing, request paid quota or enable paid products. If the console requires billing, stop and reassess.
2. Under APIs & Services → Library, enable Gmail API and Google Calendar API.
3. Under Google Auth Platform (or OAuth consent screen), configure the app name Scorpions AI, your support email and developer contact. Choose External / Testing for the hackathon, and add the Google accounts that will actually test the app under Audience → Test users. Keep publishing/verification status honest. Google may require verification and verified domains before public access to sensitive scopes; do not bypass warnings or claim unrestricted public authorization.
4. Under Clients / Credentials, create an OAuth client of type Web application. Add this exact authorized redirect URI:

   `https://scorps-ai.onrender.com/api/integrations/google/callback`

   The Streamlit URL is not the callback. No authorized JavaScript origin is required because code exchange is server-side. Do not choose an installed/desktop application client.
5. In Data Access, configure only the implemented scopes:

   - `https://www.googleapis.com/auth/gmail.send` — send reviewed emails; no inbox reading.
   - `https://www.googleapis.com/auth/calendar.events.owned.readonly` — read primary owned calendar events; no writes.

   Each connection requests only its own service scope. Drive and calendar-write scopes are deliberately absent because those actions are not implemented in this stage.
6. Enter the OAuth client ID and secret only through Render's secure Environment interface. Do not paste client secrets into chat, frontend settings, source files, screenshots or documentation.

## Render variables

| Variable | Value/source |
| --- | --- |
| GOOGLE_CLIENT_ID | Web application client ID from Google Cloud |
| GOOGLE_CLIENT_SECRET | Matching client secret from Google Cloud |
| GOOGLE_REDIRECT_URI | Exact HTTPS callback above |
| TOKEN_ENCRYPTION_KEY | A separately generated Fernet key (32 random bytes, URL-safe base64 encoded) |

Generate TOKEN_ENCRYPTION_KEY with the local masked helper `python -m scripts.generate_token_key`. It displays no key text or logs and copies only after the operator clicks Copy. Store the key securely and keep it stable; replacing/losing it makes existing token ciphertext unreadable. Never reuse the database password or APP_SECRET_KEY.

For development, the matching registered redirect is `http://127.0.0.1:8000/api/integrations/google/callback`. All four values are required before Connect buttons appear. Missing optional configuration does not disable the rest of the application.

## User flow and verification

1. Sign into Scorpions AI and open Email & Calendar.
2. Choose Connect Gmail sending or Connect Calendar reading, then Continue securely with Google. On the backend landing page, press Continue to Google. Opening or previewing that landing link does not consume the connection; only the explicit POST button binds the browser and starts authorization. Complete Google's authorization yourself. Do not send your Google password or connection code to anyone.
3. The callback displays a one-time 16-character code. Return to the exact signed-in workspace that started the connection, paste the code into its masked connection field and confirm. Consent alone does not activate a connection. This additional step binds Google's consent to the intended application account across Streamlit/backend domains.
4. Calendar: click Read next seven days; verify only your primary calendar data appears. No calendar is changed.
5. Gmail: save a synthetic draft addressed to an email account you own. Review the exact recipient, subject and body, check the explicit approval box and click Send approved email. Verify receipt and Sent mail. Do not test against other people without permission.
6. Verify a second Scorpions account cannot see the connection, tokens or approvals. Disconnect each service and verify access is removed locally. To revoke Google's grant as well, remove Scorpions AI under https://myaccount.google.com/connections . Local disconnect does not claim provider-side revocation.

## Security and operational behavior

- PKCE S256, cryptographically random single-use state, ten-minute browser binding via Secure/HttpOnly/SameSite=Lax cookie in production, and final authenticated confirmation. Confirmation expires after fifteen minutes from flow creation and locks after five bad attempts.
- Access/refresh tokens and pending exchanges are Fernet-encrypted in PostgreSQL. Refresh occurs on use when expiry is near; tokens never go to frontend code, API responses, AI prompts or application logs.
- Uvicorn access logging is disabled because OAuth callback query strings contain transient authorization codes. Hosting/proxy request-log retention must also be reviewed before broad public OAuth rollout.
- Email approval uses an immutable snapshot, claimed once before sending. Failures and timeouts cannot trigger automatic duplicate sends. Unknown outcomes require checking Sent mail before preparing a new send. Generic pending-approval buttons cannot authorize Gmail sends.
- External Testing refresh tokens commonly expire after seven days. Reconnection can be necessary; public production access may require Google's verification. See https://developers.google.com/identity/protocols/oauth2 and https://developers.google.com/identity/protocols/oauth2/web-server .
- Current Google Workspace no-cost Standard Tier and quota/billing policy: https://developers.google.com/workspace/guides/quota-overview . Verify these rules again before changing hosting/account plans.

## Verification status

Automated tests use synthetic tokens and mocked Google endpoints. They validate OAuth state/cookie/expiry/replay, account isolation, encrypted storage, refresh preservation, single-use email snapshots, timeout handling and read-only calendar access. They do not establish actual Google authorization, delivery or Calendar access. Record live results only after operator setup and user browser consent are completed.
