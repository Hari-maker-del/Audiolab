import { readdir } from "node:fs/promises";
import { spawnSync } from "node:child_process";
import path from "node:path";

const roots = ["frontend", "api"];
const files = [];

async function walk(directory) {
  let entries;
  try {
    entries = await readdir(directory, { withFileTypes: true });
  } catch (error) {
    if (error.code === "ENOENT") return;
    throw error;
  }
  for (const entry of entries) {
    const fullPath = path.join(directory, entry.name);
    if (entry.isDirectory()) await walk(fullPath);
    else if (entry.isFile() && fullPath.endsWith(".js")) files.push(fullPath);
  }
}

for (const root of roots) await walk(root);
if (!files.length) {
  console.error("Build check failed: no JavaScript files were found.");
  process.exit(1);
}

let failed = false;
for (const file of files.sort()) {
  const result = spawnSync(process.execPath, ["--check", file], { encoding: "utf8" });
  if (result.status !== 0) {
    failed = true;
    console.error(result.stderr || result.stdout || `Syntax check failed: ${file}`);
  }
}
if (failed) process.exit(1);
console.log(`Build check passed: syntax validated for ${files.length} JavaScript files.`);
