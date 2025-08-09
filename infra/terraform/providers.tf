terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

# Default region (home)
provider "aws" {
  region = var.home_region
}

# Explicit providers for multi-region resources
provider "aws" {
  alias  = "home"
  region = var.home_region
}

provider "aws" {
  alias  = "replica"
  region = var.replica_region
}
