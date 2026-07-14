import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

const forbidden = [
  /sb_secret_[0-9A-Za-z_-]{12,}/,
  /sk_live_/i,
  /sk-(?:proj|ant)-[0-9A-Za-z_-]{16,}/,
  /AIza[0-9A-Za-z\-_]{10,}/,
  /xox[baprs]-/i,
  /gh[pousr]_[0-9A-Za-z]{30,}/,
  /-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----/,
  /postgres(?:ql)?:\/\/[^:\s/]+:[^@<\s]{12,}@/i,
  /eyJ[0-9A-Za-z_-]{20,}\.[0-9A-Za-z_-]{20,}\.[0-9A-Za-z_-]{20,}/
];

function walk(dir) {
  let entries;
  try {
    entries = readdirSync(dir);
  } catch (error) {
    if (error?.code === "ENOENT") return [];
    throw error;
  }
  const files = [];

  for (const entry of entries) {
    const fullPath = join(dir, entry);
    const isIgnored =
      entry === ".env" ||
      (/^\.env\./.test(entry) && entry !== ".env.example") ||
      fullPath.includes("node_modules") ||
      fullPath.includes(".git") ||
      fullPath.includes(".next") ||
      fullPath.includes(".turbo") ||
      fullPath.includes("test-results") ||
      fullPath.includes("playwright-report") ||
      fullPath.includes("__pycache__") ||
      fullPath.includes(".pytest_cache") ||
      fullPath.includes(".mypy_cache") ||
      fullPath.includes(".ruff_cache") ||
      fullPath.includes("prd") ||
      fullPath.includes("stories") ||
      fullPath.includes("dist") ||
      fullPath.includes("coverage");

    if (isIgnored) {
      continue;
    }

    let stats;
    try {
      stats = statSync(fullPath);
    } catch (error) {
      if (error?.code === "ENOENT") continue;
      throw error;
    }
    if (stats.isDirectory()) {
      files.push(...walk(fullPath));
      continue;
    }

    files.push(fullPath);
  }

  return files;
}

const files = walk(".");

for (const file of files) {
  if (file.endsWith("check-no-secrets.mjs")) continue;
  let content;
  try {
    content = readFileSync(file, "utf8");
  } catch (error) {
    if (error?.code === "ENOENT") continue;
    throw error;
  }
  for (const pattern of forbidden) {
    if (pattern.test(content)) {
      console.error(`Potential secret detected in ${file}`);
      process.exit(1);
    }
  }
}

console.log("No obvious secrets detected.");
