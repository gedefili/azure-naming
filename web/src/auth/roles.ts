/*
 * Repository: azure-naming
 * Path: web/src/auth/roles.ts
 * Purpose: Pure helpers for parsing and inspecting Entra role claims
 * Author: GitHub Copilot
 * Created: 2026-04-27
 * Last-Modified: 2026-04-27
 * Version: 0.1.0
 */

/**
 * Lowercased role names that grant administrative privileges in the Naming
 * Service UI.  The list is duplicated server-side; keep both in sync.
 */
export const ADMIN_ROLES: readonly string[] = Object.freeze([
  "admin",
  "sanmar-naming-admin",
  "sanmar.naming.admin",
]);

/**
 * Extract the `roles` claim from an Entra ID token claim bag, defensively
 * filtering out non-string entries.  Never throws.
 */
export function parseRoles(claims: unknown): string[] {
  if (!claims || typeof claims !== "object") return [];
  const value = (claims as Record<string, unknown>).roles;
  if (!Array.isArray(value)) return [];
  return value.filter((r): r is string => typeof r === "string");
}

/** Case-insensitive admin check against `ADMIN_ROLES`. */
export function isAdmin(roles: readonly string[]): boolean {
  return roles.some((r) => ADMIN_ROLES.includes(r.toLowerCase()));
}
