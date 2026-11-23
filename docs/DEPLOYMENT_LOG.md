# Deployment operations

## 2026-11-23

- Restored Render MCP OAuth using the registered Codex client. Credentials remain in the client's credential store.
- Verified Scorpion's's workspace and existing SCORPS-AI service srv-dc1s34ifngtc738gp1ag. Plan is free, branch deploy/render-free, public origin https://scorps-ai.onrender.com.
- Confirmed previous deployment dep-dc1vfsljbvbc73cl6r10 used fd62f2d and Python 3.12.16.
- Sanitized startup failure was PostgreSQL [connect] OperationalError, SQLSTATE unavailable, DNS resolution failed. Authentication, TLS and migration SQL had not been reached.
- Started one retry dep-dc228qqjnfac73a4ru1g to check whether the earlier DNS failure was transient. No infrastructure or billing changes.
- Pending inspection of the configured pooler hostname. MCP provides environment-variable updates but no environment-variable read or remote shell tool.

- Retry dep-dc228qqjnfac73a4ru1g failed with the same sanitized DNS error on fd62f2d. User confirmed the displayed pooler hostname matches Supabase.
- Added secret-free parsed-host validation and resolver recheck after DNS connection failure to distinguish malformed URI hosts, temporary resolver failures, missing DNS addresses, and intermittent resolution. No TLS or billing changes.
- Validation: 19 tests passed under Python 3.12 outside the sandbox; the sandbox run stalled at the asynchronous document test.
