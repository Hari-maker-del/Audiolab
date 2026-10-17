const test = require("node:test");
const assert = require("node:assert/strict");
const { createClient, normalizeBaseUrl } = require("../job-client.js");

function jsonResponse(payload, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    async json() { return payload; },
    async blob() { return new Blob([JSON.stringify(payload)], { type: "application/json" }); }
  };
}

test("normalizes API base URL and rejects non-HTTP schemes", () => {
  assert.equal(normalizeBaseUrl(" http://127.0.0.1:8000/// "), "http://127.0.0.1:8000");
  assert.throws(() => normalizeBaseUrl("file:///tmp/api"), /http/);
});

test("polls queued job until success and returns final payload", async () => {
  const states = [
    jsonResponse({ job_id: "abc", status: "queued" }),
    jsonResponse({ job_id: "abc", status: "running" }),
    jsonResponse({ job_id: "abc", status: "succeeded", result: { segments: [] } })
  ];
  const progress = [];
  const client = createClient({
    baseUrl: "http://localhost:8000/",
    fetchImpl: async url => { assert.match(url, /\/jobs\/abc$/); return states.shift(); },
    sleep: async () => {}, pollIntervalMs: 0
  });
  const job = await client.pollJob("abc", value => progress.push(value.status));
  assert.equal(job.status, "succeeded");
  assert.deepEqual(progress, ["queued", "running"]);
});

test("recovers from a temporary network interruption", async () => {
  let calls = 0;
  const progress = [];
  const client = createClient({
    baseUrl: "http://localhost:8000",
    fetchImpl: async () => {
      calls += 1;
      if (calls === 1) throw new TypeError("connection reset");
      return jsonResponse({ job_id: "retry", status: "succeeded" });
    },
    sleep: async () => {}, pollIntervalMs: 0, maxTransientFailures: 2
  });
  const result = await client.pollJob("retry", value => progress.push(value.status));
  assert.equal(result.status, "succeeded");
  assert.equal(calls, 2);
  assert.deepEqual(progress, ["retrying"]);
});

test("retries temporary 429 and 5xx responses", async () => {
  let calls = 0;
  const client = createClient({
    baseUrl: "http://localhost:8000",
    fetchImpl: async () => {
      calls += 1;
      if (calls === 1) return jsonResponse({ detail: "Busy" }, 429);
      if (calls === 2) return jsonResponse({ detail: "Unavailable" }, 503);
      return jsonResponse({ status: "succeeded", job_id: "busy" });
    },
    sleep: async () => {}, pollIntervalMs: 0, maxTransientFailures: 2
  });
  assert.equal((await client.pollJob("busy")).status, "succeeded");
  assert.equal(calls, 3);
});

test("does not retry terminal authorization errors", async () => {
  let calls = 0;
  const client = createClient({
    baseUrl: "http://localhost:8000",
    fetchImpl: async () => { calls += 1; return jsonResponse({ detail: "Forbidden" }, 403); },
    sleep: async () => {}, pollIntervalMs: 0
  });
  await assert.rejects(client.pollJob("denied"), /Forbidden/);
  assert.equal(calls, 1);
});

test("surfaces failed jobs and rejects malformed status payloads", async () => {
  const failed = createClient({
    baseUrl: "http://localhost:8000",
    fetchImpl: async () => jsonResponse({ status: "failed", error: "Local model unavailable" }),
    sleep: async () => {}, pollIntervalMs: 0
  });
  await assert.rejects(failed.pollJob("fail"), /Local model unavailable/);

  const malformed = createClient({
    baseUrl: "http://localhost:8000",
    fetchImpl: async () => jsonResponse({ job_id: "bad" }),
    sleep: async () => {}, pollIntervalMs: 0
  });
  await assert.rejects(malformed.pollJob("bad"), /invalid job-status response/);
});

test("times out instead of polling forever", async () => {
  let clock = 0;
  const client = createClient({
    baseUrl: "http://localhost:8000",
    fetchImpl: async () => jsonResponse({ status: "running" }),
    sleep: async ms => { clock += Math.max(ms, 1); },
    now: () => clock,
    maxDurationMs: 3,
    pollIntervalMs: 1
  });
  await assert.rejects(client.pollJob("slow"), /timed out/);
});

test("download rejects HTML/error payloads disguised as successful responses", async () => {
  const client = createClient({
    baseUrl: "http://localhost:8000",
    fetchImpl: async () => ({
      ok: true, status: 200,
      async blob() { return new Blob(["<html>not a zip</html>"], { type: "text/html" }); }
    })
  });
  await assert.rejects(client.downloadRender("html"), /not a ZIP archive/);
});

test("download accepts a ZIP signature and returns the blob", async () => {
  const client = createClient({
    baseUrl: "http://localhost:8000",
    fetchImpl: async url => {
      assert.match(url, /\/jobs\/zip-job\/download$/);
      return {
        ok: true, status: 200,
        async blob() {
          return new Blob([new Uint8Array([0x50, 0x4b, 0x03, 0x04, ...new Array(32).fill(0)])]);
        }
      };
    }
  });
  const blob = await client.downloadRender("zip-job");
  assert.equal(blob.size, 36);
});


test("downloadAudio accepts a RIFF/WAVE result and rejects non-WAV content", async () => {
  const wavBytes = new Uint8Array(64);
  wavBytes.set([0x52, 0x49, 0x46, 0x46], 0); // RIFF
  wavBytes.set([0x57, 0x41, 0x56, 0x45], 8); // WAVE
  const client = createClient({
    baseUrl: "http://localhost:8000",
    fetchImpl: async url => {
      assert.match(url, /\/jobs\/voice-job\/download$/);
      return { ok: true, status: 200, async blob() { return new Blob([wavBytes], { type: "audio/wav" }); } };
    }
  });
  const blob = await client.downloadAudio("voice-job");
  assert.equal(blob.size, 64);

  const invalid = createClient({
    baseUrl: "http://localhost:8000",
    fetchImpl: async () => ({
      ok: true, status: 200,
      async blob() { return new Blob(["<html>not audio</html>"], { type: "text/html" }); }
    })
  });
  await assert.rejects(invalid.downloadAudio("bad-audio"), /not a valid RIFF\/WAVE file/);
});
