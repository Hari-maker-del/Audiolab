# Audiolab MVP local workflows

## Open the app

- Deployed frontend: use the deployed Vercel URL and navigate to /projects.
- Windows local setup: run START-AUDIOLAB.bat, then open http://127.0.0.1:5500/app-pages.html#/dashboard.
- Existing AI workspace: http://127.0.0.1:5500/studio.html.

The app-page shell supports hash-based navigation when served by the simple local Python server. Vercel uses clean paths and rewrites them to app-pages.html.

## Project workflow

1. Open New project.
2. Enter a project name and select a workflow.
3. Optionally select an audio file up to 100 MB.
4. Create the project. Project metadata and the source audio blob are stored in IndexedDB in the current browser profile.
5. Open the editor to arrange multiple audio tracks. Set each track's start offset, level and mute state; play the timeline mix; save the timeline; add or remove tracks; and update project notes.
6. In the existing Studio, generate speech and choose **Save to Project**. Audiolab stores the generated WAV and creates a project with a persistent audio track in the same browser's IndexedDB.
7. Export the original file, convert a browser-decodable source to PCM 16-bit WAV, or render the saved timeline as a mixed WAV using browser OfflineAudioContext.
8. Revisit Export history to download a stored export again or remove the local history entry.

## Storage and compatibility

- Data is local to the current browser profile and origin; it is not cloud-synced and will not automatically appear on another device.
- Browser storage can be cleared by the user or browser and is not a backup.
- Audio upload is capped at 100 MB per file. Browser decode memory requirements can be higher than the source file size.
- WAV conversion requires Web Audio API support and a source format that the browser can decode. The original-file export does not transcode audio.
- The project editor currently provides source playback, project metadata, notes, file replacement and export. It is not yet a multitrack DAW with persisted cut/trim/effect automation.
- The jobs page shows local export history, not fabricated server-side jobs. Actual AI generation/transcription remains in the existing local Studio and requires a running FastAPI backend and configured models.

## Not connected yet

Authentication, password reset emails, cloud project sync, team collaboration, payment processing, API-key issuance and admin privileges are not enabled. Do not treat their route placeholders as production functionality. Admin and billing actions require server-side authentication/authorization and a real provider before launch.

## Safety

The frontend checks the local API only when a user explicitly requests it and targets 127.0.0.1:8000. Do not expose an unauthenticated local inference backend to the public internet.