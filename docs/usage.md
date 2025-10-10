# 📘 Usage Instructions

This guide covers how to use the Azure Naming Function’s RESTful endpoints to claim, release, and audit names, as well as synchronize slug data.

All HTTP-triggered endpoints require an **Authorization header** containing a valid bearer token issued by Entra ID.

---

## 🔐 Authentication (Required)

Include the following header with each request:

```
Authorization: Bearer <access_token>
```

Tokens are validated using Entra ID. Your user must belong to one of the following roles:

* `reader` — basic access to view docs and audit your own usage
* `contributor` — create/claim/release names and run slug sync
* `admin` — full contributor permissions plus cross-user audit access

---

## 📤 Claim or Generate a Name

**POST** `/api/claim`

You can also call **POST** `/api/generate` if you prefer to keep the claim-specific route separate. Both endpoints validate RBAC, generate a compliant name, persist it, and return the same payload.

### Body:

```json
{
  "resource_type": "storage_account",
  "environment": "dev",
  "region": "wus2",
  "project": "finance",
  "purpose": "costreports",
  "system": "erp",
  "index": "01"
}
```

### Returns (`201 Created`):

```json
{
  "name": "sanmar-st-finance-costreports-dev-wus2-01",
  "resourceType": "storage_account",
  "region": "wus2",
  "environment": "dev",
  "slug": "st",
  "project": "finance",
  "purpose": "costreports",
  "system": "erp",
  "index": "01",
  "claimedBy": "<user object id>",
  "summary": null,
  "display": [
    {"key": "name", "label": "Storage Account Name", "value": "sanmar-st-finance-costreports-dev-wus2-01"},
    {"key": "resourceType", "label": "Resource Type", "value": "storage_account"},
    {"key": "slug", "label": "Slug", "value": "st"},
    {"key": "environment", "label": "Environment", "value": "dev"},
    {"key": "region", "label": "Region", "value": "wus2"},
    {"key": "project", "label": "Project", "value": "finance"},
    {"key": "purpose", "label": "Purpose", "value": "costreports"},
    {"key": "system", "label": "System", "value": "erp"},
    {"key": "index", "label": "Index", "value": "01"}
  ]
}
```

If the generated name already exists you receive `409 Conflict` so the caller can retry with different optional segments.

---

## 📥 Release a Name

**POST** `/api/release`

### Body:

```json
{
  "name": "st-sanmar-finance-costreports-dev-wus2"
}
```

### Returns:

```json
{
  "message": "Name successfully released."
}
```

Released names are still tracked in audit history but made available for reuse.

---

## 🔍 Audit a Single Name

**GET** `/api/audit?name=st-sanmar-finance-costreports-dev-wus2`

Returns the claim/release history for a specific name.

### Response:

```json
{
  "name": "st-sanmar-finance-costreports-dev-wus2",
  "history": [
    {
      "timestamp": "2024-01-10T18:22:31Z",
      "event": "claimed",
      "user": "john@contoso.com"
    },
    {
      "timestamp": "2024-02-14T13:02:10Z",
      "event": "released",
      "user": "john@contoso.com"
    }
  ]
}
```

---

## 📊 Bulk Audit

**GET** `/api/audit_bulk?user=john@contoso.com&project=finance`

### Optional Query Parameters:

* `user` – object ID or UPN (defaults to the caller)
* `project` – project slug stored with the claim
* `purpose` – purpose slug stored with the claim
* `region`
* `environment`
* `action` – `claimed` or `released`
* `start` / `end` – ISO 8601 timestamps for filtering by event time

> ℹ️ Querying users other than yourself requires the `admin` role.

### Returns:

```json
{
  "results": [
    {
      "name": "sanmar-st-finance-costreports-dev-wus2-01",
      "event_id": "7e2f...",
      "user": "john@contoso.com",
      "action": "claimed",
      "timestamp": "2024-01-10T18:22:31Z",
      "region": "wus2",
      "environment": "dev",
      "project": "finance",
      "purpose": "costreports",
      "resource_type": "storage_account"
    }
  ]
}
```

---

## 🔄 Manual Slug Sync

**POST** `/api/slug_sync`

Manually refreshes slug definitions from the GitHub `defined_specs` file and updates Table Storage.

### Returns:

```json
{
  "message": "Slug sync complete. 84 entries updated/created."
}
```

> ℹ️ The `summary` field is populated when the active naming rule defines a summary template; otherwise it is `null`.
> 📌 This example reflects the built-in `USStrictRuleProvider` (`providers.us_rules`) layered on top of the default rule set. If you register a custom naming rule provider the returned fields may differ.

This endpoint is RBAC-protected and requires the `contributor` role or higher. The sync process populates `ResourceType` (canonical underscore format) and `FullName` (human-readable with spaces) so that the pluggable slug providers can resolve either input style.

---

## 🕓 Automated Slug Sync

The system includes a scheduled function (`slug_sync_timer`) that runs weekly on Sundays at 4:00 AM UTC to keep slug mappings in sync automatically.

No user interaction is required.

---

Next: [🔐 RBAC & Entra Setup](auth.md)
