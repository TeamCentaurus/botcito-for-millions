resource "google_compute_instance" "instance-vm" {
  boot_disk {
    auto_delete = true
    device_name = local.instance_name

    initialize_params {
      image = data.google_compute_image.ubuntu_latest.self_link
      size  = 25
      type  = "pd-balanced"
    }

    mode = "READ_WRITE"
  }

  can_ip_forward      = false
  deletion_protection = false
  enable_display      = false

  labels = local.common_labels
  machine_type = var.machine_type
  name         = local.instance_name
  zone         = var.zone

  network_interface {
    network = "default"
    network_ip = google_compute_address.internal_ip.address
    access_config {
      network_tier = "PREMIUM"
      nat_ip = google_compute_address.external_ip.address
    } # Esto asigna una IP externa a la instancia

    queue_count = 0
    stack_type  = "IPV4_ONLY"
    subnetwork  = "projects/${var.project_id}/regions/${var.region}/subnetworks/default"
  }

  scheduling {
    automatic_restart   = true
    on_host_maintenance = "MIGRATE"
    preemptible         = false
    provisioning_model  = "STANDARD"
  }

  service_account {
    email  = local.default_service_account_email # var.service_account_email
    scopes = ["https://www.googleapis.com/auth/devstorage.read_only",
              "https://www.googleapis.com/auth/logging.write",
              "https://www.googleapis.com/auth/monitoring.write",
              "https://www.googleapis.com/auth/service.management.readonly",
              "https://www.googleapis.com/auth/servicecontrol",
              "https://www.googleapis.com/auth/trace.append"]
  }

  shielded_instance_config {
    enable_integrity_monitoring = true
    enable_secure_boot          = false
    enable_vtpm                 = true
  }

  metadata = {
    startup-script = file("${path.module}/${var.metadata_script}")
  }

  depends_on = [google_compute_address.external_ip, google_compute_address.internal_ip]

  tags = ["airflow-server", "http-server", "https-server"]
}

resource "google_compute_address" "external_ip" {
  name = "airflow-ip-external"
  address_type = "EXTERNAL"
}

resource "google_compute_address" "internal_ip" {
  name = "airflow-ip-internal"
  address_type = "INTERNAL"
  subnetwork  = "projects/${var.project_id}/regions/${var.region}/subnetworks/default"
}
