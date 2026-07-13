import { defineConfig, devices } from "@playwright/test";

const apiURL = process.env.BIGHEAD_REAL_API_URL ?? "http://127.0.0.1:8010";

export default defineConfig({
  testDir: "./tests/real-e2e",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: "http://127.0.0.1:3101",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    extraHTTPHeaders: { "x-bighead-e2e-mode": "real" }
  },
  webServer: [
    {
      command: "uv run --project . python -m bighead_api",
      cwd: "../api",
      url: `${apiURL}/health/live`,
      timeout: 120_000,
      reuseExistingServer: false,
      env: { ...process.env, APP_ENV: "test" }
    },
    {
      command: "pnpm exec next start --port 3101",
      cwd: ".",
      url: "http://127.0.0.1:3101",
      timeout: 180_000,
      reuseExistingServer: false,
      env: { ...process.env, APP_ENV: "test", NODE_ENV: "test" }
    }
  ],
  projects: [
    { name: "real-desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "real-mobile", use: { ...devices["Pixel 5"] } }
  ]
});
