/*
 * Repository: azure-naming
 * Path: extensions/confluence/src/resolvers.ts
 * Purpose: Pure resolver implementations callable directly from tests
 * Author: GitHub Copilot
 * Created: 2026-04-27
 * Last-Modified: 2026-04-27
 * Version: 0.1.0
 */
import type { ApiCallOptions, NamingApiClient } from "./api";

export interface ListClaimsPayload {
  region?: string;
  environment?: string;
  query?: string;
  owner?: string;
}

export interface ClaimPayload {
  resource_type: string;
  region: string;
  environment: string;
  project?: string;
  purpose?: string;
}

export interface ReleasePayload {
  name: string;
  region: string;
  environment: string;
  reason: string;
}

export interface ResolverApi {
  call<T = unknown>(path: string, opts?: ApiCallOptions): Promise<T>;
}

const FORGE_SOURCE = "confluence-forge";

export async function listClaims(api: ResolverApi, payload: ListClaimsPayload | null): Promise<unknown> {
  const safe = payload ?? {};
  return api.call("/claims", {
    method: "GET",
    query: {
      region: safe.region,
      environment: safe.environment,
      q: safe.query,
      owner: safe.owner ?? "all",
    },
  });
}

export async function createClaim(api: ResolverApi, payload: ClaimPayload): Promise<unknown> {
  return api.call("/claim", {
    method: "POST",
    body: { ...payload, source: FORGE_SOURCE },
  });
}

export async function releaseClaim(api: ResolverApi, payload: ReleasePayload): Promise<unknown> {
  return api.call("/release", {
    method: "POST",
    body: payload,
  });
}

/**
 * Bind the resolver functions to a concrete API client.  The Forge `index.tsx`
 * file calls this once and registers the returned handlers with the SDK.
 */
export function bindResolvers(client: NamingApiClient): {
  listClaims: (payload?: ListClaimsPayload | null) => Promise<unknown>;
  claim: (payload: ClaimPayload) => Promise<unknown>;
  release: (payload: ReleasePayload) => Promise<unknown>;
} {
  return {
    listClaims: (payload) => listClaims(client, payload ?? null),
    claim: (payload) => createClaim(client, payload),
    release: (payload) => releaseClaim(client, payload),
  };
}
