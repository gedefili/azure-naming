/*
 * Repository: azure-naming
 * Path: web/src/App.tsx
 * Purpose: Root app component — auth gate, top bar, routes
 * Author: GitHub Copilot
 * Created: 2026-04-26
 * Last-Modified: 2026-04-26
 * Version: 0.1.0
 */
import { useMsal, useIsAuthenticated } from "@azure/msal-react";
import { Routes, Route, Navigate, NavLink } from "react-router-dom";
import { LogOut, Sun, Moon, Monitor, Shield } from "lucide-react";

import { loginRequest } from "./auth/msalConfig";
import { useIsAdmin } from "./auth/useAccessToken";
import { useTheme } from "./theme/ThemeProvider";
import { MyClaimsPage } from "./pages/MyClaimsPage";
import { AllClaimsPage } from "./pages/AllClaimsPage";
import { SettingsPage } from "./pages/SettingsPage";

function SignInScreen(): JSX.Element {
  const { instance } = useMsal();
  return (
    <div className="empty-state" style={{ paddingTop: "10vh" }}>
      <h1>Azure Naming</h1>
      <p>Sign in with your SanMar account to claim and manage Azure resource names.</p>
      <button onClick={() => instance.loginRedirect(loginRequest)} type="button">
        Sign in with Microsoft
      </button>
    </div>
  );
}

function ThemeToggle(): JSX.Element {
  const { mode, setMode } = useTheme();
  const next: Record<typeof mode, typeof mode> = {
    auto: "light",
    light: "dark",
    dark: "auto",
  };
  const Icon = mode === "auto" ? Monitor : mode === "light" ? Sun : Moon;
  return (
    <button
      type="button"
      className="secondary"
      onClick={() => setMode(next[mode])}
      aria-label={`Theme: ${mode}. Click to cycle.`}
      title={`Theme: ${mode}`}
    >
      <Icon size={16} aria-hidden="true" />
    </button>
  );
}

export default function App(): JSX.Element {
  const isAuthenticated = useIsAuthenticated();
  const isAdmin = useIsAdmin();
  const { instance, accounts } = useMsal();

  if (!isAuthenticated) {
    return (
      <div className="app-shell">
        <main className="content">
          <SignInScreen />
        </main>
      </div>
    );
  }

  const account = accounts[0];

  return (
    <div className="app-shell">
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
          onClick={() => instance.logoutRedirect()}
          aria-label="Sign out"
          title="Sign out"
        >
          <LogOut size={16} aria-hidden="true" />
        </button>
      </header>
      <main className="content">
        <Routes>
          <Route path="/" element={<MyClaimsPage />} />
          <Route path="/all" element={isAdmin ? <AllClaimsPage /> : <Navigate to="/" replace />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/auth/callback" element={<Navigate to="/" replace />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}
