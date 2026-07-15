import { readFileSync } from "node:fs";
import { spawnSync } from "node:child_process";

const command = process.platform === "win32" ? "pnpm.cmd" : "pnpm";
const webURL = process.env.BIGHEAD_DEPLOYED_WEB_URL ?? "http://127.0.0.1:3002";
const apiURL = process.env.BIGHEAD_DEPLOYED_API_URL ?? "http://127.0.0.1:8000";

const status = spawnSync(
  command,
  ["exec", "supabase", "status", "--output", "json"],
  { encoding: "utf8", shell: process.platform === "win32" }
);
if (status.status !== 0) {
  process.stderr.write(
    status.stderr || "Local Supabase is not running. Run pnpm db:start first.\n"
  );
  process.exit(status.status ?? 1);
}

const local = JSON.parse(status.stdout);
const seed = readFileSync(
  new URL("../supabase/seed.sql", import.meta.url),
  "utf8"
);
const atlasEmail = seed.match(/owner@atlas\.bighead\.(?:dev|test)/)?.[0];
const beaconEmail = seed.match(/owner@beacon\.bighead\.(?:dev|test)/)?.[0];
if (!atlasEmail || !beaconEmail) {
  throw new Error(
    "Deterministic Atlas/Beacon owners are missing from supabase/seed.sql."
  );
}

async function requireHealthy(url, label, expectedStatus) {
  let response;
  try {
    response = await fetch(url, { signal: AbortSignal.timeout(5_000) });
  } catch (error) {
    throw new Error(`${label} is unavailable at ${url}`, { cause: error });
  }
  if (!response.ok) {
    throw new Error(`${label} returned HTTP ${response.status} at ${url}`);
  }
  if (expectedStatus) {
    const payload = await response.json();
    if (payload.status !== expectedStatus) {
      throw new Error(`${label} did not report ${expectedStatus} at ${url}`);
    }
  }
}

await requireHealthy(`${apiURL}/health/ready`, "BigHead API", "ready");
await requireHealthy(webURL, "BigHead web");

const env = {
  ...process.env,
  BIGHEAD_WORKSPACE_MODE: "real",
  BIGHEAD_DEPLOYED_WEB_URL: webURL,
  BIGHEAD_REAL_API_URL: apiURL,
  BIGHEAD_E2E_EMAIL: atlasEmail,
  BIGHEAD_E2E_BEACON_EMAIL: beaconEmail,
  BIGHEAD_E2E_PASSWORD: "BigHeadLocalOnly!2026",
  BIGHEAD_E2E_ORGANIZATION_ID: "a7100000-0000-0000-0000-000000000001",
  BIGHEAD_REAL_SUPABASE_URL: local.API_URL,
  SUPABASE_PUBLISHABLE_KEY: local.PUBLISHABLE_KEY
};

const test = spawnSync(
  command,
  [
    "--filter",
    "@bighead/web",
    "exec",
    "playwright",
    "test",
    "--config",
    "playwright.deployed.config.ts",
    ...process.argv.slice(2)
  ],
  { env, stdio: "inherit", shell: process.platform === "win32" }
);
process.exit(test.status ?? 1);
