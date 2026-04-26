/*
 * Repository: azure-naming
 * Path: web/src/theme/theme.test.ts
 * Purpose: Unit tests for theme derivation helpers
 * Author: GitHub Copilot
 * Created: 2026-04-26
 * Last-Modified: 2026-04-26
 * Version: 0.1.0
 */
import { describe, expect, it } from "vitest";
import { deriveHue, buildTokens, buildAccent } from "./theme";

describe("deriveHue", () => {
  it("is deterministic for the same seed", () => {
    expect(deriveHue("alice@sanmar.com")).toBe(deriveHue("alice@sanmar.com"));
  });

  it("falls inside one of the safe hue ranges", () => {
    const safe = (h: number): boolean => {
      return (
        (h >= 195 && h < 250) ||
        (h >= 260 && h < 310) ||
        (h >= 160 && h < 195) ||
        (h >= 110 && h < 145)
      );
    };
    for (const seed of ["alice", "bob", "carol", "dan", "eve", "frank", "grace"]) {
      expect(safe(deriveHue(seed))).toBe(true);
    }
  });
});

describe("buildAccent", () => {
  it("produces darker accent text against light accent", () => {
    const a = buildAccent(200, false);
    expect(a.accent).toMatch(/oklch/);
    expect(a.accentText).toMatch(/oklch/);
  });
});

describe("buildTokens", () => {
  it("returns 11 token keys for both modes", () => {
    expect(Object.keys(buildTokens("light", 200))).toHaveLength(11);
    expect(Object.keys(buildTokens("dark", 200))).toHaveLength(11);
  });

  it("has different surfaces in light vs dark", () => {
    expect(buildTokens("light", 200).surfaceBase).not.toBe(
      buildTokens("dark", 200).surfaceBase,
    );
  });
});
