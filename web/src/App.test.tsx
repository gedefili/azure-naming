/*
 * Repository: azure-naming
 * Path: web/src/App.test.tsx
 * Purpose: Tests for the App auth gate and route map
 */
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";

const mockUseIsAuthenticated = vi.fn();
const mockUseMsal = vi.fn();
vi.mock("@azure/msal-react", () => ({
  useIsAuthenticated: () => mockUseIsAuthenticated(),
  useMsal: () => mockUseMsal(),
}));

const apiStub = {
  listClaims: vi.fn().mockResolvedValue({ items: [], count: 0, scope: "me", is_admin: false }),
  claim: vi.fn(),
  release: vi.fn(),
  remediate: vi.fn(),
  audit: vi.fn(),
};
vi.mock("./api/useApiClient", () => ({ useApiClient: () => apiStub }));

import App from "./App";
import { withProviders } from "./test-utils";

describe("App", () => {
  beforeEach(() => {
    mockUseIsAuthenticated.mockReset();
    mockUseMsal.mockReset();
  });

  it("renders SignInScreen when unauthenticated", () => {
    mockUseIsAuthenticated.mockReturnValue(false);
    mockUseMsal.mockReturnValue({ instance: { loginRedirect: vi.fn() }, accounts: [] });
    render(withProviders(<App />));
    expect(screen.getByRole("button", { name: /sign in with microsoft/i })).toBeInTheDocument();
  });

  it("renders TopBar + MyClaims when authenticated", async () => {
    mockUseIsAuthenticated.mockReturnValue(true);
    mockUseMsal.mockReturnValue({
      instance: { logoutRedirect: vi.fn() },
      accounts: [{ idTokenClaims: { roles: [] }, username: "alice@sanmar.com" }],
    });
    render(withProviders(<App />));
    // "My Claims" appears in both the navigation and the page heading.
    expect((await screen.findAllByText(/my claims/i)).length).toBeGreaterThanOrEqual(1);
  });
});
