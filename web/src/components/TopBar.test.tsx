/*
 * Repository: azure-naming
 * Path: web/src/components/TopBar.test.tsx
 * Purpose: Tests for TopBar admin gating + logout
 */
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

const mockUseMsal = vi.fn();
vi.mock("@azure/msal-react", () => ({
  useMsal: () => mockUseMsal(),
}));

import { ThemeProvider } from "../theme/ThemeProvider";
import { MemoryStorage } from "../lib/storage";
import { TopBar } from "./TopBar";

function renderTopBar() {
  return render(
    <MemoryRouter>
      <ThemeProvider seed="alice" storage={new MemoryStorage()}>
        <TopBar />
      </ThemeProvider>
    </MemoryRouter>,
  );
}

describe("TopBar", () => {
  beforeEach(() => mockUseMsal.mockReset());

  it("hides All Claims for non-admins", () => {
    mockUseMsal.mockReturnValue({
      instance: { logoutRedirect: vi.fn() },
      accounts: [{ idTokenClaims: { roles: ["user"] }, username: "u@x" }],
    });
    renderTopBar();
    expect(screen.queryByText(/all claims/i)).toBeNull();
    expect(screen.getByText(/my claims/i)).toBeInTheDocument();
  });

  it("shows All Claims for admins", () => {
    mockUseMsal.mockReturnValue({
      instance: { logoutRedirect: vi.fn() },
      accounts: [{ idTokenClaims: { roles: ["sanmar.naming.admin"] }, username: "u@x" }],
    });
    renderTopBar();
    expect(screen.getByText(/all claims/i)).toBeInTheDocument();
  });

  it("invokes logoutRedirect on sign-out click", async () => {
    const logoutRedirect = vi.fn().mockResolvedValue(undefined);
    mockUseMsal.mockReturnValue({
      instance: { logoutRedirect },
      accounts: [{ username: "u@x" }],
    });
    renderTopBar();
    await userEvent.click(screen.getByRole("button", { name: /sign out/i }));
    expect(logoutRedirect).toHaveBeenCalled();
  });
});
