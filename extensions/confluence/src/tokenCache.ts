/*
 * Repository: azure-naming
 * Path: extensions/confluence/src/tokenCache.ts
 * Purpose: Testable cache for Entra access tokens with injectable clock + fetcher
 * Author: GitHub Copilot
 * Created: 2026-04-27
 * Last-Modified: 2026-04-27
 * Version: 0.1.0
 */
import type { ForgeConfig } from "./config";

export interface TokenResponse {
  access_token: string;
  expires_in: number;
}

export interface TokenFetcher {
  (config: ForgeConfig): Promise<TokenResponse>;
}

interface CachedToken {
  token: string;
  expiresAt: number;
}

/** Margin (ms) before actual expiry that we treat the token as expired. */
export const REFRESH_SKEW_MS = 60_000;

export class TokenCache {
  private cached: CachedToken | null = null;

  constructor(
    private readonly config: ForgeConfig,
    private readonly fetcher: TokenFetcher,
    private readonly now: () => number = Date.now,
  ) {}

  async getToken(): Promise<string> {
    const current = this.cached;
    if (current && current.expiresAt - this.now() > REFRESH_SKEW_MS) {
      return current.token;
    }
    const response = await this.fetcher(this.config);
    if (!response?.access_token) {
      throw new Error("Token fetcher returned no access_token");
    }
    this.cached = {
      token: response.access_token,
      expiresAt: this.now() + response.expires_in * 1000,
    };
    return this.cached.token;
  }

  /** Drop any cached token. */
  invalidate(): void {
    this.cached = null;
  }
}
