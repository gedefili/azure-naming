import type * as React from "react";
/*
 * Repository: azure-naming
 * Path: web/src/components/StateBadge.tsx
 * Purpose: Small badge that classifies a claim state into a known visual class
 * Author: GitHub Copilot
 * Created: 2026-04-27
 * Last-Modified: 2026-04-27
 * Version: 0.1.0
 */

export type BadgeClass = "claimed" | "released" | "orphaned";

const KNOWN_STATES: Record<string, BadgeClass> = {
  claimed: "claimed",
  orphaned: "orphaned",
  released: "released",
};

/** Maps a free-form state string to a known CSS class name. */
export function classifyState(state?: string | null): BadgeClass {
  const lowered = (state ?? "released").toLowerCase();
  return KNOWN_STATES[lowered] ?? "released";
}

export function StateBadge({ state }: { state?: string }): React.JSX.Element {
  const cls = classifyState(state);
  const label = (state ?? "released").toLowerCase();
  return <span className={`badge ${cls}`}>{label}</span>;
}
