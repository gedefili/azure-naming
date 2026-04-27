/*
 * Repository: azure-naming
 * Path: web/src/lib/json.ts
 * Purpose: Defensive JSON parsing helpers
 * Author: GitHub Copilot
 * Created: 2026-04-27
 * Last-Modified: 2026-04-27
 * Version: 0.1.0
 */

/** Parse `text` as JSON, returning `fallback` on empty input or parse error. */
export function safeJsonParse<T>(text: string, fallback: T): T {
  if (!text) return fallback;
  try {
    return JSON.parse(text) as T;
  } catch {
    return fallback;
  }
}
