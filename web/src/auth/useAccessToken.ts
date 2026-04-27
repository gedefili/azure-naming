/*
 * Repository: azure-naming
 * Path: web/src/auth/useAccessToken.ts
 * Purpose: React hooks that bridge MSAL state to the API client and UI
 * Author: GitHub Copilot
 * Created: 2026-04-26
 * Last-Modified: 2026-04-27
 * Version: 0.2.0
 */
import { useCallback } from "react";
import {
  InteractionRequiredAuthError,
  type AccountInfo,
} from "@azure/msal-browser";
import { useMsal } from "@azure/msal-react";
import { apiTokenRequest } from "./msalConfig";
import { isAdmin, parseRoles } from "./roles";

/**
 * Returns an async token provider for the Naming Service API.  The provider
 * resolves to:
 *
 * - `string` — a fresh access token
 * - `null`    — there is no signed-in account, **or** an interactive redirect
 *               was just initiated (the page is about to navigate away)
 *
 * Other errors propagate so React Query can surface them.
 */
export function useAccessToken(): () => Promise<string | null> {
  const { instance, accounts } = useMsal();

  return useCallback(async (): Promise<string | null> => {
    const account: AccountInfo | undefined = accounts[0];
    if (!account) return null;
    try {
      const result = await instance.acquireTokenSilent({
        ...apiTokenRequest,
        account,
      });
      return result.accessToken;
    } catch (err) {
      if (err instanceof InteractionRequiredAuthError) {
        await instance.acquireTokenRedirect({ ...apiTokenRequest, account });
        return null;
      }
      throw err;
    }
  }, [instance, accounts]);
}

export function useUserRoles(): string[] {
  const { accounts } = useMsal();
  return parseRoles(accounts[0]?.idTokenClaims);
}

export function useIsAdmin(): boolean {
  return isAdmin(useUserRoles());
}
