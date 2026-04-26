/*
 * Repository: azure-naming
 * Path: web/src/api/client.ts
 * Purpose: Thin fetch wrapper that injects the Entra access token and source header
 * Author: GitHub Copilot
 * Created: 2026-04-26
 * Last-Modified: 2026-04-26
 * Version: 0.1.0
 */

const API_BASE_URL =
  import.meta.env.VITE_NAMING_API_BASE_URL ?? "/api";

export class ApiError extends Error {
  status: number;
  body: string;
  constructor(status: number, body: string, message?: string) {
    super(message ?? `API error ${status}`);
    this.status = status;
    this.body = body;
  }
}

export interface ClaimsListResponse {
  items: ClaimSummary[];
  count: number;
  scope: string;
  is_admin: boolean;
  continuation?: string;
}

export interface ClaimSummary {
  name: string;
  resource_type?: string;
  region?: string;
  environment?: string;
  in_use?: boolean;
  claim_state?: string;
  claimed_by?: string;
  claimed_at?: string;
  released_by?: string;
  released_at?: string;
  release_reason?: string;
  state_changed_by?: string;
  state_changed_at?: string;
  state_version?: number;
  orphaned_by?: string;
  orphaned_at?: string;
  orphan_reason?: string;
  slug?: string;
  project?: string;
  purpose?: string;
  subsystem?: string;
  system?: string;
  index?: string;
}

export interface ClaimRequestBody {
  resource_type: string;
  region: string;
  environment: string;
  project?: string;
  purpose?: string;
  subsystem?: string;
  system?: string;
  index?: string;
}

export interface ClaimResponse {
  name: string;
  resourceType: string;
  region: string;
  environment: string;
  slug: string;
  claimedBy: string;
}

export interface ListClaimsParams {
  owner?: string;
  region?: string;
  environment?: string;
  resource_type?: string;
  project?: string;
  state?: string;
  in_use?: boolean;
  query?: string;
  limit?: number;
  continuation?: string;
}

function buildUrl(path: string, params?: Record<string, string | number | boolean | undefined>): string {
  const url = new URL(path.startsWith("http") ? path : `${API_BASE_URL}${path}`, window.location.origin);
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v === undefined || v === null || v === "") continue;
      url.searchParams.set(k, String(v));
    }
  }
  return url.toString();
}

export interface ApiClient {
  listClaims(params?: ListClaimsParams): Promise<ClaimsListResponse>;
  claim(body: ClaimRequestBody): Promise<ClaimResponse>;
  release(name: string, region: string, environment: string, reason: string): Promise<void>;
  remediate(
    name: string,
    region: string,
    environment: string,
    action: "orphan" | "purge",
    reason: string,
  ): Promise<void>;
  audit(name: string, region: string, environment: string): Promise<unknown>;
}

export function createApiClient(getToken: () => Promise<string | null>): ApiClient {
  async function call<T>(path: string, init: RequestInit = {}, params?: Record<string, string | number | boolean | undefined>): Promise<T> {
    const token = await getToken();
    if (!token) {
      throw new ApiError(401, "", "Not signed in");
    }
    const headers = new Headers(init.headers);
    headers.set("Authorization", `Bearer ${token}`);
    headers.set("X-Sanmar-Source", "web");
    if (init.body && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }

    const res = await fetch(buildUrl(path, params), { ...init, headers });
    const text = await res.text();
    if (!res.ok) {
      throw new ApiError(res.status, text);
    }
    return text ? (JSON.parse(text) as T) : (undefined as T);
  }

  return {
    listClaims: (params) => call<ClaimsListResponse>("/claims", { method: "GET" }, params as Record<string, string | number | boolean | undefined>),
    claim: (body) => call<ClaimResponse>("/claim", { method: "POST", body: JSON.stringify(body) }),
    release: (name, region, environment, reason) =>
      call<void>("/release", {
        method: "POST",
        body: JSON.stringify({ name, region, environment, reason }),
      }),
    remediate: (name, region, environment, action, reason) =>
      call<void>("/claims/remediate", {
        method: "POST",
        body: JSON.stringify({ name, region, environment, action, reason }),
      }),
    audit: (name, region, environment) =>
      call<unknown>("/audit", { method: "GET" }, { name, region, environment }),
  };
}
