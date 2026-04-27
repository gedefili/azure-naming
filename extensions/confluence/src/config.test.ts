/*
 * Repository: azure-naming
 * Path: extensions/confluence/src/config.test.ts
 * Purpose: Tests for Forge config parsing
 */
import { describe, expect, it } from "vitest";
import { parseConfig, loadConfig } from "./config";

describe("parseConfig", () => {
  const valid = {
    ENTRA_TENANT_ID: "tenant",
    ENTRA_CLIENT_ID: "client",
    ENTRA_CLIENT_SECRET: "secret",
    NAMING_API_RESOURCE: "api://naming",
    NAMING_API_BASE_URL: "https://naming.example.com/api/",
  };

  it("returns a frozen ForgeConfig with trimmed base URL", () => {
    const config = parseConfig(valid);
    expect(config.tenantId).toBe("tenant");
    expect(config.clientId).toBe("client");
    expect(config.clientSecret).toBe("secret");
    expect(config.resource).toBe("api://naming");
    expect(config.baseUrl).toBe("https://naming.example.com/api");
  });

  it("throws listing every missing variable", () => {
    expect(() => parseConfig({})).toThrowError(/Forge config missing/);
    try {
      parseConfig({});
    } catch (err) {
      const msg = (err as Error).message;
      expect(msg).toContain("Entra tenant id");
      expect(msg).toContain("Entra client id");
      expect(msg).toContain("Entra client secret");
      expect(msg).toContain("Naming API resource");
      expect(msg).toContain("Naming API base URL");
    }
  });

  it("throws when only one var is missing", () => {
    const { ENTRA_CLIENT_SECRET: _omit, ...rest } = valid;
    void _omit;
    expect(() => parseConfig(rest)).toThrowError(/Entra client secret/);
  });
});

describe("loadConfig", () => {
  it("reads from process.env", () => {
    const saved = { ...process.env };
    process.env.ENTRA_TENANT_ID = "tid";
    process.env.ENTRA_CLIENT_ID = "cid";
    process.env.ENTRA_CLIENT_SECRET = "sec";
    process.env.NAMING_API_RESOURCE = "api://r";
    process.env.NAMING_API_BASE_URL = "https://x/api/";
    try {
      const config = loadConfig();
      expect(config.tenantId).toBe("tid");
      expect(config.baseUrl).toBe("https://x/api");
    } finally {
      process.env = saved;
    }
  });
});
