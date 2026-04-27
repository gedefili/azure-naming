import type * as React from "react";
/*
 * Repository: azure-naming
 * Path: web/src/components/ThemeToggle.tsx
 * Purpose: Cycle button for the auto / light / dark theme modes
 * Author: GitHub Copilot
 * Created: 2026-04-27
 * Last-Modified: 2026-04-27
 * Version: 0.1.0
 */
import { Monitor, Moon, Sun } from "lucide-react";
import { useTheme } from "../theme/ThemeProvider";
import type { ThemeMode } from "../theme/theme";

export const NEXT_MODE: Record<ThemeMode, ThemeMode> = {
  auto: "light",
  light: "dark",
  dark: "auto",
};

export function ThemeToggle(): React.JSX.Element {
  const { mode, setMode } = useTheme();
  const Icon = mode === "auto" ? Monitor : mode === "light" ? Sun : Moon;
  return (
    <button
      type="button"
      className="secondary"
      onClick={() => setMode(NEXT_MODE[mode])}
      aria-label={`Theme: ${mode}. Click to cycle.`}
      title={`Theme: ${mode}`}
    >
      <Icon size={16} aria-hidden="true" />
    </button>
  );
}
