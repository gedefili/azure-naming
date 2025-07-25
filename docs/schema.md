# 🗃 Table Schemas & Naming Rules

This document explains the structure of the Azure Table Storage tables and the logic used to generate SanMar-compliant Azure resource names.

---

## 📁 Tables Used

### 1. `ClaimedNames`

Tracks all currently claimed names.

| Property       | Type     | Description                            |
| -------------- | -------- | -------------------------------------- |
| `PartitionKey` | string   | Always `claimed`                       |
| `RowKey`       | string   | The generated name                     |
| `ResourceType` | string   | E.g., `storage_account`                |
| `Slug`         | string   | The assigned short form, e.g., `st`    |
| `Project`      | string   | Project identifier                     |
| `Purpose`      | string   | Purpose or function of the resource    |
| `Environment`  | string   | E.g., `dev`, `prod`                    |
| `Region`       | string   | Azure region short name (e.g., `wus2`) |
| `ClaimedBy`    | string   | Email or UPN of the claimant           |
| `ClaimedAt`    | ISO 8601 | UTC timestamp                          |
| `Released`     | bool     | If true, the name is no longer in use  |
| `ReleasedAt`   | ISO 8601 | Timestamp when released (if any)       |

---

### 2. `AuditLogs`

Tracks all claims and releases for auditing.

| Property       | Type     | Description                         |
| -------------- | -------- | ----------------------------------- |
| `PartitionKey` | string   | The name (`RowKey` in ClaimedNames) |
| `RowKey`       | string   | A UUID or timestamp ID              |
| `User`         | string   | Who performed the operation         |
| `Action`       | string   | `claimed` or `released`             |
| `Timestamp`    | ISO 8601 | UTC timestamp                       |
| `Note`         | string   | Optional contextual message         |

---

### 3. `SlugMappings`

Pulled from the [Azure terraform-azurerm-naming](https://github.com/Azure/terraform-azurerm-naming) project.

| Property       | Type     | Description                                  |
| -------------- | -------- | -------------------------------------------- |
| `PartitionKey` | string   | Always `slug`                                |
| `RowKey`       | string   | The short slug (e.g., `st`)                  |
| `Slug`         | string   | Duplicate of `RowKey`                        |
| `FullName`     | string   | Full resource type (e.g., `storage_account`) |
| `UpdatedAt`    | ISO 8601 | When last updated                            |

---

## 🧪 Naming Rule Logic

A valid name must:

* Be all lowercase
* Use only hyphens (no underscores or dots)
* Follow length constraints (e.g., storage accounts ≤ 24 chars)
* Use the correct **slug** for the resource type
* Include `sanmar` for globally unique resources (e.g., storage accounts)

### Format Example:

```
<slug>-sanmar-<project>-<purpose>-<env>-<region>
```

> Example: `st-sanmar-finance-costreports-dev-wus2`

---

Next: [🚀 Deployment Guide](deployment.md)
