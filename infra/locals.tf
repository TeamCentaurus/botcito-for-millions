# infra/locals.tf

locals {
  # Concatenamos variables para crear un prefijo único
  prefix = "airflow-server-${var.environment}"

  # Etiquetas comunes que deben llevar TODOS los recursos para el tracking de costos
  common_labels = {
    project    = "botcito"
    owner      = "teamcentaurus"
    managed_by = "terraform"
    env        = var.environment
  }

  # Configuración de red (calculada)
  instance_name = "${local.prefix}-vm-02"

  default_service_account_email = "${data.google_project.project.number}-compute@developer.gserviceaccount.com"

  ## cloud function
  service_account_roles = [
    "roles/logging.logWriter",      # Escribir logs
    "roles/pubsub.subscriber",      # Ser activada por Pub/Sub
    "roles/storage.objectCreator",  # Escribir archivos en el Bucket
    "roles/artifactregistry.reader" # Lectura de imagen Docker (necesario para Cloud Functions v2)
  ]
}

