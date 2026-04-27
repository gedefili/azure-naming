/*
 * Repository: azure-naming
 * Path: web/src/lib/storage.test.ts
 * Purpose: Unit tests for the Storage adapters
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  MemoryStorage,
  getDefaultStorage,
  readEnum,
  readInt,
  readString,
  writeString,
} from "./storage";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("MemoryStorage", () => {
  it("supports get/set/remove and returns null for missing keys", () => {
    const s = new MemoryStorage();
    expect(s.getItem("k")).toBeNull();
    s.setItem("k", "v");
    expect(s.getItem("k")).toBe("v");
    s.removeItem("k");
    expect(s.getItem("k")).toBeNull();
  });
});

describe("readString / readEnum / readInt", () => {
  it("readString returns fallback when missing", () => {
    const s = new MemoryStorage();
    expect(readString(s, "k", "default")).toBe("default");
    s.setItem("k", "v");
    expect(readString(s, "k", "default")).toBe("v");
  });

  it("readEnum gates against an allowlist", () => {
    const s = new MemoryStorage();
    s.setItem("mode", "alien");
    expect(readEnum(s, "mode", ["a", "b"] as const, "a")).toBe("a");
    s.setItem("mode", "b");
    expect(readEnum(s, "mode", ["a", "b"] as const, "a")).toBe("b");
  });

  it("readInt rejects non-numeric, non-integer, and out-of-range", () => {
    const s = new MemoryStorage();
    expect(readInt(s, "k", 99)).toBe(99);
    s.setItem("k", "abc");
    expect(readInt(s, "k", 99)).toBe(99);
    s.setItem("k", "3.5");
    expect(readInt(s, "k", 99)).toBe(99);
    s.setItem("k", "5");
    expect(readInt(s, "k", 99, 0, 10)).toBe(5);
    s.setItem("k", "1000");
    expect(readInt(s, "k", 99, 0, 10)).toBe(99);
  });
});

describe("writeString", () => {
  it("writes through normal storage", () => {
    const s = new MemoryStorage();
    writeString(s, "k", "v");
    expect(s.getItem("k")).toBe("v");
  });

  it("swallows storage errors", () => {
    const broken = {
      getItem: () => null,
      setItem: () => {
        throw new Error("quota");
      },
      removeItem: () => undefined,
    };
    expect(() => writeString(broken, "k", "v")).not.toThrow();
  });
});

describe("getDefaultStorage", () => {
  it("returns localStorage when usable", () => {
    const result = getDefaultStorage();
    result.setItem("aznaming.probe.value", "1");
    expect(result.getItem("aznaming.probe.value")).toBe("1");
    result.removeItem("aznaming.probe.value");
  });

  it("falls back to memory when localStorage throws", () => {
    const original = window.localStorage;
    Object.defineProperty(window, "localStorage", {
      configurable: true,
      get: () => ({
        getItem: () => null,
        setItem: () => {
          throw new Error("blocked");
        },
        removeItem: () => undefined,
      }),
    });
    try {
      const fallback = getDefaultStorage();
      fallback.setItem("k", "v");
      expect(fallback.getItem("k")).toBe("v");
    } finally {
      Object.defineProperty(window, "localStorage", {
        configurable: true,
        value: original,
      });
    }
  });
});
