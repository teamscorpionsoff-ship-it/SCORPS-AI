# Architecture

Streamlit (`frontend/Home.py`) is the browser UI and communicates with FastAPI over authenticated bearer sessions. FastAPI routes call small local services and the SQLite/PostgreSQL persistence adapter (`app/db.py`). Passwords use PBKDF2 and sessions use signed, expiring tokens. Every private query includes the authenticated user ID.

The demo assistant runs deterministic local intents. Planning is deterministic and labels missing task durations as tentative. Documents are extracted then stored in the user's database records. Email drafts and approval records remain local. External actions are not executed. Provider abstractions and OAuth token storage/refresh remain future work.
