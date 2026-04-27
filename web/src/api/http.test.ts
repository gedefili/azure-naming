/*
 * Repository: azure-naming
 * Path: web/src/api/http.test.ts
 * Purpose: Unit tests for the request transport
 */
import { describe, expect, it, vi } from "vitest";
import { createRequester, SOURCE_HEADER, SOURCE_VALUE } from "./http";
import { ApiError } from "./errors";

function fakeFetch(opts: { ok: boolean; status: number; body: string }): {
  fetchImpl: typeof fetch;
  spy: ReturnType<typeof vi.fn>;
} {
  const spy = vi.fn(async () => ({
    ok: opts.ok,
    status: opts.status,
    text: async () => opts.body,
  })) as unknown as ReturnType<typeof vi.fn>;
  return { fetchImpl: spy as unknown as typeof fetch, spy };
}

describe("createRequester", () => {
  it("attaches Bearer token, source header, and JSON content-type", async () => {
    const { fetchImpl, spy } = fakeFetch({ ok: true, status: 200, body: '{"ok":true}' });
    const request = createRequester({
      baseUrl: "/api",
      getToken: async () => "TKN",
      fetchImpl,
    });
    const result = await request<{ ok: boolean }>("/claim", {
      method: "POST",
      body: { x: 1 },
    });
    expect(result).toEqual({ ok: true });
    const [url, init] = spy.mock.calls[0]!;
    expect(url).toBe("/api/claim");
    expect((init as RequestInit).method).toBe("POST");
    const headers = (init as RequestInit).headers as Headers;
    expect(headers.get("Authorization")).toBe("Bearer TKN");
    expect(headers.get(SOURCE_HEADER)).toBe(SOURCE_VALUE);
    expect(headers.get("Content-Type")).toBe("application/json");
    expect((init as RequestInit).body).toBe('{"x":1}');
    expect((init as RequestInit).credentials).toBe("omit");
  });

  it("appends query parameters", async () => {
    const { fetchImpl, spy } = fakeFetch({ ok: true, status: 200, body: "{}" });
    const request = createRequester({
      baseUrl: "/api",
      getToken: async () => "TKN",
      fetchImpl,
    });
    await request("/claims", { query: { region: "wus2", q: undefined } });
    const [url] = spy.mock.calls[0]!;
    expect(url).toBe("/api/claims?region=wus2");
  });

  it("sends string body verbatim and uses GET as default", async () => {
    const { fetchImpl, spy } = fakeFetch({ ok: true, status: 200, body: "{}" });
    const request = createRequester({
      baseUrl: "/api",
      getToken: async () => "TKN",
      fetchImpl,
    });
    await request("/x", { body: "raw=value", contentType: "application/x-www-form-urlencoded" });
    const [, init] = spy.mock.calls[0]!;
    expect((init as RequestInit).body).toBe("raw=value");
    const headers = (init as RequestInit).headers as Headers;
    expect(headers.get("Content-Type")).toBe("application/x-www-form-urlencoded");
  });

  it("throws ApiError when no token is available", async () => {
    const { fetchImpl } = fakeFetch({ ok: true, status: 200, body: "{}" });
    const request = createRequester({
      baseUrl: "/api",
      getToken: async () => null,
      fetchImpl,
    });
    await expect(request("/x")).rejects.toBeInstanceOf(ApiError);
    await expect(request("/x")).rejects.toMatchObject({ status: 401 });
  });

  it("throws ApiError on non-2xx with body", async () => {
    const { fetchImpl } = fakeFetch({ ok: false, status: 500, body: "boom" });
    const request = createRequester({
      baseUrl: "/api",
      getToken: async () => "TKN",
      fetchImpl,
    });
    try {
      await request("/x");
      expect.fail("Expected throw");
    } catch (err) {
      expect(err).toBeInstanceOf(ApiError);
      expect((err as ApiError).status).toBe(500);
      expect((err as ApiError).body).toBe("boom");
    }
  });

  it("returns undefined when body is empty", async () => {
    const { fetchImpl } = fakeFetch({ ok: true, status: 204, body: "" });
    const request = createRequester({
      baseUrl: "/api",
      getToken: async () => "TKN",
      fetchImpl,
    });
    expect(await request("/x")).toBeUndefined();
  });

  it("forwards AbortSignal", async () => {
    const { fetchImpl, spy } = fakeFetch({ ok: true, status: 200, body: "{}" });
    const request = createRequester({
      baseUrl: "/api",
      getToken: async () => "TKN",
      fetchImpl,
    });
    const controller = new AbortController();
    await request("/x", { signal: controller.signal });
    const [, init] = spy.mock.calls[0]!;
    expect((init as RequestInit).signal).toBe(controller.signal);
  });
});
