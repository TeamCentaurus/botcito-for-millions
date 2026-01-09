resource "google_compute_instance" "instance-vm" {
  boot_disk {
    auto_delete = true
    device_name = local.instance_name

    initialize_params {
      image = data.google_compute_image.ubuntu_latest.self_link
      size  = 30
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
    scopes = ["cloud-platform"]
  }

  shielded_instance_config {
    enable_integrity_monitoring = true
    enable_secure_boot          = false
    enable_vtpm                 = true
  }

  metadata_startup_script = file("${path.module}/${var.metadata_script}")

  tags = ["airflow-server", "http-server", "https-server"]

  depends_on = [google_compute_address.external_ip, google_compute_address.internal_ip]
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

resource "google_compute_firewall" "allow_iap_proxy" {
  name = "allow-ssh-and-apps-from-iap"
  network = "default"

  allow {
    protocol = "tcp"
    ports    = ["22", "8080", "9000", "9001"]
  }

  source_ranges = ["35.235.240.0/20"] # Google Cloud IP range

  target_tags = ["airflow-server"]
}

resource "google_project_iam_member" "iap_tunnel_accessor" {
  for_each = toset(var.iap_users)
  project = var.project_id
  role    = "roles/iap.tunnelResourceAccessor"
  member  = "user:${each.value}"
}

resource "google_service_account_iam_member" "allow_self_impersonate" {
  for_each = toset(var.iap_users)
  service_account_id = "projects/${var.project_id}/serviceAccounts/${local.default_service_account_email}"
  role            = "roles/iam.serviceAccountUser"
  member          = "user:${each.value}"
}