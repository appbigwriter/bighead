import { readFileSync } from "node:fs";
import { spawnSync } from "node:child_process";

const command = process.platform === "win32" ? "pnpm.cmd" : "pnpm";
const status = spawnSync(
  command,
  ["exec", "supabase", "status", "--output", "json"],
  { encoding: "utf8", shell: process.platform === "win32" }
);
if (status.status !== 0) {
  process.stderr.write(status.stderr || "Local Supabase is not running.\n");
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

const env = {
  ...process.env,
  APP_ENV: "test",
  APP_URL: "http://127.0.0.1:3101",
  API_URL: "http://127.0.0.1:8010",
  API_PORT: "8010",
  BIGHEAD_REAL_API_URL: "http://127.0.0.1:8010",
  BIGHEAD_WORKSPACE_MODE: "real",
  BIGHEAD_E2E_EMAIL: atlasEmail,
  BIGHEAD_E2E_BEACON_EMAIL: beaconEmail,
  BIGHEAD_E2E_PASSWORD: "BigHeadLocalOnly!2026",
  BIGHEAD_E2E_ORGANIZATION_ID: "a7100000-0000-0000-0000-000000000001",
  BIGHEAD_REAL_SUPABASE_URL: local.API_URL,
  CORS_ORIGINS: "http://127.0.0.1:3101",
  LOG_LEVEL: "WARNING",
  DATABASE_URL: local.DB_URL,
  DIRECT_DATABASE_URL: local.DB_URL,
  SUPABASE_URL: local.API_URL,
  SUPABASE_PUBLISHABLE_KEY: local.PUBLISHABLE_KEY,
  NEXT_PUBLIC_SUPABASE_URL: local.API_URL,
  NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: local.PUBLISHABLE_KEY,
  SUPABASE_SECRET_KEY: local.SECRET_KEY,
  STORAGE_BUCKET: "artifacts",
  REDIS_URL: "redis://127.0.0.1:6379/0",
  QUEUE_NAME: "bighead:e2e",
  JOB_LEASE_SECONDS: "30",
  OTEL_SERVICE_NAME: "bighead-api-e2e",
  OTEL_EXPORTER_OTLP_ENDPOINT: "http://127.0.0.1:4318",
  OTEL_EXPORTER_OTLP_HEADERS: "",
  SENTRY_DSN: "",
  ENCRYPTION_KEY: "local-e2e-encryption-key-32chars",
  WEBHOOK_SIGNING_SECRET: "local-e2e-webhook-secret",
  PORTAL_TOKEN_PEPPER: "local-e2e-portal-pepper"
};

const build = spawnSync(
  command,
  ["--filter", "@bighead/web", "build"],
  { env, stdio: "inherit", shell: process.platform === "win32" }
);
if (build.status !== 0) process.exit(build.status ?? 1);

const test = spawnSync(
  command,
  [
    "--filter",
    "@bighead/web",
    "exec",
    "playwright",
    "test",
    "--config",
    "playwright.real.config.ts",
    ...process.argv.slice(2)
  ],
  { env, stdio: "inherit", shell: process.platform === "win32" }
);
process.exit(test.status ?? 1);
