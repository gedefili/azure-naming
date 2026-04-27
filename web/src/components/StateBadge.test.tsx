/*
 * Repository: azure-naming
 * Path: web/src/components/StateBadge.test.tsx
 * Purpose: Tests for StateBadge classification and rendering
 */
import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { StateBadge, classifyState } from "./StateBadge";

describe("classifyState", () => {
  it("maps known states", () => {
    expect(classifyState("claimed")).toBe("claimed");
    expect(classifyState("orphaned")).toBe("orphaned");
    expect(classifyState("released")).toBe("released");
  });
  it("treats unknown / null as released", () => {
    expect(classifyState(undefined)).toBe("released");
    expect(classifyState(null)).toBe("released");
    expect(classifyState("alien")).toBe("released");
  });
  it("is case-insensitive", () => {
    expect(classifyState("CLAIMED")).toBe("claimed");
  });
});

describe("StateBadge", () => {
  it("renders the lowercased state with class", () => {
    const { container } = render(<StateBadge state="Claimed" />);
    const badge = container.querySelector("span")!;
    expect(badge.className).toContain("badge");
    expect(badge.className).toContain("claimed");
    expect(badge.textContent).toBe("claimed");
  });
});
