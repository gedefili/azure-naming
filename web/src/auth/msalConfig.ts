/*
 * Repository: azure-naming
 * Path: web/src/auth/msalConfig.ts
 * Purpose: MSAL.js public-client configuration and scope helpers
 * Author: GitHub Copilot
 * Created: 2026-04-26
 * Last-Modified: 2026-04-26
 * Version: 0.1.0
 */
import {
  PublicClientApplication,
  type Configuration,
  type RedirectRequest,
} from "@azure/msal-browser";

const tenantId = import.meta.env.VITE_ENTRA_TENANT_ID;
const clientId = import.meta.env.VITE_ENTRA_CLIENT_ID;
const apiClientId = import.meta.env.VITE_NAMING_API_CLIENT_ID;

if (!tenantId || !clientId) {
  // Fail fast in dev. In production, the SWA app_settings inject these values
  // at build time via the deployment pipeline.
  // eslint-disable-next-line no-console
  console.warn(
    "[auth] Missing VITE_ENTRA_TENANT_ID or VITE_ENTRA_CLIENT_ID. " +
      "Sign-in will fail until these are set.",
  );
}

export const msalConfig: Configuration = {
  auth: {
    clientId: clientId ?? "missing-client-id",
    authority: `https://login.microsoftonline.com/${tenantId ?? "common"}`,
    redirectUri: `${window.location.origin}/auth/callback`,
    postLogoutRedirectUri: `${window.location.origin}/`,
    navigateToLoginRequestUrl: true,
  },
  cache: {
    // Use sessionStorage so tokens are cleared when the tab closes. Never use
    // localStorage for tokens.
    cacheLocation: "sessionStorage",
    storeAuthStateInCookie: false,
  },
  system: {
    allowNativeBroker: false,
  },
};

export const apiScopes: string[] = apiClientId
  ? [`api://${apiClientId}/user_access`]
  : [];

export const graphScopes: string[] = ["User.Read"];

export const loginRequest: RedirectRequest = {
  scopes: ["openid", "profile", "email", ...apiScopes],
  prompt: "select_account",
};

export const apiTokenRequest: RedirectRequest = {
  scopes: apiScopes.length > 0 ? apiScopes : ["openid"],
};

export const graphTokenRequest: RedirectRequest = {
  scopes: graphScopes,
};

export const msalInstance = new PublicClientApplication(msalConfig);
