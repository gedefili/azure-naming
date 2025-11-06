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
