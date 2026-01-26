# Botcito for millions

## Estructura del repo

```text
BOTCITO-FOR-MILLIONS/
├── .github/                   # CI/CD workflows
├── dags/                      # 1. ORQUESTACIÓN (Airflow DAGs)
│   ├── data_ingestion.py      # Pipeline: Fetch Data -> Kafka/MinIO
│   └── strategy_inference.py  # Pipeline: Read Data -> ML Model -> Buy/Sell Signal
├── docker/                    # 2. CONFIGURACIÓN DE CONTENEDORES
├── infra/                     # 3. INFRAESTRUCTURA (Terraform - ya lo tienes)
│   ├── main.tf
│   └── ...
├── notebooks/                 # 4. EXPERIMENTACIÓN
│   └── test-models.ipynb
├── src/                       # 5. CÓDIGO FUENTE (Lógica de Negocio)
│   ├── bot_core/              # LIBRERÍA COMPARTIDA (Tu "Business Logic")
│   │   ├── __init__.py
│   │   ├── connectors.py      # Wrappers para MinIO, Postgres, Kafka
│   │   ├── strategies.py      # Lógica de trading y ML (Modelos LGBM aquí)
│   │   └── utils.py
│   └── notification_service/  # MICROSERVICIO (API / Worker)
│       ├── main.py            # FastAPI/Flask app
│       └── telegram_bot.py    # Lógica de envío de alertas
├── tests/                     # Unit & Integration tests
├── .env                       # Variables de entorno (NO subir a git)
├── docker-compose.yml         # El orquestador de infraestructura local/VM
├── pyproject.toml             # Definición del paquete y dependencias (uv)
├── uv.lock                    # Librrerias con hashes para reproducibilidad
└── README.md
```


## Configuracion de CI/CD repo en VM (solo la primera vez)
1- 
```bash 
# Exportamos el id del proyecto en una variable
export PROJECT_ID=$(gcloud config get-value project)
# Nos conectamos a la vm desde el shell de GCP
gcloud compute ssh airflow-server-prod-vm-02 \
  --zone=us-central1-a \
  --project=$PROJECT_ID \
  --tunnel-through-iap
```
2- En la VM ejecutamos lo siguiente
```bash 
# Generamos una SSH key para GitActions
ssh-keygen -t ed25519 -C "vm-deploy-key"

# Copiamos la llave pública
cat ~/.ssh/id_ed25519.pub

# En el repo: Settings -> Deploy keys -> Add deploy key -> SSH_KEY_VM_02: pegar llave pública

# Clonamos el repositorio en la carpeta previamennte creada con el script de inicializacion de terraform
cd /opt/
sudo git clone https://github.com/TeamCentaurus/botcito-for-millions.git botcito

# 1️⃣ Crear grupo (solo si no existe)
sudo groupadd botcito-devs 2>/dev/null || true
# 2️⃣ Agregar usuarios al grupo botcito-devs
sudo usermod -aG botcito-devs $USER
sudo usermod -aG botcito-devs leonel.aliaga 
# 3️⃣ Agregar usuarios al grupo docker
sudo usermod -aG docker $USER
sudo usermod -aG docker leonel.aliaga
# 4️⃣ Asignar grupo y permisos al proyecto
sudo chown -R :botcito-devs /opt/botcito
sudo chmod -R 775 /opt/botcito
# 5️⃣ Aplicar grupo a la sesión actual
newgrp botcito-devs
# 6️⃣ Marcar el repositorio como seguro para git
git config --global --add safe.directory /opt/botcito
# 7️⃣ Crear archivo .env
cd /opt/botcito
nano .env
# 8️⃣ Asegurar permisos del archivo .env
sudo chown :botcito-devs .env
sudo chmod 660 .env

# Settings -> Actions -> Runners -> New self-hosted runner
# Seguimos las instrucciones de instalación
# Después del ./run.sh ejecutamos lo siguiente para que el CI/CD se levante solo despues de un mantenimieto
cd
sudo ./svc.sh install
sudo ./svc.sh start
# Verificamos el estado
sudo ./svc.sh status
# Si no esta activo
cd ~/actions-runner
sudo ./svc.sh install
sudo ./svc.sh start
sudo ./svc.sh status
# levantamos el worflow para pull y up
```
3- Ver la UI de airflow ejecutar lo siguiente en el powershell de windows
``` bash
# powershell
gcloud compute start-iap-tunnel airflow-server-prod-vm-02 8080 `
     --local-host-port=localhost:8080 `
     --zone=us-central1-a
gcloud compute start-iap-tunnel airflow-server-prod-vm-02 9001 `
     --local-host-port=localhost:9001 `
     --zone=us-central1-a
gcloud compute start-iap-tunnel airflow-server-prod-vm-02 9000 `
     --local-host-port=localhost:9000 `
     --zone=us-central1-a
# vsc
gcloud compute start-iap-tunnel airflow-server-prod-vm-02 9001 \
    --local-host-port=localhost:9001 \
    --zone=us-central1-a
gcloud compute start-iap-tunnel airflow-server-prod-vm-02 8080 \
    --local-host-port=localhost:8080 \
    --zone=us-central1-a
gcloud compute start-iap-tunnel airflow-server-prod-vm-02 9000 \
    --local-host-port=localhost:9000 \
    --zone=us-central1-a
# o ambos túneles al mismo tiempo
gcloud compute start-iap-tunnel airflow-server-prod-vm-02 8080 --local-host-port=localhost:8080 --zone=us-central1-a & \
gcloud compute start-iap-tunnel airflow-server-prod-vm-02 9001 --local-host-port=localhost:9001 --zone=us-central1-a &
```
# dsdsd