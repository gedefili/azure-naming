/*
 * Repository: azure-naming
 * Path: web/playwright.config.ts
 * Purpose: Playwright config with a "screenshots" project that runs against a
 *          locally previewed Vite build, and a "smoke" project for quick checks.
 * Author: SanMar Platform Team
 * Created: 2026-04-27
 * Last-Modified: 2026-04-27
 * Version: 1.0.0
 */
import { defineConfig, devices } from "@playwright/test";

const PORT = Number(process.env.PREVIEW_PORT ?? 4173);
const BASE_URL = process.env.PREVIEW_BASE_URL ?? `http://127.0.0.1:${PORT}`;

export default defineConfig({
  testDir: "tests/e2e",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["junit", { outputFile: "junit-e2e.xml" }]] : "list",
  use: {
    baseURL: BASE_URL,
    trace: "retain-on-failure",
    actionTimeout: 10_000,
    navigationTimeout: 30_000,
  },
  projects: [
    {
      name: "smoke",
      testMatch: /smoke\.spec\.ts$/,
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "screenshots",
      testMatch: /screenshots\.spec\.ts$/,
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1440, height: 900 },
        deviceScaleFactor: 2,
      },
    },
  ],
});
