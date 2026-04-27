/*
 * Repository: azure-naming
 * Path: web/src/api/types.ts
 * Purpose: Shared API DTO types for the Azure Naming Service
 * Author: GitHub Copilot
 * Created: 2026-04-27
 * Last-Modified: 2026-04-27
 * Version: 0.1.0
 */

export interface ClaimSummary {
  name: string;
  resource_type?: string;
  region?: string;
  environment?: string;
  in_use?: boolean;
  claim_state?: string;
  claimed_by?: string;
  claimed_at?: string;
  released_by?: string;
  released_at?: string;
  release_reason?: string;
  state_changed_by?: string;
  state_changed_at?: string;
  state_version?: number;
  orphaned_by?: string;
  orphaned_at?: string;
  orphan_reason?: string;
  slug?: string;
  project?: string;
  purpose?: string;
  subsystem?: string;
  system?: string;
  index?: string;
}

export interface ClaimsListResponse {
  items: ClaimSummary[];
  count: number;
  scope: string;
  is_admin: boolean;
  continuation?: string;
}

export interface ClaimRequestBody {
  resource_type: string;
  region: string;
  environment: string;
  project?: string;
  purpose?: string;
  subsystem?: string;
  system?: string;
  index?: string;
}

export interface ClaimResponse {
  name: string;
  resourceType: string;
  region: string;
  environment: string;
  slug: string;
  claimedBy: string;
}

export interface ListClaimsParams {
  owner?: string;
  region?: string;
  environment?: string;
  resource_type?: string;
  project?: string;
  state?: string;
  in_use?: boolean;
  query?: string;
  limit?: number;
  continuation?: string;
}

export type RemediateAction = "orphan" | "purge";
