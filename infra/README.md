# Configuración del uso de Terraform en GCP con Workload Identity Federation para GitHub Actions

## Crear cuenta de servicio 
1- Abrir el Shell y crear una variable con tu id de proyecto
```bash 
export PROJECT_ID=$(gcloud config get-value project)
```
2- Crear la cuenta de servicio que utilizará terraform
```bash 
gcloud iam service-accounts create terraform-runner \
    --description="Se usará para levantar la infraestructura del pipeline y de uso exclusivo de terraform" \
    --display-name="terraform-runner"
```
3- Asignar los roles a la cuenta de servicio
```bash 
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:terraform-runner@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/compute.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:terraform-runner@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/iam.serviceAccountUser"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:terraform-runner@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/iam.securityAdmin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:terraform-runner@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/storage.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:terraform-runner@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/iam.workloadIdentityUser"
```
4- Configuramos y creamos el Workload Identity Pool y Workload Identity Provider
```bash 
# Creamos el Pool (el contenedor de identidades externas)
gcloud iam workload-identity-pools create "github-terraform-pool" \
  --project="${PROJECT_ID}" \
  --location="global" \
  --display-name="Pool para terraform"

# Creamos el provider (conecta con GitHub)
gcloud iam workload-identity-pools providers create-oidc "github-terraform-provider" \
  --project="${PROJECT_ID}" \
  --location="global" \
  --workload-identity-pool="github-terraform-pool" \
  --display-name="Provider para pool de terraform" \
  --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository" \
  --attribute-condition="assertion.repository == 'TeamCentaurus/botcito-for-millions'" \
  --issuer-uri="https://token.actions.githubusercontent.com"
```
5- Conectamos a la cuenta de servicio y le indicamos que el repositorio actue como dicha cuenta
```bash 
# Obtener el ID completo del Pool
export POOL_ID=$(gcloud iam workload-identity-pools describe "github-terraform-pool" --location="global" --format="value(name)")

# Dar permiso de impersonación
gcloud iam service-accounts add-iam-policy-binding "terraform-runner@${PROJECT_ID}.iam.gserviceaccount.com" \
    --project="${PROJECT_ID}" \
    --role="roles/iam.workloadIdentityUser" \
    --member="principalSet://iam.googleapis.com/${POOL_ID}/attribute.repository/TeamCentaurus/botcito-for-millions"
```
6- Ubicamos la sección de "Workload Identity Pools" en la consola de GCP y copiamos el identificador del provider y en cuenta de servicios copiamos la cuenta que vinculamos en el paso anterior
   para luego usarla en la configuracion del workflow de terraform en la sección del auth

7- Creamos y asignamos las etiquetas al bucket que terraform utilizara para guardar y no perder su estado
```bash 
gcloud storage buckets create gs://${PROJECT_ID}-gcs02-github-terraform-state-bucket \
    --project=$PROJECT_ID \
    --default-storage-class=STANDARD \
    --location=us-central1 \
    --uniform-bucket-level-access \
    --soft-delete-duration=7d

gcloud storage buckets update gs://${PROJECT_ID}-gcs02-github-terraform-state-bucket \
    --update-labels=env=prod,project=botcito,service=terraform-backend,owner=teamcentaurus
```
8- Habilitamos las APIs
```bash 
gcloud services enable \
  cloudresourcemanager.googleapis.com \
  iam.googleapis.com \
  iamcredentials.googleapis.com \
  serviceusage.googleapis.com \
  storage.googleapis.com \
  compute.googleapis.com \
  --project=$PROJECT_ID
```

8- Imprimos los valores de la cuenta de servicio y del provider, valores a actualizar en las secrets de gitactions
```bash 
SERVICE_ACCOUNT=$(gcloud iam service-accounts list \
  --project="$PROJECT_ID" \
  --filter="displayName=terraform-runner" \
  --format="value(email)")
echo
echo "========== Secrets para actualizar =========="
echo "SERVICE_ACCOUNT     : $SERVICE_ACCOUNT"
echo "IDENTITY_PROVIDER   : ${POOL_ID}/providers/github-terraform-provider"
echo "============================================"
echo
```