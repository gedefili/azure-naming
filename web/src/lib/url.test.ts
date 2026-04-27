/*
 * Repository: azure-naming
 * Path: web/src/lib/url.test.ts
 * Purpose: Unit tests for URL helpers
 */
import { describe, expect, it } from "vitest";
import { appendQuery, buildUrl, joinUrl } from "./url";

describe("joinUrl", () => {
  it("joins absolute base with relative path", () => {
    expect(joinUrl("https://x.com/api", "/claims")).toBe("https://x.com/api/claims");
    expect(joinUrl("https://x.com/api/", "claims")).toBe("https://x.com/api/claims");
    expect(joinUrl("https://x.com/api///", "///claims")).toBe("https://x.com/api/claims");
  });

  it("joins rooted base with relative path", () => {
    expect(joinUrl("/api", "/claims")).toBe("/api/claims");
  });

  it("returns absolute path unchanged", () => {
    expect(joinUrl("/api", "https://other/x")).toBe("https://other/x");
  });

  it("handles empty base", () => {
    expect(joinUrl("", "claims")).toBe("/claims");
    expect(joinUrl("", "/claims")).toBe("/claims");
  });
});

describe("appendQuery", () => {
  it("returns unchanged URL when no params", () => {
    expect(appendQuery("/x")).toBe("/x");
    expect(appendQuery("/x", {})).toBe("/x");
    expect(appendQuery("/x", { a: undefined, b: null, c: "" })).toBe("/x");
  });

  it("appends query parameters with ? when none exist", () => {
    expect(appendQuery("/x", { a: 1, b: "two" })).toBe("/x?a=1&b=two");
  });

  it("uses & when ? already present", () => {
    expect(appendQuery("/x?z=0", { a: 1 })).toBe("/x?z=0&a=1");
  });

  it("encodes special characters", () => {
    expect(appendQuery("/x", { q: "a&b" })).toContain("q=a%26b");
  });

  it("coerces booleans and numbers via String()", () => {
    expect(appendQuery("/x", { a: true, b: 0 })).toBe("/x?a=true&b=0");
  });
});

describe("buildUrl", () => {
  it("composes joinUrl + appendQuery", () => {
    expect(buildUrl("https://x.com/api", "/claims", { region: "wus2" })).toBe(
      "https://x.com/api/claims?region=wus2",
    );
  });
});
