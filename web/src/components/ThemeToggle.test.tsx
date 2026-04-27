/*
 * Repository: azure-naming
 * Path: web/src/components/ThemeToggle.test.tsx
 * Purpose: Tests for ThemeToggle button behaviour
 */
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ThemeProvider } from "../theme/ThemeProvider";
import { ThemeToggle, NEXT_MODE } from "./ThemeToggle";
import { MemoryStorage } from "../lib/storage";

function setup() {
  const storage = new MemoryStorage();
  render(
    <ThemeProvider seed="alice" storage={storage}>
      <ThemeToggle />
    </ThemeProvider>,
  );
  return storage;
}

describe("ThemeToggle", () => {
  it("cycles through the three modes", async () => {
    setup();
    const button = screen.getByRole("button");
    expect(button.getAttribute("aria-label")).toContain("auto");
    await userEvent.click(button);
    expect(button.getAttribute("aria-label")).toContain("light");
    await userEvent.click(button);
    expect(button.getAttribute("aria-label")).toContain("dark");
    await userEvent.click(button);
    expect(button.getAttribute("aria-label")).toContain("auto");
  });

  it("NEXT_MODE forms a closed cycle", () => {
    expect(NEXT_MODE.auto).toBe("light");
    expect(NEXT_MODE.light).toBe("dark");
    expect(NEXT_MODE.dark).toBe("auto");
  });
});
