import type * as React from "react";
/*
 * Repository: azure-naming
 * Path: web/src/components/SignInScreen.tsx
 * Purpose: Unauthenticated landing screen with Microsoft sign-in button
 * Author: GitHub Copilot
 * Created: 2026-04-27
 * Last-Modified: 2026-04-27
 * Version: 0.1.0
 */
import { useMsal } from "@azure/msal-react";
import { loginRequest } from "../auth/msalConfig";

export function SignInScreen(): React.JSX.Element {
  const { instance } = useMsal();
  return (
    <div className="empty-state" style={{ paddingTop: "10vh" }}>
      <h1>Azure Naming</h1>
      <p>Sign in with your SanMar account to claim and manage Azure resource names.</p>
      <button
        onClick={() => {
          void instance.loginRedirect(loginRequest);
        }}
        type="button"
      >
        Sign in with Microsoft
      </button>
    </div>
  );
}
