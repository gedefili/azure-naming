/*
 * Repository: azure-naming
 * Path: web/src/lib/url.ts
 * Purpose: Pure helpers for joining base URLs and appending query parameters
 * Author: GitHub Copilot
 * Created: 2026-04-27
 * Last-Modified: 2026-04-27
 * Version: 0.1.0
 */

export type QueryValue = string | number | boolean | undefined | null;
export type QueryParams = Readonly<Record<string, QueryValue>>;

const ABSOLUTE_URL = /^https?:\/\//i;

/**
 * Join a base URL and a path safely.
 *
 * - Accepts both `http(s)://host[/prefix]` bases and rooted bases like `/api`.
 * - Collapses any combination of trailing/leading slashes into a single one.
 * - If `path` is itself absolute, returns it unchanged (allows escape hatches).
 *
 * The function never reaches outside the supplied base — it only manipulates
 * strings, never falls back to `window.location`.
 */
export function joinUrl(base: string, path: string): string {
  if (ABSOLUTE_URL.test(path)) return path;
  if (!base) return path.startsWith("/") ? path : `/${path}`;
  const trimmedBase = base.replace(/\/+$/, "");
  const trimmedPath = path.replace(/^\/+/, "");
  return `${trimmedBase}/${trimmedPath}`;
}

/**
 * Append the supplied query parameters to a URL.  Values that are `undefined`,
 * `null`, or empty-string are skipped.  All other values are coerced via
 * `String()`.  The function never mutates its inputs and never throws.
 */
export function appendQuery(url: string, params?: QueryParams): string {
  if (!params) return url;
  const entries = Object.entries(params).filter(
    ([, value]) => value !== undefined && value !== null && value !== "",
  );
  if (entries.length === 0) return url;
  const search = new URLSearchParams();
  for (const [key, value] of entries) {
    search.append(key, String(value));
  }
  const separator = url.includes("?") ? "&" : "?";
  return `${url}${separator}${search.toString()}`;
}

/** Convenience: `joinUrl` followed by `appendQuery`. */
export function buildUrl(base: string, path: string, params?: QueryParams): string {
  return appendQuery(joinUrl(base, path), params);
}
