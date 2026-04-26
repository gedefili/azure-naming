/*
 * Repository: azure-naming
 * Path: web/src/pages/MyClaimsPage.tsx
 * Purpose: User's own claims dashboard
 * Author: GitHub Copilot
 * Created: 2026-04-26
 * Last-Modified: 2026-04-26
 * Version: 0.1.0
 */
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";

import { useApiClient } from "../api/useApiClient";
import { type ClaimSummary } from "../api/client";
import { ClaimsTable } from "../components/ClaimsTable";
import { ClaimDrawer } from "../components/ClaimDrawer";
import { ConfirmDialog } from "../components/ConfirmDialog";

export function MyClaimsPage(): JSX.Element {
  const api = useApiClient();
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [releasing, setReleasing] = useState<ClaimSummary | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ["claims", "me", search],
    queryFn: () => api.listClaims({ owner: "me", query: search || undefined, limit: 100 }),
  });

  const releaseMutation = useMutation({
    mutationFn: ({ claim, reason }: { claim: ClaimSummary; reason: string }) =>
      api.release(claim.name, claim.region ?? "", claim.environment ?? "", reason),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["claims"] });
      setReleasing(null);
    },
  });

  return (
    <section aria-labelledby="my-claims-heading">
      <div style={{ display: "flex", alignItems: "center", marginBottom: "var(--space-4)" }}>
        <h2 id="my-claims-heading" style={{ margin: 0, flex: 1 }}>My Claims</h2>
        <button type="button" onClick={() => setDrawerOpen(true)}>
          <Plus size={16} aria-hidden="true" /> Claim a Name
        </button>
      </div>
      <div className="toolbar">
        <input
          type="search"
          placeholder="Search by name, project, owner…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          aria-label="Search claims"
        />
      </div>
      {isLoading && <p>Loading…</p>}
      {error && <p className="error" role="alert">{String(error)}</p>}
      {data && (
        <ClaimsTable
          items={data.items}
          onRelease={(c) => setReleasing(c)}
        />
      )}
      <ClaimDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} />
      <ConfirmDialog
        open={releasing !== null}
        title="Release this name?"
        message={
          releasing
            ? `Releasing ${releasing.name} will mark it available for re-use. This cannot be undone except by claiming the same name again.`
            : ""
        }
        confirmWord="RELEASE"
        busy={releaseMutation.isPending}
        onCancel={() => setReleasing(null)}
        onConfirm={(reason) => {
          if (releasing) releaseMutation.mutate({ claim: releasing, reason });
        }}
      />
    </section>
  );
}
