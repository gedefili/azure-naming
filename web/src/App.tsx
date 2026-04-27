import type * as React from "react";
/*
 * Repository: azure-naming
 * Path: web/src/App.tsx
 * Purpose: Root component — auth gate + route map
 * Author: GitHub Copilot
 * Created: 2026-04-26
 * Last-Modified: 2026-04-27
 * Version: 0.2.0
 */
import { useIsAuthenticated } from "@azure/msal-react";
import { Routes, Route, Navigate } from "react-router-dom";

import { useIsAdmin } from "./auth/useAccessToken";
import { SignInScreen } from "./components/SignInScreen";
import { TopBar } from "./components/TopBar";
import { MyClaimsPage } from "./pages/MyClaimsPage";
import { AllClaimsPage } from "./pages/AllClaimsPage";
import { SettingsPage } from "./pages/SettingsPage";

export default function App(): React.JSX.Element {
  const isAuthenticated = useIsAuthenticated();
  const isAdmin = useIsAdmin();

  if (!isAuthenticated) {
    return (
      <div className="app-shell">
        <main className="content">
          <SignInScreen />
        </main>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <TopBar />
      <main className="content">
        <Routes>
          <Route path="/" element={<MyClaimsPage />} />
          <Route
            path="/all"
            element={isAdmin ? <AllClaimsPage /> : <Navigate to="/" replace />}
          />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/auth/callback" element={<Navigate to="/" replace />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}
