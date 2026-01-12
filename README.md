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

# En el repo: Settings -> Deploy keys -> Add deploy key -> pegar llave pública

# Clonamos el repositorio en la carpeta previamennte creada con el script de inicializacion de terraform
cd opt/
sudo git clone https://github.com/TeamCentaurus/botcito-for-millions.git botcito

# Creamos y añadimos a los miembros al grupo para editar sin errores de "Permission Denied"
sudo groupadd botcito-devs
sudo usermod -aG botcito-devs $USER
sudo usermod -aG botcito-devs leonel.aliaga 
# Agregamos al grupo de docker
sudo usermod -aG docker $USER
sudo usermod -aG docker leonel.aliaga
# Hacemos que la carpeta sea propiedad del grupo
sudo chown -R :botcito-devs /opt/botcito
sudo chmod -R 775 /opt/botcito
# Cambiamos el grupo primario de la sesion en curso
newgrp botcito-devs
# Declaramos la carpeta  como segura
git config --global --add safe.directory /opt/botcito

# Settings -> Actions -> Runners -> New self-hosted runner
# Seguimos las instrucciones de instalación
# Después del ./run.sh ejecutamos lo siguiente para que el CI/CD se levante solo despues de un mantenimieto
sudo ./svc.sh install
sudo ./svc.sh start
# Verificamos el estado
sudo ./svc.sh status
# Si no esta activo
cd ~/actions-runner
sudo ./svc.sh install
sudo ./svc.sh start
sudo ./svc.sh status

# Creamos el archivo .env con las variables necesarias
cd /opt/botcito
nano .env
# Agreganos al grupo dev
sudo chown :botcito-devs .env
sudo chmod 660 .env
```