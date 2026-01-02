data "google_compute_image" "ubuntu_latest" {
  family  = "ubuntu-2204-lts"
  project = "ubuntu-os-cloud"
}

data "google_project" "project" {
  project_id = var.project_id
}