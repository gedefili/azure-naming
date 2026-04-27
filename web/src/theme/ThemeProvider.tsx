import type * as React from "react";
/*
 * Repository: azure-naming
 * Path: web/src/theme/ThemeProvider.tsx
 * Purpose: React provider that owns theme mode + hue and applies CSS tokens
 * Author: GitHub Copilot
 * Created: 2026-04-26
 * Last-Modified: 2026-04-27
 * Version: 0.2.0
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
import {
  getDefaultStorage,
  readEnum,
  readInt,
  writeString,
  type StorageLike,
} from "../lib/storage";

export interface ThemeContextValue {
  mode: ThemeMode;
  setMode: (m: ThemeMode) => void;
  hue: number;
  setHue: (h: number) => void;
  resolvedMode: "light" | "dark";
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

export const MODE_KEY = "aznaming.themeMode";
export const HUE_KEY = "aznaming.themeHue";

const ALLOWED_MODES: readonly ThemeMode[] = ["auto", "light", "dark"];

export interface ThemeProviderProps {
  seed: string | undefined;
  children: ReactNode;
  /** Inject for tests / SSR. */
  storage?: StorageLike;
}

export function ThemeProvider({
  seed,
  children,
  storage,
}: ThemeProviderProps): React.JSX.Element {
  const store = useMemo(() => storage ?? getDefaultStorage(), [storage]);

  const defaultHue = useMemo(() => deriveHue(seed ?? "anonymous"), [seed]);

  const [mode, setModeState] = useState<ThemeMode>(() =>
    readEnum<ThemeMode>(store, MODE_KEY, ALLOWED_MODES, "auto"),
  );

  const [hue, setHueState] = useState<number>(() =>
    readInt(store, HUE_KEY, defaultHue, 0, 360),
  );

  const [resolvedMode, setResolvedMode] = useState<"light" | "dark">(() =>
    resolveMode(mode),
  );

  useEffect(() => {
    setResolvedMode(resolveMode(mode));
    if (mode !== "auto") return;
    if (typeof window === "undefined" || !window.matchMedia) return;
    const mql = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = (): void => setResolvedMode(mql.matches ? "dark" : "light");
    mql.addEventListener("change", handler);
    return () => mql.removeEventListener("change", handler);
  }, [mode]);

  useEffect(() => {
    applyTokens(buildTokens(resolvedMode, hue));
    if (typeof document !== "undefined") {
      document.documentElement.dataset.theme = resolvedMode;
    }
  }, [resolvedMode, hue]);

  const setMode = useCallback(
    (m: ThemeMode) => {
      writeString(store, MODE_KEY, m);
      setModeState(m);
    },
    [store],
  );

  const setHue = useCallback(
    (h: number) => {
      const clamped = Math.max(0, Math.min(360, Math.round(h)));
      writeString(store, HUE_KEY, String(clamped));
      setHueState(clamped);
    },
    [store],
  );

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
