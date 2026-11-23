# Security

Secrets are read from environment settings, `.env` is ignored, and only variable names appear in `.env.example`. Passwords are salted PBKDF2 hashes. Sessions are HMAC-signed and expire after one day. API resources scope reads and writes by user ID. Errors avoid configuration values. Google OAuth and encrypted refresh-token storage are not implemented; Google is reported disconnected. Use a random `APP_SECRET_KEY` of at least 32 characters in production. Do not expose the demo signing fallback on a public deployment.
