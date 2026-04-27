/*
 * Repository: azure-naming
 * Path: web/src/api/client.ts
 * Purpose: Typed Naming Service API surface backed by an injectable Requester
 * Author: GitHub Copilot
 * Created: 2026-04-26
 * Last-Modified: 2026-04-27
 * Version: 0.2.0
 */
import { createRequester, type HttpClientDeps, type Requester } from "./http";
import type {
  ClaimsListResponse,
  ClaimRequestBody,
  ClaimResponse,
  ListClaimsParams,
  RemediateAction,
} from "./types";

export type {
  ClaimSummary,
  ClaimsListResponse,
  ClaimRequestBody,
  ClaimResponse,
  ListClaimsParams,
  RemediateAction,
} from "./types";
export { ApiError, RedirectingError, isApiError } from "./errors";

export const DEFAULT_API_BASE_URL: string = ((): string => {
  const raw = (import.meta.env.VITE_NAMING_API_BASE_URL ?? "/api") as string;
  return raw.replace(/\/+$/, "") || "/api";
})();

export interface ApiClient {
  listClaims(params?: ListClaimsParams, signal?: AbortSignal): Promise<ClaimsListResponse>;
  claim(body: ClaimRequestBody, signal?: AbortSignal): Promise<ClaimResponse>;
  release(
    name: string,
    region: string,
    environment: string,
    reason: string,
    signal?: AbortSignal,
  ): Promise<void>;
  remediate(
    name: string,
    region: string,
    environment: string,
    action: RemediateAction,
    reason: string,
    signal?: AbortSignal,
  ): Promise<void>;
  audit(
    name: string,
    region: string,
    environment: string,
    signal?: AbortSignal,
  ): Promise<unknown>;
}

/** Build an `ApiClient` over a pre-built `Requester` (preferred for tests). */
export function clientFromRequester(request: Requester): ApiClient {
  return {
    listClaims: (params, signal) =>
      request<ClaimsListResponse>("/claims", {
        method: "GET",
        query: params as Record<string, string | number | boolean | undefined> | undefined,
        signal,
      }),
    claim: (body, signal) =>
      request<ClaimResponse>("/claim", { method: "POST", body, signal }),
    release: (name, region, environment, reason, signal) =>
      request<void>("/release", {
        method: "POST",
        body: { name, region, environment, reason },
        signal,
      }),
    remediate: (name, region, environment, action, reason, signal) =>
      request<void>("/claims/remediate", {
        method: "POST",
        body: { name, region, environment, action, reason },
        signal,
      }),
    audit: (name, region, environment, signal) =>
      request<unknown>("/audit", {
        method: "GET",
        query: { name, region, environment },
        signal,
      }),
  };
}

/** Build an `ApiClient` from raw deps. */
export function createApiClient(
  getToken: HttpClientDeps["getToken"],
  options: { baseUrl?: string; fetchImpl?: typeof fetch } = {},
): ApiClient {
  const requester = createRequester({
    getToken,
    baseUrl: options.baseUrl ?? DEFAULT_API_BASE_URL,
    fetchImpl: options.fetchImpl,
  });
  return clientFromRequester(requester);
}
