/*
 * Repository: azure-naming
 * Path: extensions/confluence/src/api.ts
 * Purpose: Naming Service HTTP client used by Forge resolvers and the macro
 * Author: GitHub Copilot
 * Created: 2026-04-26
 * Last-Modified: 2026-04-27
 * Version: 0.2.0
 */
import { fetch as forgeFetch } from "@forge/api";
import { loadConfig, type ForgeConfig } from "./config";
import { TokenCache } from "./tokenCache";
import { createTokenFetcher } from "./tokenFetcher";
import {
  buildQueryString,
  joinPath,
  sanitizeErrorBody,
  FORGE_SOURCE,
  SOURCE_HEADER,
  type FetchLike,
} from "./http";

export interface ApiCallOptions {
  method?: "GET" | "POST" | "DELETE" | "PUT" | "PATCH";
  body?: unknown;
  query?: Record<string, string | undefined | null>;
}

export interface NamingApiClient {
  call<T = unknown>(path: string, opts?: ApiCallOptions): Promise<T>;
}

/**
 * Pure factory used by tests — caller supplies the config, fetcher, and a
 * pre-built TokenCache so all dependencies are explicit.
 */
export function createNamingApiClient(deps: {
  config: ForgeConfig;
  fetchImpl: FetchLike;
  tokenCache: Pick<TokenCache, "getToken">;
}): NamingApiClient {
  return {
    async call<T = unknown>(path: string, opts: ApiCallOptions = {}): Promise<T> {
      const token = await deps.tokenCache.getToken();
      const url = `${joinPath(deps.config.baseUrl, path)}${buildQueryString(opts.query)}`;
      const response = await deps.fetchImpl(url, {
        method: opts.method ?? "GET",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
          [SOURCE_HEADER]: FORGE_SOURCE,
        },
        body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
      });
      const text = await response.text();
      if (!response.ok) {
        throw new Error(
          `Naming API ${opts.method ?? "GET"} ${path} failed: ${response.status} ${sanitizeErrorBody(text)}`,
        );
      }
      if (!text) return {} as T;
      try {
        return JSON.parse(text) as T;
      } catch {
        throw new Error(`Naming API returned non-JSON body for ${path}`);
      }
    },
  };
}

let defaultClient: NamingApiClient | null = null;

function getDefaultClient(): NamingApiClient {
  if (defaultClient) return defaultClient;
  const config = loadConfig();
  const tokenCache = new TokenCache(config, createTokenFetcher(forgeFetch as unknown as FetchLike));
  defaultClient = createNamingApiClient({
    config,
    fetchImpl: forgeFetch as unknown as FetchLike,
    tokenCache,
  });
  return defaultClient;
}

/** Forge runtime entrypoint used by `index.tsx` and resolvers. */
export async function callNamingApi<T = unknown>(
  path: string,
  opts: ApiCallOptions = {},
): Promise<T> {
  return getDefaultClient().call<T>(path, opts);
}

/** Test hook: replace the runtime client (e.g. in `beforeEach`). */
export function __setDefaultClientForTests(client: NamingApiClient | null): void {
  defaultClient = client;
}
