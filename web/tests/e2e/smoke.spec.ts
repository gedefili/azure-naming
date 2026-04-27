/*
 * Repository: azure-naming
 * Path: web/tests/e2e/smoke.spec.ts
 * Purpose: Tiny smoke test that the SPA shell renders against the preview server
 */
import { test, expect } from "@playwright/test";

test("home loads the sign-in screen or app shell", async ({ page }) => {
  const resp = await page.goto("/");
  expect(resp?.ok(), `home returned ${resp?.status()}`).toBe(true);
  // The app either shows the sign-in CTA (anonymous) or the My Claims heading
  // (authenticated). Either is acceptable for the smoke check.
  await expect(
    page.getByRole("button", { name: /sign in with microsoft/i }).or(
      page.getByRole("heading", { name: /my claims/i }),
    ),
  ).toBeVisible({ timeout: 15_000 });
});
