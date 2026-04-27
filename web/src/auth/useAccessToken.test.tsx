/*
 * Repository: azure-naming
 * Path: web/src/auth/useAccessToken.test.tsx
 * Purpose: Hook tests with a mocked msal-react module
 */
import { describe, expect, it, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";

const mockUseMsal = vi.fn();

vi.mock("@azure/msal-react", () => ({
  useMsal: () => mockUseMsal(),
}));

import { InteractionRequiredAuthError } from "@azure/msal-browser";
import { useAccessToken, useIsAdmin, useUserRoles } from "./useAccessToken";

describe("useAccessToken", () => {
  beforeEach(() => {
    mockUseMsal.mockReset();
  });

  it("returns null when no account is signed in", async () => {
    mockUseMsal.mockReturnValue({
      instance: { acquireTokenSilent: vi.fn(), acquireTokenRedirect: vi.fn() },
      accounts: [],
    });
    const { result } = renderHook(() => useAccessToken());
    expect(await result.current()).toBeNull();
  });

  it("returns the token from acquireTokenSilent on success", async () => {
    const acquireTokenSilent = vi.fn().mockResolvedValue({ accessToken: "TKN" });
    mockUseMsal.mockReturnValue({
      instance: { acquireTokenSilent, acquireTokenRedirect: vi.fn() },
      accounts: [{ homeAccountId: "h", environment: "e", tenantId: "t", username: "u" }],
    });
    const { result } = renderHook(() => useAccessToken());
    await waitFor(() => expect(result.current).toBeTypeOf("function"));
    expect(await result.current()).toBe("TKN");
    expect(acquireTokenSilent).toHaveBeenCalled();
  });

  it("falls back to redirect on InteractionRequiredAuthError and returns null", async () => {
    const interactionErr = new InteractionRequiredAuthError("interaction_required");
    const acquireTokenRedirect = vi.fn().mockResolvedValue(undefined);
    mockUseMsal.mockReturnValue({
      instance: {
        acquireTokenSilent: vi.fn().mockRejectedValue(interactionErr),
        acquireTokenRedirect,
      },
      accounts: [{ username: "u" }],
    });
    const { result } = renderHook(() => useAccessToken());
    expect(await result.current()).toBeNull();
    expect(acquireTokenRedirect).toHaveBeenCalled();
  });

  it("rethrows non-interaction errors", async () => {
    mockUseMsal.mockReturnValue({
      instance: {
        acquireTokenSilent: vi.fn().mockRejectedValue(new Error("network")),
        acquireTokenRedirect: vi.fn(),
      },
      accounts: [{ username: "u" }],
    });
    const { result } = renderHook(() => useAccessToken());
    await expect(result.current()).rejects.toThrow("network");
  });
});

describe("useUserRoles / useIsAdmin", () => {
  beforeEach(() => mockUseMsal.mockReset());

  it("returns parsed roles", () => {
    mockUseMsal.mockReturnValue({
      instance: {},
      accounts: [{ idTokenClaims: { roles: ["sanmar.naming.admin", "user"] } }],
    });
    const { result: rolesResult } = renderHook(() => useUserRoles());
    expect(rolesResult.current).toContain("sanmar.naming.admin");

    const { result: adminResult } = renderHook(() => useIsAdmin());
    expect(adminResult.current).toBe(true);
  });

  it("returns false when no roles claim", () => {
    mockUseMsal.mockReturnValue({ instance: {}, accounts: [] });
    const { result } = renderHook(() => useIsAdmin());
    expect(result.current).toBe(false);
  });
});
