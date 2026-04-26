/*
 * Repository: azure-naming
 * Path: web/src/theme/theme.ts
 * Purpose: Runtime theme tokens (light/dark/auto) plus deterministic accent derivation
 * Author: GitHub Copilot
 * Created: 2026-04-26
 * Last-Modified: 2026-04-26
 * Version: 0.1.0
 */

export type ThemeMode = "auto" | "light" | "dark";

export interface ThemeTokens {
  surfaceBase: string;
  surfaceRaised: string;
  surfaceMuted: string;
  textPrimary: string;
  textSecondary: string;
  border: string;
  accent: string;
  accentHover: string;
  accentText: string;
  danger: string;
  dangerText: string;
}

const SAFE_HUE_RANGES: Array<[number, number]> = [
  [195, 250], // blue → indigo
  [260, 310], // purple
  [160, 195], // teal
  [110, 145], // green
];

/** Stable string hash → 32-bit unsigned int. */
function hashString(value: string): number {
  let h = 2166136261;
  for (let i = 0; i < value.length; i += 1) {
    h ^= value.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

/** Pick a SanMar-friendly hue (avoids angry reds and muddy yellows). */
export function deriveHue(seed: string): number {
  const h = hashString(seed);
  const range = SAFE_HUE_RANGES[h % SAFE_HUE_RANGES.length]!;
  const [lo, hi] = range;
  return lo + ((h >>> 8) % (hi - lo));
}

export function buildAccent(hue: number, dark: boolean): {
  accent: string;
  accentHover: string;
  accentText: string;
} {
  const lightness = dark ? 60 : 45;
  const hoverLightness = dark ? 70 : 38;
  const accent = `oklch(${lightness}% 0.15 ${hue})`;
  const accentHover = `oklch(${hoverLightness}% 0.15 ${hue})`;
  // Pair white text with darker accents and near-black with light accents
  const accentText = lightness >= 55 ? "oklch(15% 0 0)" : "oklch(98% 0 0)";
  return { accent, accentHover, accentText };
}

export function buildTokens(mode: "light" | "dark", hue: number): ThemeTokens {
  const dark = mode === "dark";
  const { accent, accentHover, accentText } = buildAccent(hue, dark);
  return {
    surfaceBase: dark ? "oklch(18% 0.01 250)" : "oklch(99% 0 0)",
    surfaceRaised: dark ? "oklch(22% 0.01 250)" : "oklch(96% 0 0)",
    surfaceMuted: dark ? "oklch(26% 0.01 250)" : "oklch(94% 0.005 250)",
    textPrimary: dark ? "oklch(96% 0 0)" : "oklch(20% 0 0)",
    textSecondary: dark ? "oklch(75% 0 0)" : "oklch(45% 0 0)",
    border: dark ? "oklch(35% 0.01 250)" : "oklch(88% 0 0)",
    accent,
    accentHover,
    accentText,
    danger: dark ? "oklch(60% 0.18 25)" : "oklch(50% 0.18 25)",
    dangerText: "oklch(98% 0 0)",
  };
}

export function applyTokens(tokens: ThemeTokens): void {
  const root = document.documentElement;
  for (const [key, value] of Object.entries(tokens)) {
    const cssName = "--" + key.replace(/[A-Z]/g, (m) => "-" + m.toLowerCase());
    root.style.setProperty(cssName, value);
  }
}

export function resolveMode(mode: ThemeMode): "light" | "dark" {
  if (mode !== "auto") return mode;
  if (typeof window !== "undefined" && window.matchMedia) {
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  return "light";
}
