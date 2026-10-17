# Audiolab cloud foundation

This milestone adds the cloud integration layer while preserving the existing Vercel frontend and `/studio.html`.

## Architecture

- **Web:** static frontend hosted on Vercel.
- **Identity:** Supabase Auth email/password with email confirmation and password reset.
- **Database:** `audiolab_projects`, `audiolab_audio_assets`, and `audiolab_processing_jobs`.
- **Audio storage:** private Supabase Storage bucket `audiolab-audio`; browser receives short-lived signed URLs only after authenticated access.
- **Inference:** the existing online Studio uses the hosted AI4Bharat IndicF5 Hugging Face Space from the browser when not running on localhost. Its availability, queue time and free usage are provider-controlled. Local FastAPI remains available for development/fallback and is not made public by this change.

## Safe setup (do not use a shared production database blindly)

1. Create or select a **dedicated Audiolab Supabase project** on a free plan. Creating a project can affect organization billing; do not upgrade or enable paid compute/GPU without explicit approval.
2. In Supabase SQL Editor, apply `supabase/migrations/20261017000000_audiolab_cloud.sql`.
3. In Supabase API settings, ensure the Data API exposes the three `public.audiolab_*` tables. The migration grants the browser's `authenticated` role only the operations used by the app. All three tables have RLS enabled and ownership policies.
4. In Supabase Auth settings, configure the site's Site URL and redirect URLs for your Vercel domain and local development URL. Email confirmation should remain enabled for a public multi-user app.
5. Set `supabaseUrl` and the **publishable key (or legacy anon key)** in `frontend/cloud-config.js`. This configuration is intentionally public. Never add a service-role/secret key to this file or any browser JavaScript.
6. Deploy the repository to Vercel, then test sign-up, email verification, sign-in, sign-out, password reset, project creation, audio upload, playback from a second browser/device and per-user isolation.

## What this milestone supports

- Sign-up/sign-in/sign-out and password-reset calls to real Supabase Auth when configured.
- Cloud project metadata, per-user RLS, private audio upload and short-lived signed audio URLs.
- Project creation from generated Studio audio when the user is signed in and cloud config is active.
- Cloud project editor page with notes, audio playback, upload and deletion.

## Honest limitations

- Cloud mode is **not live until a dedicated Supabase project is configured, the migration is applied, Auth redirect settings are configured, and Vercel is deployed**.
- The current public IndicF5 Space is a hosted inference endpoint, not a dedicated Audiolab worker. Free capacity and uptime are not guaranteed; no paid worker has been provisioned.
- `audiolab_processing_jobs` is a secure schema foundation for a future authenticated worker. A queue consumer that updates job status and stores results still needs to be deployed before we advertise durable background jobs for all AI tools.
- Existing browser IndexedDB projects are not automatically migrated to cloud. They remain on the original device until the user uploads/saves them to a cloud project.
- Supabase free-tier quotas and policies can change. Review current quotas before inviting many users or uploading large libraries.

## Security notes

- The storage bucket is private. Object paths begin with the authenticated user's UUID, and storage policies enforce that boundary.
- Database RLS checks `auth.uid()` against `owner_id`. Browser code uses only the publishable/anon key.
- The 100 MB per-file client and bucket limits are guardrails, not a substitute for provider quotas or server-side abuse controls.
- Never expose the local FastAPI server to the public internet without authenticated API access and deployment hardening.
