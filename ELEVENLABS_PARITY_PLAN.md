# Audiolab — 12-Capability Audio Platform Roadmap

Last updated: 2026-10-16

## Goal

Evolve Audiolab into a trustworthy, Indian-language-first AI audio studio with capabilities comparable in scope to a modern commercial voice platform, while preserving the Turmeric × Malt visual identity and the local-first, zero-cost-by-default architecture.

**Important:** a feature is not complete merely because a screen exists. Every capability must call a real implementation, report unavailable dependencies honestly, and pass an end-to-end test before being marked verified.

## Architecture constraints

- Keep the Vercel deployment static/frontend-only. Do not deploy PyTorch, IndicF5, or other heavyweight inference dependencies to Vercel.
- Keep local inference in the Windows FastAPI backend. Use CUDA when genuinely available and CPU fallback when supported.
- Preserve the existing IndicF5 TTS and OpenVoice voice-conversion paths; do not replace them with browser speech synthesis or fabricated audio.
- Keep user audio private by default. Cloud processing/storage must be opt-in and must disclose the provider and data flow.
- No secrets or model weights in Git. API keys belong in local environment variables or a properly secured server environment.
- Free/local implementations are preferred. External APIs (including commercial voice, dubbing, transcription, agent, and music services) must be optional adapters with explicit quota/cost warnings. Do not promise all 12 capabilities are unlimited or hosted for free.
- Obtain confirmation that the user owns or has permission to use a voice reference. Never facilitate deceptive impersonation.

## The 12 capabilities

| # | Capability | Audiolab implementation target | Runtime truth requirement |
|---|---|---|---|
| 1 | Text-to-Speech | IndicF5-based reference-conditioned TTS with language-aware UI, transcript, generation progress, playback, download, and history | Generate a real WAV through the loaded model; otherwise show the exact backend/model error |
| 2 | Voice Cloning | Voice profile library with user-provided reference audio, exact transcript, consent, quality analysis, and reuse in TTS | Distinguish reference-conditioned synthesis from a separately trained persistent voice clone |
| 3 | Voice Library & Design | Browse saved voices, create/rename/delete profiles; define designed voice presets only where a real supported model exists | Never label a text preset as an actual cloned/generated voice |
| 4 | Multilingual Speech | Show only languages supported by the active model; begin with verified IndicF5 language support and expand only after tests | Do not claim language support just because a language appears in a dropdown |
| 5 | Sound Effects | Sound-effect generation adapter with prompt, duration, preview, download, and history | If no real local model/provider is configured, mark unavailable rather than synthesizing a placeholder |
| 6 | Dubbing & Localization | Upload source audio/video, transcribe, translate, synthesize/dub, and align outputs through a real pipeline | Label translation, voice matching, and timing limits; external providers require opt-in |
| 7 | Speech-to-Text | Real transcription adapter; local/offline option where feasible, with timestamps/speaker labels only if supported | No fake transcript or speaker labels |
| 8 | Conversational AI Voice Agents | Voice conversation workspace connecting speech recognition, an explicitly configured LLM, and speech output | Clearly identify required model/provider keys and possible cost; never silently send audio to a cloud |
| 9 | AI Music Generation | Prompt-based music generation adapter with duration/style controls and downloadable output | Requires a compatible real model or provider; disclose license, resource, and cost limitations |
| 10 | Voice Changer / Isolation | Keep OpenVoice conversion as a separate path; add genuine source separation/noise isolation only with a compatible implementation | Do not confuse TTS with conversion or simple noise reduction with source separation |
| 11 | Audio Studio & Production | Extend existing editor: waveform, transport, trim, fades, gain, speed, reverse, effects, mixing, export | Each operation must actually alter audio and exports must be valid and playable |
| 12 | API & Developer Integration | Documented FastAPI endpoints, validation, OpenAPI docs, health/model status, examples, error contracts, and local setup | API status must reflect real dependencies; protect endpoints before any public exposure |

## Delivery phases

### Phase 0 — Audit and contracts
- Audit current frontend routes, scripts, FastAPI endpoints, model status, and tests.
- Produce a feature-by-feature current state table: implemented, partially implemented, planned, or runtime-verified.
- Define consistent API request/response/error formats and a shared capability-status response.

### Phase 1 — Core audio platform
- Verify and harden existing IndicF5 generation, reference analysis, voice profiles, history, OpenVoice conversion, and audio editor.
- Ensure UI status comes from backend health and each result is a real audio artifact.
- Add end-to-end checks for upload → generation/conversion/edit → playback/download.

### Phase 2 — Local speech foundation
- Add real speech-to-text and multilingual capability detection using an installable local model where practical.
- Add transcript editing, language metadata, and reusable voice profiles.
- Document Windows setup, disk/RAM/GPU requirements, and CPU performance.

### Phase 3 — Optional advanced capabilities
- Add sound effects, dubbing/localization, conversational voice agents, and music generation through explicit provider/model adapters.
- Keep adapters disabled until configured and verified.
- Add cost/privacy/licensing notices before cloud use.

### Phase 4 — Reliability and release
- Run static checks and endpoint tests.
- Test supported browsers/mobile layouts, upload limits, failure states, and valid exported files.
- Update README and this status file only with verified outcomes.
- Provide a final matrix of PASS / FAIL / NOT CONFIGURED, clearly separating source integration from real runtime verification.

## Acceptance criteria

- No fake generation, placeholder audio, or false “model ready” indicators.
- Missing model, provider key, hardware, storage, or permission produces a clear actionable message.
- Users can download valid outputs and understand where files are stored.
- Every cloud feature has explicit data-flow disclosure and provider configuration.
- Zero-cost/local paths remain usable without requiring a paid subscription, wherever a viable local implementation exists.
