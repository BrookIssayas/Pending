# TBD — status board

Next.js frontend for the job application tracker. Shows every detected
application, filterable by status, with an animated split-flap status
indicator.

## Setup

```bash
npm install
cp .env.local.example .env.local
```

Fill in `.env.local`:

- `NEXT_PUBLIC_SUPABASE_URL` / `NEXT_PUBLIC_SUPABASE_ANON_KEY` — from your
  Supabase project's API settings (the **anon** public key, not the service
  role key).
- `API_BASE_URL` — your FastAPI backend's base URL, including the
  `/api/v1` prefix (e.g. `http://localhost:8000/api/v1`).

```bash
npm run dev
```

Visit `http://localhost:3000`.

## How auth works

Sign-in uses Supabase's Google OAuth provider directly (`supabase.auth.signInWithOAuth`).
This establishes a Supabase session for identity — it's separate from
whatever flow your backend already uses to obtain Gmail read-access tokens
(the `user_provider_tokens` table). If those are two different OAuth grants
in your backend today, a user may need to complete both once: this sign-in
for app access, and your existing Gmail-connect flow for the pipeline to
read their inbox.

Every request to `/applications` sends the Supabase session's
`access_token` as a `Bearer` token. Your backend's `get_current_user`
dependency validates it and returns the `user_id`, exactly as already
wired up in Phase 5.

## Backend CORS

Confirm your FastAPI app's CORS middleware allows `http://localhost:3000`
as an origin during development, and your deployed frontend's origin in
production — otherwise the browser will block the `/applications` request
even with a valid token.

## Notes

- No write operations — this reads `GET /applications` only, matching the
  backend's read-only route surface from Phase 5.
- No detail/click-through view yet — that's deferred, per Phase 5 scope.
- Google Fonts (Space Mono, IBM Plex Sans) are fetched at build time via
  `next/font/google`, which requires network access during `next build`.
