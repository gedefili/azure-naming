import type * as React from "react";
/*
 * Repository: azure-naming
 * Path: web/src/pages/SettingsPage.tsx
 * Purpose: Settings (theme accent, environment info)
 * Author: GitHub Copilot
 * Created: 2026-04-26
 * Last-Modified: 2026-04-26
 * Version: 0.1.0
 */
import { useTheme } from "../theme/ThemeProvider";
import { deriveHue } from "../theme/theme";
import { useMsal } from "@azure/msal-react";

export function SettingsPage(): React.JSX.Element {
  const { mode, setMode, hue, setHue, resolvedMode } = useTheme();
  const { accounts } = useMsal();
  const username = accounts[0]?.username;
  const defaultHue = deriveHue(username ?? "anonymous");

  return (
    <section aria-labelledby="settings-heading">
      <h2 id="settings-heading">Settings</h2>
      <div className="card" style={{ marginBottom: "var(--space-5)" }}>
        <h3>Theme</h3>
        <div className="field">
          <label htmlFor="theme-mode">Mode</label>
          <select id="theme-mode" value={mode} onChange={(e) => setMode(e.target.value as typeof mode)}>
            <option value="auto">Auto (follow system)</option>
            <option value="light">Light</option>
            <option value="dark">Dark</option>
          </select>
          <span className="help">Currently rendering: {resolvedMode}</span>
        </div>
        <div className="field">
          <label htmlFor="theme-hue">Accent hue ({hue}°)</label>
          <input
            id="theme-hue"
            type="range"
            min="0"
            max="360"
            value={hue}
            onChange={(e) => setHue(Number(e.target.value))}
          />
          <button type="button" className="secondary" onClick={() => setHue(defaultHue)}>
            Reset to derived hue
          </button>
        </div>
      </div>
      <div className="card">
        <h3>About</h3>
        <dl>
          <dt>API base URL</dt>
          <dd><code>{import.meta.env.VITE_NAMING_API_BASE_URL ?? "/api"}</code></dd>
          <dt>Tenant</dt>
          <dd><code>{import.meta.env.VITE_ENTRA_TENANT_ID ?? "—"}</code></dd>
          <dt>App version</dt>
          <dd><code>{import.meta.env.VITE_APP_VERSION ?? "dev"}</code></dd>
        </dl>
      </div>
    </section>
  );
}
