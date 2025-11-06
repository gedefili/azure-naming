# Terraform/OpenTofu Provider

The repository bundles a standalone provider that exposes the Azure Naming service as Terraform/OpenTofu resources. The provider
lives in [`terraform-provider-sanmar/`](../../terraform-provider-sanmar/) and can be compiled with the HashiCorp plugin toolchain.

## Features

* `sanmar_naming_claim` resource with full CRUD lifecycle (claim, import, update via re-claim, and destroy via release).
* `sanmar_naming_slug` data source that resolves slugs and metadata for a resource type.
* Azure Active Directory authentication through `DefaultAzureCredential`, giving seamless support for developer logins, managed
  identities, and workload identity federation.
* Robust HTTP client with retry/back-off and helpful error messages when API calls fail.

## Building locally

```bash
cd terraform-provider-sanmar
# Fetch module dependencies (requires network access)
go mod tidy
# Build the provider binary
go build -o terraform-provider-sanmar
```

To execute the unit tests you will need access to the Go module proxy or direct GitHub access:

```bash
go test ./...
```

> [!NOTE]
> The automated CI environment in this repository does not have outbound network access, so `go test` will fail if the Go module
> cache is empty. Run the command locally where dependency downloads are allowed.

## Using the provider with Terraform/OpenTofu

After compiling the provider binary you can point Terraform or OpenTofu at the
local build by adding a `provider_installation` block to your CLI configuration
(`~/.terraformrc` or `~/.tofurc`). Replace `<repo-root>` with the absolute path
to this repository:

```hcl
provider_installation {
  dev_overrides {
    "sanmar/naming" = "<repo-root>/terraform-provider-sanmar"
  }
  direct {}
}
```

With the override in place a normal `terraform init` or `tofu init` will load
the provider from your working copy so you can iterate locally without
publishing to a registry.

## Provider configuration

```hcl
terraform {
  required_providers {
    sanmar = {
      source  = "sanmar/naming"
      version = "0.1.0"
    }
  }
}

provider "sanmar" {
  endpoint = "https://<function-app-hostname>"    # defaults to http://localhost:7071
  scope    = "api://<entra-app-id>/.default"       # optional scope for token requests
}

resource "sanmar_naming_claim" "example" {
  resource_type = "storage_account"
  region        = "wus2"
  environment   = "prd"
  project       = "atlas"
  metadata = {
    owner = "finops"
  }
}

data "sanmar_naming_slug" "storage" {
  resource_type = "storage_account"
}
```

* When the provider runs inside Azure (for example from a deployment pipeline) the managed identity will be used automatically.
* Developers can authenticate locally with `az login`, Visual Studio Code, or environment variables understood by
  `DefaultAzureCredential`.

## Reusing stored defaults across Terraform runs

The name service persists per-user defaults so repeated claim requests can omit
stable fields like environment and region. Defaults can be saved either as
permanent values for the account or scoped to a short-lived session. The
`UserSettingsService` writes these values to table storage and merges them into
every claim payload before the naming rules execute.【F:core/user_settings.py†L180-L236】【F:core/name_service.py†L200-L223】

1. **Persist your defaults once.** The snippet below records both long-lived
   defaults and a session profile named `terraform-prd`. Replace the
   placeholders with your Entra object ID and the Function App connection
   string for table storage.

   ```bash
   python - <<'PY'
   import os
   from core.user_settings import TableStorageSettingsRepository, UserSettingsService

   connection_string = os.environ.get("AzureWebJobsStorage", "<storage-connection-string>")
   user_id = "<entra-object-id>"

   service = UserSettingsService(
       repository=TableStorageSettingsRepository(connection_string),
   )

   service.set_permanent_defaults(
       user_id,
       {
           "environment": "prd",
           "region": "wus2",
           "system": "commerce",
       },
   )

   service.set_session_defaults(
       user_id,
       "terraform-prd",
       {
           "environment": "prd",
           "region": "wus2",
           "system": "commerce",
       },
   )
   PY
   ```

   The same call works against the in-memory repository during local
   development; omit the connection string to fall back automatically.【F:core/user_settings.py†L237-L259】

2. **Call the claim endpoint with only the changing pieces.** After storing
   defaults you can issue an HTTP request that omits the repeated fields. The
   backend fills them in before generating the name.

   ```bash
   curl -X POST "https://<function-app-hostname>/api/claim" \
     -H "Authorization: Bearer ${TOKEN}" \
     -H "Content-Type: application/json" \
     -d '{
       "resource_type": "storage_account",
       "session_id": "terraform-prd",
       "project": "atlas"
     }'
   ```

3. **Reference the same session from Terraform.** Attach the `session_id`
   attribute to each `sanmar_naming_claim` resource so the provider forwards it
   with every request. Only provide the segments that vary per resource—here the
   project slug—while the service injects the saved environment, region, and
   system values.【F:terraform-provider-sanmar/provider/resource_claim.go†L32-L85】【F:terraform-provider-sanmar/provider/resource_claim.go†L120-L164】

   ```hcl
   locals {
     naming_session = "terraform-prd"
   }

   resource "sanmar_naming_claim" "storage" {
     resource_type = "storage_account"
     region        = "wus2"      # required by the provider schema today
     environment   = "prd"       # mirrors the stored default
     session_id    = local.naming_session

     project = "atlas"
   }

   resource "sanmar_naming_claim" "function" {
     resource_type = "function_app"
     region        = "wus2"
     environment   = "prd"
     session_id    = local.naming_session

     project = "atlas"
     purpose = "api"
   }
   ```

   Because the defaults are stored server-side, you can create additional claim
   resources that only set the fields which vary (such as `project`, `purpose`,
   or `index`) without repeating broader context in every API payload.

## Example name claims

The `sanmar_naming_claim` resource supports all of the segments exposed by the
Azure naming service. You can claim multiple names in the same plan with
different combinations of optional arguments:

```hcl
resource "sanmar_naming_claim" "storage" {
  resource_type = "storage_account"
  region        = "wus2"
  environment   = "prd"
  project       = "atlas"
}

resource "sanmar_naming_claim" "function" {
  resource_type = "function_app"
  region        = "cus"
  environment   = "stg"
  purpose       = "orders"
  subsystem     = "imports"
}

resource "sanmar_naming_claim" "kv" {
  resource_type = "key_vault"
  region        = "eus2"
  environment   = "dev"
  system        = "sales"
  index         = "02"
}

output "storage_account_name" {
  value = sanmar_naming_claim.storage.name
}

output "function_app_name" {
  value = sanmar_naming_claim.function.name
}

output "key_vault_name" {
  value = sanmar_naming_claim.kv.name
}
```

Running `terraform apply` or `tofu apply` will request each name from the
service and surface the generated values via the `name` attribute and outputs.
Destroying the workspace releases the claims.

### Passing names into modules

You can wire the generated names directly into other modules. The following
example provisions three names and passes them to a reusable module that creates
the Azure resources:

```hcl
module "atlas" {
  source = "../modules/atlas"

  storage_account_name = sanmar_naming_claim.storage.name
  function_app_name    = sanmar_naming_claim.function.name
  key_vault_name       = sanmar_naming_claim.kv.name
}
```

Modules can also accept the entire claim object if they need additional
metadata (such as the claim ID or timestamps). The pattern scales cleanly when
you have multiple modules to feed:

```hcl
module "orders" {
  source = "../modules/orders"

  naming_claim = sanmar_naming_claim.function
}

module "billing" {
  source = "../modules/billing"

  naming_claim = sanmar_naming_claim.kv
}
```

If you prefer to keep naming concerns local to each module, declare the claims
inside the module and expose the `name` attribute through module outputs:

```hcl
// modules/storage-account/main.tf
resource "sanmar_naming_claim" "this" {
  resource_type = "storage_account"
  region        = var.region
  environment   = var.environment
  project       = var.project
}

output "name" {
  value = sanmar_naming_claim.this.name
}
```

Then in the root module you can consume the generated name along with the
resource that was created inside the child module:

```hcl
module "storage" {
  source = "../modules/storage-account"

  region      = "wus2"
  environment = "prd"
  project     = "atlas"
}

output "storage_account_name" {
  value = module.storage.name
}
```

## Retrying and troubleshooting

The provider retries transient HTTP failures up to four times with exponential back-off. You can override the behaviour in the
provider block:

```hcl
provider "sanmar" {
  retry_max_attempts = 6
  retry_min_backoff  = "750ms"
  retry_max_backoff  = "8s"
}
```

For verbose logs run Terraform with:

```bash
TF_LOG=DEBUG terraform apply
```

This surfaces the provider's structured logs, including HTTP status codes and retry attempts.
