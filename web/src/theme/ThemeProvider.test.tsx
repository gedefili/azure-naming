/*
 * Repository: azure-naming
 * Path: web/src/theme/ThemeProvider.test.tsx
 * Purpose: Tests for ThemeProvider state, persistence, and matchMedia listener
 */
import { describe, expect, it, vi, beforeEach } from "vitest";
import { act, render, renderHook } from "@testing-library/react";
import { ThemeProvider, useTheme, MODE_KEY, HUE_KEY } from "./ThemeProvider";
import { MemoryStorage } from "../lib/storage";

function wrapper(storage = new MemoryStorage(), seed: string | undefined = "alice"): {
  Wrapper: React.FC<{ children: React.ReactNode }>;
  storage: MemoryStorage;
} {
  const Wrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => (
    <ThemeProvider seed={seed} storage={storage}>
      {children}
    </ThemeProvider>
  );
  return { Wrapper, storage };
}

describe("ThemeProvider", () => {
  beforeEach(() => {
    document.documentElement.removeAttribute("data-theme");
  });

  it("provides defaults and exposes setMode/setHue", () => {
    const { Wrapper } = wrapper();
    const { result } = renderHook(() => useTheme(), { wrapper: Wrapper });
    expect(result.current.mode).toBe("auto");
    expect(typeof result.current.setMode).toBe("function");
    expect(typeof result.current.setHue).toBe("function");
  });

  it("persists mode changes to storage", () => {
    const storage = new MemoryStorage();
    const { Wrapper } = wrapper(storage);
    const { result } = renderHook(() => useTheme(), { wrapper: Wrapper });
    act(() => result.current.setMode("dark"));
    expect(result.current.mode).toBe("dark");
    expect(storage.getItem(MODE_KEY)).toBe("dark");
  });

  it("persists hue with clamping", () => {
    const storage = new MemoryStorage();
    const { Wrapper } = wrapper(storage);
    const { result } = renderHook(() => useTheme(), { wrapper: Wrapper });
    act(() => result.current.setHue(999));
    expect(result.current.hue).toBe(360);
    expect(storage.getItem(HUE_KEY)).toBe("360");
    act(() => result.current.setHue(-50));
    expect(result.current.hue).toBe(0);
  });

  it("reads stored mode/hue on init", () => {
    const storage = new MemoryStorage();
    storage.setItem(MODE_KEY, "light");
    storage.setItem(HUE_KEY, "180");
    const { Wrapper } = wrapper(storage);
    const { result } = renderHook(() => useTheme(), { wrapper: Wrapper });
    expect(result.current.mode).toBe("light");
    expect(result.current.hue).toBe(180);
  });

  it("falls back to derived hue on invalid stored values", () => {
    const storage = new MemoryStorage();
    storage.setItem(HUE_KEY, "not-a-number");
    const { Wrapper } = wrapper(storage, "alice");
    const { result } = renderHook(() => useTheme(), { wrapper: Wrapper });
    expect(result.current.hue).toBeGreaterThanOrEqual(0);
    expect(result.current.hue).toBeLessThanOrEqual(360);
  });

  it("applies CSS tokens to documentElement", () => {
    const { Wrapper } = wrapper();
    render(
      <Wrapper>
        <div />
      </Wrapper>,
    );
    expect(document.documentElement.dataset.theme).toMatch(/light|dark/);
    expect(document.documentElement.style.getPropertyValue("--accent")).toBeTruthy();
  });

  it("throws when useTheme is used outside provider", () => {
    const consoleErr = vi.spyOn(console, "error").mockImplementation(() => undefined);
    expect(() => renderHook(() => useTheme())).toThrow(/ThemeProvider/);
    consoleErr.mockRestore();
  });
});
