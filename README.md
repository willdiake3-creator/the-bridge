# Passage API

FastAPI backend for the Passage platform, built directly against `schema.sql`.
The six frontend pages (`landing.html`, `dashboard.html`, `programs.html`,
`sop-drafting.html`, `referee-portal.html`, `staged-submission.html`) are now
wired to call this API directly instead of using hardcoded JS data — see
"Running the whole thing together" below.

## What's real here

- **Auth** — bcrypt password hashing, JWT access + refresh tokens (refresh
  lifetime extends when "remember me" is on), real Google ID-token
  verification via `google-auth`, and `PATCH /auth/me` for updating
  `fee_strategy` from the dashboard's tier selector.
- **Catalog** — `/programs` search and `/programs/{id}` detail (with
  requirements), backed by actual Postgres queries — field, level, region,
  fee status, free text — matching the filters in `programs.html`.
- **Applications** — the Kanban board's data, enriched with joined
  program/university names and fee info so the frontend never has to do a
  second round-trip per card, plus an event log per application (`/applications/events/recent`
  powers the dashboard's live activity bar).
- **Documents** — vault uploads (`POST /documents`, multipart), listing,
  and a placeholder GPA-conversion endpoint backing the dashboard's Vault
  tab and its conversion table.
- **Essays** — the intake → draft → student-edit → approve flow. The
  draft function (`app/routers/essays.py::_draft_sop`) is a placeholder
  for the real LLM call — swap it in without touching anything else.
- **Referees** — token-authenticated public upload endpoint (`referee-portal.html`
  reads the token straight from its own URL query string), no account
  needed on the referee's side.
- **Wallet + Kpay** — top-up creates a Kpay checkout session; the balance
  only moves once `/wallet/kpay-webhook` confirms the charge actually
  succeeded (never on the top-up request itself). Per-application fees
  are confirmed one at a time via `/wallet/fee/confirm` and debited from
  the pre-funded balance — nothing charges without that explicit call,
  wired into both the dashboard's Kanban cards and the staged-submission
  review flow.

## What's a placeholder

- The SOP draft is templated, not LLM-generated yet.
- File uploads (transcripts, referee letters) store a fake `vault://`
  URL instead of actually streaming to S3/GCS.
- Kpay's exact endpoint paths/auth header are **assumed**, not verified
  against a live account — see the comment at the top of
  `app/payments/kpay.py` for exactly what to double-check before going
  live. Everything else in the app only talks to the `PaymentProvider`
  interface in `app/payments/base.py`, so correcting Kpay's specifics is
  a one-file change.
- **Student profile fields are minimal** — only email/full name/proxy
  email/fee strategy exist. `staged-submission.html`'s "Personal
  information" section says so explicitly rather than faking a date of
  birth or passport number that isn't in the schema.
- **Essays aren't linked to a specific application yet** — there's no
  endpoint that sets `applications.essay_id`. The staged-submission page
  flags this in its Essay section instead of pretending it's wired.
- No RPA/portal-automation layer — that's the "staged submission,
  student clicks the real submit" flow, which doesn't need backend
  automation code, just the `/applications/{id}` and `/wallet/fee/confirm`
  endpoints already here.

## Setup

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in real values

# Create the database and apply the schema (schema.sql lives one level up,
# alongside the frontend files)
createdb passage
psql passage < ../schema.sql

# Seed the catalog with the same 50-field taxonomy the frontend uses
python -m scripts.seed

# Run it
uvicorn app.main:app --reload
```

API docs land at `http://localhost:8000/docs` (FastAPI's automatic Swagger UI).

## Running the whole thing together

The frontend files call `http://localhost:8000` by default (see the
`API_BASE` constant at the top of each `<script>` block). To run the full
stack locally:

1. Start the backend as above (`uvicorn app.main:app --reload`).
2. Set `FRONTEND_URL` in `.env` to wherever you're serving the HTML files
   from (CORS is locked to that origin) — e.g. `http://localhost:5500` if
   you serve them with `python -m http.server 5500` from the folder
   containing the `.html` files.
3. Open `landing.html` through that server (not via `file://` — `fetch()`
   calls and CORS both behave better served over http). Register or sign
   in; every page after that reads its auth token and calls the API for
   real.
4. Optional: set `window.PASSAGE_API_BASE = 'https://your-api'` and
   `window.PASSAGE_GOOGLE_CLIENT_ID = '...'` in a small `<script>` before
   each page's main script if you're not running on localhost:8000, or
   want real Google Sign-In.

Auth tokens are stored via a small `localStorage`-with-in-memory-fallback
wrapper in each page (`AuthStore`) — falls back gracefully if storage is
blocked, persists normally anywhere else.

## Not included yet

- Alembic migrations (schema.sql is the source of truth for now — add
  Alembic once the schema stabilizes and you need versioned changes).
- Rate limiting, request logging, structured error responses.
- The Document Ingestion (OCR) and Portal Automation pieces from the
  original architecture doc — those are separate services that read
  from / write to these same tables, not part of this API layer.
- Linking essays to applications, and richer student profile fields
  (DOB, passport, nationality) — both called out above since the
  frontend already has UI expecting them.

