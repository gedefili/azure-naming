/*
 * Repository: azure-naming
 * Path: web/tests/e2e/screenshots.spec.ts
 * Purpose: Capture deterministic PNG screenshots of the SPA for documentation
 *          and release-note artifacts. The build serves the static SPA from
 *          a preview server; auth and API calls are intercepted/mocked here so
 *          screenshots are reproducible without a real backend.
 * Author: SanMar Platform Team
 * Created: 2026-04-27
 * Last-Modified: 2026-04-27
 * Version: 1.0.0
 */
import { test, expect } from "@playwright/test";
import * as fs from "node:fs";
import * as path from "node:path";

const OUT_DIR = path.resolve(process.cwd(), "screenshots");

test.beforeAll(() => {
  fs.mkdirSync(OUT_DIR, { recursive: true });
});

test.beforeEach(async ({ page }) => {
  // Stub all backend endpoints with deterministic data so the screenshots
  // are reproducible even without the real Azure Function.
  await page.route(/\/api\/claims(\?.*)?$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        items: [
          {
            name: "stwus2dev01",
            resource_type: "storage_account",
            region: "wus2",
            environment: "dev",
            in_use: true,
            claim_state: "claimed",
            claimed_at: "2026-04-26T12:00:00Z",
            claimed_by: "alice@sanmar.com",
          },
          {
            name: "kvwus2prd01",
            resource_type: "key_vault",
            region: "wus2",
            environment: "prd",
            in_use: false,
            claim_state: "released",
            claimed_by: "bob@sanmar.com",
          },
        ],
        count: 2,
        scope: "me",
        is_admin: true,
      }),
    });
  });
});

test("anonymous sign-in screen", async ({ page }) => {
  await page.goto("/");
  const cta = page.getByRole("button", { name: /sign in with microsoft/i });
  await expect(cta).toBeVisible({ timeout: 15_000 });
  await page.screenshot({ path: path.join(OUT_DIR, "01-sign-in.png"), fullPage: true });
});

test("my claims (light)", async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem("naming.theme.mode", "light");
  });
  await page.goto("/");
  // Skip if the smoke screen blocks (no auth). The screenshot still captures
  // the visible state which is what we want to publish.
  await page.waitForLoadState("networkidle");
  await page.screenshot({ path: path.join(OUT_DIR, "02-my-claims-light.png"), fullPage: true });
});

test("my claims (dark)", async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem("naming.theme.mode", "dark");
  });
  await page.goto("/");
  await page.waitForLoadState("networkidle");
  await page.screenshot({ path: path.join(OUT_DIR, "03-my-claims-dark.png"), fullPage: true });
});
