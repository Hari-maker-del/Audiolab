# Phase 13 — Local end-to-end smoke test

This smoke test checks the **real local Audiolab API** without exposing it publicly. It can submit real model-backed jobs when you supply your own audio files. CI also runs a loopback HTTP test server to verify the smoke-test client's health → submit → poll → history → download workflow, but that fixture does **not** run speech or voice models.

## 1. Start the local API on loopback

In PowerShell, open a terminal and run:

\`\`\`powershell
cd path\to\Audiolab\backend
python -m uvicorn server:app --host 127.0.0.1 --port 8000
\`\`\`

Keep that terminal open. Do not change the host to \`0.0.0.0\` or forward the port to the internet for this test.

From a second PowerShell terminal at the repository root:

\`\`\`powershell
python scripts/audiolab_e2e_smoke.py
\`\`\`

This checks \`GET /health\` and \`GET /jobs\`. It does not run inference unless you provide an audio input.

## 2. Exercise actual transcription

Use a short audio file containing clear speech. The first run may download the configured local faster-whisper model, so it can take time and needs local disk/network access for model acquisition.

\`\`\`powershell
python scripts/audiolab_e2e_smoke.py --transcribe-audio "C:\path\to\short-speech.wav" --timeout 1800
\`\`\`

The script submits \`POST /jobs/dub-transcribe\`, polls \`GET /jobs/{job_id}\`, checks that timestamped segments were returned, and verifies the completed job appears in \`GET /jobs\` history.

## 3. Exercise actual dubbing render and ZIP export

Create a JSON manifest beside the target voice reference audio. The \`target_audio\` path is relative to the manifest file. Every segment needs a start/end time and a reviewed translation.

Example \`render-manifest.json\`:

\`\`\`json
{
  "target_audio": "target-voice.wav",
  "target_language": "Tamil",
  "ref_text": "The exact words spoken in the target voice reference",
  "segments": [
    {
      "start": 0.0,
      "end": 1.8,
      "source_text": "Hello",
      "translated_text": "வணக்கம்"
    }
  ]
}
\`\`\`

Run only if you have permission to use the target voice recording:

\`\`\`powershell
python scripts/audiolab_e2e_smoke.py --render-manifest ".\render-manifest.json" --confirm-voice-rights --timeout 1800
\`\`\`

The script submits the real \`/jobs/dub-render\` endpoint, waits for a terminal status, confirms the job appears in history, downloads \`/jobs/{job_id}/download\`, checks the ZIP signature and CRCs, and requires non-empty \`dubbed_voice.wav\`, \`subtitles.srt\`, and \`segments.json\`. The archive is saved under \`audiolab-e2e-results\`. The backend's downloadable artifact is temporary and may be deleted after download.

You can combine \`--transcribe-audio\` and \`--render-manifest\` to exercise both flows in one run.

## Optional API key

If you configured \`AUDIOLAB_API_KEY\` in the backend environment, set the same variable in the smoke-test terminal. The script sends it as a request header and never writes it to a file:

\`\`\`powershell
$env:AUDIOLAB_API_KEY = "your-local-key"
python scripts/audiolab_e2e_smoke.py
\`\`\`

Do not paste secrets into frontend JavaScript or commit them.

## What the result means

- \`PASS\` for health/history confirms the local API responds, not that model weights are loaded.
- \`PASS\` for transcription confirms one real local transcription job completed and its metadata is visible in history.
- \`PASS\` for render confirms one real local render completed and its downloaded ZIP has the expected files.
- CI's HTTP fixture validates the test harness and API contract with synthetic data only. It does not prove the model works on your machine.
- Failures should be reported as-is; missing optional dependencies, unavailable model weights, hardware limits, and poor input audio are not silently treated as success.
