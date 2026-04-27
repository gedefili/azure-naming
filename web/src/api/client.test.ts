/*
 * Repository: azure-naming
 * Path: web/src/api/client.test.ts
 * Purpose: Unit tests for the typed API surface
 */
import { describe, expect, it, vi } from "vitest";
import { clientFromRequester, createApiClient } from "./client";

describe("clientFromRequester", () => {
  function makeClient(): {
    request: ReturnType<typeof vi.fn>;
    client: ReturnType<typeof clientFromRequester>;
  } {
    const request = vi.fn().mockResolvedValue(undefined);
    const client = clientFromRequester(request as never);
    return { request, client };
  }

  it("listClaims sends GET /claims with params", async () => {
    const { request, client } = makeClient();
    await client.listClaims({ owner: "me", region: "wus2" });
    expect(request).toHaveBeenCalledWith("/claims", {
      method: "GET",
      query: { owner: "me", region: "wus2" },
      signal: undefined,
    });
  });

  it("claim sends POST /claim with body", async () => {
    const { request, client } = makeClient();
    await client.claim({ resource_type: "x", region: "y", environment: "z" });
    expect(request).toHaveBeenCalledWith("/claim", {
      method: "POST",
      body: { resource_type: "x", region: "y", environment: "z" },
      signal: undefined,
    });
  });

  it("release sends POST /release with the four named fields", async () => {
    const { request, client } = makeClient();
    await client.release("n", "wus2", "dev", "no longer needed");
    expect(request).toHaveBeenCalledWith("/release", {
      method: "POST",
      body: { name: "n", region: "wus2", environment: "dev", reason: "no longer needed" },
      signal: undefined,
    });
  });

  it("remediate sends POST /claims/remediate", async () => {
    const { request, client } = makeClient();
    await client.remediate("n", "wus2", "dev", "purge", "cleanup");
    expect(request).toHaveBeenCalledWith("/claims/remediate", {
      method: "POST",
      body: { name: "n", region: "wus2", environment: "dev", action: "purge", reason: "cleanup" },
      signal: undefined,
    });
  });

  it("audit sends GET /audit with query params", async () => {
    const { request, client } = makeClient();
    await client.audit("n", "wus2", "dev");
    expect(request).toHaveBeenCalledWith("/audit", {
      method: "GET",
      query: { name: "n", region: "wus2", environment: "dev" },
      signal: undefined,
    });
  });

  it("forwards optional signal", async () => {
    const { request, client } = makeClient();
    const ctl = new AbortController();
    await client.listClaims({}, ctl.signal);
    expect(request).toHaveBeenCalledWith("/claims", expect.objectContaining({ signal: ctl.signal }));
  });
});

describe("createApiClient", () => {
  it("composes a Requester from injected fetch and exposes the API surface", async () => {
    const fetchImpl = vi.fn(async () => ({
      ok: true,
      status: 200,
      text: async () => '{"items":[],"count":0,"scope":"me","is_admin":false}',
    })) as unknown as typeof fetch;
    const client = createApiClient(async () => "TOKEN", { baseUrl: "/api", fetchImpl });
    const result = await client.listClaims();
    expect(result.count).toBe(0);
    expect(result.is_admin).toBe(false);
  });
});
