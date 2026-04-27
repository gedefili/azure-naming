/*
 * Repository: azure-naming
 * Path: web/src/auth/msalConfig.test.ts
 * Purpose: Tests for buildMsalConfig + scope helpers
 */
import { describe, expect, it, vi } from "vitest";
import {
  buildApiScopes,
  buildApiTokenRequest,
  buildLoginRequest,
  buildMsalConfig,
} from "./msalConfig";

const baseEnv = {
  tenantId: "tenant",
  clientId: "client",
  apiClientId: "api-client",
  origin: "https://app.example.com",
  isProduction: false,
};

describe("buildMsalConfig", () => {
  it("builds a configuration with derived authority and redirect URIs", () => {
    const config = buildMsalConfig(baseEnv);
    expect(config.auth.authority).toBe("https://login.microsoftonline.com/tenant");
    expect(config.auth.redirectUri).toBe("https://app.example.com/auth/callback");
    expect(config.auth.postLogoutRedirectUri).toBe("https://app.example.com/");
    expect(config.cache?.cacheLocation).toBe("sessionStorage");
    expect(config.cache?.storeAuthStateInCookie).toBe(false);
  });

  it("warns in development when client/tenant ids are missing", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => undefined);
    expect(() =>
      buildMsalConfig({ ...baseEnv, clientId: undefined, tenantId: undefined }),
    ).not.toThrow();
    expect(warn).toHaveBeenCalled();
    warn.mockRestore();
  });

  it("throws in production when client/tenant ids are missing", () => {
    expect(() =>
      buildMsalConfig({ ...baseEnv, clientId: undefined, isProduction: true }),
    ).toThrow(/Missing/);
  });
});

describe("buildApiScopes", () => {
  it("returns scope when provided", () => {
    expect(buildApiScopes("api-client")).toEqual(["api://api-client/user_access"]);
  });
  it("returns empty list when no api client id", () => {
    expect(buildApiScopes(undefined)).toEqual([]);
  });
});

describe("buildLoginRequest", () => {
  it("includes openid/profile/email and api scopes", () => {
    const req = buildLoginRequest(["api://x/user_access"]);
    expect(req.scopes).toContain("openid");
    expect(req.scopes).toContain("profile");
    expect(req.scopes).toContain("email");
    expect(req.scopes).toContain("api://x/user_access");
    expect(req.prompt).toBe("select_account");
  });
});

describe("buildApiTokenRequest", () => {
  it("uses provided api scopes when present", () => {
    expect(buildApiTokenRequest(["api://x"]).scopes).toEqual(["api://x"]);
  });
  it("falls back to openid when scopes are empty", () => {
    expect(buildApiTokenRequest([]).scopes).toEqual(["openid"]);
  });
});
