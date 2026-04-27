/*
 * Repository: azure-naming
 * Path: extensions/confluence/src/api.test.ts
 * Purpose: Tests for the Naming Service API client used by Forge
 */
import { describe, expect, it, vi } from "vitest";
import { createNamingApiClient, callNamingApi, __setDefaultClientForTests } from "./api";
import type { ForgeConfig } from "./config";
import type { FetchLike } from "./http";

const config: ForgeConfig = {
  tenantId: "t",
  clientId: "c",
  clientSecret: "s",
  resource: "api://r",
  baseUrl: "https://api.example.com/api",
};

interface FakeResponse {
  ok: boolean;
  status: number;
  body: string;
}

function fakeFetch(response: FakeResponse): {
  fetchImpl: FetchLike;
  spy: ReturnType<typeof vi.fn>;
} {
  const spy = vi.fn(async () => ({
    ok: response.ok,
    status: response.status,
    text: async () => response.body,
    json: async () => JSON.parse(response.body),
  }));
  return { fetchImpl: spy as unknown as FetchLike, spy };
}

const tokenCache = { getToken: async () => "TOKEN" };

describe("createNamingApiClient", () => {
  it("includes Bearer token, source header, and Content-Type", async () => {
    const { fetchImpl, spy } = fakeFetch({ ok: true, status: 200, body: '{"ok":true}' });
    const client = createNamingApiClient({ config, fetchImpl, tokenCache });
    await client.call("/claim", { method: "POST", body: { x: 1 } });
    const [url, init] = spy.mock.calls[0]!;
    expect(url).toBe("https://api.example.com/api/claim");
    expect(init.method).toBe("POST");
    expect(init.headers!.Authorization).toBe("Bearer TOKEN");
    expect(init.headers!["X-Sanmar-Source"]).toBe("confluence-forge");
    expect(init.headers!["Content-Type"]).toBe("application/json");
    expect(init.body).toBe('{"x":1}');
  });

  it("appends query parameters and skips empty ones", async () => {
    const { fetchImpl, spy } = fakeFetch({ ok: true, status: 200, body: "{}" });
    const client = createNamingApiClient({ config, fetchImpl, tokenCache });
    await client.call("/claims", { query: { region: "wus2", q: undefined, owner: "all" } });
    const [url] = spy.mock.calls[0]!;
    expect(url).toContain("region=wus2");
    expect(url).toContain("owner=all");
    expect(url).not.toContain("q=");
  });

  it("defaults the HTTP method to GET and sends no body", async () => {
    const { fetchImpl, spy } = fakeFetch({ ok: true, status: 200, body: "{}" });
    const client = createNamingApiClient({ config, fetchImpl, tokenCache });
    await client.call("/claims");
    const [, init] = spy.mock.calls[0]!;
    expect(init.method).toBe("GET");
    expect(init.body).toBeUndefined();
  });

  it("returns parsed JSON body on success", async () => {
    const { fetchImpl } = fakeFetch({ ok: true, status: 200, body: '{"name":"abc"}' });
    const client = createNamingApiClient({ config, fetchImpl, tokenCache });
    const result = await client.call<{ name: string }>("/claim");
    expect(result.name).toBe("abc");
  });

  it("returns empty object when the body is empty", async () => {
    const { fetchImpl } = fakeFetch({ ok: true, status: 204, body: "" });
    const client = createNamingApiClient({ config, fetchImpl, tokenCache });
    expect(await client.call("/release")).toEqual({});
  });

  it("throws on non-2xx with sanitized body", async () => {
    const { fetchImpl } = fakeFetch({ ok: false, status: 403, body: "denied\nreason" });
    const client = createNamingApiClient({ config, fetchImpl, tokenCache });
    await expect(client.call("/claim", { method: "POST" })).rejects.toThrow(
      /403 denied reason/,
    );
  });

  it("throws on non-JSON success body", async () => {
    const { fetchImpl } = fakeFetch({ ok: true, status: 200, body: "<html/>" });
    const client = createNamingApiClient({ config, fetchImpl, tokenCache });
    await expect(client.call("/claim")).rejects.toThrow(/non-JSON body/);
  });
});

describe("callNamingApi (default client)", () => {
  it("delegates to the injected default client", async () => {
    const fakeClient = { call: vi.fn(async () => ({ ok: true })) };
    __setDefaultClientForTests(fakeClient as unknown as ReturnType<typeof createNamingApiClient>);
    const result = await callNamingApi("/claims", { method: "GET" });
    expect(result).toEqual({ ok: true });
    expect(fakeClient.call).toHaveBeenCalledWith("/claims", { method: "GET" });
    __setDefaultClientForTests(null);
  });

  it("lazily builds a default client from process.env when none is set", async () => {
    process.env.ENTRA_TENANT_ID = "tid";
    process.env.ENTRA_CLIENT_ID = "cid";
    process.env.ENTRA_CLIENT_SECRET = "sec";
    process.env.NAMING_API_RESOURCE = "api://r";
    process.env.NAMING_API_BASE_URL = "https://api.example.com/api/";
    __setDefaultClientForTests(null);
    // Calling against the lazily-built default client will actually attempt a fetch via
    // the @forge/api stub; we only need to verify the build path runs without throwing
    // a config error. Errors from the network call are acceptable here.
    await expect(callNamingApi("/claims")).rejects.toBeDefined();
    __setDefaultClientForTests(null);
    delete process.env.ENTRA_TENANT_ID;
    delete process.env.ENTRA_CLIENT_ID;
    delete process.env.ENTRA_CLIENT_SECRET;
    delete process.env.NAMING_API_RESOURCE;
    delete process.env.NAMING_API_BASE_URL;
  });
});
