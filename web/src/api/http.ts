/*
 * Repository: azure-naming
 * Path: web/src/api/http.ts
 * Purpose: Transport-only HTTP layer for the Naming Service API
 * Author: GitHub Copilot
 * Created: 2026-04-27
 * Last-Modified: 2026-04-27
 * Version: 0.1.0
 */
import { buildUrl, type QueryParams } from "../lib/url";
import { safeJsonParse } from "../lib/json";
import { ApiError } from "./errors";

/**
 * Identifies the request origin in audit logs.  Held as a constant so it
 * cannot drift between call sites.
 */
export const SOURCE_HEADER = "X-Sanmar-Source";
export const SOURCE_VALUE = "web";

/** Async token provider returning an access token, an empty string, or null. */
export type TokenProvider = () => Promise<string | null>;

export interface HttpOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  query?: QueryParams;
  body?: unknown;
  /** Content-type for the request body (defaults to JSON when body is set). */
  contentType?: string;
  /** Optional abort signal forwarded to fetch. */
  signal?: AbortSignal;
}

export interface HttpClientDeps {
  baseUrl: string;
  getToken: TokenProvider;
  fetchImpl?: typeof fetch;
}

/** A typed HTTP request function bound to a base URL and token provider. */
export type Requester = <T>(path: string, opts?: HttpOptions) => Promise<T>;

/**
 * Build a Requester.  Pure factory — accepts an injectable `fetchImpl` and
 * `getToken` so that tests can swap them out without monkey-patching globals.
 */
export function createRequester(deps: HttpClientDeps): Requester {
  const fetchImpl = deps.fetchImpl ?? fetch;
  return async function request<T>(path: string, opts: HttpOptions = {}): Promise<T> {
    const token = await deps.getToken();
    if (!token) {
      throw new ApiError(401, "", "Not signed in");
    }

    const headers = new Headers();
    headers.set("Authorization", `Bearer ${token}`);
    headers.set(SOURCE_HEADER, SOURCE_VALUE);
    headers.set("Accept", "application/json");

    let body: BodyInit | undefined;
    if (opts.body !== undefined) {
      body = typeof opts.body === "string" ? opts.body : JSON.stringify(opts.body);
      headers.set("Content-Type", opts.contentType ?? "application/json");
    }

    const url = buildUrl(deps.baseUrl, path, opts.query);
    const response = await fetchImpl(url, {
      method: opts.method ?? "GET",
      headers,
      body,
      signal: opts.signal,
      // Do not send cookies — we use bearer tokens.
      credentials: "omit",
    });

    const text = await response.text();
    if (!response.ok) {
      throw new ApiError(response.status, text);
    }
    return safeJsonParse<T>(text, undefined as T);
  };
}
