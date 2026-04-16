# Remediation Verification Report - April 16, 2026

## Objective

Validate the April 16 remediation work for:

- CAF-backed slug coverage for the previously missing resource types
- Admin remediation of orphaned claims
- Reuse of released or orphaned claims
- Audit visibility into claim state transitions

This report captures the local runtime verification performed against the Azure Functions host in the repository dev environment.

---

## Code Changes Verified

### 1. CAF slug coverage

The service now resolves the following canonical resource types from the CAF sync source:

- `container_app` -> `ca`
- `container_app_environment` -> `cae`
- `subnet` -> `snet`

The sync path now stores the canonical shape expected by lookup:

- `Slug`
- `FullName`
- `ResourceType`
- `Source`
- `UpdatedAt`

### 2. Claim lifecycle remediation

Added admin-only runtime support for:

- Marking a claim as `orphaned` and reusable
- Purging a claim entirely from the active `ClaimedNames` table

Endpoint added:

- `POST /api/claims/remediate`

### 3. Reusable claims

Released or orphaned claims are now reusable. Re-claiming the same generated name updates the existing row instead of failing due to duplicate creation semantics.

### 4. Audit state tracking

The name record and audit responses now expose lifecycle metadata including:

- `claim_state`
- `state_changed_at`
- `state_changed_by`
- `state_version`
- `orphaned_at`
- `orphaned_by`
- `orphan_reason`
- audit event `state_before`
- audit event `state_after`

---

## Verification Performed

### Unit and coverage gate

Ran the required repository test gate:

```bash
/workspaces/azure-naming/.venv/bin/python tools/run_tests_with_coverage.py
```

Observed result:

- `268 passed in 4.39s`
- Coverage summary generated successfully

### Local function host

Started the local stack with the workspace task:

```bash
dev:start-local-stack
```

Observed result:

- Functions host available at `http://localhost:7071`
- Local auth bypass active through `local.settings.json`
- Admin-only route verification possible without external Entra token acquisition

### Runtime HTTP verification

Performed the following live HTTP flow against the local host:

1. `POST /api/slug_sync`
2. `GET /api/slug?resource_type=container_app`
3. `GET /api/slug?resource_type=container_app_environment`
4. `GET /api/slug?resource_type=subnet`
5. `POST /api/claim`
6. `POST /api/release`
7. `POST /api/claim` again for the same deterministic payload
8. `POST /api/claims/remediate` with `action=orphan`
9. `POST /api/claim` again for the same deterministic payload
10. `POST /api/claims/remediate` with `action=purge`
11. `GET /api/audit_bulk?action=purged&user=local-dev-user`
12. Re-created the same claim, orphaned it, then called `GET /api/audit` before final purge cleanup

---

## Observed Runtime Results

### Slug sync and lookup

`POST /api/slug_sync` returned HTTP `200` with:

```json
{
  "message": "Slug sync complete. 183 created, 0 updated, 0 existing (183 total)."
}
```

The three previously missing resource types now resolve correctly:

```json
{
  "resourceType": "container_app",
  "slug": "ca",
  "source": "microsoft_caf"
}
```

```json
{
  "resourceType": "container_app_environment",
  "slug": "cae",
  "source": "microsoft_caf"
}
```

```json
{
  "resourceType": "subnet",
  "slug": "snet",
  "source": "microsoft_caf"
}
```

### Release reuse

Claim payload used:

```json
{
  "resource_type": "storage_account",
  "region": "wus2",
  "environment": "tst",
  "system": "nmtst",
  "project": "copilot",
  "purpose": "remediation"
}
```

Generated name:

- `wus2tststsanmarnmtst`

Observed behavior:

- Initial `POST /api/claim` returned HTTP `201`
- `POST /api/release` returned HTTP `200`
- Repeating `POST /api/claim` with the same payload returned HTTP `201` for the same generated name

This confirms released names are reusable and no duplicate-create conflict blocks reclaim.

### Orphan remediation reuse

Observed behavior:

- `POST /api/claims/remediate` with `action=orphan` returned HTTP `200`
- Repeating `POST /api/claim` with the same payload again returned HTTP `201` for the same generated name

This confirms orphaned claims are reusable through the standard claim flow.

### Purge remediation

Observed behavior:

- `POST /api/claims/remediate` with `action=purge` returned HTTP `200`
- `GET /api/audit` for the purged active record returned HTTP `404`
- `GET /api/audit_bulk?action=purged&user=local-dev-user` returned the purge audit event

Observed purge audit payload included:

```json
{
  "action": "purged",
  "name": "wus2tststsanmarnmtst",
  "resource_type": "storage_account",
  "state_before": "claimed",
  "state_after": "purged",
  "state_version": "5"
}
```

### Audit state visibility before purge

To verify the enriched single-name audit shape, the claim was re-created, orphaned, inspected, and then purged for cleanup.

`GET /api/audit` returned HTTP `200` with state fields present:

```json
{
  "name": "wus2tststsanmarnmtst",
  "claim_state": "orphaned",
  "in_use": false,
  "orphan_reason": "capture audit state before final cleanup",
  "orphaned_by": "local-dev-user",
  "state_changed_by": "local-dev-user",
  "state_version": 2
}
```

This confirms the runtime audit response exposes the new lifecycle state data.

---

## Cleanup Performed

The local verification finished with the test claim purged from the active names table.

Final local cleanup action:

- `POST /api/claims/remediate` with `action=purge`

Result:

- No leftover active claim for `wus2tststsanmarnmtst` in the local verification flow

---

## Outcome Summary

The remediation is verified locally end-to-end.

- Missing CAF-backed slug lookups are fixed
- Released claims can be re-used
- Orphaned claims can be re-used
- Admin operators have a supported runtime mechanism to orphan or purge claims
- Audit endpoints now expose lifecycle state transitions and remediation metadata

---

## External Follow-up Still Required

The following steps could not be completed from this local workspace because they require deployment access to the live environment and service data:

1. Deploy the updated function app to the target environment.
2. Trigger `POST /api/slug_sync` in the deployed environment so the canonical CAF mappings are written to the live `SlugMappings` table.
3. Use `POST /api/claims/remediate` as an admin against the live service to orphan or purge the legacy provider-created orphaned claims.
4. Re-run the external Terraform provider lifecycle test fixture against the deployed service.

These are operational follow-up steps, not unresolved code defects in the local implementation.