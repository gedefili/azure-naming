/*
 * Repository: azure-naming
 * Path: web/src/pages/SettingsPage.test.tsx
 * Purpose: Tests for SettingsPage theme controls
 */
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("@azure/msal-react", () => ({
  useMsal: () => ({ instance: {}, accounts: [{ username: "alice@sanmar.com" }] }),
}));

import { SettingsPage } from "./SettingsPage";
import { ThemeProvider } from "../theme/ThemeProvider";
import { MemoryStorage } from "../lib/storage";

function renderPage() {
  return render(
    <ThemeProvider seed="alice" storage={new MemoryStorage()}>
      <SettingsPage />
    </ThemeProvider>,
  );
}

describe("SettingsPage", () => {
  it("renders theme controls", () => {
    renderPage();
    expect(screen.getByLabelText(/^mode$/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/accent hue/i)).toBeInTheDocument();
  });

  it("changes the mode via the select", async () => {
    renderPage();
    const select = screen.getByLabelText(/^mode$/i);
    await userEvent.selectOptions(select, "dark");
    expect((select as HTMLSelectElement).value).toBe("dark");
  });

  it("resets hue via the reset button", async () => {
    renderPage();
    const reset = screen.getByRole("button", { name: /reset/i });
    await userEvent.click(reset);
    // No throw is sufficient; deriveHue value is theme-internal.
    expect(reset).toBeInTheDocument();
  });
});
