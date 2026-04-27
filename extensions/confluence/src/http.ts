/*
 * Repository: azure-naming
 * Path: extensions/confluence/src/http.ts
 * Purpose: Pure HTTP helpers shared by Forge token fetcher and API client
 * Author: GitHub Copilot
 * Created: 2026-04-27
 * Last-Modified: 2026-04-27
 * Version: 0.1.0
 */

export type FetchLike = (
  url: string,
  init: {
    method?: string;
    headers?: Record<string, string>;
    body?: string;
  },
) => Promise<{
  ok: boolean;
  status: number;
  text(): Promise<string>;
  json(): Promise<unknown>;
}>;

export const SOURCE_HEADER = "X-Sanmar-Source";
export const FORGE_SOURCE = "confluence-forge";

export function buildQueryString(query?: Record<string, string | undefined | null>): string {
  if (!query) return "";
  const entries = Object.entries(query).filter(
    ([, v]) => v !== undefined && v !== null && v !== "",
  );
  if (entries.length === 0) return "";
  const params = new URLSearchParams();
  for (const [k, v] of entries) params.append(k, String(v));
  return `?${params.toString()}`;
}

export function joinPath(base: string, path: string): string {
  return `${base.replace(/\/+$/, "")}/${path.replace(/^\/+/, "")}`;
}

/**
 * Sanitize an upstream error body before bubbling it into Confluence —
 * truncates long bodies and strips characters that break tooltips.
 */
export function sanitizeErrorBody(text: string, max = 240): string {
  const cleaned = text.replace(/[\r\n\t]+/g, " ").trim();
  return cleaned.length > max ? `${cleaned.slice(0, max - 1)}…` : cleaned;
}
