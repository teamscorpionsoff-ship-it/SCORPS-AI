# Hosted acceptance audit

Tested 2026-11-27 against the existing Render backend and Streamlit frontend using synthetic accounts and data.

## Verified

- Public production health, anonymous denial, registration, login and incorrect-password rejection.
- Task creation/readback/deletion, cross-user list/delete isolation, planning, and rejection of invalid task updates after the fix.
- Memory lifecycle and isolation.
- Draft lifecycle and isolation on the first run. A create request failed during the second run while deployment was changing; a subsequent isolated create/readback/delete test passed with HTTP 200.
- Private Supabase document upload, exact original download, unauthorized download denial, deletion and unsupported-file rejection.
- Demo chat, unsafe research URL rejection through per-source errors, integration status, approval isolation/decision/replay denial.
- CORS: exact frontend origin allowed (200), unrelated origin rejected (400).
- Public browser: synthetic registration, login after reload, updated overview and empty planner success. All nine workspace pages also passed Streamlit AppTest with mocked API responses.

## Corrections

- Shared create/update validation for task priority, status, positive duration and ISO date.
- Planner starts at the supplied current time and respects total planning-window limits.
- Removed Streamlit inline expression rendering that exposed DeltaGenerator documentation and crashed the empty planner.
- Preserve visible errors for failed task/memory/upload saves; draft success only follows successful API response.
- Added original document download and deletion controls; corrected misleading hosted/local wording.
- Restored UTF-8 characters after an encoding regression found during public browser checks.

## Results and limits

49 local tests passed. The last hosted audit recorded 28 PASS and one draft-create FAIL, followed by the successful isolated draft retest described above. These are distinct results, not a claim that every request succeeded. Synthetic test objects were cleaned through their normal APIs; synthetic account records, audit chat messages and rejected approvals remain because no account-deletion API exists. No real user records were modified.

AI uses deterministic demo logic. Groq/live search execution and Google OAuth are not implemented/verified end-to-end; having a key configured does not enable these capabilities. Randomized evaluation selected 10 cases (seed 3230192215) and was BLOCKED without executing a live model. Persistent browser login across reload is not implemented: Streamlit session state requires signing in again. Restart-level database persistence, mobile device coverage, email delivery, calendar writes and Google document integrations were not claimed as tested. This audit is not an exhaustive security assessment.

Frontend: https://scorps-ai-jnlhdjfokp7ttjlbspes5k.streamlit.app/

Backend: https://scorps-ai.onrender.com
