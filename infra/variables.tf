variable "project_id" {
  description = "Project id"
  type = string
}
variable "region" {
  description = "Region"
  type = string
  default = "us-central1"
}
variable "zone" {
  description = "Zone"
  type = string
  default = "us-central1-a"
}
variable "machine_type" {
  description = "Machine type"
  type = string
  default = "e2-standard-4"
}
variable "environment" {
  description = "Environment (dev, prod, etc.)"
  type = string
  default = "prod"
}
variable "metadata_script" {
  description = "Path to the startup script"
  type = string
  default = "initscript_chef.sh"
}