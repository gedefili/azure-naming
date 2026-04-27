/*
 * Repository: azure-naming
 * Path: web/src/auth/roles.test.ts
 * Purpose: Tests for role parsing and admin classification
 */
import { describe, expect, it } from "vitest";
import { ADMIN_ROLES, isAdmin, parseRoles } from "./roles";

describe("parseRoles", () => {
  it("returns [] when claims are falsy or wrong shape", () => {
    expect(parseRoles(null)).toEqual([]);
    expect(parseRoles(undefined)).toEqual([]);
    expect(parseRoles("string")).toEqual([]);
    expect(parseRoles({})).toEqual([]);
    expect(parseRoles({ roles: "not-array" })).toEqual([]);
  });

  it("filters non-string entries", () => {
    expect(parseRoles({ roles: ["a", 1, null, "b"] })).toEqual(["a", "b"]);
  });
});

describe("isAdmin", () => {
  it("matches each admin role case-insensitively", () => {
    for (const role of ADMIN_ROLES) {
      expect(isAdmin([role.toUpperCase()])).toBe(true);
      expect(isAdmin([role])).toBe(true);
    }
  });

  it("returns false for unknown roles", () => {
    expect(isAdmin([])).toBe(false);
    expect(isAdmin(["user", "developer"])).toBe(false);
  });
});

describe("ADMIN_ROLES", () => {
  it("contains the expected lowercase set", () => {
    expect(ADMIN_ROLES).toContain("admin");
    expect(ADMIN_ROLES).toContain("sanmar-naming-admin");
    expect(ADMIN_ROLES).toContain("sanmar.naming.admin");
  });
});
