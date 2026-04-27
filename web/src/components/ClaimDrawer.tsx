import type * as React from "react";
/*
 * Repository: azure-naming
 * Path: web/src/components/ClaimDrawer.tsx
 * Purpose: Slide-in drawer with claim form
 * Author: GitHub Copilot
 * Created: 2026-04-26
 * Last-Modified: 2026-04-26
 * Version: 0.1.0
 */
import { useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { X } from "lucide-react";
import { useApiClient } from "../api/useApiClient";
import { ApiError } from "../api/client";

interface ClaimDrawerProps {
  open: boolean;
  onClose: () => void;
}

export function ClaimDrawer({ open, onClose }: ClaimDrawerProps): React.JSX.Element | null {
  const api = useApiClient();
  const qc = useQueryClient();
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: (body: Parameters<typeof api.claim>[0]) => api.claim(body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["claims"] });
      onClose();
    },
    onError: (err: unknown) => {
      if (err instanceof ApiError) setError(err.body || err.message);
      else setError(String(err));
    },
  });

  if (!open) return null;

  function handleSubmit(e: FormEvent<HTMLFormElement>): void {
    e.preventDefault();
    setError(null);
    const form = e.currentTarget;
    const data = new FormData(form);
    const body = {
      resource_type: String(data.get("resource_type") ?? ""),
      region: String(data.get("region") ?? "").toLowerCase(),
      environment: String(data.get("environment") ?? "").toLowerCase(),
      project: (data.get("project") as string) || undefined,
      purpose: (data.get("purpose") as string) || undefined,
    };
    mutation.mutate(body);
  }

  return (
    <div className="drawer-backdrop" role="dialog" aria-modal="true" aria-label="Claim a name">
      <div className="drawer">
        <div style={{ display: "flex", alignItems: "center", marginBottom: "var(--space-4)" }}>
          <h2 style={{ margin: 0, flex: 1 }}>Claim a Name</h2>
          <button type="button" className="secondary" onClick={onClose} aria-label="Close">
            <X size={16} aria-hidden="true" />
          </button>
        </div>
        <form onSubmit={handleSubmit}>
          <div className="field">
            <label htmlFor="resource_type">Resource type</label>
            <input id="resource_type" name="resource_type" required placeholder="e.g. storage_account" />
            <span className="help">Canonical resource type slug. See /api/rules for the full list.</span>
          </div>
          <div className="field">
            <label htmlFor="region">Region</label>
            <select id="region" name="region" required defaultValue="wus2">
              <option value="wus2">wus2 (West US 2)</option>
              <option value="eus1">eus1 (East US)</option>
              <option value="eus2">eus2 (East US 2)</option>
            </select>
          </div>
          <div className="field">
            <label htmlFor="environment">Environment</label>
            <select id="environment" name="environment" required defaultValue="dev">
              <option value="dev">dev</option>
              <option value="alt">alt</option>
              <option value="stg">stg</option>
              <option value="prd">prd</option>
              <option value="sbx">sbx</option>
              <option value="tst">tst</option>
            </select>
          </div>
          <div className="field">
            <label htmlFor="project">Project (optional)</label>
            <input id="project" name="project" />
          </div>
          <div className="field">
            <label htmlFor="purpose">Purpose (optional)</label>
            <input id="purpose" name="purpose" />
          </div>
          {error && <p className="error" role="alert">{error}</p>}
          <div style={{ display: "flex", gap: "var(--space-3)", marginTop: "var(--space-4)" }}>
            <button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? "Claiming…" : "Claim"}
            </button>
            <button type="button" className="secondary" onClick={onClose}>
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
