import type * as React from "react";
/*
 * Repository: azure-naming
 * Path: web/src/components/ConfirmDialog.tsx
 * Purpose: Typed-confirmation modal for destructive actions
 * Author: GitHub Copilot
 * Created: 2026-04-26
 * Last-Modified: 2026-04-26
 * Version: 0.1.0
 */
import { useState } from "react";

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  message: string;
  confirmWord: string;
  onConfirm: (reason: string) => void;
  onCancel: () => void;
  busy?: boolean;
}

export function ConfirmDialog({
  open,
  title,
  message,
  confirmWord,
  onConfirm,
  onCancel,
  busy,
}: ConfirmDialogProps): React.JSX.Element | null {
  const [typed, setTyped] = useState("");
  const [reason, setReason] = useState("");

  if (!open) return null;
  const matches = typed.trim().toUpperCase() === confirmWord.toUpperCase();

  return (
    <div className="drawer-backdrop" role="dialog" aria-modal="true" aria-label={title}>
      <div className="drawer" style={{ width: "min(420px, 100%)" }}>
        <h2>{title}</h2>
        <p>{message}</p>
        <div className="field">
          <label htmlFor="confirm-word">
            Type <code>{confirmWord}</code> to confirm
          </label>
          <input
            id="confirm-word"
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            autoComplete="off"
          />
        </div>
        <div className="field">
          <label htmlFor="confirm-reason">Reason</label>
          <input
            id="confirm-reason"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Why is this needed?"
          />
        </div>
        <div style={{ display: "flex", gap: "var(--space-3)" }}>
          <button
            type="button"
            className="danger"
            disabled={!matches || !reason || busy}
            onClick={() => onConfirm(reason)}
          >
            {busy ? "Working…" : confirmWord}
          </button>
          <button type="button" className="secondary" onClick={onCancel}>
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
