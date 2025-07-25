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

* `user` — basic access to claim/release/audit personal usage
* `manager` — privileged access to view any audit log
* `admin` — all manager permissions plus provisioning

---

## 📤 Claim a Name

**POST** `/api/claim`

### Body:

```json
{
  "resourceType": "storage_account",
  "environment": "dev",
  "region": "westus2",
  "project": "finance",
  "purpose": "costreports"
}
```

### Returns:

```json
{
  "name": "st-sanmar-finance-costreports-dev-wus2"
}
```

This claims a unique name and stores it as **in use**.

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

* `user` (email)
* `project` (slug)
* `start` and `end` (ISO 8601 timestamps)

### Returns:

An array of claim/release records across names matching the filters.

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

This endpoint is RBAC-protected and requires the `user` role or higher.

---

## 🕓 Automated Slug Sync

The system includes a scheduled function (`slug_sync_timer`) that runs weekly on Sundays at 4:00 AM UTC to keep slug mappings in sync automatically.

No user interaction is required.

---

Next: [🔐 RBAC & Entra Setup](auth.md)
