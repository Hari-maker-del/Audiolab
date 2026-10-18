# Audiolab — Neon Postgres setup

Audiolab's Neon configuration is intentionally scoped to **Postgres only**. It does not enable paid add-ons, GPUs, the AI Gateway, or other Neon services.

## Initialize the linked project

Run from the repository root in a terminal where you can sign in to Neon:

```powershell
npm i -g neon@latest
# If global installation fails:
npx neon@latest init -y --org-id org-sweet-pond-57819835 --project-id wandering-mouse-40880776 --branch production --services postgres
neon deploy
```

If a Neon command opens a browser, finish sign-in. If sign-in fails or times out, run `neon login` and retry. The CLI should write a local `.neon` context and pull `DATABASE_URL` into `.env.local` or `.env`.

Do not commit `.env`, `.env.local`, or any database connection string.

## Build and connectivity checks

```powershell
npm install
npm run build
npm run neon:smoke
```

The build command syntax-checks the JavaScript under `frontend/` and `api/`. The smoke test requires `DATABASE_URL` and executes a real `SELECT 1` against Neon.

For Vercel, set `DATABASE_URL` in Project Settings → Environment Variables. Keep it server-side only. The `/api/neon-health` endpoint reports database reachability without returning credentials.

## Schema

The initial schema is in `neon/migrations/001_cloud_workspace.sql`. Apply it only to the dedicated Audiolab database after confirming the CLI is linked to the intended project.

## Important boundaries

- Neon Postgres does not, by itself, provide email/password account flows or private audio object storage.
- The existing cloud UI currently calls Supabase Auth, Supabase Postgres tables, and Supabase Storage. It is **not yet switched to Neon** by adding this database connection alone.
- The Neon schema is metadata-only; no audio bytes are stored in Postgres.
- The initial migration must be applied after Neon setup. No production migration is automatically run by the Vercel health endpoint.
- Do not expose the database connection string to browser JavaScript.
- Remote AI inference is separate from the database and remains dependent on the selected inference provider's availability and limits.
