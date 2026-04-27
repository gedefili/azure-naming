import type * as React from "react";
/*
 * Repository: azure-naming
 * Path: web/src/components/ClaimsTable.tsx
 * Purpose: Table component for rendering ClaimSummary rows
 * Author: GitHub Copilot
 * Created: 2026-04-26
 * Last-Modified: 2026-04-26
 * Version: 0.1.0
 */
import { type ClaimSummary } from "../api/client";
import { StateBadge } from "./StateBadge";

interface ClaimsTableProps {
  items: ClaimSummary[];
  showOwner?: boolean;
  onRelease?: (claim: ClaimSummary) => void;
  onPurge?: (claim: ClaimSummary) => void;
}

export function ClaimsTable({ items, showOwner, onRelease, onPurge }: ClaimsTableProps): React.JSX.Element {
  if (items.length === 0) {
    return (
      <div className="empty-state">
        <p>No claims yet.</p>
      </div>
    );
  }

  return (
    <table className="claims-table" aria-label="Claimed names">
      <thead>
        <tr>
          <th scope="col">Name</th>
          <th scope="col">Resource Type</th>
          <th scope="col">Region</th>
          <th scope="col">Environment</th>
          {showOwner && <th scope="col">Owner</th>}
          <th scope="col">Claimed</th>
          <th scope="col">State</th>
          <th scope="col">Actions</th>
        </tr>
      </thead>
      <tbody>
        {items.map((c) => (
          <tr key={c.name}>
            <td><code>{c.name}</code></td>
            <td>{c.resource_type ?? "—"}</td>
            <td>{c.region ?? "—"}</td>
            <td>{c.environment ?? "—"}</td>
            {showOwner && <td>{c.claimed_by ?? "—"}</td>}
            <td>{c.claimed_at ? new Date(c.claimed_at).toLocaleString() : "—"}</td>
            <td><StateBadge state={c.claim_state} /></td>
            <td>
              {c.in_use && onRelease && (
                <button type="button" className="secondary" onClick={() => onRelease(c)}>
                  Release
                </button>
              )}
              {onPurge && (
                <button type="button" className="danger" onClick={() => onPurge(c)} style={{ marginLeft: 4 }}>
                  Purge
                </button>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
