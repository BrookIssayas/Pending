# Pending

Automatically detects job application emails in a user's Gmail, tracks each
application's status (Applied → Interviewing → Rejected / Offer, or Ghosted
after 3 months of silence), and surfaces it in a dashboard — no manual
spreadsheet tracking required.

## Status

**Backend is fully functional.** Gmail ingestion, two-pass Gemini
classification, status tracking, and the API are all working end to end.

**Frontend is a prototype.** It's enough to log in and see your applications,
but it's not the real interface — a proper frontend is planned for later.

## How it works

1. A daily scheduled job (GitHub Actions) fetches each user's new Gmail
   messages since their last sync.
2. Emails are classified in two passes with Gemini: first to flag
   job-related emails and extract the company, then to resolve each one
   against the user's existing applications and decide the resulting status.
3. Results are written to Supabase (Postgres) — one row per application,
   plus a full event history per email processed.
4. The FastAPI backend exposes the current state over a REST API,
   authenticated via Supabase JWTs.
5. The frontend (prototype) reads that API and displays it.

## Tech stack

- **Backend**: FastAPI (Python), Supabase (Postgres + Auth), Gmail API,
  Gemini API
- **Frontend**: Next.js (App Router, TypeScript)
- **Scheduling**: GitHub Actions (daily cron)
- **Hosting**: Vercel (both frontend and backend, as separate projects)

## Backend

### Setup

```bash
cd backend
pip install -r requirements.txt
```

### Environment variables

```
GEMINI_API_KEY=INSERT_GEMINI_API_KEY
SUPABASE_URL=INSERT_SUPABASE_URL
SUPABASE_ANON_KEY=INSERT_SUPABASE_ANON_KEY
SUPABASE_ADMIN_KEY=INSERT_SUPABASE_ADMIN_KEY
SUPABASE_JWT_SECRET=INSERT_SUPABASE_JWT_SECRET
LOG_LEVEL=INSERT_LOG_LEVEL
CORS_ORIGINS=INSERT_CORS_ORIGINS
GOOGLE_CLIENT_ID=INSERT_GOOGLE_CLIENT_ID
GOOGLE_CLIENT_SECRET=INSERT_GOOGLE_CLIENT_SECRET
```

### Run locally

```bash
python -m uvicorn app.api.main:app --reload --port 8000 
```

### Deployed

`https://pending-backend-ten.vercel.app`

## Frontend (prototype)

### Setup

```bash
cd frontend
npm install
```

```
NEXT_PUBLIC_SUPABASE_URL=INSERT_NEXT_PUBLIC_SUPABASE_URL
NEXT_PUBLIC_SUPABASE_ANON_KEY=INSERT_NEXT_PUBLIC_SUPABASE_ANON_KEY
NEXT_PUBLIC_API_BASE_URL=INSERT_NEXT_PUBLIC_API_BASE_URL
```

### Run locally

```bash
npm run dev
```

### Deployed

`https://pending-plum.vercel.app`

## Daily sync

Runs automatically via GitHub Actions (`.github/workflows/daily-sync.yml`),
once per day. Can also be triggered manually from the repo's Actions tab.
