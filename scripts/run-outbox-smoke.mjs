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
const test = spawnSync(
  "uv",
  [
    "run",
    "--project",
    "apps/worker",
    "--extra",
    "dev",
    "pytest",
    "apps/worker/tests/test_outbox_integration.py",
    "-q"
  ],
  {
    stdio: "inherit",
    env: {
      ...process.env,
      BIGHEAD_RUN_OUTBOX_INTEGRATION: "1",
      SUPABASE_INTEGRATION_URL: local.API_URL,
      SUPABASE_INTEGRATION_SECRET_KEY: local.SECRET_KEY,
      SUPABASE_INTEGRATION_DATABASE_URL: local.DB_URL,
      REDIS_URL: process.env.REDIS_URL ?? "redis://127.0.0.1:6379/0"
    }
  }
);

process.exit(test.status ?? 1);
