terraform {
 backend "gcs" {
   bucket  = "${var.project_id}-gcs02-github-terraform-state-bucket"
   prefix  = "terraform/state"
 }
}