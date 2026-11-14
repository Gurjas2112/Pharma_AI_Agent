import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 30 * 60 * 1000,
  expect: { timeout: 15_000 },
  retries: 0,
  workers: 1,
  reporter: [["list"]],
  outputDir: "./test-results",
  use: {
    baseURL: process.env.E2E_BASE_URL || "https://repurpora.vercel.app",
    viewport: { width: 1440, height: 900 },
    video: { mode: "on", size: { width: 1440, height: 900 } },
    screenshot: "off",
    acceptDownloads: true,
    launchOptions: { slowMo: 60 },
  },
});
