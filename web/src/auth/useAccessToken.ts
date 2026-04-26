/*
 * Repository: azure-naming
 * Path: web/src/auth/useAccessToken.ts
 * Purpose: Hook that acquires an access token for the Naming Service API
 * Author: GitHub Copilot
 * Created: 2026-04-26
 * Last-Modified: 2026-04-26
 * Version: 0.1.0
 */
import { useCallback } from "react";
import {
  InteractionRequiredAuthError,
  type AccountInfo,
} from "@azure/msal-browser";
import { useMsal } from "@azure/msal-react";
import { apiTokenRequest } from "./msalConfig";

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
        await instance.acquireTokenRedirect({
          ...apiTokenRequest,
          account,
        });
        return null;
      }
      throw err;
    }
  }, [instance, accounts]);
}

export function useUserRoles(): string[] {
  const { accounts } = useMsal();
  const account = accounts[0];
  if (!account || !account.idTokenClaims) return [];
  const claims = account.idTokenClaims as Record<string, unknown>;
  const roles = claims.roles;
  if (Array.isArray(roles)) return roles.filter((r): r is string => typeof r === "string");
  return [];
}

export function useIsAdmin(): boolean {
  const roles = useUserRoles();
  return roles.some((r) =>
    ["admin", "sanmar-naming-admin", "sanmar.naming.admin"].includes(r.toLowerCase()),
  );
}
