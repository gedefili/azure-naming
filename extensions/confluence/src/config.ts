/*
 * Repository: azure-naming
 * Path: extensions/confluence/src/config.ts
 * Purpose: Pure environment variable parsing for the Forge extension
 * Author: GitHub Copilot
 * Created: 2026-04-27
 * Last-Modified: 2026-04-27
 * Version: 0.1.0
 */

export interface ForgeConfig {
  tenantId: string;
  clientId: string;
  clientSecret: string;
  resource: string;
  baseUrl: string;
}

export interface EnvBag {
  ENTRA_TENANT_ID?: string;
  ENTRA_CLIENT_ID?: string;
  ENTRA_CLIENT_SECRET?: string;
  NAMING_API_RESOURCE?: string;
  NAMING_API_BASE_URL?: string;
}

/**
 * Parse and validate the environment bag.  Throws an explanatory error when
 * any required variable is missing.  Pure — never reads `process.env` itself.
 */
export function parseConfig(env: EnvBag): ForgeConfig {
  const required: Array<[keyof EnvBag, string]> = [
    ["ENTRA_TENANT_ID", "Entra tenant id"],
    ["ENTRA_CLIENT_ID", "Entra client id"],
    ["ENTRA_CLIENT_SECRET", "Entra client secret"],
    ["NAMING_API_RESOURCE", "Naming API resource (api://...)"],
    ["NAMING_API_BASE_URL", "Naming API base URL"],
  ];
  const missing = required.filter(([key]) => !env[key]).map(([, label]) => label);
  if (missing.length > 0) {
    throw new Error(`Forge config missing: ${missing.join(", ")}`);
  }
  return {
    tenantId: env.ENTRA_TENANT_ID!,
    clientId: env.ENTRA_CLIENT_ID!,
    clientSecret: env.ENTRA_CLIENT_SECRET!,
    resource: env.NAMING_API_RESOURCE!,
    baseUrl: env.NAMING_API_BASE_URL!.replace(/\/+$/, ""),
  };
}

/** Convenience for prod call sites — reads from `process.env` once. */
export function loadConfig(): ForgeConfig {
  return parseConfig(process.env as EnvBag);
}
