terraform {
  required_version = ">= 1.5"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.100"
    }
    azuread = {
      source  = "hashicorp/azuread"
      version = "~> 2.50"
    }
  }

  # Uncomment and configure for remote state:
  # backend "azurerm" {
  #   resource_group_name  = "terraform-state-rg"
  #   storage_account_name = "tfstateXXXXX"
  #   container_name       = "tfstate"
  #   key                  = "naming-service.tfstate"
  # }
}

provider "azurerm" {
  features {}
}

provider "azuread" {}
