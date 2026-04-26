/*
 * Repository: azure-naming
 * Path: extensions/confluence/src/api.ts
 * Purpose: Backend HTTP client for the Azure Naming API with Entra token caching
 * Author: GitHub Copilot
 * Created: 2026-04-26
 * Last-Modified: 2026-04-26
 * Version: 0.1.0
 */
import api, { fetch as forgeFetch } from "@forge/api";

interface CachedToken {
  token: string;
  expiresAt: number;
}

let cached: CachedToken | null = null;

/**
 * Acquires an Entra access token using the client_credentials flow with the
 * forge-stored client secret. The Forge app has a separate Entra app
 * registration with its own application permission to call the naming API.
 */
async function getToken(): Promise<string> {
  if (cached && cached.expiresAt - Date.now() > 60_000) {
    return cached.token;
  }
  const tenant = process.env.ENTRA_TENANT_ID;
  const clientId = process.env.ENTRA_CLIENT_ID;
  const resource = process.env.NAMING_API_RESOURCE;
  if (!tenant || !clientId || !resource) {
    throw new Error("Missing ENTRA_TENANT_ID / ENTRA_CLIENT_ID / NAMING_API_RESOURCE env vars");
  }
  const secret = await api.asApp().requestConfluence as unknown; // placeholder for forge storage.secret
  // In a real Forge app, secrets come from `storage.secret('entra-client-secret').get()`.
  // We delegate the actual fetch via the @forge/api egress.
  const body = new URLSearchParams({
    client_id: clientId,
    grant_type: "client_credentials",
    scope: `${resource}/.default`,
    client_secret: String(secret ?? process.env.ENTRA_CLIENT_SECRET ?? ""),
  });
  const res = await forgeFetch(`https://login.microsoftonline.com/${tenant}/oauth2/v2.0/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: body.toString(),
  });
  if (!res.ok) {
    throw new Error(`Entra token request failed: ${res.status} ${await res.text()}`);
  }
  const data = (await res.json()) as { access_token: string; expires_in: number };
  cached = {
    token: data.access_token,
    expiresAt: Date.now() + data.expires_in * 1000,
  };
  return cached.token;
}

interface ApiCallOptions {
  method?: "GET" | "POST" | "DELETE";
  body?: unknown;
  query?: Record<string, string | undefined>;
}

export async function callNamingApi<T = unknown>(path: string, opts: ApiCallOptions = {}): Promise<T> {
  const base = process.env.NAMING_API_BASE_URL;
  if (!base) throw new Error("NAMING_API_BASE_URL is not configured");
  const token = await getToken();
  const url = new URL(path.startsWith("/") ? path : `/${path}`, base);
  if (opts.query) {
    for (const [k, v] of Object.entries(opts.query)) {
      if (v !== undefined) url.searchParams.set(k, v);
    }
  }
  const res = await forgeFetch(url.toString(), {
    method: opts.method ?? "GET",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      "X-Sanmar-Source": "confluence-forge",
    },
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
  });
  const text = await res.text();
  if (!res.ok) {
    throw new Error(`Naming API ${opts.method ?? "GET"} ${path} failed: ${res.status} ${text}`);
  }
  return text ? (JSON.parse(text) as T) : ({} as T);
}
