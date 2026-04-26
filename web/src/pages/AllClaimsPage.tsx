/*
 * Repository: azure-naming
 * Path: web/src/pages/AllClaimsPage.tsx
 * Purpose: Admin view of all claims with remediation actions
 * Author: GitHub Copilot
 * Created: 2026-04-26
 * Last-Modified: 2026-04-26
 * Version: 0.1.0
 */
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useApiClient } from "../api/useApiClient";
import { type ClaimSummary } from "../api/client";
import { ClaimsTable } from "../components/ClaimsTable";
import { ConfirmDialog } from "../components/ConfirmDialog";

export function AllClaimsPage(): JSX.Element {
  const api = useApiClient();
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [purging, setPurging] = useState<ClaimSummary | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ["claims", "all", search],
    queryFn: () => api.listClaims({ owner: "all", query: search || undefined, limit: 200 }),
  });

  const purgeMutation = useMutation({
    mutationFn: ({ claim, reason }: { claim: ClaimSummary; reason: string }) =>
      api.remediate(claim.name, claim.region ?? "", claim.environment ?? "", "purge", reason),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["claims"] });
      setPurging(null);
    },
  });

  return (
    <section aria-labelledby="all-claims-heading">
      <h2 id="all-claims-heading">All Claims (Admin)</h2>
      <div className="toolbar">
        <input
          type="search"
          placeholder="Search by name, project, owner…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          aria-label="Search all claims"
        />
      </div>
      {isLoading && <p>Loading…</p>}
      {error && <p className="error" role="alert">{String(error)}</p>}
      {data && <ClaimsTable items={data.items} showOwner onPurge={(c) => setPurging(c)} />}
      <ConfirmDialog
        open={purging !== null}
        title="Purge this claim?"
        message={
          purging
            ? `Purging ${purging.name} permanently deletes the claim record. The audit log entry remains. This cannot be undone.`
            : ""
        }
        confirmWord="PURGE"
        busy={purgeMutation.isPending}
        onCancel={() => setPurging(null)}
        onConfirm={(reason) => {
          if (purging) purgeMutation.mutate({ claim: purging, reason });
        }}
      />
    </section>
  );
}
