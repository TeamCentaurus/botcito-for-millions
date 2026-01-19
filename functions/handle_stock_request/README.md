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
1- Creamos una cuenta de servicio para cloud function
```bash
export PROJECT_ID=$(gcloud config get-value project)
gcloud iam service-accounts create function-stock-sa \
    --description="Cuenta para uso de cloud function" \
    --display-name="function-stock-sa"
```
2- Asignamos los siguientes roles:
    - logging.logWriter
    - pubsub.subscriber
    - storage.objectCreator
    - artifactregistry.reader
```bash
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:function-stock-sa@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/logging.logWriter"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:function-stock-sa@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/pubsub.subscriber"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:function-stock-sa@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/storage.objectCreator"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:function-stock-sa@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/artifactregistry.reader"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:function-stock-sa@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/run.invoker"
```
3- creamos un topic de pubsub
```bash
gcloud pubsub topics create cron-stock-topic \
  --labels=project=botcito,owner=teamcentaurus,service=cloudfunction
gcloud pubsub subscriptions create cron-stock-sub --topic cron-stock-topic
```
4- Creamos un trabajo cron con Cloud Scheduler
```bash
gcloud config set project $PROJECT_ID
gcloud config set run/region "us-central1"

PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:service-$PROJECT_NUMBER@gcp-sa-cloudscheduler.iam.gserviceaccount.com" \
  --role="roles/pubsub.publisher"

gcloud scheduler jobs create pubsub cron-stock-job \
  --schedule="*/1 9-16 * * 1-5" \
  --time-zone="America/Lima" \
  --location="us-central1" \
  --topic=cron-stock-topic \
  --message-body='{"source":"scheduler","type":"minute_tick"}' \
  --description="Read minute APIs stock"
```
5- deploy function local
```bash

gcloud init
gcloud auth login
# WINDOWS
$env:PROJECT_ID=$(gcloud config get-value project)
$env:REGION="us-central1"
$env:FUNCTION_NAME="handle-stock-request"
$env:TOPIC="cron-stock-topic"
$env:SERVICE_ACCOUNT="function-stock-sa@$($env:PROJECT_ID).iam.gserviceaccount.com"
$env:BUCKET_NAME="$($env:PROJECT_ID)-gcs02-github-terraform-state-bucket"

echo $env:BUCKET_NAME

# lINUX
export PROJECT_ID=$(gcloud config get-value project)
export REGION=us-central1
export FUNCTION_NAME=handle-stock-request
export TOPIC=cron-stock-topic
export SERVICE_ACCOUNT=function-stock-sa@$PROJECT_ID.iam.gserviceaccount.com
export BUCKET_NAME=$PROJECT_ID-gcs02-github-terraform-state-bucket
export TWELVEDATA_API_KEY=""
echo $PROJECT_ID
# AMBOS
cd functions/handle_stock_request
gcloud functions deploy $FUNCTION_NAME \
  --gen2 \
  --region=$REGION \
  --runtime=python311 \
  --source=. \
  --entry-point=handle_stock_request \
  --trigger-topic=$TOPIC \
  --service-account=$SERVICE_ACCOUNT \
  --set-env-vars=BUCKET_NAME=$BUCKET_NAME,TWELVEDATA_API_KEY=$TWELVEDATA_API_KEY \
  --memory=1024Mi \
  --timeout=50s

# test
gcloud pubsub topics publish cron-stock-topic \
  --message='{"source":"manual-test","reason":"function-test"}'

gcloud logs read \
  "resource.type=cloud_function AND resource.labels.function_name=$FUNCTION_NAME" \
  --limit=50

```
2- CI/CD
```bash
export PROJECT_ID=$(gcloud config get-value project)
# 1.
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:terraform-runner@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/iam.serviceAccountAdmin"
# 2. 
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:terraform-runner@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="cloudfunctions.developer"
# 3. 
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:terraform-runner@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/artifactregistry.reader"
 # 4.    
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:terraform-runner@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/run.admin"
```


