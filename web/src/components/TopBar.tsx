import type * as React from "react";
/*
 * Repository: azure-naming
 * Path: web/src/components/TopBar.tsx
 * Purpose: Authenticated top navigation bar
 * Author: GitHub Copilot
 * Created: 2026-04-27
 * Last-Modified: 2026-04-27
 * Version: 0.1.0
 */
import { LogOut, Shield } from "lucide-react";
import { useMsal } from "@azure/msal-react";
import { NavLink } from "react-router-dom";
import { useIsAdmin } from "../auth/useAccessToken";
import { ThemeToggle } from "./ThemeToggle";

export function TopBar(): React.JSX.Element {
  const { instance, accounts } = useMsal();
  const isAdmin = useIsAdmin();
  const account = accounts[0];

  return (
    <header className="topbar">
      <h1>Azure Naming</h1>
      <nav style={{ display: "flex", gap: "var(--space-3)" }} aria-label="Primary">
        <NavLink to="/" end>
          My Claims
        </NavLink>
        {isAdmin && (
          <NavLink to="/all">
            <Shield size={14} aria-hidden="true" /> All Claims
          </NavLink>
        )}
        <NavLink to="/settings">Settings</NavLink>
      </nav>
      <div className="spacer" />
      <span style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>
        {account?.name ?? account?.username}
      </span>
      <ThemeToggle />
      <button
        type="button"
        className="secondary"
        onClick={() => {
          void instance.logoutRedirect();
        }}
        aria-label="Sign out"
        title="Sign out"
      >
        <LogOut size={16} aria-hidden="true" />
      </button>
    </header>
  );
}
