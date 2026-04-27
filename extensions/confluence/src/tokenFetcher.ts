/*
 * Repository: azure-naming
 * Path: extensions/confluence/src/tokenFetcher.ts
 * Purpose: Real Entra client_credentials token fetcher (Forge runtime only)
 * Author: GitHub Copilot
 * Created: 2026-04-27
 * Last-Modified: 2026-04-27
 * Version: 0.1.0
 */
import type { ForgeConfig } from "./config";
import type { TokenFetcher, TokenResponse } from "./tokenCache";
import { sanitizeErrorBody, type FetchLike } from "./http";

/**
 * Build a TokenFetcher bound to a `fetch`-compatible function.  Splitting
 * this from the cache lets tests pass a stub fetcher.
 */
export function createTokenFetcher(fetchImpl: FetchLike): TokenFetcher {
  return async function fetchEntraToken(config: ForgeConfig): Promise<TokenResponse> {
    const body = new URLSearchParams({
      client_id: config.clientId,
      grant_type: "client_credentials",
      scope: `${config.resource}/.default`,
      client_secret: config.clientSecret,
    });
    const response = await fetchImpl(
      `https://login.microsoftonline.com/${config.tenantId}/oauth2/v2.0/token`,
      {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: body.toString(),
      },
    );
    if (!response.ok) {
      const errorBody = sanitizeErrorBody(await response.text());
      throw new Error(`Entra token request failed: ${response.status} ${errorBody}`);
    }
    const data = (await response.json()) as TokenResponse;
    if (!data?.access_token || typeof data.expires_in !== "number") {
      throw new Error("Entra token response missing access_token / expires_in");
    }
    return data;
  };
}
