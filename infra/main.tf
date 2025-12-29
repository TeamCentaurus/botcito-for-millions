resource "google_storage_bucket" "my-bucket" {
  name          = "bkt-demo-000232123122313"
  location      = "us-central1"
  force_destroy = true
  public_access_prevention = "enforced"
}