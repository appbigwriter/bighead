import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

const forbidden = [
  /service_role/i,
  /sk_live_/i,
  /AIza[0-9A-Za-z\-_]{10,}/,
  /xox[baprs]-/i
];

function walk(dir) {
  const entries = readdirSync(dir);
  const files = [];

  for (const entry of entries) {
    const fullPath = join(dir, entry);
    const isIgnored =
      fullPath.includes("node_modules") ||
      fullPath.includes(".git") ||
      fullPath.includes(".next") ||
      fullPath.includes("prd") ||
      fullPath.includes("stories") ||
      fullPath.includes("dist") ||
      fullPath.includes("coverage");

    if (isIgnored) {
      continue;
    }

    const stats = statSync(fullPath);
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
  const content = readFileSync(file, "utf8");
  for (const pattern of forbidden) {
    if (pattern.test(content) && !content.includes("OPTIONAL_UNTIL_PROVIDER_SELECTED")) {
      console.error(`Potential secret detected in ${file}`);
      process.exit(1);
    }
  }
}

console.log("No obvious secrets detected.");
