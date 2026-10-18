import { spawnSync } from "node:child_process";

const files = [
  "frontend/voice-convert.js",
  "frontend/voice-persistence.js",
  "frontend/hf-client.js",
  "frontend/studio-fix.js",
  "frontend/app-fixed.js",
  "frontend/job-client.js",
  "frontend/project-assets.js",
  "frontend/mvp-workflows.js",
  "frontend/landing-3d.js",
  "api/neon-health.js",
  "scripts/neon-smoke.mjs"
];

let failed = false;
for (const file of files) {
  const result = spawnSync(process.execPath, ["--check", file], { encoding: "utf8" });
  if (result.status !== 0) {
    failed = true;
    console.error(result.stderr || result.stdout || `Syntax check failed: ${file}`);
  }
}
if (failed) process.exit(1);
console.log(`Build check passed: syntax validated for ${files.length} application and Neon JavaScript files.`);
