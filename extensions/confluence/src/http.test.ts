/*
 * Repository: azure-naming
 * Path: extensions/confluence/src/http.test.ts
 * Purpose: Tests for the Forge HTTP helper functions
 */
import { describe, expect, it } from "vitest";
import { buildQueryString, joinPath, sanitizeErrorBody, FORGE_SOURCE, SOURCE_HEADER } from "./http";

describe("buildQueryString", () => {
  it("returns empty for missing or empty params", () => {
    expect(buildQueryString()).toBe("");
    expect(buildQueryString({})).toBe("");
    expect(buildQueryString({ a: undefined, b: null, c: "" })).toBe("");
  });

  it("encodes provided values", () => {
    const qs = buildQueryString({ a: "1", b: "two words", c: undefined, d: "x&y" });
    expect(qs.startsWith("?")).toBe(true);
    const parsed = new URLSearchParams(qs.slice(1));
    expect(parsed.get("a")).toBe("1");
    expect(parsed.get("b")).toBe("two words");
    expect(parsed.get("d")).toBe("x&y");
    expect(parsed.has("c")).toBe(false);
  });
});

describe("joinPath", () => {
  it("collapses slashes regardless of leading/trailing", () => {
    expect(joinPath("https://x.com", "claims")).toBe("https://x.com/claims");
    expect(joinPath("https://x.com/", "/claims")).toBe("https://x.com/claims");
    expect(joinPath("https://x.com//", "//claims")).toBe("https://x.com/claims");
  });
});

describe("sanitizeErrorBody", () => {
  it("strips control whitespace", () => {
    expect(sanitizeErrorBody("a\nb\tc\rd  ")).toBe("a b c d");
  });
  it("truncates to max length", () => {
    const long = "x".repeat(500);
    const sanitized = sanitizeErrorBody(long, 50);
    expect(sanitized.length).toBe(50);
    expect(sanitized.endsWith("…")).toBe(true);
  });
  it("returns short bodies unchanged", () => {
    expect(sanitizeErrorBody("short")).toBe("short");
  });
});

describe("source constants", () => {
  it("expose stable header values", () => {
    expect(SOURCE_HEADER).toBe("X-Sanmar-Source");
    expect(FORGE_SOURCE).toBe("confluence-forge");
  });
});
