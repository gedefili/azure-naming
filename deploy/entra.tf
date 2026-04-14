# ---------------------------------------------------------------------------
# Entra ID App Registration
# ---------------------------------------------------------------------------
data "azuread_client_config" "current" {}

resource "azuread_application" "main" {
  display_name = var.entra_app_display_name
  owners       = coalescelist(var.entra_app_owners, [data.azuread_client_config.current.object_id])

  sign_in_audience = "AzureADMyOrg"

  # Expose an API scope so tokens include the correct audience
  api {
    mapped_claims_enabled          = false
    requested_access_token_version = 2

    oauth2_permission_scope {
      admin_consent_description  = "Allows the app to access the Naming Service API on behalf of the signed-in user."
      admin_consent_display_name = "Access Naming Service"
      id                         = "00000000-0000-0000-0000-000000000001"
      enabled                    = true
      type                       = "User"
      user_consent_description   = "Allow the application to access the Naming Service on your behalf."
      user_consent_display_name  = "Access Naming Service"
      value                      = "user_access"
    }
  }

  # App Roles matching the three Entra roles used by the service
  app_role {
    allowed_member_types = ["User"]
    description          = "Read-only access to naming service (slugs, own audits)."
    display_name         = "Reader"
    id                   = "11111111-1111-1111-1111-111111111111"
    enabled              = true
    value                = "reader"
  }

  app_role {
    allowed_member_types = ["User"]
    description          = "Full API access: claim, release, and manage names."
    display_name         = "Contributor"
    id                   = "22222222-2222-2222-2222-222222222222"
    enabled              = true
    value                = "contributor"
  }

  app_role {
    allowed_member_types = ["User"]
    description          = "Administrator access: cross-user audits, slug sync, full control."
    display_name         = "Admin"
    id                   = "33333333-3333-3333-3333-333333333333"
    enabled              = true
    value                = "admin"
  }

  web {
    implicit_grant {
      access_token_issuance_enabled = false
      id_token_issuance_enabled     = false
    }
  }
}

resource "azuread_service_principal" "main" {
  client_id                    = azuread_application.main.client_id
  app_role_assignment_required = true
}

resource "azuread_application_password" "main" {
  application_id = azuread_application.main.id
  display_name   = "terraform-managed"
  end_date       = timeadd(timestamp(), "8760h") # 1 year
}
