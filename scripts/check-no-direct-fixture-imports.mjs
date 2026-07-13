import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

function walk(dir) {
  const entries = readdirSync(dir);
  const files = [];

  for (const entry of entries) {
    const fullPath = join(dir, entry);
    const stats = statSync(fullPath);

    if (stats.isDirectory()) {
      if (fullPath.includes("node_modules") || fullPath.includes(".next")) {
        continue;
      }
      files.push(...walk(fullPath));
      continue;
    }

    if (fullPath.endsWith(".ts") || fullPath.endsWith(".tsx")) {
      files.push(fullPath);
    }
  }

  return files;
}

const files = walk("apps/web/src");
const violations = [];

for (const file of files) {
  const content = readFileSync(file, "utf8");
  const runtimeContent = content.replace(/^import type .*mock-workspace.*$/gm, "");
  const normalizedFile = file.replaceAll("\\", "/");
  const importsFixtures =
    runtimeContent.includes("packages/contracts/src/fixtures") ||
    runtimeContent.includes("@bighead/contracts/src/fixtures") ||
    runtimeContent.includes("/fixtures/") ||
    runtimeContent.includes('from "./mock-workspace"') ||
    runtimeContent.includes("from './mock-workspace'") ||
    runtimeContent.includes('from "@/lib/mock-workspace"') ||
    runtimeContent.includes("from '@/lib/mock-workspace'");

  const isAllowed =
    normalizedFile.includes("lib/mock-workspace.ts") ||
    normalizedFile.includes("lib/workspace-service.ts") ||
    normalizedFile.includes("/mocks/") ||
    normalizedFile.includes("/tests/") ||
    normalizedFile.includes(".test.") ||
    normalizedFile.includes("msw") ||
    normalizedFile.includes("stories");

  if (importsFixtures && !isAllowed) {
    violations.push(file);
  }
}

if (violations.length > 0) {
  console.error("Direct fixture imports found outside mock boundaries:");
  for (const violation of violations) {
    console.error(`- ${violation}`);
  }
  process.exit(1);
}

console.log("No direct fixture imports found outside mock boundaries.");
