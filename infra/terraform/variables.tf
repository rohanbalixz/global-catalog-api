variable "project_name" {
  description = "Project slug used for resource names"
  type        = string
  default     = "global-catalog"
}

variable "home_region" {
  description = "Primary AWS region"
  type        = string
  default     = "us-east-1"
}

variable "replica_region" {
  description = "Replica AWS region"
  type        = string
  default     = "eu-west-1"
}

variable "table_name" {
  description = "DynamoDB Global Table name"
  type        = string
  default     = "GlobalCatalog"
}
