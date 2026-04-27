/*
 * Repository: azure-naming
 * Path: web/src/theme/theme.extra.test.ts
 * Purpose: Additional coverage for applyTokens, resolveMode, tokenToCssVar
 */
import { describe, expect, it, vi } from "vitest";
import { applyTokens, buildTokens, resolveMode, tokenToCssVar } from "./theme";

describe("tokenToCssVar", () => {
  it("converts camelCase to kebab CSS variable name", () => {
    expect(tokenToCssVar("surfaceBase")).toBe("--surface-base");
    expect(tokenToCssVar("danger")).toBe("--danger");
    expect(tokenToCssVar("accentText")).toBe("--accent-text");
  });
});

describe("applyTokens", () => {
  it("writes every token onto the supplied element", () => {
    const root = document.createElement("div");
    applyTokens(buildTokens("dark", 200), root);
    expect(root.style.getPropertyValue("--surface-base")).toContain("oklch");
    expect(root.style.getPropertyValue("--accent")).toContain("oklch");
  });

  it("returns silently when target is null", () => {
    expect(() => applyTokens(buildTokens("light", 200), null)).not.toThrow();
  });

  it("uses document.documentElement by default", () => {
    applyTokens(buildTokens("light", 220));
    expect(document.documentElement.style.getPropertyValue("--accent")).toBeTruthy();
  });
});

describe("resolveMode", () => {
  it("returns the explicit mode unchanged", () => {
    expect(resolveMode("light")).toBe("light");
    expect(resolveMode("dark")).toBe("dark");
  });

  it("uses the injected matchMedia for auto", () => {
    const dark = vi.fn(() => ({ matches: true }) as MediaQueryList);
    const light = vi.fn(() => ({ matches: false }) as MediaQueryList);
    expect(resolveMode("auto", dark)).toBe("dark");
    expect(resolveMode("auto", light)).toBe("light");
  });

  it("falls back to light when no matchMedia is available", () => {
    expect(resolveMode("auto", () => null)).toBe("light");
  });
});
