import { spawnSync } from "node:child_process";

const status = spawnSync(
  "pnpm",
  ["exec", "supabase", "status", "--output", "json"],
  { encoding: "utf8", shell: process.platform === "win32" }
);

if (status.status !== 0) {
  process.stderr.write(
    status.stderr ?? status.error?.message ?? "Supabase status failed\n"
  );
  process.exit(status.status ?? 1);
}

const local = JSON.parse(status.stdout);
const env = {
  ...process.env,
  BIGHEAD_RUN_SUPABASE_INTEGRATION: "1",
  SUPABASE_INTEGRATION_URL: local.API_URL,
  SUPABASE_INTEGRATION_PUBLISHABLE_KEY: local.PUBLISHABLE_KEY,
  SUPABASE_INTEGRATION_SECRET_KEY: local.SECRET_KEY,
  SUPABASE_INTEGRATION_DATABASE_URL: local.DB_URL
};
const test = spawnSync(
  "uv",
  [
    "run",
    "--project",
    "apps/api",
    "pytest",
    "-q",
    "apps/api/tests/test_supabase_integration.py"
  ],
  { env, stdio: "inherit" }
);
process.exit(test.status ?? 1);
