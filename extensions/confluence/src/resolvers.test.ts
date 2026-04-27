/*
 * Repository: azure-naming
 * Path: extensions/confluence/src/resolvers.test.ts
 * Purpose: Tests for resolver dispatch and payload shaping
 */
import { describe, expect, it, vi } from "vitest";
import { bindResolvers, createClaim, listClaims, releaseClaim } from "./resolvers";

function makeApi(): { call: ReturnType<typeof vi.fn> } {
  return { call: vi.fn().mockResolvedValue({ ok: true }) };
}

describe("listClaims", () => {
  it("defaults owner to all when payload is null", async () => {
    const api = makeApi();
    await listClaims(api, null);
    expect(api.call).toHaveBeenCalledWith("/claims", {
      method: "GET",
      query: { region: undefined, environment: undefined, q: undefined, owner: "all" },
    });
  });

  it("forwards region/environment/query/owner overrides", async () => {
    const api = makeApi();
    await listClaims(api, { region: "wus2", environment: "dev", query: "foo", owner: "me" });
    expect(api.call).toHaveBeenCalledWith("/claims", {
      method: "GET",
      query: { region: "wus2", environment: "dev", q: "foo", owner: "me" },
    });
  });
});

describe("createClaim", () => {
  it("posts body and tags the source header", async () => {
    const api = makeApi();
    await createClaim(api, {
      resource_type: "storage_account",
      region: "wus2",
      environment: "dev",
      project: "p",
    });
    expect(api.call).toHaveBeenCalledWith("/claim", {
      method: "POST",
      body: {
        resource_type: "storage_account",
        region: "wus2",
        environment: "dev",
        project: "p",
        source: "confluence-forge",
      },
    });
  });
});

describe("releaseClaim", () => {
  it("posts release payload to /release", async () => {
    const api = makeApi();
    await releaseClaim(api, { name: "n", region: "wus2", environment: "dev", reason: "done" });
    expect(api.call).toHaveBeenCalledWith("/release", {
      method: "POST",
      body: { name: "n", region: "wus2", environment: "dev", reason: "done" },
    });
  });
});

describe("bindResolvers", () => {
  it("delegates to the underlying client", async () => {
    const api = makeApi();
    const handlers = bindResolvers(api as never);
    await handlers.listClaims();
    await handlers.claim({ resource_type: "x", region: "wus2", environment: "dev" });
    await handlers.release({ name: "n", region: "r", environment: "e", reason: "why" });
    expect(api.call).toHaveBeenCalledTimes(3);
  });
});
