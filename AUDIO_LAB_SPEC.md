# Audio Lab (Web) — Product Specification

**Product goal:** Build a polished, responsive audio editor with a real AI voice-generation layer. Keep ordinary audio editing browser-first and free to run, and keep heavyweight AI inference in an explicitly configured local backend. Do not imply that AI works when the real model/backend is unavailable.

## 1. Product principles

- **Local-first and zero-cost by default:** browser editing must not require a paid service. Local AI inference runs on the user's computer. Static frontend hosting is optional; hosted inference is not assumed.
- **Real functionality only:** no fake model states, simulated generations, hardcoded audio, or browser speech synthesis presented as voice cloning. Clearly label unavailable or experimental features.
- **Consent-first voice features:** users must confirm that they own the reference voice or have permission to use it. Do not facilitate deceptive impersonation, fraud, harassment, or unauthorized cloning.
- **Accessible, responsive UX:** support desktop, tablet, and mobile layouts, keyboard use, visible focus states, labels, and understandable errors.
- **Keep existing Audiolab identity:** preserve the existing Turmeric × Malt visual direction and working project structure unless a change is needed for a verified feature.

## 2. Audio editor — browser engine

Use the Web Audio API and typed, testable TypeScript modules where the frontend stack supports them.

### Import and decode
- Drag-and-drop and file picker.
- Accept WAV, MP3, OGG, FLAC, and M4A only when the browser can decode the selected file; show a specific unsupported/corrupt-file message otherwise.
- Do not promise universal browser support for every codec.
- Validate MIME/type, file size, duration, sample rate, and channel count; warn before loading large files and handle memory failures gracefully.
- Do not upload user audio for normal browser editing.

### Waveform and transport
- Draw a waveform on Canvas using downsampled PCM data, not every raw sample.
- Provide play/pause, stop, current-time/duration display, seek, selection loop, zoom, and draggable trim/selection handles.
- Keep time values precise and clamp them to valid buffer bounds.
- Support undo/redo for edit operations.

### Non-destructive edits and effects
Implement real preview and export for:
- Trim/cut using a selected start/end time.
- Fade-in and fade-out.
- Gain/volume boost and reduction with a configurable soft limiter or clipping warning.
- Playback speed changes.
- Reverse playback and reverse export.
- Speed changes that preserve pitch only if a genuine pitch-preserving implementation is present; otherwise label the simple resampling behavior accurately.
- Optional effects (pitch/key change, reverb, bass boost, stereo widening/“8D-like” effect) must be individually labelled experimental until implemented and tested. Avoid exaggerated claims.

Keep the source buffer unchanged and represent edits as an operation state/history so users can undo, redo, compare, and export.

## 3. Export and format handling

- WAV PCM is the reliable baseline export. Implement and test a correct WAV header, sample format, channel layout, sample rate, clipping behavior, and duration.
- Offer MP3, OGG, or FLAC only when the corresponding encoder is bundled and verified. A browser accepting a file does not mean the app can encode it.
- If using ffmpeg.wasm, lazy-load it, show progress, handle cancellation/errors, and warn about its download and memory cost. Prefer a simple WAV path first.
- Export dialog: selected range or full audio, output format, quality/bitrate when supported, output filename, progress, cancel where possible, and download.
- Verify exported files can be decoded again and their duration/sample metadata match expectations within reasonable tolerances.

## 4. AI voice features — separate from browser DSP

Treat these as distinct capabilities. Do not present one as another.

### A. Reference-conditioned text-to-speech / voice cloning
- User records or uploads a clean reference clip and supplies its exact transcript.
- Confirm rights/consent before submission.
- Validate duration, format, level, clipping, silence, and transcript presence; offer useful guidance rather than silently altering the input.
- User enters text and chooses a language only from languages the installed model actually supports.
- Run a real, documented pretrained model through a genuine backend. Audiolab's current target is AI4Bharat IndicF5 through the local Python/FastAPI backend; do not substitute simulated speech, browser speech synthesis, placeholder WAVs, or a different model without clearly documenting the change.
- Return a real audio file with generation state, errors, playback, download, and saved history when storage is configured.
- The UI must show whether the model is loaded, loading, unavailable, or failed based on actual backend health—not a static green badge.

### B. Voice conversion
- This is not the same as TTS. It accepts source speech and changes vocal timbre while trying to preserve timing/intonation.
- Do not advertise it as working until a compatible, licensed conversion model and a real backend endpoint are implemented and tested.
- If unavailable, show it as planned/disabled with a truthful explanation.

### C. In-place speech editing
- Word/phoneme-level replacement while preserving voice and prosody is advanced and out of scope until a real supported pipeline exists.
- Never fake this with ordinary text-to-speech or simple audio splicing.

### Inference architecture
- Frontend: static web UI can be deployed separately.
- Local backend: Python + FastAPI + PyTorch with a real pretrained model; use CUDA when correctly available and fall back to CPU when supported. Display device/runtime information honestly.
- The backend may run at `http://127.0.0.1:8000` on the user's machine. Document that a public static website cannot directly access a visitor's local machine unless that visitor runs the backend and the browser can reach it.
- Never put `HF_TOKEN`, Supabase service-role keys, or any private secret in frontend code or Git.
- Do not install PyTorch or the AI model in the static Vercel frontend build.
- No paid GPU/server/object store is required by the default setup. Explain that public, always-on hosted AI inference usually has costs or restrictive quotas; do not claim unlimited hosted inference is free.
- Use temporary processing files and clean them up safely. Add bounded input sizes/timeouts and concurrency limits.

## 5. Backend API contract

Keep endpoints consistent with the existing backend where practical. Document request fields, response types, errors, and size limits. Suggested contracts:

- `GET /health`: API status, model status, supported languages, runtime/device; never report the model ready unless it really is.
- `POST /analyze`: multipart audio upload; return duration, sample rate, channels, peak/clipping indicators, silence/level checks, and actionable feedback.
- `POST /generate`: text, language, exact reference transcript, reference audio, and a consent confirmation; return real WAV audio on success or a structured error.
- `GET /voices` and `/voices/{id}`: only if voice profiles are truly persisted. Never return demo records as user data.
- `GET /generations` and `/generations/{id}`: only for real saved jobs; explain whether history is browser-local, local-backend, or database-backed.
- `GET /models`: actual configured model names, licenses, load status, supported capabilities, and device/runtime details.
- `GET/PUT /settings`: only settings the implementation actually supports; do not expose secrets in responses.
- Add request validation, safe filenames, CORS limited to documented origins, sensible timeouts, upload limits, and clear HTTP status codes. Do not log voice/audio content or secrets.

Do not add a database just for appearances. If persistent cloud history/storage is added later, document retention, access rules, deletion, and required setup. Browser-local history is acceptable for the free local-first baseline.

## 6. Responsible use, privacy, and licensing

- Consent checkbox before voice cloning: “I confirm I own this voice or have permission to use it.”
- Explain where the reference audio and generated output are processed and stored.
- Provide delete controls for local history/files where applicable.
- Do not upload reference audio unless the user has clearly chosen a feature that requires it and the destination is explained.
- Never claim to be legally compliant without review. Add Terms, Privacy, FAQ, and About pages that accurately describe actual behavior.
- Maintain a model/third-party dependency register with project URL, version/revision, license, attribution, and commercial-use limitations. Verify the current model license before any commercial use; do not assume all “open-source” models allow commercial use.
- Add an AI-generated audio disclosure/metadata option where feasible; never market an output as a genuine recording of a real person.
- Avoid retaining abuse-related content unnecessarily. Any public deployment should add authentication, rate limits, reporting, and abuse monitoring appropriate to its risk.

## 7. UI and trust pages

Preserve Audiolab's visual identity and build clear pages or views for:
- Studio / editor
- Import and waveform
- Edit controls and effects
- Export
- Voice cloning / generation
- Voice library (only if functional)
- History (clearly label local vs server persistence)
- Models / runtime status
- Settings
- About, Privacy, Terms, FAQ, and guides

Use clear empty, loading, progress, success, unavailable, and error states. No dead buttons: every enabled control must perform its stated action. Disabled/planned features must be labelled.

## 8. Suggested implementation phases

1. **Audit existing code:** preserve working behavior, map routes/components/endpoints, list placeholders, and identify current stack before editing.
2. **Browser editor MVP:** import/decode, waveform, playback, selection, trim, gain, fades, reverse, undo/redo, and tested WAV export.
3. **Real local AI TTS:** wire the UI to the existing local FastAPI/IndicF5 pipeline, display truthful health state, generate/play/download real WAV, and handle errors.
4. **Persistence and safety:** real history/voice profiles only where implemented; consent, deletion, privacy explanations, upload limits, and abuse safeguards.
5. **Additional formats/effects:** ship encoder-backed exports and DSP features incrementally with tests.
6. **Voice conversion / advanced speech editing:** only after choosing a compatible model, verifying licensing, and implementing real inference.
7. **Deployment and documentation:** keep Vercel/static hosting frontend-only; document local backend startup, environment variables, CUDA/CPU behavior, troubleshooting, and what will not work without the local backend.

## 9. Definition of done / acceptance tests

### Browser audio editor
- [ ] Import a valid WAV and at least one supported compressed format; reject unsupported/corrupt files clearly.
- [ ] Waveform, playback, seeking, selection, and loop reflect the loaded buffer correctly.
- [ ] Trim, fades, gain, speed, and reverse change the actual preview/exported audio.
- [ ] Undo/redo restores prior edit states accurately.
- [ ] WAV export reopens in the app and has the expected duration and audible content.
- [ ] Clipping and large-file warnings are actionable.
- [ ] UI works on a narrow mobile viewport and desktop, with keyboard-visible focus.

### Real AI
- [ ] When the backend is off, UI says unavailable and explains how to start it; it never reports success.
- [ ] When the real IndicF5 model is unavailable or fails to load, the error is visible and no fake audio is returned.
- [ ] With a valid reference clip, exact transcript, consent confirmation, and supported text/language, `/generate` calls the actual model and returns a decodable, non-empty WAV.
- [ ] Generated audio can be played and downloaded; history is saved only according to the documented persistence mode.
- [ ] The status/device/language labels come from actual backend capabilities.
- [ ] No tokens/secrets are present in frontend bundles, logs, or repository files.

### Engineering quality
- [ ] Unit tests cover audio buffer edits, WAV encoding, request validation, and state transitions.
- [ ] Manual/API test instructions are in the repository.
- [ ] Build, lint, and tests are run where available; report exact results and unresolved failures honestly.
- [ ] README, local startup instructions, privacy statements, model licensing notes, and deployment instructions match the real implementation.

## 10. Agent implementation rules

When implementing this specification:
1. Audit before changing files. Preserve existing functioning behavior and design.
2. Make real, testable changes; do not stop at mockups or a checklist.
3. Work incrementally and run the relevant checks after each phase.
4. Do not mark a feature complete until acceptance tests pass.
5. Keep a clear `IMPLEMENTATION_STATUS.md` with **Implemented / Tested / Partial / Planned / Blocked** status and the evidence for each claim.
6. Never claim that the whole product is complete if a backend, model, encoder, secret, license, or external service is missing.
