/*
 * Repository: azure-naming
 * Path: web/src/lib/storage.ts
 * Purpose: Defensive typed wrapper over Storage (sessionStorage / localStorage)
 * Author: GitHub Copilot
 * Created: 2026-04-27
 * Last-Modified: 2026-04-27
 * Version: 0.1.0
 */

/**
 * Minimal subset of the DOM Storage API we depend on.  Defining it locally
 * lets us inject in-memory storage for tests and SSR.
 */
export interface StorageLike {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

/**
 * In-memory fallback used when `window` / `localStorage` is unavailable
 * (server-side render, sandboxed iframe, privacy mode).
 */
export class MemoryStorage implements StorageLike {
  private readonly map = new Map<string, string>();
  getItem(key: string): string | null {
    return this.map.has(key) ? this.map.get(key)! : null;
  }
  setItem(key: string, value: string): void {
    this.map.set(key, value);
  }
  removeItem(key: string): void {
    this.map.delete(key);
  }
}

/** Returns `window.localStorage` if usable, else an in-memory shim. */
export function getDefaultStorage(): StorageLike {
  if (typeof window === "undefined") return new MemoryStorage();
  try {
    const probeKey = "__aznaming_probe__";
    window.localStorage.setItem(probeKey, "1");
    window.localStorage.removeItem(probeKey);
    return window.localStorage;
  } catch {
    return new MemoryStorage();
  }
}

/**
 * Read a string value, returning `fallback` when the key is missing.
 */
export function readString(
  storage: StorageLike,
  key: string,
  fallback: string,
): string {
  const value = storage.getItem(key);
  return value ?? fallback;
}

/**
 * Read a value constrained to a finite enum, returning `fallback` when the
 * stored value is missing or unrecognized.
 */
export function readEnum<T extends string>(
  storage: StorageLike,
  key: string,
  allowed: readonly T[],
  fallback: T,
): T {
  const value = storage.getItem(key);
  return value !== null && (allowed as readonly string[]).includes(value)
    ? (value as T)
    : fallback;
}

/**
 * Read a finite integer (within an inclusive range), returning `fallback`
 * when missing, non-numeric, or out of range.
 */
export function readInt(
  storage: StorageLike,
  key: string,
  fallback: number,
  min = Number.MIN_SAFE_INTEGER,
  max = Number.MAX_SAFE_INTEGER,
): number {
  const raw = storage.getItem(key);
  if (raw === null) return fallback;
  const parsed = Number(raw);
  if (!Number.isFinite(parsed) || !Number.isInteger(parsed)) return fallback;
  if (parsed < min || parsed > max) return fallback;
  return parsed;
}

/** Best-effort write — swallows quota / disabled-storage errors. */
export function writeString(storage: StorageLike, key: string, value: string): void {
  try {
    storage.setItem(key, value);
  } catch {
    // Storage may be full or disabled; we degrade gracefully.
  }
}
