# Test plan and verification

Run `python -m pytest`. Current automated tests cover deterministic plan ordering and unknown/oversized duration behavior. `python scripts/deploy_check.py` probes health and config endpoints when the API is running. `python scripts/evaluate_llm.py` selects a randomized 5–20-case synthetic sample and writes a BLOCKED report unless a live evaluation adapter is available; a mock is never reported as a live pass.

Authentication, user isolation, frontend interaction, CORS, external providers, storage persistence across restarts, and randomized live model evaluation are not covered by the current small suite. Live model evaluation requires a real configured provider and must select 5–20 seeded test-bank cases; no model is declared accepted in demo mode.
