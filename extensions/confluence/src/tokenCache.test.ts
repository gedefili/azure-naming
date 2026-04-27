/*
 * Repository: azure-naming
 * Path: extensions/confluence/src/tokenCache.test.ts
 * Purpose: Tests for TokenCache caching, refresh, and error semantics
 */
import { describe, expect, it, vi } from "vitest";
import { REFRESH_SKEW_MS, TokenCache } from "./tokenCache";
import type { ForgeConfig } from "./config";

const config: ForgeConfig = {
  tenantId: "t",
  clientId: "c",
  clientSecret: "s",
  resource: "api://r",
  baseUrl: "https://api",
};

describe("TokenCache", () => {
  it("calls the fetcher on first access", async () => {
    const fetcher = vi.fn().mockResolvedValue({ access_token: "abc", expires_in: 3600 });
    const cache = new TokenCache(config, fetcher, () => 1_000_000);
    expect(await cache.getToken()).toBe("abc");
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("returns cached token while inside the refresh window", async () => {
    const fetcher = vi.fn().mockResolvedValue({ access_token: "abc", expires_in: 3600 });
    let now = 1_000_000;
    const cache = new TokenCache(config, fetcher, () => now);
    await cache.getToken();
    now += 1000; // far below skew
    expect(await cache.getToken()).toBe("abc");
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("refreshes when within skew of expiry", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce({ access_token: "old", expires_in: 60 })
      .mockResolvedValueOnce({ access_token: "new", expires_in: 60 });
    let now = 0;
    const cache = new TokenCache(config, fetcher, () => now);
    await cache.getToken();
    now += 60_000 - REFRESH_SKEW_MS + 1; // just past the skew threshold
    expect(await cache.getToken()).toBe("new");
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("propagates fetcher errors and does not cache", async () => {
    const fetcher = vi.fn().mockRejectedValue(new Error("boom"));
    const cache = new TokenCache(config, fetcher, () => 0);
    await expect(cache.getToken()).rejects.toThrow("boom");
    await expect(cache.getToken()).rejects.toThrow("boom");
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("rejects when fetcher returns no access_token", async () => {
    const fetcher = vi.fn().mockResolvedValue({ access_token: "", expires_in: 60 } as never);
    const cache = new TokenCache(config, fetcher, () => 0);
    await expect(cache.getToken()).rejects.toThrow(/no access_token/);
  });

  it("invalidate forces a refresh", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce({ access_token: "a", expires_in: 3600 })
      .mockResolvedValueOnce({ access_token: "b", expires_in: 3600 });
    const cache = new TokenCache(config, fetcher, () => 0);
    await cache.getToken();
    cache.invalidate();
    expect(await cache.getToken()).toBe("b");
  });
});
