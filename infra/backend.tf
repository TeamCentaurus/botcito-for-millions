terraform {
 backend "gcs" {}
}

# terraform {
#  backend "gcs" {
#    bucket  = "gcs02-github-terraform-state-bucket"
#    prefix  = "terraform/state"
#  }
# }