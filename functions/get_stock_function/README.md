handle_stock_request/
├── main.py
├── requirements.txt
├── tickers.json        <-- Archivo con tus 100+ acciones
├── README.md           <-- Documentación
├── .dockerignore
└── Dockerfile

1- Habilitamos APIs necesarias
```bash
gcloud services enable \
  cloudfunctions.googleapis.com \
  cloudbuild.googleapis.com \
  pubsub.googleapis.com \
  cloudscheduler.googleapis.com \
  storage.googleapis.com \
  artifactregistry.googleapis.com \
  logging.googleapis.com \
  run.googleapis.com
```
2-asignamos roles correspondiente a los servicios a usar a la cuenta de servicio que usará par el ci/cd
```bash
export PROJECT_ID=$(gcloud config get-value project)
# 1. Permiso para subir imágenes a Artifact Registry
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:terraform-runner@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/artifactregistry.writer"
# 2. Permiso para ejecutar la construcción en Cloud Build (necesario para desplegar funciones)
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:terraform-runner@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/cloudbuild.builds.editor"
# 3. Permiso para crear y actualizar la Cloud Function (Gen 2)
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:terraform-runner@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/cloudfunctions.developer"
# 4. Permiso para gestionar el servicio de Cloud Run subyacente (Gen 2 corre sobre Cloud Run)
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:terraform-runner@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/run.developer"
# 5. Permite que el pipeline "asigne" la sa a la función durante el comando de despliegue
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:terraform-runner@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/iam.serviceAccountUser"

# 1. Permiso para crear Cuentas de Servicio (Error 1)
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:terraform-runner@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/iam.serviceAccountAdmin"
# 2. Permiso para crear Tópicos de Pub/Sub (Error 2)
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:terraform-runner@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/pubsub.admin"
# 3. Permiso para crear Repositorios en Artifact Registry (Error 3)
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:terraform-runner@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/artifactregistry.admin"
```
1- Creamos una cuenta de servicio para cloud function (terraform)
2- Asignamos los siguientes roles: (terraform)
    - logging.logWriter
    - pubsub.subscriber
    - storage.objectCreator
    - artifactregistry.reader

