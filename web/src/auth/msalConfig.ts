/*
 * Repository: azure-naming
 * Path: web/src/auth/msalConfig.ts
 * Purpose: MSAL.js public-client configuration and scope helpers
 * Author: GitHub Copilot
 * Created: 2026-04-26
 * Last-Modified: 2026-04-27
 * Version: 0.2.0
 */
import {
  PublicClientApplication,
  type Configuration,
  type RedirectRequest,
} from "@azure/msal-browser";

export interface AuthEnv {
  tenantId?: string;
  clientId?: string;
  apiClientId?: string;
  origin: string;
  /** True when running a production build. */
  isProduction: boolean;
}

/**
 * Build an MSAL `Configuration` from the supplied environment.  Throws when
 * required values are missing in a production build (fail-closed) and emits a
 * console warning in dev (fail-open so contributors can still load the app).
 */
export function buildMsalConfig(env: AuthEnv): Configuration {
  if (!env.tenantId || !env.clientId) {
    const message =
      "Missing VITE_ENTRA_TENANT_ID or VITE_ENTRA_CLIENT_ID. " +
      "Sign-in will fail until these are set.";
    if (env.isProduction) {
      throw new Error(`[auth] ${message}`);
    }
    // eslint-disable-next-line no-console
    console.warn(`[auth] ${message}`);
  }

  return {
    auth: {
      clientId: env.clientId ?? "missing-client-id",
      authority: `https://login.microsoftonline.com/${env.tenantId ?? "common"}`,
      redirectUri: `${env.origin}/auth/callback`,
      postLogoutRedirectUri: `${env.origin}/`,
      navigateToLoginRequestUrl: true,
    },
    cache: {
      // sessionStorage clears tokens when the tab closes; never use localStorage.
      cacheLocation: "sessionStorage",
      storeAuthStateInCookie: false,
    },
    system: {
      allowNativeBroker: false,
    },
  };
}

/** Returns the API scope list (empty when no API client id is configured). */
export function buildApiScopes(apiClientId: string | undefined): string[] {
  return apiClientId ? [`api://${apiClientId}/user_access`] : [];
}

export function buildLoginRequest(apiScopes: readonly string[]): RedirectRequest {
  return {
    scopes: ["openid", "profile", "email", ...apiScopes],
    prompt: "select_account",
  };
}

export function buildApiTokenRequest(apiScopes: readonly string[]): RedirectRequest {
  return { scopes: apiScopes.length > 0 ? [...apiScopes] : ["openid"] };
}

const tenantId = import.meta.env.VITE_ENTRA_TENANT_ID as string | undefined;
const clientId = import.meta.env.VITE_ENTRA_CLIENT_ID as string | undefined;
const apiClientId = import.meta.env.VITE_NAMING_API_CLIENT_ID as string | undefined;
const isProduction = import.meta.env.MODE === "production";
const origin = typeof window !== "undefined" ? window.location.origin : "http://localhost";

export const msalConfig: Configuration = buildMsalConfig({
  tenantId,
  clientId,
  apiClientId,
  origin,
  isProduction,
});

export const apiScopes: string[] = buildApiScopes(apiClientId);
export const graphScopes: string[] = ["User.Read"];

export const loginRequest: RedirectRequest = buildLoginRequest(apiScopes);
export const apiTokenRequest: RedirectRequest = buildApiTokenRequest(apiScopes);
export const graphTokenRequest: RedirectRequest = { scopes: graphScopes };

export const msalInstance = new PublicClientApplication(msalConfig);
