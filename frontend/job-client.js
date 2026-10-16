(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.AudiolabJobs = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const TERMINAL = new Set(["succeeded", "failed"]);
  const ACTIVE = new Set(["queued", "running"]);

  function normalizeBaseUrl(value) {
    const base = String(value || "http://127.0.0.1:8000").trim().replace(/\/+$/, "");
    if (!/^https?:\/\//i.test(base)) throw new Error("Audiolab API address must start with http:// or https://.");
    return base;
  }

  function createClient(options) {
    const config = options || {};
    const baseUrl = normalizeBaseUrl(config.baseUrl);
    const fetchImpl = config.fetchImpl || (typeof fetch === "function" ? fetch.bind(globalThis) : null);
    const sleep = config.sleep || (ms => new Promise(resolve => setTimeout(resolve, ms)));
    const now = config.now || (() => Date.now());
    const pollIntervalMs = Math.max(0, Number(config.pollIntervalMs ?? 1500));
    const maxDurationMs = Math.max(1, Number(config.maxDurationMs ?? 30 * 60 * 1000));
    const maxTransientFailures = Math.max(0, Number(config.maxTransientFailures ?? 5));

    if (!fetchImpl) throw new Error("Fetch is unavailable in this environment.");

    async function readError(response, fallback) {
      try {
        const payload = await response.json();
        return payload && typeof payload.detail === "string" ? payload.detail : fallback;
      } catch (_) {
        return fallback;
      }
    }

    async function pollJob(jobId, onProgress) {
      const id = String(jobId || "").trim();
      if (!id) throw new Error("A job ID is required.");
      const deadline = now() + maxDurationMs;
      let transientFailures = 0;
      while (now() < deadline) {
        let response;
        try {
          response = await fetchImpl(baseUrl + "/jobs/" + encodeURIComponent(id), {
            headers: { Accept: "application/json" }
          });
        } catch (error) {
          transientFailures += 1;
          if (transientFailures > maxTransientFailures) {
            throw new Error("Lost connection while checking the audio job. Check the local backend and retry.");
          }
          if (typeof onProgress === "function") onProgress({
            status: "retrying", retryCount: transientFailures,
            message: "Connection interrupted; retrying job status."
          });
          await sleep(Math.min(pollIntervalMs * transientFailures, 10000));
          continue;
        }

        if (!response.ok) {
          const fallback = "Could not check audio job (" + response.status + ").";
          if (response.status === 429 || response.status >= 500) {
            transientFailures += 1;
            if (transientFailures > maxTransientFailures) {
              throw new Error(await readError(response, fallback));
            }
            if (typeof onProgress === "function") onProgress({
              status: "retrying", retryCount: transientFailures,
              message: "The backend is temporarily busy; retrying."
            });
            await sleep(Math.min(pollIntervalMs * transientFailures, 10000));
            continue;
          }
          throw new Error(await readError(response, fallback));
        }

        let job;
        try { job = await response.json(); }
        catch (_) { throw new Error("The backend returned invalid job-status JSON."); }
        if (!job || typeof job !== "object" || typeof job.status !== "string") {
          throw new Error("The backend returned an invalid job-status response.");
        }
        transientFailures = 0;
        if (job.status === "succeeded") return job;
        if (job.status === "failed") throw new Error(
          typeof job.error === "string" && job.error ? job.error : "Audio job failed. Check local model setup and try again."
        );
        if (!ACTIVE.has(job.status)) throw new Error("The backend returned an unknown job status.");
        if (typeof onProgress === "function") onProgress(job);
        await sleep(pollIntervalMs);
      }
      throw new Error("Audio job timed out while waiting for the backend. Check local backend status before retrying.");
    }

    async function downloadRender(jobId) {
      const id = String(jobId || "").trim();
      if (!id) throw new Error("A job ID is required to download the render.");
      const response = await fetchImpl(baseUrl + "/jobs/" + encodeURIComponent(id) + "/download");
      if (!response.ok) throw new Error(await readError(
        response, "The completed dubbing archive could not be downloaded (" + response.status + ")."
      ));
      const blob = await response.blob();
      if (!blob || typeof blob.size !== "number" || blob.size < 22) {
        throw new Error("The backend returned an empty or incomplete dubbing archive.");
      }
      const signature = new Uint8Array(await blob.slice(0, 4).arrayBuffer());
      if (signature[0] !== 0x50 || signature[1] !== 0x4b) {
        throw new Error("The download is not a ZIP archive. Check the backend response and try again.");
      }
      return blob;
    }

    return { baseUrl, pollJob, downloadRender };
  }

  return { createClient, normalizeBaseUrl };
});
