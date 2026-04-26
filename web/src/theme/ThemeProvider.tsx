/*
 * Repository: azure-naming
 * Path: web/src/theme/ThemeProvider.tsx
 * Purpose: React provider for runtime theme tokens
 * Author: GitHub Copilot
 * Created: 2026-04-26
 * Last-Modified: 2026-04-26
 * Version: 0.1.0
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  applyTokens,
  buildTokens,
  deriveHue,
  resolveMode,
  type ThemeMode,
} from "./theme";

interface ThemeContextValue {
  mode: ThemeMode;
  setMode: (m: ThemeMode) => void;
  hue: number;
  setHue: (h: number) => void;
  resolvedMode: "light" | "dark";
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

const MODE_KEY = "aznaming.themeMode";
const HUE_KEY = "aznaming.themeHue";

export function ThemeProvider({
  seed,
  children,
}: {
  seed: string | undefined;
  children: ReactNode;
}): JSX.Element {
  const [mode, setModeState] = useState<ThemeMode>(() => {
    const stored = typeof window !== "undefined" ? window.localStorage.getItem(MODE_KEY) : null;
    if (stored === "light" || stored === "dark" || stored === "auto") return stored;
    return "auto";
  });

  const defaultHue = useMemo(() => deriveHue(seed ?? "anonymous"), [seed]);

  const [hue, setHueState] = useState<number>(() => {
    const stored = typeof window !== "undefined" ? window.localStorage.getItem(HUE_KEY) : null;
    if (stored && !Number.isNaN(Number(stored))) return Number(stored);
    return defaultHue;
  });

  const [resolvedMode, setResolvedMode] = useState<"light" | "dark">(() => resolveMode(mode));

  useEffect(() => {
    const next = resolveMode(mode);
    setResolvedMode(next);
    if (mode !== "auto") return;
    if (typeof window === "undefined" || !window.matchMedia) return;
    const mql = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = () => setResolvedMode(mql.matches ? "dark" : "light");
    mql.addEventListener("change", handler);
    return () => mql.removeEventListener("change", handler);
  }, [mode]);

  useEffect(() => {
    applyTokens(buildTokens(resolvedMode, hue));
    document.documentElement.dataset.theme = resolvedMode;
  }, [resolvedMode, hue]);

  const setMode = useCallback((m: ThemeMode) => {
    window.localStorage.setItem(MODE_KEY, m);
    setModeState(m);
  }, []);

  const setHue = useCallback((h: number) => {
    window.localStorage.setItem(HUE_KEY, String(h));
    setHueState(h);
  }, []);

  const value = useMemo(
    () => ({ mode, setMode, hue, setHue, resolvedMode }),
    [mode, setMode, hue, setHue, resolvedMode],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used within ThemeProvider");
  return ctx;
}
