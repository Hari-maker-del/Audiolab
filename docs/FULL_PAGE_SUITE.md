# Audiolab full page suite

This branch adds route coverage and responsive page foundations for the supplied sitemap. It distinguishes page availability from real backend integrations.

## Scope
- Public marketing, help and legal routes
- Signup/login/reset/verify/onboarding route foundations
- Dashboard, projects, new project and editor route foundations
- AI tool, transcript, library, export and job route foundations
- Workspace, sharing, review, versions and notifications route foundations
- Profile, security, billing, usage, API keys and account route foundations
- Admin and system/error route foundations

## Boundaries
- Existing local Studio remains at `/studio.html` and is not replaced.
- New project metadata is stored in browser localStorage only.
- Authentication, payment, collaboration, admin privileges, cloud storage and API-key management are not working until integrated with real providers and tested.
- AI tool pages do not claim model readiness or successful inference.
- Vercel frontend routing is separate from the Windows loopback FastAPI backend. No local backend is exposed publicly.
- Legal content is starter copy and requires review before launch.

## Completion sequence
1. Route coverage and responsive shell.
2. Persistent project model, import/upload, editor state, exports and job status.
3. Real authentication, per-user database and storage.
4. AI workflows connected to tested backend capabilities.
5. Collaboration, billing, admin RBAC, security, accessibility and end-to-end tests.
