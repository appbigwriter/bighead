import { defineConfig, devices } from "@playwright/test";

const webURL = process.env.BIGHEAD_DEPLOYED_WEB_URL ?? "http://127.0.0.1:3002";

export default defineConfig({
  testDir: "./tests/real-e2e",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: webURL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    extraHTTPHeaders: { "x-bighead-e2e-mode": "real" }
  },
  projects: [
    { name: "deployed-desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "deployed-mobile", use: { ...devices["Pixel 5"] } }
  ]
});
