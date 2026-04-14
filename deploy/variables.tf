variable "project_name" {
  description = "Short project identifier used in resource naming."
  type        = string
  default     = "naming"
}

variable "environment" {
  description = "Deployment environment (dev, staging, prod)."
  type        = string
  default     = "prod"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod."
  }
}

variable "location" {
  description = "Azure region for all resources."
  type        = string
  default     = "westus2"
}

variable "python_version" {
  description = "Python version for the Function App runtime."
  type        = string
  default     = "3.11"
}

variable "storage_account_name" {
  description = "Globally unique name for the Storage Account (3-24 lowercase alphanumeric)."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9]{3,24}$", var.storage_account_name))
    error_message = "Storage account name must be 3-24 lowercase letters and numbers."
  }
}

variable "entra_app_display_name" {
  description = "Display name for the Entra ID App Registration."
  type        = string
  default     = "Azure Naming Service"
}

variable "entra_app_owners" {
  description = "List of Entra ID user object IDs to set as App Registration owners."
  type        = list(string)
  default     = []
}

variable "tags" {
  description = "Tags applied to all resources."
  type        = map(string)
  default     = {}
}
